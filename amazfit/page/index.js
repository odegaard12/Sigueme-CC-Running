// Pantalla del reloj: toma GPS y pulso cada 10 s y los manda al móvil (app
// Zepp), que los guarda y los sube a la web. Si el móvil no está al alcance,
// los puntos esperan en el reloj y se mandan todos al volver.
import { BasePage } from '@zeppos/zml/base-page'
import { createWidget, widget, prop, align, text_style } from '@zos/ui'
import { Geolocation, HeartRate } from '@zos/sensor'
import { setPageBrightTime, resetPageBrightTime, pauseDropWristScreenOff, resetDropWristScreenOff } from '@zos/display'
import { px } from '@zos/utils'

const CADA_MS = 10000
const MAX_COLA = 1500        // ~4 h de puntos si el móvil no está al alcance
const POR_ENVIO = 60

const GRIS = 0x7d8a83
const BLANCO = 0xf1f3f1
const VERDE = 0x7fd46a
const ROJO = 0xe0473a

Page(BasePage({
  state: {
    activo: false, cola: [], enviados: 0, ultimoOk: 0, enviando: false,
    pulso: null, fix: false, lat: null, lon: null, reloj: null,
  },

  build() {
    this.w = {}
    createWidget(widget.TEXT, {
      x: 0, y: px(52), w: px(480), h: px(40), text: 'SÍGUEME', color: GRIS,
      text_size: px(26), align_h: align.CENTER_H,
    })
    this.w.pulso = createWidget(widget.TEXT, {
      x: 0, y: px(100), w: px(480), h: px(110), text: '—', color: BLANCO,
      text_size: px(96), align_h: align.CENTER_H,
    })
    createWidget(widget.TEXT, {
      x: 0, y: px(205), w: px(480), h: px(34), text: 'ppm', color: GRIS,
      text_size: px(24), align_h: align.CENTER_H,
    })
    this.w.gps = createWidget(widget.TEXT, {
      x: px(40), y: px(250), w: px(400), h: px(34), text: 'GPS parado', color: GRIS,
      text_size: px(24), align_h: align.CENTER_H,
    })
    this.w.envio = createWidget(widget.TEXT, {
      x: px(40), y: px(286), w: px(400), h: px(34), text: '', color: GRIS,
      text_size: px(22), align_h: align.CENTER_H, text_style: text_style.ELLIPSIS,
    })
    this.w.boton = createWidget(widget.BUTTON, {
      x: px(120), y: px(344), w: px(240), h: px(76), radius: px(38),
      text: 'Empezar', text_size: px(30), normal_color: 0x1f6b35, press_color: 0x2f8a4a,
      click_func: () => this.alternar(),
    })
  },

  onInit() {
    this.geo = new Geolocation()
    this.hr = new HeartRate()
    this.alGeo = () => {
      this.state.fix = this.geo.getStatus() === 'A'
      if (this.state.fix) {
        this.state.lat = this.geo.getLatitude({ format: 'DD' })
        this.state.lon = this.geo.getLongitude({ format: 'DD' })
      }
      this.pintar()
    }
    this.alPulso = () => {
      const v = this.hr.getCurrent()
      if (v > 0 && v < 250) this.state.pulso = v
      this.pintar()
    }
  },

  alternar() {
    if (this.state.activo) this.parar()
    else this.arrancar()
  },

  arrancar() {
    this.state.activo = true
    this.geo.start()
    this.geo.onChange(this.alGeo)
    this.hr.onCurrentChange(this.alPulso)
    // La pantalla encendida mientras sigue: Zepp OS solo garantiza que la
    // app corra en primer plano (en segundo plano está por probar).
    setPageBrightTime({ brightTime: 2147483000 })   // el máximo que admite
    pauseDropWristScreenOff({ duration: 0 })
    this.state.reloj = setInterval(() => this.tomarYMandar(), CADA_MS)
    this.w.boton.setProperty(prop.MORE, { text: 'Parar', normal_color: 0x6b1f1f, press_color: 0x8a2f2f })
    this.pintar()
  },

  parar() {
    this.state.activo = false
    if (this.state.reloj) clearInterval(this.state.reloj)
    this.state.reloj = null
    try { this.geo.offChange(this.alGeo); this.geo.stop() } catch (e) {}
    try { this.hr.offCurrentChange(this.alPulso) } catch (e) {}
    resetPageBrightTime()
    resetDropWristScreenOff()
    this.w.boton.setProperty(prop.MORE, { text: 'Empezar', normal_color: 0x1f6b35, press_color: 0x2f8a4a })
    this.mandar()            // lo que quede en la cola
    this.pintar()
  },

  tomarYMandar() {
    const p = { t: Date.now(), hr: this.state.pulso }
    if (this.state.fix && typeof this.state.lat === 'number') {
      p.lat = Math.round(this.state.lat * 1e6) / 1e6
      p.lon = Math.round(this.state.lon * 1e6) / 1e6
    }
    if (p.lat == null && p.hr == null) return
    this.state.cola.push(p)
    if (this.state.cola.length > MAX_COLA) this.state.cola.splice(0, this.state.cola.length - MAX_COLA)
    this.mandar()
  },

  mandar() {
    if (this.state.enviando || !this.state.cola.length) return
    this.state.enviando = true
    const lote = this.state.cola.slice(0, POR_ENVIO)
    this.request({ method: 'gps.enviar', params: { puntos: lote } })
      .then(() => {
        this.state.cola.splice(0, lote.length)
        this.state.enviados += lote.length
        this.state.ultimoOk = Date.now()
      })
      .catch(() => {})       // sin móvil al alcance: se reintenta en la próxima toma
      .finally(() => {
        this.state.enviando = false
        this.pintar()
        if (this.state.cola.length && Date.now() - this.state.ultimoOk < 2000) this.mandar()
      })
  },

  pintar() {
    const s = this.state
    this.w.pulso.setProperty(prop.TEXT, s.pulso ? String(s.pulso) : '—')
    this.w.gps.setProperty(prop.MORE, {
      text: !s.activo ? 'GPS parado' : s.fix ? 'GPS listo' : 'Buscando GPS…',
      color: !s.activo ? GRIS : s.fix ? VERDE : BLANCO,
    })
    const hace = s.ultimoOk ? Math.round((Date.now() - s.ultimoOk) / 1000) : null
    this.w.envio.setProperty(prop.MORE, {
      text: !s.activo && !s.enviados ? 'Pulsa Empezar al salir'
        : s.cola.length > 3 ? s.cola.length + ' puntos esperando al móvil'
        : hace != null ? 'Enviado hace ' + hace + ' s' : 'Conectando con el móvil…',
      color: s.cola.length > 3 ? ROJO : GRIS,
    })
  },

  onDestroy() {
    if (this.state.activo) this.parar()
  },
}))
