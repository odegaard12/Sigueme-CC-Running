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
            avisar(this, "Seguimiento detenido: abre Sígueme CC y pulsa EMPEZAR")
            stopSelf(); return
        }
        corriendo = true
        // con la pantalla apagada Android duerme la CPU: sin esto la cola no salía
        cierre = (getSystemService(POWER_SERVICE) as PowerManager)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "sigueme:carrera").apply { acquire(16 * 3600 * 1000L) }
        lm = getSystemService(LOCATION_SERVICE) as LocationManager
        try {
            lm.requestLocationUpdates(LocationManager.GPS_PROVIDER, 5000L, 0f, this, Looper.getMainLooper())
        } catch (e: SecurityException) {
            stopSelf()
        }
    }

    // si Android mata el proceso, que lo vuelva a arrancar en cuanto pueda
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int) = START_STICKY

    private fun recargarPlan() {
        val f = File(filesDir, "plan.json")
        if (f.lastModified() != planCargado) { planCargado = f.lastModified(); plan = cargarPlan(this) }
    }

    override fun onDestroy() {
        corriendo = false
        prefs(this).edit().putBoolean("empezar_pendiente", false).apply()     // PARAR: la web ya no se pone en marcha
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
        var texto = "Sin plan de avisos"
        val pl0 = plan
        if (pl0 != null && pl0.antesDeSalir(System.currentTimeMillis())) {
            texto = "En la salida · empieza a las ${pl0.horaSalida}"
        } else plan?.let { pl ->
            val ultimo = p.getFloat("km", 0f).toDouble()
            val k = pl.kmEnRuta(l.latitude, l.longitude, ultimo)
            texto = if (k == null) "Fuera de la ruta (más de 150 m)" else String.format(Locale("es", "ES"), "Km %.1f de %.1f km", k, pl.distancia)
            if (k != null) {
                p.edit().putFloat("km", k.toFloat()).putLong("km_t", System.currentTimeMillis()).apply()
                val toca = pl.avisoQueToca(k, p.getInt("aviso", 0))
                // dos avisos seguidos se pisan en la pulsera: 20 s entre uno y otro
                if (toca != null && System.currentTimeMillis() - ultimoAviso > 20_000) {
                    ultimoAviso = System.currentTimeMillis()
                    p.edit().putInt("aviso", toca.first).putString("ultimo_aviso", toca.second).apply()
                    avisar(this, toca.second)
                }
            }
        }
        // la notificación fija, una vez por minuto: cada 5 s gastaba y alguna app de
        // pulsera la podía reenviar
        if (System.currentTimeMillis() - ultimaFija > 60_000) {
            ultimaFija = System.currentTimeMillis()
            val pendientes = pendientes(this)
            nm().notify(FIJA, fija(texto, if (pendientes > 0) "$pendientes posiciones esperando cobertura" else "Posición enviada"))
        }
        p.edit().putString("estado_km", texto).putLong("dato_t", System.currentTimeMillis()).apply()
        if (System.currentTimeMillis() - ultimoEnvio > 20_000) {
            ultimoEnvio = System.currentTimeMillis()
            val c = applicationContext
            red.execute { enviarCola(c) }
        }
    }

    @Deprecated("API vieja") override fun onStatusChanged(provider: String?, status: Int, extras: android.os.Bundle?) {}
    override fun onProviderEnabled(provider: String) {}
    override fun onProviderDisabled(provider: String) {}

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
        /** De verdad en marcha en este proceso (si Android lo mata, vuelve a false). */
        @Volatile var corriendo = false
        private var nAviso = 100

        fun prefs(c: Context) = c.getSharedPreferences("sigueme", MODE_PRIVATE)
        fun cargarPlan(c: Context): Plan? = try { Plan(File(c.filesDir, "plan.json").readText()) } catch (e: Exception) { null }

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
            synchronized(cola) { File(c.filesDir, "cola.jsonl").appendText(o.toString() + "\n") }
        }

        fun pendientes(c: Context): Int = synchronized(cola) {
            File(c.filesDir, "cola.jsonl").takeIf { it.exists() }?.useLines { it.count() } ?: 0
        }

        /** EMPEZAR pone en marcha la carrera en la web; sin cobertura en ese
         *  momento, se reintenta con cada envío hasta que llega. Baja también el
         *  plan al día. */
        fun empezarEnLaWeb(c: Context): String? {
            val p = prefs(c)
            val url = p.getString("url", null) ?: return null
            val id = p.getString("id", null) ?: return null
            val (codigo, txt) = try { post("$url/api/plan", JSONObject().put("device_id", id).put("accion", "empezar").toString()) }
                                catch (e: Exception) { return null }
            if (codigo == 403) {      // identificador viejo: reintentar solo bloquearía la IP
                p.edit().putBoolean("empezar_pendiente", false)
                    .putString("web_estado", "identificador no válido: vuelve a escanear el código del panel").apply()
                return "El servidor no reconoce el identificador: vuelve a escanear el código del panel (pestaña Móvil)."
            }
            if (codigo != 200) return null
            try { Plan(txt); File(c.filesDir, "plan.json").writeText(txt) } catch (e: Exception) {}
            val msg = try { JSONObject(txt).optString("mensaje", "") } catch (e: Exception) { "" }
            p.edit().putBoolean("empezar_pendiente", false).putString("web_estado", msg).apply()
            return msg
        }

        /** Manda la cola en lotes de 300; solo borra lo que el servidor confirmó (200). */
        fun enviarCola(c: Context) {
            val p = prefs(c)
            val url = p.getString("url", null) ?: return
            val id = p.getString("id", null) ?: return
            if (p.getBoolean("empezar_pendiente", false)) empezarEnLaWeb(c)
            while (true) {
                val lote = synchronized(cola) {
                    File(c.filesDir, "cola.jsonl").takeIf { it.exists() }?.useLines { it.take(300).toList() } ?: emptyList()
                }
                if (lote.isEmpty()) return
                // una línea rota (proceso cortado a mitad de escribir) se salta: antes tumbaba la app y bloqueaba la cola
                val puntos = lote.mapNotNull { try { JSONObject(it) } catch (e: Exception) { null } }
                if (puntos.isEmpty()) { quitar(c, lote.size); continue }
                val cuerpo = JSONObject().put("device_id", id).put("location", JSONArray(puntos))
                val codigo = try { post("$url/api/gps", cuerpo.toString()).first } catch (e: Exception) { return }
                if (codigo != 200) return
                quitar(c, lote.size)
                p.edit().putLong("enviado_t", System.currentTimeMillis()).apply()
            }
        }

        private fun quitar(c: Context, n: Int) = synchronized(cola) {
            val f = File(c.filesDir, "cola.jsonl")
            val resto = f.readLines().drop(n)
            f.writeText(if (resto.isEmpty()) "" else resto.joinToString("\n", postfix = "\n"))
        }

        fun post(url: String, cuerpo: String): Pair<Int, String> {
            val con = URL(url).openConnection() as HttpURLConnection
            con.connectTimeout = 15_000; con.readTimeout = 30_000
            con.requestMethod = "POST"; con.doOutput = true
            con.setRequestProperty("Content-Type", "application/json")
            con.outputStream.use { it.write(cuerpo.toByteArray()) }
            val codigo = con.responseCode
            val txt = (if (codigo < 400) con.inputStream else con.errorStream)?.bufferedReader()?.use { it.readText() } ?: ""
            con.disconnect()
            return codigo to txt
        }
    }
}
