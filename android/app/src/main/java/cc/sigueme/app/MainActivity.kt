package cc.sigueme.app

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.text.InputType
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import org.json.JSONObject
import java.io.File
import kotlin.concurrent.thread

/** Una sola pantalla, sin librerías: configurar (QR del panel), bajar el plan,
 *  probar un aviso y empezar/parar el seguimiento. */
class MainActivity : Activity() {
    private lateinit var estado: TextView
    private lateinit var botonCarrera: Button
    private val prefs by lazy { Seguimiento.prefs(this) }

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        Seguimiento.canales(this)
        val caja = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(48, 64, 48, 64) }
        caja.addView(TextView(this).apply { text = "Sígueme CC"; textSize = 28f; setTextColor(Color.WHITE) })
        estado = TextView(this).apply { textSize = 16f; setTextColor(Color.LTGRAY); setPadding(0, 24, 0, 24) }
        caja.addView(estado)
        botonCarrera = boton(caja, "Empezar seguimiento") { carrera() }
        boton(caja, "Actualizar plan") { bajarPlan() }
        boton(caja, "Probar aviso en la pulsera") {
            Seguimiento.avisar(this, "Prueba de Sígueme CC · si lo ves en la pulsera, los avisos funcionan")
        }
        boton(caja, "Quitar ahorro de batería") { sinAhorro() }
        boton(caja, "Configurar a mano") { aMano() }
        caja.addView(TextView(this).apply {
            textSize = 13f; setTextColor(Color.GRAY); setPadding(0, 32, 0, 0)
            text = "Configura la app con la cámara del móvil: apunta al código QR del panel " +
                "(5 · App del móvil) y ábrelo con Sígueme CC.\n\nEn carrera la app sigue con la pantalla " +
                "apagada y sin cobertura: lanza los avisos (Mi Fitness los pasa a la pulsera) y guarda tu " +
                "posición para mandarla cuando vuelva la cobertura."
        })
        setContentView(ScrollView(this).apply { setBackgroundColor(Color.rgb(12, 15, 14)); addView(caja) })
        pedirPermisos()
        leerEnlace(intent)
    }

    override fun onNewIntent(i: Intent) { super.onNewIntent(i); leerEnlace(i) }
    override fun onResume() { super.onResume(); pintar() }

    private fun boton(caja: LinearLayout, txt: String, accion: () -> Unit) = Button(this).apply {
        text = txt; isAllCaps = false; textSize = 17f; setOnClickListener { accion() }
        caja.addView(this, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 16 })
    }

    private fun pintar() {
        val plan = Seguimiento.cargarPlan(this)
        val url = prefs.getString("url", null)
        val activo = prefs.getBoolean("activo", false)
        val enviado = prefs.getLong("enviado_t", 0)
        estado.text = buildString {
            append(if (url == null) "Sin configurar: escanea el código QR del panel.\n" else "Servidor: ${Uri.parse(url).host}\n")
            append(if (plan == null) "Sin plan de la carrera.\n"
                   else "${plan.nombre} · ${Plan.kmTxt(plan.distancia)} · ${plan.avisos.size} avisos\n")
            append(if (activo) "● SIGUIENDO · km ${Plan.kmTxt(prefs.getFloat("km", 0f).toDouble())}\n" else "Parado\n")
            prefs.getString("ultimo_aviso", null)?.let { if (activo) append("Último aviso: $it\n") }
            val cola = Seguimiento.pendientes(this@MainActivity)
            if (cola > 0) append("$cola posiciones esperando cobertura\n")
            if (enviado > 0) append("Última posición enviada: hace ${(System.currentTimeMillis() - enviado) / 60000} min\n")
            val pm = getSystemService(POWER_SERVICE) as PowerManager
            if (!pm.isIgnoringBatteryOptimizations(packageName)) append("⚠ Quita el ahorro de batería o Android puede cortar la app\n")
        }
        botonCarrera.text = if (activo) "Parar seguimiento" else "Empezar seguimiento"
    }

    /** siguemecc://config?u=https://tu-dominio&id=… (el QR del panel) */
    private fun leerEnlace(i: Intent?) {
        val d = i?.data ?: return
        if (d.scheme != "siguemecc") return
        val u = d.getQueryParameter("u")?.trimEnd('/') ?: return
        val id = d.getQueryParameter("id") ?: return
        setIntent(Intent(this, MainActivity::class.java))       // no volver a preguntar al girar la pantalla
        configurar(u, id)
    }

    private fun configurar(u: String, id: String) {
        val host = Uri.parse(u).host
        if (!(u.startsWith("https://") || u.startsWith("http://")) || host.isNullOrBlank() || id.length < 8) {
            aviso("Configuración no válida"); return
        }
        // a quién se manda tu posición: que se vea antes de aceptar
        AlertDialog.Builder(this).setTitle("¿Usar este servidor?")
            .setMessage("Tu posición se mandará a:\n\n$host")
            .setPositiveButton("Sí") { _, _ ->
                prefs.edit().putString("url", u).putString("id", id).apply()
                bajarPlan()
            }.setNegativeButton("No", null).show()
    }

    private fun bajarPlan() {
        val url = prefs.getString("url", null) ?: return aviso("Escanea antes el código QR del panel")
        val id = prefs.getString("id", null) ?: return
        estado.text = "Bajando el plan…"
        thread {
            val msg = try {
                val (codigo, txt) = Seguimiento.post("$url/api/plan", JSONObject().put("device_id", id).toString())
                when (codigo) {
                    200 -> {
                        val plan = Plan(txt)                      // si no se entiende, no se guarda
                        File(filesDir, "plan.json").writeText(txt)
                        if (!prefs.getBoolean("activo", false)) prefs.edit().putFloat("km", 0f).putInt("aviso", 0).apply()
                        "Plan listo: ${plan.nombre}, ${plan.avisos.size} avisos. Ya puedes ir sin cobertura."
                    }
                    403 -> "El servidor no reconoce el identificador: vuelve a escanear el código del panel."
                    else -> "El servidor contestó $codigo"
                }
            } catch (e: Exception) { "Sin conexión con el servidor (${e.javaClass.simpleName})" }
            runOnUiThread { pintar(); aviso(msg) }
        }
    }

    private fun carrera() {
        val servicio = Intent(this, Seguimiento::class.java)
        if (prefs.getBoolean("activo", false)) {
            AlertDialog.Builder(this).setMessage("¿Parar el seguimiento?").setPositiveButton("Parar") { _, _ ->
                stopService(servicio); prefs.edit().putBoolean("activo", false).apply(); pintar()
            }.setNegativeButton("No", null).show()
            return
        }
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            pedirPermisos(); return aviso("Hace falta el permiso de ubicación precisa")
        }
        prefs.edit().putFloat("km", 0f).putInt("aviso", 0).remove("ultimo_aviso").apply()   // carrera nueva
        startForegroundService(servicio)
        estado.postDelayed({ pintar() }, 600)
    }

    private fun sinAhorro() {
        val pm = getSystemService(POWER_SERVICE) as PowerManager
        if (pm.isIgnoringBatteryOptimizations(packageName)) return aviso("Ya está sin ahorro de batería ✓")
        startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$packageName")))
    }

    private fun aMano() {
        val caja = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(48, 16, 48, 0) }
        val url = EditText(this).apply { hint = "https://tu-dominio"; inputType = InputType.TYPE_TEXT_VARIATION_URI; setText(prefs.getString("url", "")) }
        val id = EditText(this).apply { hint = "Identificador (panel)"; setText(prefs.getString("id", "")) }
        caja.addView(url); caja.addView(id)
        AlertDialog.Builder(this).setTitle("Configurar a mano").setView(caja)
            .setPositiveButton("Guardar") { _, _ -> configurar(url.text.toString().trim().trimEnd('/'), id.text.toString().trim()) }
            .setNegativeButton("Cancelar", null).show()
    }

    private fun pedirPermisos() {
        val faltan = mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
        if (Build.VERSION.SDK_INT >= 33) faltan += Manifest.permission.POST_NOTIFICATIONS
        faltan.removeAll { checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED }
        if (faltan.isNotEmpty()) requestPermissions(faltan.toTypedArray(), 1)
    }

    private fun aviso(t: String) {
        AlertDialog.Builder(this).setMessage(t).setPositiveButton("Vale", null).show()
    }
}
