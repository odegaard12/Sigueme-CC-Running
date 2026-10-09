// Ajustes, en la app Zepp del móvil: dónde mandar los datos. Son los mismos
// que se ponen en Traccar (panel admin → tarjeta "GPS del móvil").
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
        label: 'Dirección del servidor',
        placeholder: 'https://odegaard12.online/api/gps',
        value: s.getItem('url') || 'https://odegaard12.online/api/gps',
        onChange: v => s.setItem('url', v),
      })]),
      fila([TextInput({
        label: 'Identificador (el de la tarjeta "GPS del móvil" del panel)',
        placeholder: 'odg-…',
        value: s.getItem('id') || '',
        onChange: v => s.setItem('id', v),
      })]),
      fila([Text({ paragraph: true, style: { color: '#7d8a83', fontSize: '13px' } },
        (estado.pendientes ? estado.pendientes + ' puntos esperando a subir · ' : '') +
        (envio ? 'último envío ' + new Date(envio).toLocaleTimeString() : 'sin envíos todavía'))]),
      error ? fila([Text({ paragraph: true, style: { color: '#e0473a', fontSize: '13px' } }, error)]) : null,
    ].filter(Boolean))
  },
})
