// Ajustes, en la app Zepp del móvil: dónde mandar los datos. Son los mismos
// que enseña el panel (pestaña Móvil → «Sin la app…» → Ver la configuración).
AppSettingsPage({
  build(props) {
    const s = props.settingsStorage
    let estado = {}
    try { estado = JSON.parse(s.getItem('estado') || '{}') } catch (e) {}
    const error = s.getItem('ultimo_error')
    const envio = s.getItem('ultimo_envio')
    const fila = (hijos, extra) => View({ style: Object.assign({ marginTop: '14px', padding: '0 16px' }, extra || {}) }, hijos)

    return Section({}, [
      fila([Text({ bold: true, paragraph: true }, 'Sígueme · reloj → web')]),
      fila([TextInput({
        label: 'Dirección del servidor (o pega el enlace de configuración del panel)',
        placeholder: 'https://tu-dominio',
        value: s.getItem('url') || '',
        onChange: v => {
          // el enlace de configuración del panel trae la dirección y el identificador: se rellenan los dos solos
          const m = /^(https?:\/\/[^\/#\s]+).*#id=([\w-]{8,100})/.exec((v || '').trim())
          if (m) { s.setItem('url', m[1] + '/api/gps'); s.setItem('id', m[2]) } else s.setItem('url', v)
        },
      })]),
      fila([TextInput({
        label: 'Identificador (panel: Móvil → Ver la configuración)',
        placeholder: 'odg-…',
        value: s.getItem('id') || '',
        onChange: v => {
          const m = /#id=([\w-]{8,100})/.exec((v || '').trim())
          s.setItem('id', m ? m[1] : (v || '').trim())
        },
      })]),
      fila([Text({ paragraph: true, style: { color: '#7d8a83', fontSize: '13px' } },
        (estado.pendientes ? estado.pendientes + ' puntos esperando a subir · ' : '') +
        (envio ? 'último envío ' + new Date(envio).toLocaleTimeString() : 'sin envíos todavía'))]),
      error ? fila([Text({ paragraph: true, style: { color: '#e0473a', fontSize: '13px' } }, error)]) : null,
    ].filter(Boolean))
  },
})
