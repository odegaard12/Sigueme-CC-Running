package cc.sigueme.app

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.app.NotificationManager
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.provider.Settings
import android.text.InputType
import android.view.Gravity
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.TextView
import org.json.JSONObject
import java.io.File
import java.util.Locale
import kotlin.concurrent.thread

/** Una sola pantalla, sin librerías: estado de la carrera, botón grande para
 *  empezar/parar y la lista «Listo para salir» (cada fila arregla lo suyo). */
class MainActivity : Activity() {
    // los colores de la web
    private val fondoC = Color.rgb(12, 15, 14)
    private val tarjetaC = Color.rgb(22, 27, 25)
    private val bordeC = Color.rgb(38, 48, 44)
    private val textoC = Color.rgb(241, 243, 241)
    private val apagadoC = Color.rgb(138, 150, 143)
    private val verdeC = Color.rgb(127, 212, 106)
    private val rojoC = Color.rgb(255, 138, 122)
    private val ambarC = Color.rgb(243, 201, 105)

    private val prefs by lazy { Seguimiento.prefs(this) }
    private var sinAvisosOk = false
    private val reloj = Handler(Looper.getMainLooper())
    private val repintar = object : Runnable { override fun run() { pintar(); reloj.postDelayed(this, 2000) } }

    private lateinit var carreraTxt: TextView
    private lateinit var pastilla: TextView
    private lateinit var kmTxt: TextView
    private lateinit var deTxt: TextView
    private lateinit var barra: ProgressBar
    private lateinit var avisoTxt: TextView
    private lateinit var redTxt: TextView
    private lateinit var botonGrande: TextView
    private lateinit var lista: LinearLayout

    private fun Int.px() = (this * resources.displayMetrics.density).toInt()

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        Seguimiento.canales(this)
        window.statusBarColor = fondoC
        window.navigationBarColor = fondoC
        val caja = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(20.px(), 28.px(), 20.px(), 32.px()) }

        // cabecera
        val cab = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.BOTTOM }
        cab.addView(texto(26f, textoC).apply { text = "Sígueme "; typeface = Typeface.DEFAULT_BOLD })
        cab.addView(texto(26f, apagadoC).apply { text = "CC" })
        caja.addView(cab)
        carreraTxt = texto(15f, apagadoC)
        caja.addView(carreraTxt)

        // tarjeta de estado
        val estado = tarjeta()
        pastilla = TextView(this).apply {
            textSize = 12f; typeface = Typeface.DEFAULT_BOLD; letterSpacing = 0.08f
            setPadding(10.px(), 4.px(), 10.px(), 4.px())
        }
        estado.addView(pastilla, LinearLayout.LayoutParams(-2, -2))
        kmTxt = texto(56f, textoC).apply { typeface = Typeface.DEFAULT_BOLD; setPadding(0, 8.px(), 0, 0) }
        estado.addView(kmTxt)
        deTxt = texto(14f, apagadoC)
        estado.addView(deTxt)
        barra = ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply {
            max = 1000
            progressTintList = ColorStateList.valueOf(verdeC)
            progressBackgroundTintList = ColorStateList.valueOf(bordeC)
        }
        estado.addView(barra, LinearLayout.LayoutParams(-1, 10.px()).apply { topMargin = 12.px(); bottomMargin = 12.px() })
        avisoTxt = texto(16f, textoC)
        estado.addView(avisoTxt)
        redTxt = texto(13f, apagadoC)
        estado.addView(redTxt, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 6.px() })
        caja.addView(estado)

        // botón grande
        botonGrande = TextView(this).apply {
            gravity = Gravity.CENTER; textSize = 20f; typeface = Typeface.DEFAULT_BOLD; isClickable = true
            setOnClickListener { carrera() }
        }
        caja.addView(botonGrande, LinearLayout.LayoutParams(-1, 64.px()).apply { topMargin = 14.px() })

        // acciones secundarias
        val fila = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        fila.addView(botonSec("Probar aviso") { probarAviso() }, LinearLayout.LayoutParams(0, 52.px(), 1f).apply { rightMargin = 6.px() })
        fila.addView(botonSec("Actualizar plan") { bajarPlan() }, LinearLayout.LayoutParams(0, 52.px(), 1f).apply { leftMargin = 6.px() })
        caja.addView(fila, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 12.px() })

        // lista de comprobación
        val prep = tarjeta()
        prep.addView(texto(12f, apagadoC).apply { text = "LISTO PARA SALIR"; typeface = Typeface.DEFAULT_BOLD; letterSpacing = 0.08f })
        lista = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        prep.addView(lista)
        caja.addView(prep)

        caja.addView(texto(13f, apagadoC).apply {
            setPadding(4.px(), 18.px(), 4.px(), 0)
            text = "Con la pantalla apagada y sin cobertura, la app sigue tu km con el GPS, lanza los avisos " +
                "(Mi Fitness los pasa a la pulsera) y guarda tu posición hasta que vuelve la cobertura.\n\n" +
                "En Samsung, para que no la duerma: Ajustes → Batería → Límites de uso en segundo plano → " +
                "«Apps que nunca se suspenden» → añade Sígueme CC."
        })
        caja.addView(texto(14f, verdeC).apply {
            text = "Configurar a mano"; typeface = Typeface.DEFAULT_BOLD
            setPadding(4.px(), 16.px(), 4.px(), 4.px()); setOnClickListener { aMano() }
        })
        setContentView(ScrollView(this).apply { setBackgroundColor(fondoC); addView(caja) })
        pedirPermisos()
        leerEnlace(intent)
    }

    override fun onNewIntent(i: Intent) { super.onNewIntent(i); leerEnlace(i) }
    override fun onResume() { super.onResume(); reloj.post(repintar) }
    override fun onPause() { reloj.removeCallbacks(repintar); super.onPause() }

    // ---------- piezas ----------
    private fun fondo(color: Int, radio: Int, borde: Int? = null) = GradientDrawable().apply {
        setColor(color); cornerRadius = radio.px().toFloat(); if (borde != null) setStroke(1.px(), borde)
    }
    private fun texto(tam: Float, color: Int) = TextView(this).apply { textSize = tam; setTextColor(color) }
    private fun tarjeta() = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL; background = fondo(tarjetaC, 16, bordeC)
        setPadding(18.px(), 16.px(), 18.px(), 18.px())
        layoutParams = LinearLayout.LayoutParams(-1, -2).apply { topMargin = 16.px() }
    }
    private fun botonSec(txt: String, accion: () -> Unit) = TextView(this).apply {
        text = txt; gravity = Gravity.CENTER; textSize = 15f; setTextColor(textoC); typeface = Typeface.DEFAULT_BOLD
        background = fondo(tarjetaC, 14, bordeC); isClickable = true; setOnClickListener { accion() }
    }

    private fun filaLista(ok: Boolean, txt: String, arreglo: () -> Unit) = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(0, 10.px(), 0, 10.px())
        addView(TextView(this@MainActivity).apply {
            text = if (ok) "✓" else "!"; gravity = Gravity.CENTER; textSize = 13f; typeface = Typeface.DEFAULT_BOLD
            setTextColor(fondoC); background = fondo(if (ok) verdeC else ambarC, 11)
        }, LinearLayout.LayoutParams(22.px(), 22.px()).apply { rightMargin = 12.px() })
        addView(texto(15f, if (ok) textoC else ambarC).apply { text = txt }, LinearLayout.LayoutParams(0, -2, 1f))
        if (!ok) {
            addView(texto(13f, verdeC).apply { text = "Arreglar ›"; typeface = Typeface.DEFAULT_BOLD })
            isClickable = true; setOnClickListener { arreglo() }
        }
    }

    // ---------- estado ----------
    private fun pintar() {
        val plan = Seguimiento.cargarPlan(this)
        val url = prefs.getString("url", null)
        val activo = Seguimiento.corriendo
        carreraTxt.text = plan?.nombre ?: "Sin carrera: escanea el código del panel"

        pastilla.text = if (activo) "● SIGUIENDO" else "PARADO"
        pastilla.setTextColor(if (activo) fondoC else apagadoC)
        pastilla.background = fondo(if (activo) verdeC else bordeC, 20)

        val km = if (activo) prefs.getFloat("km", 0f).toDouble() else 0.0
        kmTxt.text = String.format(Locale("es", "ES"), "%.1f", km)
        deTxt.text = when {
            plan == null -> "km"
            // el estado solo si dice algo que no sea el km (fuera de la ruta, sin GPS)
            activo -> String.format(Locale("es", "ES"), "de %.1f km", plan.distancia) + (prefs.getString("estado_km", null)
                ?.takeUnless { it.startsWith("Km ") }?.let { " · $it" } ?: if (prefs.contains("estado_km")) "" else " · buscando GPS…")
            else -> String.format(Locale("es", "ES"), "de %.1f km", plan.distancia)
        }
        barra.progress = if (plan != null && plan.distancia > 0) (km / plan.distancia * 1000).toInt() else 0

        val ultimo = prefs.getString("ultimo_aviso", null)
        avisoTxt.text = when {
            activo && ultimo != null -> Plan.notificacion(ultimo).let { (t, c) -> "Último aviso: $t" + (if (c.isEmpty()) "" else " · " + c.replace('\n', ' ')) }
            activo -> "Esperando el primer aviso…"
            plan != null -> "${plan.avisos.size} avisos guardados en el móvil"
            else -> "Sin avisos"
        }
        val cola = Seguimiento.pendientes(this)
        val enviado = prefs.getLong("enviado_t", 0)
        redTxt.text = listOfNotNull(
            when {
                cola > 0 && url == null -> "$cola posiciones guardadas (falta configurar el servidor)"
                cola > 0 -> "📡 $cola posiciones esperando cobertura"
                activo -> "Posición al día en la web"
                else -> null
            },
            if (enviado > 0) "última enviada hace ${(System.currentTimeMillis() - enviado) / 60000} min" else null
        ).joinToString(" · ") + when {
            !activo -> ""
            prefs.getBoolean("empezar_pendiente", false) -> "\nWeb: se pondrá en marcha en cuanto haya cobertura"
            else -> prefs.getString("web_estado", null)?.takeIf { it.isNotBlank() }?.let { "\nWeb: $it" } ?: ""
        }

        botonGrande.text = if (activo) "PARAR SEGUIMIENTO" else "EMPEZAR SEGUIMIENTO"
        botonGrande.setTextColor(if (activo) rojoC else fondoC)
        botonGrande.background = if (activo) fondo(tarjetaC, 16, rojoC) else fondo(verdeC, 16)

        val pm = getSystemService(POWER_SERVICE) as PowerManager
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        val avisosOn = nm.areNotificationsEnabled() &&
            (nm.getNotificationChannel(Seguimiento.CANAL_AVISOS)?.importance ?: 0) >= NotificationManager.IMPORTANCE_DEFAULT
        lista.removeAllViews()
        lista.addView(filaLista(url != null, if (url != null) "Servidor: ${Uri.parse(url).host}" else "Escanea el código del panel") { aMano() })
        lista.addView(filaLista(plan != null && plan.avisos.isNotEmpty(),
            if (plan != null) "Plan: ${plan.avisos.size} avisos, ${plan.subidas.size} " + (if (plan.subidas.size == 1) "subida" else "subidas") else "Falta bajar el plan") { bajarPlan() })
        lista.addView(filaLista(tiene(Manifest.permission.ACCESS_FINE_LOCATION), "Ubicación precisa") { ajustesApp() })
        lista.addView(filaLista(avisosOn, if (avisosOn) "Notificaciones de avisos" else "Notificaciones apagadas") { ajustesAvisos() })
        lista.addView(filaLista(pm.isIgnoringBatteryOptimizations(packageName), "Sin ahorro de batería") { sinAhorro() })
        lista.addView(filaLista(prefs.getLong("prueba_t", 0) > 0, "Aviso de prueba en la pulsera") { probarAviso() })
    }

    private fun tiene(permiso: String) = checkSelfPermission(permiso) == PackageManager.PERMISSION_GRANTED

    // ---------- acciones ----------
    /** El QR del panel abre app.html, que abre siguemecc://config?u=…&id=… */
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
        // solo https: Android no deja mandar datos sin cifrar, y así no van en claro
        if (!u.startsWith("https://") || host.isNullOrBlank() || id.length < 8) {
            dialogo("Configuración no válida: la dirección tiene que empezar por https://")
            return
        }
        AlertDialog.Builder(this).setTitle("¿Usar este servidor?")
            .setMessage("Tu posición se mandará a:\n\n$host")
            .setPositiveButton("Sí") { _, _ ->
                prefs.edit().putString("url", u).putString("id", id).remove("bloqueado_hasta").apply()
                bajarPlan()
            }.setNegativeButton("No", null).show()
    }

    private fun bajarPlan() {
        val url = prefs.getString("url", null)
        val id = prefs.getString("id", null)
        if (url == null || id == null) {
            dialogo("Escanea antes el código QR del panel (5 · App del móvil)")
            return
        }
        avisoTxt.text = "Bajando el plan…"
        thread {
            val msg = try {
                val (codigo, txt) = Seguimiento.post("$url/api/plan", JSONObject().put("device_id", id).toString())
                when (codigo) {
                    200 -> {
                        val plan = Plan(txt)                      // si no se entiende, no se guarda
                        Seguimiento.escribirSeguro(File(filesDir, "plan.json"), txt)
                        if (!Seguimiento.corriendo) prefs.edit().putFloat("km", 0f).putInt("aviso", 0).apply()
                        "Plan listo: ${plan.nombre}\n${plan.avisos.size} avisos guardados. Ya puedes ir sin cobertura."
                    }
                    403 -> "El servidor no reconoce el identificador: vuelve a escanear el código del panel."
                    429 -> "Demasiados intentos fallidos: espera 15 minutos."
                    else -> "El servidor contestó $codigo"
                }
            } catch (e: Exception) { "Sin conexión con el servidor. Prueba otra vez con cobertura." }
            runOnUiThread { if (!isFinishing && !isDestroyed) { pintar(); dialogo(msg) } }
        }
    }

    private fun probarAviso() {
        Seguimiento.avisar(this, "Prueba de Sígueme CC · si lo ves en la pulsera · los avisos funcionan")
        prefs.edit().putLong("prueba_t", System.currentTimeMillis()).apply()
        pintar()
        dialogo("Aviso enviado: tiene que vibrar el móvil y salir en la pulsera.\n\nSi no sale en la pulsera: en Mi Fitness → " +
            "notificaciones de apps, activa Sígueme CC, y prueba con una actividad en marcha en la pulsera.")
    }

    private fun carrera() {
        val servicio = Intent(this, Seguimiento::class.java)
        if (Seguimiento.corriendo) {
            AlertDialog.Builder(this).setMessage("¿Parar el seguimiento?\n\nLa web deja de recibir tu posición.")
                .setPositiveButton("Parar") { _, _ ->
                    stopService(servicio)
                    prefs.edit().remove("km_t").apply()      // la próxima vez, carrera nueva desde el km 0
                    reloj.postDelayed({ pintar() }, 300)
                }
                .setNegativeButton("Seguir", null).show()
            return
        }
        if (!tiene(Manifest.permission.ACCESS_FINE_LOCATION)) {
            pedirPermisos()
            dialogo("Hace falta la ubicación precisa")
            return
        }
        // sin notificaciones no llega nada a la pulsera: mejor saberlo en casa
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        val avisosOn = nm.areNotificationsEnabled() &&
            (nm.getNotificationChannel(Seguimiento.CANAL_AVISOS)?.importance ?: 0) >= NotificationManager.IMPORTANCE_DEFAULT
        if (!avisosOn && !sinAvisosOk) {
            AlertDialog.Builder(this).setMessage("Las notificaciones de avisos están apagadas: no llegará ningún aviso a la pulsera.")
                .setPositiveButton("Arreglar") { _, _ -> ajustesAvisos() }
                .setNegativeButton("Empezar igual") { _, _ -> sinAvisosOk = true; carrera() }.show()
            return
        }
        if (Seguimiento.cargarPlan(this) == null) {
            AlertDialog.Builder(this).setMessage("No hay plan de avisos: solo se mandará la posición. ¿Empezar igual?")
                .setPositiveButton("Empezar") { _, _ -> arrancar(servicio) }.setNegativeButton("No", null).show()
            return
        }
        arrancar(servicio)
    }

    private fun arrancar(servicio: Intent) {
        // ⚠️ Si se vuelve a pulsar EMPEZAR a mitad de carrera (se paró sin querer o
        // Android cerró la app) se sigue donde iba: con el km a 0, desde el km 40
        // la app no encontraba la ruta y no daba más avisos. Carrera nueva si hace
        // más de 6 h del último km.
        val retomar = System.currentTimeMillis() - prefs.getLong("km_t", 0) < 6 * 3600_000L
        val e = prefs.edit().putBoolean("empezar_pendiente", true).remove("web_estado")
        if (!retomar) e.putFloat("km", 0f).putInt("aviso", 0).remove("ultimo_aviso").remove("estado_km").remove("meta_t")
        e.apply()
        startForegroundService(servicio)
        reloj.postDelayed({ pintar() }, 500)
        // la carrera también en la web, sin abrir el panel (y el plan al día)
        thread {
            val msg = Seguimiento.empezarEnLaWeb(this)
            runOnUiThread {
                pintar()
                dialogo((msg ?: "Sin cobertura ahora mismo: la web se pondrá en marcha sola en cuanto la haya.") +
                    "\n\nYa puedes guardar el móvil: la app sigue sola con la pantalla apagada.")
            }
        }
    }

    private fun sinAhorro() {
        val pm = getSystemService(POWER_SERVICE) as PowerManager
        if (pm.isIgnoringBatteryOptimizations(packageName)) { dialogo("Ya está sin ahorro de batería ✓"); return }
        startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$packageName")))
    }

    private fun ajustesApp() {
        startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$packageName")))
    }

    private fun ajustesAvisos() {
        startActivity(Intent(Settings.ACTION_CHANNEL_NOTIFICATION_SETTINGS)
            .putExtra(Settings.EXTRA_APP_PACKAGE, packageName).putExtra(Settings.EXTRA_CHANNEL_ID, Seguimiento.CANAL_AVISOS))
    }

    private fun aMano() {
        val caja = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(24.px(), 8.px(), 24.px(), 0) }
        val url = EditText(this).apply { hint = "https://tu-dominio"; inputType = InputType.TYPE_TEXT_VARIATION_URI; setText(prefs.getString("url", "")) }
        val id = EditText(this).apply { hint = "Identificador (lo enseña el panel)"; setText(prefs.getString("id", "")) }
        caja.addView(url); caja.addView(id)
        AlertDialog.Builder(this).setTitle("Configurar a mano").setView(caja)
            .setPositiveButton("Guardar") { _, _ -> configurar(url.text.toString().trim().trimEnd('/'), id.text.toString().trim()) }
            .setNegativeButton("Cancelar", null).show()
    }

    private fun pedirPermisos() {
        val faltan = mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
        if (Build.VERSION.SDK_INT >= 33) faltan += Manifest.permission.POST_NOTIFICATIONS
        faltan.removeAll { tiene(it) }
        if (faltan.isNotEmpty()) requestPermissions(faltan.toTypedArray(), 1)
    }

    private fun dialogo(t: String) {
        // la respuesta del servidor puede llegar con la pantalla ya cerrada: sin esto, la app se caía
        if (isFinishing || isDestroyed) return
        AlertDialog.Builder(this).setMessage(t).setPositiveButton("Vale", null).show()
    }
}
