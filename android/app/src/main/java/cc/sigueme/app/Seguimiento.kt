package cc.sigueme.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.location.Location
import android.net.ConnectivityManager
import android.net.Network
import android.location.LocationListener
import android.location.LocationManager
import android.os.BatteryManager
import android.os.Build
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/** Servicio en primer plano: GPS del móvil cada 5 s, avisos locales (sin
 *  cobertura) y cola de posiciones que se manda a la web cuando hay red. */
class Seguimiento : Service(), LocationListener {
    private lateinit var lm: LocationManager
    private var cierre: PowerManager.WakeLock? = null
    private var plan: Plan? = null
    private val red = Executors.newSingleThreadExecutor()
    private var ultimoEnvio = 0L
    private var ultimoAviso = 0L
    private var ultimaFija = 0L
    private var planCargado = 0L          // fecha de plan.json: si cambia, se recarga en marcha
    // vuelve la cobertura: fuera la espera y la cola sale ya, sin esperar al siguiente intento
    private val alVolverLaRed = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) {
            hayRed()
            val c = applicationContext
            try { red.execute { enviarCola(c) } } catch (_: Exception) {}
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        canales(this)
        recargarPlan()
        val n = fija("Siguiendo la carrera", plan?.nombre ?: "Sin plan: solo se manda la posición")
        // ⚠️ Si Android relanza el servicio desde segundo plano (lo mató por memoria),
        // en Android 14 puede no dejar arrancarlo: fuera limpio, sin bucle de cierres
        try {
            if (Build.VERSION.SDK_INT >= 29) startForeground(FIJA, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION)
            else startForeground(FIJA, n)
        } catch (e: Exception) {
            avisar(this, "Seguimiento detenido · abre Sígueme CC y pulsa EMPEZAR")
            stopSelf(); return
        }
        corriendo = true
        // con la pantalla apagada Android duerme la CPU entre lectura y lectura del
        // GPS: sin esto, la cola tardaba en salir al volver la cobertura. Cuesta algo
        // de batería; se prefiere a que la familia no vea la posición.
        cierre = (getSystemService(POWER_SERVICE) as PowerManager)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "sigueme:carrera").apply { acquire(16 * 3600 * 1000L) }
        try { (getSystemService(CONNECTIVITY_SERVICE) as ConnectivityManager).registerDefaultNetworkCallback(alVolverLaRed) } catch (_: Exception) {}
        lm = getSystemService(LOCATION_SERVICE) as LocationManager
        try {
            lm.requestLocationUpdates(LocationManager.GPS_PROVIDER, 5000L, 0f, this, Looper.getMainLooper())
        } catch (e: SecurityException) {
            avisar(this, "Seguimiento detenido · falta el permiso de ubicación precisa")
            stopSelf()
        }
    }

    // si Android mata el proceso, que lo vuelva a arrancar en cuanto pueda
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int) = START_STICKY

    /** ⚠️ Solo se da por cargado si se entiende: leer un plan.json a medio escribir
     *  dejaba la app sin avisos toda la carrera. Si falla, se queda el anterior. */
    private fun recargarPlan() {
        val f = File(filesDir, "plan.json")
        if (f.lastModified() == planCargado) return
        cargarPlan(this)?.let { plan = it; planCargado = f.lastModified() }
    }

    override fun onDestroy() {
        corriendo = false
        prefs(this).edit().putBoolean("empezar_pendiente", false).apply()     // PARAR: la web ya no se pone en marcha
        try { (getSystemService(CONNECTIVITY_SERVICE) as ConnectivityManager).unregisterNetworkCallback(alVolverLaRed) } catch (_: Exception) {}
        if (!::lm.isInitialized) { super.onDestroy(); return }
        try { lm.removeUpdates(this) } catch (_: Exception) {}
        cierre?.let { if (it.isHeld) it.release() }
        val c = applicationContext
        red.execute { enviarCola(c) }        // lo que quede, si hay red
        red.shutdown()
        super.onDestroy()
    }

    override fun onLocationChanged(l: Location) {
        if (l.hasAccuracy() && l.accuracy > 100) return          // arranque en frío, túneles
        val p = prefs(this)
        apuntar(this, l, bateria())
        recargarPlan()
        val ahora = System.currentTimeMillis()
        val e = p.edit()                     // un solo guardado por lectura (antes, tres)
        var texto = "Sin plan de avisos"
        val pl = plan
        if (pl != null && pl.antesDeSalir(ahora)) {
            texto = "En la salida · empieza a las ${pl.horaSalida}"
        } else if (pl != null) {
            val k = pl.kmEnRuta(l.latitude, l.longitude, p.getFloat("km", 0f).toDouble())
            texto = if (k == null) "Fuera de la ruta (más de 150 m)" else String.format(Locale("es", "ES"), "Km %.1f de %.1f km", k, pl.distancia)
            if (k != null) {
                e.putFloat("km", k.toFloat()).putLong("km_t", ahora)
                val toca = pl.avisoQueToca(k, p.getInt("aviso", 0))
                // dos avisos seguidos se pisan en la pulsera: 20 s entre uno y otro (el
                // que espera sale en la lectura siguiente: por estado, no se pierde)
                if (toca != null && ahora - ultimoAviso > 20_000) {
                    ultimoAviso = ahora
                    e.putInt("aviso", toca.first).putString("ultimo_aviso", toca.second)
                    avisar(this, toca.second)
                }
                // meta: aviso y, a los 15 min, el seguimiento se para solo (batería y,
                // sobre todo, que no se siga publicando dónde estás después)
                if (k >= pl.distancia - 0.1) {
                    val meta = p.getLong("meta_t", 0)
                    if (meta == 0L) {
                        e.putLong("meta_t", ahora)
                        avisar(this, "¡Meta! · el seguimiento se para solo en 15 min")
                    } else if (ahora - meta > 15 * 60_000 && pendientes(this) == 0) {
                        e.apply(); stopSelf(); return
                    }
                }
            }
        }
        // lejos de la ruta después de meta (camino del coche): también se para a los 15 min
        val metaT = p.getLong("meta_t", 0)
        if (metaT > 0 && ahora - metaT > 15 * 60_000 && pendientes(this) == 0) { e.apply(); stopSelf(); return }
        e.putString("estado_km", texto).apply()
        // la notificación fija, una vez por minuto: cada 5 s gastaba y alguna app de
        // pulsera la podía reenviar
        if (ahora - ultimaFija > 60_000) {
            ultimaFija = ahora
            val pendientes = pendientes(this)
            nm().notify(FIJA, fija(texto, if (pendientes > 0) "$pendientes posiciones esperando cobertura" else "Posición enviada"))
        }
        // un envío cada vez: con mala cobertura cada intento tarda; sin esto se amontonaban
        if (ahora - ultimoEnvio > 20_000 && ahora >= esperaHasta && !enviando.get()) {
            ultimoEnvio = ahora
            val c = applicationContext
            red.execute { enviarCola(c) }
        }
    }

    @Deprecated("API vieja") override fun onStatusChanged(provider: String?, status: Int, extras: android.os.Bundle?) {}
    override fun onProviderEnabled(provider: String) {}
    // GPS apagado en ajustes rápidos o por el ahorro de energía: antes, ni un aviso
    override fun onProviderDisabled(provider: String) {
        avisar(this, "Sin GPS · enciende la ubicación o no habrá avisos ni posición")
    }

    private fun bateria(): Int = (getSystemService(BATTERY_SERVICE) as BatteryManager).getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
    private fun nm() = getSystemService(NOTIFICATION_SERVICE) as NotificationManager

    private fun fija(titulo: String, texto: String): Notification {
        val abrir = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        return Notification.Builder(this, CANAL_FIJO).setSmallIcon(R.drawable.ic_noti).setContentTitle(titulo)
            .setContentText(texto).setOngoing(true).setOnlyAlertOnce(true).setContentIntent(abrir).build()
    }

    companion object {
        const val FIJA = 1
        const val CANAL_FIJO = "seguimiento"
        const val CANAL_AVISOS = "avisos"
        private val cola = Any()
        private val enviando = AtomicBoolean(false)
        private val empezando = AtomicBoolean(false)
        /** De verdad en marcha en este proceso (si Android lo mata, vuelve a false). */
        @Volatile var corriendo = false
        private var nAviso = 100

        fun prefs(c: Context) = c.getSharedPreferences("sigueme", MODE_PRIVATE)
        fun cargarPlan(c: Context): Plan? = try { Plan(File(c.filesDir, "plan.json").readText()) } catch (e: Exception) { null }

        /** Escribe entero o nada: a un temporal y luego se renombra. */
        fun escribirSeguro(f: File, texto: String) {
            val tmp = File(f.parentFile, f.name + ".tmp")
            tmp.writeText(texto)
            if (!tmp.renameTo(f)) { f.delete(); tmp.renameTo(f) }
        }

        fun canales(c: Context) {
            val nm = c.getSystemService(NOTIFICATION_SERVICE) as NotificationManager
            nm.createNotificationChannel(NotificationChannel(CANAL_FIJO, "Seguimiento en marcha", NotificationManager.IMPORTANCE_LOW))
            nm.createNotificationChannel(NotificationChannel(CANAL_AVISOS, "Avisos de la carrera", NotificationManager.IMPORTANCE_HIGH).apply {
                enableVibration(true); vibrationPattern = longArrayOf(0, 400, 200, 400)
            })
        }

        /** Notificación normal y nueva cada vez: es lo que Mi Fitness pasa a la pulsera.
         *  Título = lo importante; cuerpo = los números (Plan.notificacion). */
        fun avisar(c: Context, texto: String) {
            val (titulo, cuerpo) = Plan.notificacion(texto)
            notificar(c, titulo, cuerpo)
        }

        /** Título y cuerpo ya hechos (el aviso de prueba usa este, con el mismo diseño que los de la carrera). */
        fun notificar(c: Context, titulo: String, cuerpo: String) {
            val n = Notification.Builder(c, CANAL_AVISOS).setSmallIcon(R.drawable.ic_noti).setContentTitle(titulo)
                .setContentText(cuerpo.replace('\n', ' ')).setStyle(Notification.BigTextStyle().bigText(cuerpo))
                .setSubText("Sígueme CC")
                .setCategory(Notification.CATEGORY_MESSAGE).setAutoCancel(true).setTimeoutAfter(10 * 60 * 1000L).build()
            (c.getSystemService(NOTIFICATION_SERVICE) as NotificationManager).notify(nAviso++, n)
        }

        private fun hora(t: Long) = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.ROOT)
            .apply { timeZone = TimeZone.getTimeZone("UTC") }.format(Date(t))

        fun apuntar(c: Context, l: Location, bateria: Int) {
            val o = JSONObject().put("timestamp", hora(l.time))
                .put("coords", JSONObject().put("latitude", l.latitude).put("longitude", l.longitude)
                    .put("speed", if (l.hasSpeed()) l.speed.toDouble() else -1.0)
                    .put("accuracy", if (l.hasAccuracy()) l.accuracy.toDouble() else 0.0)
                    .put("altitude", if (l.hasAltitude()) l.altitude else 0.0))
                .put("battery", JSONObject().put("level", bateria / 100.0))
                .put("extras", JSONObject().put("origen", "app"))
            // con el móvil sin espacio no se cae el servicio: ese punto se pierde y ya
            try {
                synchronized(cola) {
                    val f = File(c.filesDir, "cola.jsonl")
                    val corta = f.length() > 0 && java.io.RandomAccessFile(f, "r").use { it.seek(f.length() - 1); it.read() } != '\n'.code
                    f.appendText((if (corta) "\n" else "") + o.toString() + "\n")
                }
            } catch (e: Exception) {}
        }

        private var cacheLong = -1L
        private var cacheCuenta = 0
        fun pendientes(c: Context): Int = synchronized(cola) {
            val f = File(c.filesDir, "cola.jsonl")
            if (!f.exists()) { cacheLong = -1L; cacheCuenta = 0 }
            else if (f.length() != cacheLong) { cacheLong = f.length(); cacheCuenta = f.useLines { it.count() } }
            cacheCuenta
        }

        /** ¿El servidor nos ha dicho que paremos? 403 = identificador no válido (hasta
         *  volver a configurar), 429 = demasiados intentos (15 min). Insistir solo
         *  alargaba el bloqueo de la IP. */
        private fun bloqueado(c: Context) = System.currentTimeMillis() < prefs(c).getLong("bloqueado_hasta", 0)
        private fun identificadorMalo(codigo: Int, cuerpo: String) = codigo == 403 && cuerpo.contains("identificador")
        private fun bloquear(c: Context, codigo: Int, cuerpo: String = "") {
            // un 403 de la red (WAF, Cloudflare) viene con HTML y es pasajero: no hay que volver a escanear nada
            val permanente = identificadorMalo(codigo, cuerpo)
            val hasta = if (permanente) Long.MAX_VALUE else System.currentTimeMillis() + 15 * 60_000
            prefs(c).edit().putLong("bloqueado_hasta", hasta).putString("web_estado",
                if (permanente) "identificador no válido: vuelve a escanear el código del panel"
                else if (codigo == 403) "la red rechazó el acceso: se reintenta en 15 min"
                else "demasiados intentos: se reintenta en 15 min").apply()
        }

        /** EMPEZAR pone en marcha la carrera en la web; sin cobertura en ese
         *  momento, se reintenta con cada envío hasta que llega. Baja también el
         *  plan al día. Una sola petición a la vez. */
        fun empezarEnLaWeb(c: Context): String? {
            val p = prefs(c)
            val url = p.getString("url", null) ?: return null
            val id = p.getString("id", null) ?: return null
            if (bloqueado(c) || !empezando.compareAndSet(false, true)) return null
            try {
                if (!p.getBoolean("empezar_pendiente", false)) return null      // PARAR entre medias
                val (codigo, txt) = try { post("$url/api/plan", JSONObject().put("device_id", id).put("accion", "empezar").put("t", p.getLong("empezar_t", 0L)).toString()) }
                                    catch (e: Exception) { return null }
                if (codigo == 403 || codigo == 429) {
                    bloquear(c, codigo, txt)
                    val malo = identificadorMalo(codigo, txt)
                    if (malo) p.edit().putBoolean("empezar_pendiente", false).apply()
                    return if (malo) "El servidor no reconoce el identificador: vuelve a escanear el código del panel (pestaña Móvil)."
                           else if (codigo == 403) "La red rechazó la petición (403): la app lo reintenta sola en 15 minutos."
                           else "Demasiados intentos fallidos: la app lo reintenta sola en 15 minutos."
                }
                if (codigo != 200) return null
                try { Plan(txt); escribirSeguro(File(c.filesDir, "plan.json"), txt) } catch (e: Exception) {}
                val msg = try { JSONObject(txt).optString("mensaje", "") } catch (e: Exception) { "" }
                p.edit().putBoolean("empezar_pendiente", false).putString("web_estado", msg).apply()
                return msg
            } finally {
                empezando.set(false)
            }
        }

        /** Sin cobertura, cada intento fallido dobla la espera (20 s → 5 min): antes
         *  se probaba cada 20 s durante horas con la radio y la CPU despiertas. En
         *  cuanto Android avisa de que hay red, la espera se olvida. */
        @Volatile var esperaHasta = 0L
        @Volatile private var espera = 20_000L
        private fun fallo() {
            espera = minOf(espera * 2, 5 * 60_000L)
            esperaHasta = System.currentTimeMillis() + espera
        }
        fun hayRed() { espera = 20_000L; esperaHasta = 0L }

        /** Manda la cola en lotes de 300; solo borra lo que el servidor confirmó (200). */
        fun enviarCola(c: Context) {
            if (!enviando.compareAndSet(false, true)) return
            try {
                val p = prefs(c)
                val url = p.getString("url", null) ?: return
                val id = p.getString("id", null) ?: return
                if (bloqueado(c)) return
                if (p.getBoolean("empezar_pendiente", false)) empezarEnLaWeb(c)
                // ⚠️ Se lee UNA vez y se quita lo enviado de golpe al final: quitar tras
                // cada lote reescribía el fichero entero (horas sin cobertura = miles de
                // líneas) y bloqueaba la pantalla, que espera al mismo cerrojo
                val todas = synchronized(cola) {
                    File(c.filesDir, "cola.jsonl").takeIf { it.exists() }?.readLines() ?: emptyList()
                }
                var hechas = 0
                try {
                    for (lote in todas.chunked(300)) {
                        // una línea rota (proceso cortado a mitad de escribir) se salta: antes tumbaba la app y bloqueaba la cola
                        val puntos = lote.mapNotNull { try { JSONObject(it) } catch (e: Exception) { null } }
                        if (puntos.isNotEmpty()) {
                            val cuerpo = JSONObject().put("device_id", id).put("location", JSONArray(puntos))
                            val (codigo, respuesta) = try { post("$url/api/gps", cuerpo.toString()) } catch (e: Exception) { fallo(); return }
                            if (codigo == 403 || codigo == 429) { bloquear(c, codigo, respuesta); return }
                            // el servidor no acepta ESE lote y reintentar no lo arregla: se descarta, o taparía los de detrás
                            if (codigo == 400 || codigo == 413 || codigo == 422) { hechas += lote.size; continue }
                            if (codigo != 200) { fallo(); return }
                        }
                        hechas += lote.size
                    }
                    espera = 20_000L; esperaHasta = 0L
                } finally {
                    if (hechas > 0) { quitar(c, hechas); p.edit().putLong("enviado_t", System.currentTimeMillis()).apply() }
                }
            } finally {
                enviando.set(false)
            }
        }

        private fun quitar(c: Context, n: Int) = synchronized(cola) {
            val f = File(c.filesDir, "cola.jsonl")
            val resto = f.readLines().drop(n)
            escribirSeguro(f, if (resto.isEmpty()) "" else resto.joinToString("\n", postfix = "\n"))
        }

        fun post(url: String, cuerpo: String): Pair<Int, String> {
            val con = URL(url).openConnection() as HttpURLConnection
            con.connectTimeout = 15_000; con.readTimeout = 30_000
            con.requestMethod = "POST"; con.doOutput = true
            con.setRequestProperty("Content-Type", "application/json")
            try {
                con.outputStream.use { it.write(cuerpo.toByteArray()) }
                val codigo = con.responseCode
                val txt = (if (codigo < 400) con.inputStream else con.errorStream)?.bufferedReader()?.use { it.readText() } ?: ""
                return codigo to txt
            } finally {
                con.disconnect()
            }
        }
    }
}
