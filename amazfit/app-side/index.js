// Servicio en el móvil (dentro de la app Zepp): recibe los puntos del reloj,
// los guarda y los sube a /api/gps de la web. Sin cobertura se quedan en el
// móvil y se suben todos al volver, igual que hace Traccar.
import { BaseSideService } from '@zeppos/zml/base-side'

const MAX_PENDIENTES = 3000
const POR_SUBIDA = 150
const URL_DEFECTO = 'https://odegaard12.online/api/gps'
let pendientes = []
let subiendo = false

AppSideService(BaseSideService({
  onInit() {
    try { pendientes = JSON.parse(this.settings.getItem('pendientes') || '[]') } catch (e) { pendientes = [] }
    this.reintento = setInterval(() => this.subir(), 30000)
  },

  onRequest(req, res) {
    if (req.method !== 'gps.enviar') {
      res({ message: 'método desconocido: ' + req.method })
      return
    }
    const nuevos = (req.params && req.params.puntos) || []
    pendientes = pendientes.concat(nuevos).slice(-MAX_PENDIENTES)
    this.guardar()
    // al reloj se le contesta ya: los puntos quedan a salvo en el móvil
    res(null, { ok: true, recibidos: nuevos.length })
    this.subir()
  },

  guardar() {
    // el almacén de ajustes no es para mucho: se guardan los últimos 1500
    // (lo que cabe en la cola del reloj, ~4 h)
    this.settings.setItem('pendientes', JSON.stringify(pendientes.slice(-1500)))
    this.settings.setItem('estado', JSON.stringify({ pendientes: pendientes.length, hora: Date.now() }))
  },

  async subir() {
    if (subiendo || !pendientes.length) return
    // ⚠️ Ajustes enseña esta dirección de entrada pero, si no se toca, no se
    // guarda: sin esto el móvil nunca subía nada ("falta la dirección")
    const url = (this.settings.getItem('url') || URL_DEFECTO).trim()
    const id = (this.settings.getItem('id') || '').trim()
    if (!url || !id) {
      this.settings.setItem('ultimo_error', 'Falta la dirección o el identificador en Ajustes')
      return
    }
    subiendo = true
    const lote = pendientes.slice(0, POR_SUBIDA)
    const cuerpo = {
      device_id: id,
      location: lote.map(p => ({
        timestamp: new Date(p.t).toISOString(),
        coords: p.lat != null ? { latitude: p.lat, longitude: p.lon } : {},
        extras: { hr: p.hr, origen: 'amazfit' },
      })),
    }
    try {
      const r = await this.fetch({
        url, method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cuerpo),
      })
      if (r && r.status >= 200 && r.status < 300) {
        pendientes = pendientes.slice(lote.length)
        this.guardar()
        this.settings.setItem('ultimo_envio', new Date().toISOString())
        this.settings.setItem('ultimo_error', '')
      } else if (r && (r.status === 400 || r.status === 413 || r.status === 422)) {
        // el servidor no acepta ESE lote (no se arregla reintentando): fuera,
        // o taparía para siempre todos los puntos de detrás
        pendientes = pendientes.slice(lote.length)
        this.guardar()
        this.settings.setItem('ultimo_error', 'El servidor rechazó ' + lote.length + ' puntos (' + r.status + ')')
      } else {
        this.settings.setItem('ultimo_error', r && r.status === 403
          ? 'Identificador incorrecto: cópialo del panel admin'
          : 'El servidor respondió ' + (r ? r.status : 'nada'))
      }
    } catch (e) {
      this.settings.setItem('ultimo_error', 'Sin conexión: ' + String(e).slice(0, 80))
    } finally {
      subiendo = false
    }
    if (pendientes.length && !this.settings.getItem('ultimo_error')) this.subir()
  },

  onRun() {},
  onDestroy() {
    if (this.reintento) clearInterval(this.reintento)
  },
}))
