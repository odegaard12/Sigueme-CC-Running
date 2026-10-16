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

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        canales(this)
        plan = cargarPlan(this)
        val n = fija("Siguiendo la carrera", plan?.nombre ?: "Sin plan: solo se manda la posición")
        if (Build.VERSION.SDK_INT >= 29) startForeground(FIJA, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION)
        else startForeground(FIJA, n)
        // con la pantalla apagada Android duerme la CPU: sin esto la cola no salía
        cierre = (getSystemService(POWER_SERVICE) as PowerManager)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "sigueme:carrera").apply { acquire(16 * 3600 * 1000L) }
        lm = getSystemService(LOCATION_SERVICE) as LocationManager
        try {
            lm.requestLocationUpdates(LocationManager.GPS_PROVIDER, 5000L, 0f, this, Looper.getMainLooper())
        } catch (e: SecurityException) {
            stopSelf()
        }
        prefs(this).edit().putBoolean("activo", true).apply()
    }

    override fun onDestroy() {
        try { lm.removeUpdates(this) } catch (_: Exception) {}
        cierre?.let { if (it.isHeld) it.release() }
        prefs(this).edit().putBoolean("activo", false).apply()
        val c = applicationContext
        red.execute { enviarCola(c) }        // lo que quede, si hay red
        red.shutdown()
        super.onDestroy()
    }

    override fun onLocationChanged(l: Location) {
        if (l.hasAccuracy() && l.accuracy > 100) return          // arranque en frío, túneles
        val p = prefs(this)
        apuntar(this, l, bateria())
        var texto = "Sin plan de avisos"
        plan?.let { pl ->
            val ultimo = p.getFloat("km", 0f).toDouble()
            val k = pl.kmEnRuta(l.latitude, l.longitude, ultimo)
            texto = if (k == null) "Fuera de la ruta (más de 150 m)" else "Km ${Plan.kmTxt(k)} de ${Plan.kmTxt(pl.distancia)}"
            if (k != null) {
                p.edit().putFloat("km", k.toFloat()).apply()
                val toca = pl.avisoQueToca(k, p.getInt("aviso", 0))
                // dos avisos seguidos se pisan en la pulsera: 20 s entre uno y otro
                if (toca != null && System.currentTimeMillis() - ultimoAviso > 20_000) {
                    ultimoAviso = System.currentTimeMillis()
                    p.edit().putInt("aviso", toca.first).putString("ultimo_aviso", toca.second).apply()
                    avisar(this, toca.second)
                }
            }
        }
        val pendientes = pendientes(this)
        nm().notify(FIJA, fija(texto, if (pendientes > 0) "$pendientes posiciones esperando cobertura" else "Posición enviada"))
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

        /** Notificación normal y nueva cada vez: es lo que Mi Fitness pasa a la pulsera. */
        fun avisar(c: Context, texto: String) {
            val n = Notification.Builder(c, CANAL_AVISOS).setSmallIcon(R.drawable.ic_noti).setContentTitle("Sígueme CC")
                .setContentText(texto).setStyle(Notification.BigTextStyle().bigText(texto))
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

        /** Manda la cola en lotes de 300; solo borra lo que el servidor confirmó (200). */
        fun enviarCola(c: Context) {
            val p = prefs(c)
            val url = p.getString("url", null) ?: return
            val id = p.getString("id", null) ?: return
            while (true) {
                val lote = synchronized(cola) {
                    File(c.filesDir, "cola.jsonl").takeIf { it.exists() }?.useLines { it.take(300).toList() } ?: emptyList()
                }
                if (lote.isEmpty()) return
                val cuerpo = JSONObject().put("device_id", id).put("location", JSONArray(lote.map { JSONObject(it) }))
                val codigo = try { post("$url/api/gps", cuerpo.toString()).first } catch (e: Exception) { return }
                if (codigo != 200) return
                synchronized(cola) {
                    val f = File(c.filesDir, "cola.jsonl")
                    val resto = f.readLines().drop(lote.size)
                    f.writeText(if (resto.isEmpty()) "" else resto.joinToString("\n", postfix = "\n"))
                }
                p.edit().putLong("enviado_t", System.currentTimeMillis()).apply()
            }
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
