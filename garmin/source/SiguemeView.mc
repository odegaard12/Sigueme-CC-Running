using Toybox.WatchUi;
using Toybox.Graphics;
using Toybox.Position;
using Toybox.Activity;
using Toybox.ActivityRecording;
using Toybox.Communications;
using Toybox.Application;
using Toybox.Time;
using Toybox.Time.Gregorian;
using Toybox.Timer;
using Toybox.Lang;
using Toybox.System;

// Pantalla única: START graba / pausa, ATRÁS guarda y sale. Cada 10 s manda los puntos pendientes por el móvil (Bluetooth);
// sin móvil se quedan en cola (hasta 600) y salen al volver, igual que hace Traccar.
class SiguemeView extends WatchUi.View {
    var sesion = null;
    var cola = [];
    var enviando = false;
    var nEnviando = 0;
    var enviados = 0;
    var estado = "Pulsa START";
    var calidad = 0;
    var pulso = null;
    var reloj = null;

    function initialize() {
        View.initialize();
    }

    function onShow() {
        Position.enableLocationEvents(Position.LOCATION_CONTINUOUS, method(:alPosicion));
        if (reloj == null) {
            reloj = new Timer.Timer();
            reloj.start(method(:enviar), 10000, true);
        }
    }

    function onHide() {
        // si se está grabando, el GPS sigue encendido
        if (sesion == null || !sesion.isRecording()) {
            Position.enableLocationEvents(Position.LOCATION_DISABLE, method(:alPosicion));
        }
    }

    function alPosicion(info as Position.Info) as Void {
        calidad = (info.accuracy != null) ? info.accuracy : 0;
        var act = Activity.getActivityInfo();
        pulso = (act != null) ? act.currentHeartRate : null;
        if (sesion != null && sesion.isRecording()) {
            apuntar(info);
        }
        WatchUi.requestUpdate();
    }

    // un punto de la cola, en el formato de Traccar Client que ya entiende la web
    function apuntar(info as Position.Info) as Void {
        if (info.position == null || info.accuracy == null || info.accuracy < Position.QUALITY_POOR) {
            return;
        }
        var p = info.position.toDegrees();
        var precision = 80;
        if (info.accuracy == Position.QUALITY_GOOD) { precision = 10; }
        else if (info.accuracy == Position.QUALITY_USABLE) { precision = 30; }
        var g = Gregorian.utcInfo(Time.now(), Time.FORMAT_SHORT);
        var ts = g.year.format("%04d") + "-" + g.month.format("%02d") + "-" + g.day.format("%02d") + "T"
               + g.hour.format("%02d") + ":" + g.min.format("%02d") + ":" + g.sec.format("%02d") + "Z";
        var extras = { "origen" => "garmin" };
        if (pulso != null) { extras.put("hr", pulso); }
        var coords = { "latitude" => p[0], "longitude" => p[1], "accuracy" => precision };
        if (info.speed != null) { coords.put("speed", info.speed); }
        cola.add({ "timestamp" => ts, "coords" => coords, "extras" => extras });
        if (cola.size() > 600) {
            cola = cola.slice(cola.size() - 600, null);
        }
    }

    // vale pegar el enlace de configuración del panel (…#id=odg-…): saca de él la dirección y el identificador
    function ajustes() {
        var url = Application.Properties.getValue("url");
        var id = Application.Properties.getValue("id");
        if (url == null) { url = ""; }
        if (id == null) { id = ""; }
        var m = url.find("#id=");
        if (m != null) {
            if (id.length() == 0) { id = url.substring(m + 4, url.length()); }
            url = url.substring(0, m);
        }
        var m2 = id.find("#id=");
        if (m2 != null) { id = id.substring(m2 + 4, id.length()); }
        if (url.length() == 0 || id.length() == 0) { return null; }
        if (url.find("http") != 0) { url = "https://" + url; }
        var ini = url.find("://");
        if (ini != null) {
            var resto = url.substring(ini + 3, url.length());
            var barra = resto.find("/");
            if (barra != null) { url = url.substring(0, ini + 3 + barra); }
        }
        return [ url + "/api/gps", id ];
    }

    function enviar() as Void {
        if (enviando || cola.size() == 0) { return; }
        var a = ajustes();
        if (a == null) {
            estado = "Falta la direccion o el identificador (ajustes)";
            WatchUi.requestUpdate();
            return;
        }
        var lote = cola.slice(0, 40);
        enviando = true;
        nEnviando = lote.size();
        Communications.makeWebRequest(
            a[0],
            { "device_id" => a[1], "location" => lote },
            {
                :method => Communications.HTTP_REQUEST_METHOD_POST,
                :headers => { "Content-Type" => Communications.REQUEST_CONTENT_TYPE_JSON },
                :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_JSON
            },
            method(:alResponder)
        );
    }

    function alResponder(codigo as Lang.Number, datos as Lang.Dictionary or Lang.String or Null) as Void {
        enviando = false;
        if (codigo == 200) {
            cola = cola.slice(nEnviando, null);
            enviados += nEnviando;
            estado = (sesion != null && sesion.isRecording()) ? "Grabando" : "En pausa";
        } else if (codigo == 403) {
            estado = "Identificador incorrecto";
        } else if (codigo == 400 || codigo == 413 || codigo == 422) {
            cola = cola.slice(nEnviando, null);          // el servidor no lo acepta: fuera, o taparia los de detras
            estado = "Lote rechazado (" + codigo + ")";
        } else {
            estado = "Sin conexion (" + codigo + ")";    // sin movil al alcance: se reintenta solo
        }
        WatchUi.requestUpdate();
    }

    function alternarGrabacion() as Void {
        if (sesion == null) {
            sesion = ActivityRecording.createSession({ :name => "Carrera", :sport => Activity.SPORT_RUNNING });
        }
        if (sesion.isRecording()) {
            sesion.stop();
            estado = "En pausa";
        } else {
            sesion.start();
            estado = "Grabando";
        }
        WatchUi.requestUpdate();
    }

    function guardarYSalir() as Void {
        if (sesion != null) {
            if (sesion.isRecording()) { sesion.stop(); }
            sesion.save();
            sesion = null;
        }
    }

    function onUpdate(dc as Graphics.Dc) as Void {
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_BLACK);
        dc.clear();
        var w = dc.getWidth();
        var h = dc.getHeight();
        var centro = Graphics.TEXT_JUSTIFY_CENTER;
        dc.setColor(0xD9F24A, Graphics.COLOR_TRANSPARENT);
        dc.drawText(w / 2, h * 0.10, Graphics.FONT_MEDIUM, "SIGUEME CC", centro);
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        dc.drawText(w / 2, h * 0.30, Graphics.FONT_SMALL, estado, centro);
        var gps = "GPS: sin senal";
        if (calidad == Position.QUALITY_GOOD) { gps = "GPS: bueno"; }
        else if (calidad == Position.QUALITY_USABLE) { gps = "GPS: usable"; }
        else if (calidad == Position.QUALITY_POOR) { gps = "GPS: flojo"; }
        dc.drawText(w / 2, h * 0.46, Graphics.FONT_SMALL, gps, centro);
        dc.drawText(w / 2, h * 0.60, Graphics.FONT_SMALL, "Pulso: " + ((pulso != null) ? pulso.toString() : "--"), centro);
        dc.drawText(w / 2, h * 0.74, Graphics.FONT_SMALL, "Sin enviar: " + cola.size().toString(), centro);
    }
}

class SiguemeDelegate extends WatchUi.BehaviorDelegate {
    var vista;

    function initialize(v) {
        BehaviorDelegate.initialize();
        vista = v;
    }

    function onSelect() as Lang.Boolean {
        vista.alternarGrabacion();
        return true;
    }

    function onBack() as Lang.Boolean {
        if (vista.sesion != null) {
            WatchUi.pushView(new WatchUi.Confirmation("Guardar y salir?"), new SalirDelegate(vista), WatchUi.SLIDE_UP);
            return true;
        }
        return false;
    }
}

class SalirDelegate extends WatchUi.ConfirmationDelegate {
    var vista;

    function initialize(v) {
        ConfirmationDelegate.initialize();
        vista = v;
    }

    function onResponse(respuesta as WatchUi.Confirm) as Lang.Boolean {
        if (respuesta == WatchUi.CONFIRM_YES) {
            vista.guardarYSalir();
            System.exit();
        }
        return true;
    }
}
