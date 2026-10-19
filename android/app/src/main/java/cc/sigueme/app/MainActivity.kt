package cc.sigueme.app

import android.Manifest
import android.animation.LayoutTransition
import android.app.Activity
import android.app.Dialog
import android.app.NotificationManager
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.ColorDrawable
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
import android.view.MotionEvent
import android.view.View
import android.view.Window
import android.view.animation.DecelerateInterpolator
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.TextView
import org.json.JSONObject
import java.io.File
import java.util.Locale
import kotlin.concurrent.thread

/** Una sola pantalla, sin librerías: arriba, el SIGUIENTE PASO (la app te lleva de la
 *  mano hasta «Todo listo»); debajo, el estado de la carrera, el botón de empezar/parar
 *  y las comprobaciones. Los mensajes llevan el mismo diseño que la pantalla. */
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
    private val guiaC = Color.rgb(27, 43, 31)
    private val rojoFondoC = Color.rgb(58, 30, 27)
    private val botonC = Color.rgb(34, 42, 38)
    private val campoC = Color.rgb(17, 22, 20)

    private class Boton(val texto: String, val accion: () -> Unit)
    private class Paso(val ok: Boolean, val fila: String, val titulo: String, val texto: String, val boton: String, val accion: () -> Unit)

    private val prefs by lazy { Seguimiento.prefs(this) }
    private var sinAvisosOk = false
    private var planCache: Pair<Long, Plan?> = -1L to null
    private fun plan(): Plan? {
        val t = File(filesDir, "plan.json").lastModified()
        if (t != planCache.first) planCache = t to Seguimiento.cargarPlan(this)
        return planCache.second
    }

    /** Apps que pasan las notificaciones a la pulsera: paquete y nombre. */
    private val pulseras = listOf(
        "com.huami.watch.hmwatchmanager" to "Zepp",
        "com.xiaomi.wearable" to "Mi Fitness",
        "com.mi.health" to "Mi Fitness",
        "com.xiaomi.hm.health" to "Zepp Life",
        "com.huawei.health" to "Huawei Health",
        "nodomain.freeyourgadget.gadgetbridge" to "Gadgetbridge")
    private fun instalada(p: String) = try { packageManager.getPackageInfo(p, 0); true } catch (e: PackageManager.NameNotFoundException) { false }
    /** ¿Tiene esa app «Acceso a notificaciones»? null si Android no deja saberlo. */
    private fun leeNotificaciones(p: String): Boolean? =
        Settings.Secure.getString(contentResolver, "enabled_notification_listeners")?.contains("$p/")
    /** La app de la pulsera instalada; si hay varias, la que ya lee las notificaciones. */
    private fun pulsera() = pulseras.filter { instalada(it.first) }.let { l -> l.firstOrNull { leeNotificaciones(it.first) == true } ?: l.firstOrNull() }

    private val reloj = Handler(Looper.getMainLooper())
    private val repintar = object : Runnable {
        override fun run() {
            pintar()
            // «¿te llegó el aviso a la pulsera?»: cuando el aviso ya ha salido y no hay otro mensaje abierto
            if (prefs.getBoolean("prueba_preguntar", false) && dialogoAbierto == null &&
                System.currentTimeMillis() - prefs.getLong("prueba_t", 0) > 9000) preguntarPrueba()
            reloj.postDelayed(this, 2000)
        }
    }

    private lateinit var carreraTxt: TextView
    private lateinit var guiaCard: LinearLayout
    private lateinit var guiaPaso: TextView
    private lateinit var guiaTitulo: TextView
    private lateinit var guiaTexto: TextView
    private lateinit var guiaBoton: TextView
    private lateinit var pastilla: TextView
    private lateinit var kmTxt: TextView
    private lateinit var deTxt: TextView
    private lateinit var barra: ProgressBar
    private lateinit var avisoTxt: TextView
    private lateinit var redTxt: TextView
    private lateinit var botonGrande: TextView
    private lateinit var lista: LinearLayout
    private var firmaLista = ""
    private var dialogoAbierto: Dialog? = null

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

        // el siguiente paso: la app te lleva de la mano
        guiaCard = tarjeta().apply { background = fondo(guiaC, 18) }
        guiaPaso = texto(14f, verdeC).apply { typeface = Typeface.DEFAULT_BOLD }
        guiaTitulo = texto(21f, textoC).apply { typeface = Typeface.DEFAULT_BOLD; setPadding(0, 4.px(), 0, 6.px()) }
        guiaTexto = texto(16f, Color.rgb(205, 212, 207)).apply { setLineSpacing(0f, 1.15f) }
        guiaBoton = boton("", true, 56) {}
        guiaCard.addView(guiaPaso); guiaCard.addView(guiaTitulo); guiaCard.addView(guiaTexto)
        guiaCard.addView(guiaBoton, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 16.px() })
        caja.addView(guiaCard)

        // tarjeta de estado
        val estado = tarjeta()
        pastilla = TextView(this).apply {
            textSize = 14f; typeface = Typeface.DEFAULT_BOLD
            setPadding(10.px(), 4.px(), 10.px(), 4.px())
        }
        estado.addView(pastilla, LinearLayout.LayoutParams(-2, -2))
        kmTxt = texto(76f, textoC).apply { typeface = Typeface.DEFAULT_BOLD; letterSpacing = -0.03f; includeFontPadding = false; setPadding(0, 14.px(), 0, 2.px()) }
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
        redTxt = texto(14f, apagadoC)
        estado.addView(redTxt, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 6.px() })
        caja.addView(estado)

        // botón grande
        botonGrande = boton("", false, 64) { carrera() }
        botonGrande.textSize = 20f
        caja.addView(botonGrande, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 14.px() })

        // acciones secundarias
        val fila = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        fila.addView(boton("Probar aviso", false, 52) { probarAviso() }, LinearLayout.LayoutParams(0, -2, 1f).apply { rightMargin = 6.px() })
        fila.addView(boton("Actualizar plan", false, 52) { bajarPlan() }, LinearLayout.LayoutParams(0, -2, 1f).apply { leftMargin = 6.px() })
        caja.addView(fila, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 12.px() })

        // todas las comprobaciones
        val prep = tarjeta()
        prep.addView(texto(20f, textoC).apply { text = "Comprobaciones"; typeface = Typeface.DEFAULT_BOLD; setPadding(0, 0, 0, 4.px()) })
        lista = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        prep.addView(lista)
        caja.addView(prep)

        // cómo funciona, en tres líneas
        val como = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(4.px(), 20.px(), 4.px(), 0) }
        como.addView(texto(16f, textoC).apply { text = "Cómo funciona"; typeface = Typeface.DEFAULT_BOLD; setPadding(0, 0, 0, 6.px()) })
        como.addView(texto(15f, apagadoC).apply {
            setLineSpacing(0f, 1.2f)
            text = "Con la pantalla apagada y sin cobertura, la app:\n" +
                "•  sigue tu km con el GPS del móvil,\n" +
                "•  lanza cada aviso como una notificación (Mi Fitness, Zepp o Huawei Health la repiten en la pulsera),\n" +
                "•  guarda tu posición y la manda a la web cuando vuelve la cobertura."
        })
        como.addView(texto(15f, apagadoC).apply {
            setLineSpacing(0f, 1.2f); setPadding(0, 12.px(), 0, 0)
            text = "En Samsung: Ajustes → Batería → Límites de uso en segundo plano → «Apps que nunca se suspenden» → añade Sígueme CC."
        })
        caja.addView(como)
        caja.addView(texto(15f, verdeC).apply {
            text = "Configurar a mano"; typeface = Typeface.DEFAULT_BOLD
            setPadding(4.px(), 18.px(), 4.px(), 8.px()); setOnClickListener { aMano() }
            pulsable(this)
        })
        setContentView(ScrollView(this).apply { setBackgroundColor(fondoC); addView(caja) })
        pedirPermisos()
        leerEnlace(intent)

        // la pantalla entra por partes (cabecera, guía, estado...) y los cambios se animan solos
        for (i in 0 until caja.childCount) {
            val v = caja.getChildAt(i)
            v.alpha = 0f; v.translationY = 16.px().toFloat()
            v.animate().alpha(1f).translationY(0f).setStartDelay(60L * i).setDuration(320).setInterpolator(DecelerateInterpolator()).start()
        }
        caja.layoutTransition = LayoutTransition().apply { enableTransitionType(LayoutTransition.CHANGING) }
    }

    override fun onNewIntent(i: Intent) { super.onNewIntent(i); leerEnlace(i) }
    override fun onResume() {
        super.onResume(); reloj.post(repintar)
        // el plan al día cada vez que se abre con cobertura: así en la salida,
        // sin cobertura, va el último (sin diálogos si no hay red)
        val f = File(filesDir, "plan.json")
        if (!Seguimiento.corriendo && prefs.getString("url", null) != null &&
            System.currentTimeMillis() - f.lastModified() > 30 * 60_000L) bajarPlan(callado = true)
    }
    override fun onPause() { reloj.removeCallbacks(repintar); super.onPause() }
    override fun onDestroy() { dialogoAbierto?.dismiss(); super.onDestroy() }

    private fun hace(t: Long): String {
        val min = (System.currentTimeMillis() - t) / 60_000
        return when {
            min < 2 -> "ahora"
            min < 60 -> "hace $min min"
            min < 48 * 60 -> "hace ${min / 60} h"
            else -> "hace ${min / 1440} días"
        }
    }

    // ---------- piezas ----------
    private fun fondo(color: Int, radio: Int, borde: Int? = null) = GradientDrawable().apply {
        setColor(color); cornerRadius = radio.px().toFloat(); if (borde != null) setStroke(1.px(), borde)
    }
    private fun texto(tam: Float, color: Int) = TextView(this).apply { textSize = tam; setTextColor(color) }
    private fun fijar(v: TextView, t: String) { if (v.text.toString() != t) v.text = t }
    private fun tarjeta() = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL; background = fondo(tarjetaC, 18)
        setPadding(18.px(), 16.px(), 18.px(), 18.px())
        layoutParams = LinearLayout.LayoutParams(-1, -2).apply { topMargin = 16.px() }
    }

    /** Se encoge un poco al pulsarlo: se nota que ha respondido. */
    private fun pulsable(v: View) {
        v.setOnTouchListener { vista, e ->
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> vista.animate().scaleX(0.97f).scaleY(0.97f).setDuration(80).start()
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> vista.animate().scaleX(1f).scaleY(1f).setDuration(120).start()
            }
            false
        }
    }
    private fun boton(txt: String, principal: Boolean, alto: Int, accion: () -> Unit) = TextView(this).apply {
        text = txt; gravity = Gravity.CENTER; textSize = if (alto >= 56) 17f else 15f; typeface = Typeface.DEFAULT_BOLD; isClickable = true
        setTextColor(if (principal) fondoC else textoC)
        background = fondo(if (principal) verdeC else tarjetaC, 16)
        minimumHeight = alto.px(); setPadding(14.px(), 12.px(), 14.px(), 12.px())
        setOnClickListener { accion() }
        pulsable(this)
    }

    private fun filaLista(ok: Boolean, txt: String, arreglo: () -> Unit) = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(0, 10.px(), 0, 10.px())
        addView(TextView(this@MainActivity).apply {
            text = if (ok) "✓" else "!"; gravity = Gravity.CENTER; textSize = 14f; typeface = Typeface.DEFAULT_BOLD
            setTextColor(fondoC); background = fondo(if (ok) verdeC else ambarC, 11)
        }, LinearLayout.LayoutParams(24.px(), 24.px()).apply { rightMargin = 12.px() })
        addView(texto(15f, if (ok) textoC else ambarC).apply { text = txt }, LinearLayout.LayoutParams(0, -2, 1f))
        if (!ok) addView(texto(14f, verdeC).apply { text = "Ir ›"; typeface = Typeface.DEFAULT_BOLD })
        isClickable = true; setOnClickListener { arreglo() }
        pulsable(this)
    }

    // ---------- mensajes con el diseño de la app ----------
    private fun mostrar(titulo: String?, texto: String, vararg botones: Boton) = mostrarVista(titulo, texto, null, *botones)

    private fun mostrarVista(titulo: String?, texto: String, vista: View?, vararg botones: Boton): Dialog? {
        // la respuesta del servidor puede llegar con la pantalla ya cerrada: sin esto, la app se caía
        if (isFinishing || isDestroyed) return null
        dialogoAbierto?.dismiss()                       // uno solo a la vez
        val d = Dialog(this)
        d.requestWindowFeature(Window.FEATURE_NO_TITLE)
        val caja = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; background = fondo(tarjetaC, 24); setPadding(22.px(), 22.px(), 22.px(), 18.px())
        }
        if (!titulo.isNullOrEmpty()) caja.addView(texto(21f, textoC).apply { text = titulo; typeface = Typeface.DEFAULT_BOLD; setPadding(0, 0, 0, 10.px()) })
        caja.addView(texto(16f, Color.rgb(205, 212, 207)).apply { text = texto; setLineSpacing(0f, 1.18f) })
        if (vista != null) caja.addView(vista, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 14.px() })
        botones.forEachIndexed { i, b ->
            val v = TextView(this).apply {
                text = b.texto; gravity = Gravity.CENTER; textSize = 16f; typeface = Typeface.DEFAULT_BOLD; isClickable = true
                setTextColor(if (i == 0) fondoC else textoC)
                background = fondo(if (i == 0) verdeC else botonC, 16)
                minimumHeight = 52.px(); setPadding(14.px(), 12.px(), 14.px(), 12.px())
                setOnClickListener { d.dismiss(); b.accion() }
            }
            pulsable(v)
            caja.addView(v, LinearLayout.LayoutParams(-1, -2).apply { topMargin = if (i == 0) 20.px() else 8.px() })
        }
        d.setContentView(FrameLayout(this).apply { setPadding(20.px(), 0, 20.px(), 0); addView(caja, FrameLayout.LayoutParams(-1, -2)) })
        d.window?.setBackgroundDrawable(ColorDrawable(Color.TRANSPARENT))
        d.window?.setLayout(-1, -2)
        d.window?.setWindowAnimations(android.R.style.Animation_Dialog)
        d.setOnDismissListener { if (dialogoAbierto === d) dialogoAbierto = null }
        dialogoAbierto = d
        d.show()
        return d
    }

    private fun dialogo(titulo: String?, t: String) { mostrar(titulo, t, Boton("Vale") {}) }

    // ---------- los pasos hasta «Todo listo» ----------
    private fun avisosActivados(): Boolean {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        return nm.areNotificationsEnabled() &&
            (nm.getNotificationChannel(Seguimiento.CANAL_AVISOS)?.importance ?: 0) >= NotificationManager.IMPORTANCE_DEFAULT
    }

    private fun pasos(plan: Plan?, url: String?): List<Paso> {
        val pm = getSystemService(POWER_SERVICE) as PowerManager
        val pb = pulsera()
        val lee = pb?.let { leeNotificaciones(it.first) }
        val subidas = plan?.subidas?.size ?: 0
        val conAvisos = plan != null && plan.avisos.isNotEmpty()
        val avisosOn = avisosActivados()
        val pruebaOk = prefs.getBoolean("prueba_ok", false)
        return listOf(
            Paso(url != null,
                if (url != null) "Servidor: ${Uri.parse(url).host}" else "Sin conectar con el servidor",
                "Conecta la app con tu servidor",
                "En el panel (pestaña Móvil) escanea el código con la cámara del móvil y pulsa «Abrir en la app». También puedes escribir la dirección a mano.",
                "Escribir la dirección a mano") { aMano() },
            Paso(conAvisos,
                when {
                    conAvisos -> "Plan: ${plan!!.avisos.size} avisos, $subidas " + (if (subidas == 1) "subida" else "subidas") +
                        " · guardado " + hace(File(filesDir, "plan.json").lastModified())
                    plan != null -> "Plan sin avisos: falta la ruta en el panel"
                    else -> "Falta bajar el plan"
                },
                "Baja el plan de la carrera",
                if (plan != null) "El plan no tiene avisos: sube la ruta en el panel (pestaña Preparar) y vuelve a bajarlo."
                else "Trae la ruta y los avisos al móvil, para que funcionen sin cobertura.",
                "Bajar el plan") { bajarPlan() },
            Paso(tiene(Manifest.permission.ACCESS_FINE_LOCATION), "Ubicación precisa",
                "Permite la ubicación precisa",
                "La app necesita el GPS para saber en qué km vas y lanzar cada aviso a tiempo.",
                "Permitir la ubicación") {
                if (shouldShowRequestPermissionRationale(Manifest.permission.ACCESS_FINE_LOCATION)) pedirPermisos() else ajustesApp()
            },
            Paso(avisosOn, if (avisosOn) "Notificaciones de avisos" else "Notificaciones apagadas",
                "Activa las notificaciones",
                "Los avisos son notificaciones del móvil: sin ellas no llega nada a la pulsera.",
                "Activar las notificaciones") { ajustesAvisos() },
            Paso(pm.isIgnoringBatteryOptimizations(packageName), "Sin ahorro de batería",
                "Quita el ahorro de batería a la app",
                "Con la pantalla apagada, Android duerme las apps para ahorrar. Si duerme esta, se pierden km y avisos.",
                "Quitar el ahorro") { sinAhorro() },
            Paso(pb != null && lee != false,
                when {
                    pb == null -> "Falta la app de la pulsera (Mi Fitness, Zepp o Huawei Health)"
                    lee == false -> "${pb.second} no puede leer las notificaciones"
                    else -> "App de la pulsera: ${pb.second}"
                },
                if (pb == null) "Instala la app de tu pulsera" else "Deja que ${pb.second} lea las notificaciones",
                if (pb == null) "Los avisos llegan a la pulsera a través de su app: Mi Fitness (Xiaomi), Zepp (Amazfit) o Huawei Health (Huawei)."
                else "Android solo deja que ${pb.second} pase las notificaciones a la pulsera si se lo permites tú.",
                if (pb == null) "Cómo instalarla" else "Dar el permiso") {
                if (pb == null) guiaPulsera(null) else accesoNotificaciones(pb)
            },
            Paso(pruebaOk,
                if (pruebaOk) "Aviso de prueba recibido en la pulsera" else "Aviso de prueba pendiente",
                "Prueba el aviso en la pulsera",
                "Pulsa el botón, bloquea el móvil y mira la pulsera." +
                    (if (pb != null) " Si no llega, falta activar Sígueme CC dentro de ${pb.second}: viene desactivada." else ""),
                "Probar el aviso") { probarAviso() })
    }

    // ---------- estado ----------
    private fun pintar() {
        val plan = plan()
        val url = prefs.getString("url", null)
        val activo = Seguimiento.corriendo
        val pasos = pasos(plan, url)
        val siguiente = pasos.firstOrNull { !it.ok }
        fijar(carreraTxt, plan?.nombre ?: "Sin carrera: conecta la app con el panel")

        // la guía: el siguiente paso, o «Todo listo»; no se enseña mientras se sigue la carrera
        guiaCard.visibility = if (activo) View.GONE else View.VISIBLE
        if (siguiente != null) {
            fijar(guiaPaso, "Paso ${pasos.indexOf(siguiente) + 1} de ${pasos.size}")
            fijar(guiaTitulo, siguiente.titulo); fijar(guiaTexto, siguiente.texto); fijar(guiaBoton, siguiente.boton)
            guiaBoton.visibility = View.VISIBLE
            guiaBoton.setOnClickListener { siguiente.accion() }
        } else {
            fijar(guiaPaso, "Todo listo")
            fijar(guiaTitulo, "Ya puedes salir")
            fijar(guiaTexto, "Cuando vayas a salir, pulsa «Empezar seguimiento». Puedes hacerlo hasta una hora antes: hasta la hora oficial la web dice «En la salida».")
            guiaBoton.visibility = View.GONE
        }

        fijar(pastilla, if (activo) "Siguiendo" else "Parado")
        pastilla.setTextColor(if (activo) fondoC else apagadoC)
        pastilla.background = fondo(if (activo) verdeC else bordeC, 20)

        val km = if (activo) prefs.getFloat("km", 0f).toDouble() else 0.0
        fijar(kmTxt, String.format(Locale("es", "ES"), "%.1f", km))
        fijar(deTxt, when {
            plan == null -> "km"
            // el estado solo si dice algo que no sea el km (fuera de la ruta, sin GPS)
            activo -> String.format(Locale("es", "ES"), "de %.1f km", plan.distancia) + (prefs.getString("estado_km", null)
                ?.takeUnless { it.startsWith("Km ") }?.let { " · $it" } ?: if (prefs.contains("estado_km")) "" else " · buscando GPS…")
            else -> String.format(Locale("es", "ES"), "de %.1f km", plan.distancia)
        })
        barra.setProgress(if (plan != null && plan.distancia > 0) (km / plan.distancia * 1000).toInt() else 0, true)

        val ultimo = prefs.getString("ultimo_aviso", null)
        fijar(avisoTxt, when {
            activo && ultimo != null -> Plan.notificacion(ultimo).let { (t, c) -> "Último aviso: $t" + (if (c.isEmpty()) "" else " · " + c.replace('\n', ' ')) }
            activo -> "Esperando el primer aviso…"
            plan != null -> "${plan.avisos.size} avisos guardados en el móvil"
            else -> "Sin avisos"
        })
        val cola = Seguimiento.pendientes(this)
        val enviado = prefs.getLong("enviado_t", 0)
        fijar(redTxt, listOfNotNull(
            when {
                cola > 0 && url == null -> "$cola posiciones guardadas (falta configurar el servidor)"
                cola > 0 -> "$cola posiciones esperando cobertura"
                activo -> "Posición al día en la web"
                else -> null
            },
            if (enviado > 0) "última enviada hace ${(System.currentTimeMillis() - enviado) / 60000} min" else null
        ).joinToString(" · ") + when {
            !activo -> ""
            prefs.getBoolean("empezar_pendiente", false) -> "\nWeb: se pondrá en marcha en cuanto haya cobertura"
            else -> prefs.getString("web_estado", null)?.takeIf { it.isNotBlank() }?.let { "\nWeb: $it" } ?: ""
        })

        // verde solo cuando todo está listo (o ya se sigue): mientras faltan pasos, el verde es el de la guía
        val listo = siguiente == null
        fijar(botonGrande, if (activo) "Parar seguimiento" else "Empezar seguimiento")
        botonGrande.setTextColor(if (activo) rojoC else if (listo) fondoC else textoC)
        // parar, relleno en rojo apagado; empezar, el verde de la web
        botonGrande.background = if (activo) fondo(rojoFondoC, 18) else fondo(if (listo) verdeC else tarjetaC, 18)

        // las comprobaciones solo se reconstruyen si cambian (y así no parpadean cada 2 s)
        val firma = pasos.joinToString("|") { "${it.ok}:${it.fila}" }
        if (firma != firmaLista) {
            firmaLista = firma
            lista.removeAllViews()
            pasos.forEach { lista.addView(filaLista(it.ok, it.fila, it.accion)) }
        }
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
            dialogo("Configuración no válida", "La dirección tiene que empezar por https:// y el identificador tiene que ser el que enseña el panel.")
            return
        }
        mostrar("¿Usar este servidor?", "Tu posición se mandará a:\n\n$host",
            Boton("Sí, usarlo") {
                prefs.edit().putString("url", u).putString("id", id).remove("bloqueado_hasta").apply()
                bajarPlan()
            }, Boton("No") {})
    }

    private var bajando = false
    private var verResultado = false      // alguien pulsó: enseñar el resultado aunque ya fuera bajando callado
    private fun bajarPlan(callado: Boolean = false) {
        val url = prefs.getString("url", null)
        val id = prefs.getString("id", null)
        if (url == null || id == null) {
            if (!callado) dialogo("Falta conectar la app", "Escanea antes el código QR del panel (pestaña Móvil) o escribe la dirección a mano.")
            return
        }
        if (!callado) { verResultado = true; fijar(avisoTxt, "Bajando el plan…") }
        if (bajando) return
        bajando = true
        thread {
            val (titulo, msg) = try {
                val (codigo, txt) = Seguimiento.post("$url/api/plan", JSONObject().put("device_id", id).toString())
                when (codigo) {
                    200 -> {
                        val plan = Plan(txt)                      // si no se entiende, no se guarda
                        Seguimiento.escribirSeguro(File(filesDir, "plan.json"), txt)
                        // a mitad de carrera (Android cerró la app y se vuelve a abrir) NO se
                        // pone el km a 0: sin ruta desde ahí no habría más avisos
                        if (!Seguimiento.corriendo && System.currentTimeMillis() - prefs.getLong("km_t", 0) > 6 * 3600_000L)
                            prefs.edit().putFloat("km", 0f).putInt("aviso", 0).apply()
                        "Plan listo" to "${plan.nombre}: ${plan.avisos.size} avisos guardados en el móvil. Ya puedes ir sin cobertura."
                    }
                    403 -> "La app no está conectada" to "El servidor no reconoce el identificador: vuelve a escanear el código del panel."
                    429 -> "Demasiados intentos" to "Espera 15 minutos antes de volver a probar."
                    else -> "No se pudo bajar el plan" to "El servidor contestó $codigo."
                }
            } catch (e: Exception) { "Sin conexión" to "No hay conexión con el servidor. Prueba otra vez cuando tengas cobertura." }
            runOnUiThread {
                bajando = false
                val ver = verResultado; verResultado = false
                if (!isFinishing && !isDestroyed) { pintar(); if (ver) dialogo(titulo, msg) }
            }
        }
    }

    private fun probarAviso() {
        // 5 s para apagar la pantalla: Zepp y Mi Fitness suelen pasar los avisos
        // solo con el móvil bloqueado, como irá en carrera. Es un aviso de verdad
        // (el mismo diseño que los de la carrera) para ver cómo se ve en la pulsera.
        reloj.postDelayed({
            Seguimiento.notificar(this, "Prueba: subida larga en 300 m", "2,3 km · 9 % · +210 m\nSi lo ves en la pulsera, los avisos funcionan.")
        }, 5000)
        prefs.edit().putLong("prueba_t", System.currentTimeMillis()).putBoolean("prueba_preguntar", true).apply()
        pintar()
        val botones = mutableListOf(Boton("Vale") {})
        pulsera()?.let { p -> packageManager.getLaunchIntentForPackage(p.first)?.let { li -> botones.add(Boton("Abrir ${p.second}") { abrir(li) }) } }
        mostrar("Aviso de prueba en 5 segundos", "Bloquea el móvil y mira la pulsera. Cuando vuelvas aquí te preguntaré si llegó.", *botones.toTypedArray())
    }

    private fun preguntarPrueba() {
        // la marca se quita al CONTESTAR: si otro mensaje tapa la pregunta, vuelve a salir
        val pb = pulsera()
        val listo = { prefs.edit().putBoolean("prueba_preguntar", false).apply() }
        mostrar("¿Te llegó el aviso a la pulsera?", "Era una prueba: «Subida larga en 300 m».",
            Boton("Sí, llegó") { listo(); prefs.edit().putBoolean("prueba_ok", true).apply(); pintar() },
            Boton("No llegó") { listo(); guiaPulsera(pb) },
            Boton("Más tarde") { listo() })?.setCancelable(false)
    }

    /** Lo que casi siempre falla: en Mi Fitness (y en Zepp) cada app viene DESACTIVADA por defecto. */
    private fun guiaPulsera(pb: Pair<String, String>?) {
        if (pb == null) {
            mostrar("Falta la app de la pulsera",
                "Los avisos llegan a la pulsera a través de su app:\n\n•  Xiaomi Smart Band → Mi Fitness\n•  Amazfit → Zepp\n•  Huawei → Huawei Health\n\nInstálala y enlaza la pulsera.",
                Boton("Instalar Mi Fitness") { tienda("com.xiaomi.wearable") },
                Boton("Instalar Zepp") { tienda("com.huami.watch.hmwatchmanager") },
                Boton("Instalar Huawei Health") { tienda("com.huawei.health") },
                Boton("Cerrar") {})
            return
        }
        val botones = mutableListOf(Boton("Probar el aviso otra vez") { probarAviso() })
        packageManager.getLaunchIntentForPackage(pb.first)?.let { li -> botones.add(0, Boton("Abrir ${pb.second}") { abrir(li) }) }
        botones.add(Boton("Cerrar") {})
        mostrar("Activar Sígueme CC en ${pb.second}",
            "${pb.second} trae cada app DESACTIVADA por defecto. Para activarla:\n\n" +
                "1.  Abre ${pb.second} y entra en los ajustes de tu pulsera (Dispositivo).\n" +
                "2.  Busca «Notificaciones» o «Alertas de apps».\n" +
                "3.  Busca «Sígueme CC» en la lista y actívala.\n" +
                "4.  Vuelve aquí y prueba el aviso.\n\n" +
                "Si no sale en la lista, pulsa antes «Probar aviso» una vez: la lista solo enseña las apps que ya han mandado una notificación. " +
                "Los nombres de los menús cambian un poco según la versión.",
            *botones.toTypedArray())
    }

    private fun accesoNotificaciones(pb: Pair<String, String>) {
        mostrar("${pb.second} necesita acceso a las notificaciones",
            "Android deja que ${pb.second} lea las notificaciones del móvil solo si tú se lo permites. Activa ${pb.second} en la lista que se abre.",
            Boton("Abrir la lista") { abrir(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)) },
            Boton("Cerrar") {})
    }

    private fun tienda(p: String) {
        try { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=$p"))) }
        catch (e: Exception) { abrir(Intent(Intent.ACTION_VIEW, Uri.parse("https://play.google.com/store/apps/details?id=$p"))) }
    }

    private fun abrir(i: Intent) {
        try { startActivity(i) } catch (e: Exception) { dialogo("No se pudo abrir", "Ábrelo a mano desde el menú de apps del móvil.") }
    }

    private fun carrera() {
        val servicio = Intent(this, Seguimiento::class.java)
        if (Seguimiento.corriendo) {
            mostrar("¿Parar el seguimiento?", "La web deja de recibir tu posición y la app deja de lanzar avisos.",
                Boton("Parar") {
                    stopService(servicio)
                    prefs.edit().remove("km_t").apply()      // la próxima vez, carrera nueva desde el km 0
                    reloj.postDelayed({ pintar() }, 300)
                },
                Boton("Seguir") {})
            return
        }
        if (!tiene(Manifest.permission.ACCESS_FINE_LOCATION)) {
            pedirPermisos()
            dialogo("Falta la ubicación", "Permite la ubicación precisa para que la app sepa en qué km vas.")
            return
        }
        // sin notificaciones no llega nada a la pulsera: mejor saberlo en casa
        if (!avisosActivados() && !sinAvisosOk) {
            mostrar("Notificaciones apagadas", "Sin ellas no llegará ningún aviso a la pulsera.",
                Boton("Activarlas") { ajustesAvisos() },
                Boton("Empezar igual") { sinAvisosOk = true; carrera() })
            return
        }
        if (plan() == null) {
            mostrar("Sin plan de avisos", "Solo se mandará la posición, sin avisos de subidas ni avituallamientos. ¿Empezar igual?",
                Boton("Empezar igual") { arrancar(servicio) }, Boton("No") {})
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
                dialogo("Seguimiento en marcha", (msg ?: "Sin cobertura ahora mismo: la web se pondrá en marcha sola en cuanto la haya.") +
                    "\n\nYa puedes guardar el móvil: la app sigue sola con la pantalla apagada.")
            }
        }
    }

    private fun sinAhorro() {
        val pm = getSystemService(POWER_SERVICE) as PowerManager
        if (pm.isIgnoringBatteryOptimizations(packageName)) { dialogo("Ya está", "La app ya está sin ahorro de batería."); return }
        abrir(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$packageName")))
    }

    private fun ajustesApp() {
        abrir(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$packageName")))
    }

    private fun ajustesAvisos() {
        abrir(Intent(Settings.ACTION_CHANNEL_NOTIFICATION_SETTINGS)
            .putExtra(Settings.EXTRA_APP_PACKAGE, packageName).putExtra(Settings.EXTRA_CHANNEL_ID, Seguimiento.CANAL_AVISOS))
    }

    private fun aMano() {
        fun campo(pista: String, valor: String, tipo: Int) = EditText(this).apply {
            hint = pista; setText(valor); inputType = tipo; textSize = 16f; setSingleLine()
            setTextColor(textoC); setHintTextColor(apagadoC)
            background = fondo(campoC, 14); setPadding(16.px(), 14.px(), 16.px(), 14.px())
        }
        val url = campo("https://tu-dominio", prefs.getString("url", "") ?: "", InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI)
        val id = campo("Identificador", prefs.getString("id", "") ?: "", InputType.TYPE_CLASS_TEXT)
        val caja = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        caja.addView(url); caja.addView(id, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 10.px() })
        mostrarVista("Configurar a mano", "La dirección y el identificador salen en el panel, pestaña Móvil.", caja,
            Boton("Guardar") { configurar(url.text.toString().trim().trimEnd('/'), id.text.toString().trim()) },
            Boton("Cancelar") {})
    }

    private fun pedirPermisos() {
        val faltan = mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
        if (Build.VERSION.SDK_INT >= 33) faltan += Manifest.permission.POST_NOTIFICATIONS
        faltan.removeAll { tiene(it) }
        if (faltan.isNotEmpty()) requestPermissions(faltan.toTypedArray(), 1)
    }
}
