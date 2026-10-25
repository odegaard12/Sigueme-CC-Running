// Sígueme CC en el reloj Garmin (Connect IQ): graba la actividad y manda posición y pulso a /api/gps de la web.
// EXPERIMENTAL: escrito sin poder compilarlo ni probarlo en un reloj real. Ver README.md.
using Toybox.Application;
using Toybox.WatchUi;

class SiguemeApp extends Application.AppBase {
    function initialize() {
        AppBase.initialize();
    }

    function getInitialView() {
        var vista = new SiguemeView();
        return [ vista, new SiguemeDelegate(vista) ];
    }
}
