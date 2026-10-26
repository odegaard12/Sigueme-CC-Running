// Servicio en el móvil (dentro de la app Zepp): recibe los puntos del reloj,
// los guarda y los sube a /api/gps de la web. Sin cobertura se quedan en el
// móvil y se suben todos al volver, igual que hace Traccar.
import { BaseSideService } from '@zeppos/zml/base-side'

const MAX_PENDIENTES = 1500      // lo mismo que se guarda: más, se perdían al cerrar Zepp
const POR_SUBIDA = 150
let pendientes = []
let subiendo = false

AppSideService(BaseSideService({
  onInit() {
    try { pendientes = JSON.parse(this.settings.getItem('pendientes') || '[]') } catch (e) { pendientes = [] }
    pendientes = pendientes.filter(p => p && Number.isFinite(p.t))
    this.reintento = setInterval(() => this.subir(), 30000)
  },

  onRequest(req, res) {
    if (req.method !== 'gps.enviar') {
      res({ message: 'método desconocido: ' + req.method })
      return
    }
    // si el reloj reenvía un lote porque no le llegó el OK, no se duplica (misma hora = mismo punto)
    const vistos = new Set(pendientes.map(p => p.t))
    const nuevos = ((req.params && req.params.puntos) || []).filter(p => p && Number.isFinite(p.t) && !vistos.has(p.t))
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
    // sin dirección por defecto: cada uno pone la de SU web (antes iba a la del autor)
    // vale con escribir solo el dominio: se completa con /api/gps (antes, sin él, no llegaba ningún punto)
    let url = (this.settings.getItem('url') || '').trim()
    let id = (this.settings.getItem('id') || '').trim()
    // vale pegar el enlace de configuración del panel (…/app.html#id=odg-…): saca de él la dirección y el identificador
    const enlace = /^(https?:\/\/[^\/#\s]+).*#id=([\w-]{8,100})/.exec(url)
    if (enlace) { url = enlace[1]; if (!id) id = enlace[2] }
    const enlaceId = /#id=([\w-]{8,100})/.exec(id)       // también vale pegar el enlace entero en el campo del identificador
    if (enlaceId) id = enlaceId[1]
    if (url && !/^https?:\/\//i.test(url)) url = 'https://' + url
    url = url.replace(/\/+$/, '')
    if (url && !/\/api\/gps$/.test(url)) url += '/api/gps'
    if (!url || !id) {
      this.settings.setItem('ultimo_error', 'Falta la dirección de tu web o el identificador en Ajustes')
      return
    }
    subiendo = true
    const lote = pendientes.slice(0, POR_SUBIDA)
    // fuera LO ENVIADO, no los primeros: si el reloj manda puntos durante el envío
    // con la cola llena, el recorte del principio hacía borrar puntos sin mandar
    const sinLote = (lista, l) => { const fuera = new Set(l); return lista.filter(q => !fuera.has(q)) }
    try {
      const cuerpo = {
        device_id: id,
        location: lote.map(p => ({
          timestamp: new Date(p.t).toISOString(),
          coords: p.lat != null ? { latitude: p.lat, longitude: p.lon } : {},
          extras: { hr: p.hr, origen: 'amazfit' },
        })),
      }
      // con tiempo límite propio: si el envío se cuelga, `subiendo` no se queda puesto para siempre
      const r = await Promise.race([
        this.fetch({ url, method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cuerpo) }),
        new Promise((_, no) => setTimeout(() => no(new Error('tiempo agotado')), 25000)),
      ])
      if (r && r.status >= 200 && r.status < 300) {
        pendientes = sinLote(pendientes, lote)
        this.guardar()
        this.settings.setItem('ultimo_envio', new Date().toISOString())
        this.settings.setItem('ultimo_error', '')
      } else if (r && (r.status === 400 || r.status === 413 || r.status === 422)) {
        // el servidor no acepta ESE lote (no se arregla reintentando): fuera,
        // o taparía para siempre todos los puntos de detrás
        pendientes = sinLote(pendientes, lote)
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
