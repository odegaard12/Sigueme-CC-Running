package cc.sigueme.app

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.animation.DecelerateInterpolator
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java.util.Locale
import kotlin.concurrent.thread
import kotlin.math.cos

/** El recorrido de una ruta, dibujado en pequeño (sin mapa: sin librerías ni teselas). */
class TrazaView(c: Context, private val puntos: List<DoubleArray>, private val tintaTraza: Int) : View(c) {
    private val d = c.resources.displayMetrics.density
    private val pincel = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE; strokeWidth = 3f * d; strokeJoin = Paint.Join.ROUND; strokeCap = Paint.Cap.ROUND; color = tintaTraza
    }

    override fun onDraw(canvas: Canvas) {
        if (puntos.size < 2) return
        val k = cos(Math.toRadians(puntos[0][1]))
        val xs = puntos.map { it[0] * k }
        val ys = puntos.map { -it[1] }
        val x0 = xs.minOrNull() ?: 0.0
        val y0 = ys.minOrNull() ?: 0.0
        val ancho = (xs.maxOrNull() ?: 0.0) - x0
        val alto = (ys.maxOrNull() ?: 0.0) - y0
        val lado = maxOf(ancho, alto).takeIf { it > 0 } ?: 1.0
        val esc = (minOf(width, height) - 12f * d) / lado
        val ox = (width - ancho * esc) / 2
        val oy = (height - alto * esc) / 2
        val path = Path()
        for (i in puntos.indices) {
            val x = ((xs[i] - x0) * esc + ox).toFloat()
            val y = ((ys[i] - y0) * esc + oy).toFloat()
            if (i == 0) path.moveTo(x, y) else path.lineTo(x, y)
        }
        canvas.drawPath(path, pincel)
    }
}

/** El perfil de altura de una ruta, con los avituallamientos marcados. */
class PerfilView(c: Context, private val perfil: List<DoubleArray>, private val avits: List<Double>,
                 private val lima: Int, private val panel: Int, private val gris: Int, private val tinta: Int) : View(c) {
    private val d = c.resources.displayMetrics.density
    private val relleno = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.FILL; color = lima }
    private val fondo = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.FILL; color = panel }
    private val linea = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; strokeWidth = 2f * d; color = tinta }
    private val letra = Paint(Paint.ANTI_ALIAS_FLAG).apply { textSize = 11f * d; color = gris; typeface = Typeface.DEFAULT_BOLD }

    override fun onDraw(canvas: Canvas) {
        canvas.drawRoundRect(RectF(0f, 0f, width.toFloat(), height.toFloat()), 6f * d, 6f * d, fondo)
        if (perfil.size < 2) return
        val izq = 44f * d; val der = 12f * d; val arriba = 12f * d; val abajo = 24f * d
        val total = perfil.last()[0].takeIf { it > 0 } ?: 1.0
        val eMin = Math.floor((perfil.minOf { it[1] }) / 10) * 10
        val eMax = (Math.ceil((perfil.maxOf { it[1] }) / 10) * 10).let { if (it <= eMin) eMin + 10 else it }
        fun x(dist: Double) = (izq + (width - izq - der) * dist / total).toFloat()
        fun y(e: Double) = (height - abajo - (height - abajo - arriba) * (e - eMin) / (eMax - eMin)).toFloat()
        val path = Path()
        path.moveTo(x(0.0), height - abajo)
        for (p in perfil) path.lineTo(x(p[0]), y(p[1]))
        path.lineTo(x(total), height - abajo)
        path.close()
        canvas.drawPath(path, relleno)
        for (a in avits) {
            canvas.drawLine(x(a), arriba, x(a), height - abajo, linea)
            val txt = String.format(Locale("es", "ES"), "%.1f", a)
            canvas.drawText(txt, x(a) - letra.measureText(txt) / 2, height - 7f * d, letra)
        }
        canvas.drawText("${eMax.toInt()} m", 4f * d, arriba + 8f * d, letra)
        canvas.drawText("${eMin.toInt()} m", 4f * d, height - abajo - 2f * d, letra)
        val fin = String.format(Locale("es", "ES"), "%.1f km", total)
        canvas.drawText(fin, width - der - letra.measureText(fin), height - 7f * d, letra)
    }
}

/** La pestaña «Rutas» de la app: la portada con las rutas publicadas y la pantalla de cada una, en el
 *  mismo estilo cartel que la web (lima, negro y letra condensada). */
class RutasPantalla(private val act: Activity, private val prefs: SharedPreferences,
                    private val irACarrera: () -> Unit,
                    private val avisar: (String, String, List<Pair<String, () -> Unit>>) -> Unit) {
    private val lima = Color.rgb(217, 242, 74)
    private val tinta = Color.rgb(12, 15, 14)
    private val papel = Color.rgb(244, 247, 230)
    private val apagado = Color.rgb(181, 192, 106)
    private val panel = Color.rgb(21, 27, 23)
    private val anton: Typeface = try { Typeface.createFromAsset(act.assets, "fonts/Anton-Regular.ttf") } catch (e: Exception) { Typeface.DEFAULT_BOLD }
    private fun Int.px() = (this * act.resources.displayMetrics.density).toInt()
    private val es = Locale("es", "ES")

    val vista = FrameLayout(act)
    private val contLista = LinearLayout(act).apply { orientation = LinearLayout.VERTICAL }
    private val scrollLista = ScrollView(act).apply { setBackgroundColor(tinta); addView(contLista) }
    private val contDetalle = LinearLayout(act).apply { orientation = LinearLayout.VERTICAL }
    private val scrollDetalle = ScrollView(act).apply { setBackgroundColor(tinta); addView(contDetalle); visibility = View.GONE }
    private var cargando = false
    private var abierta: String? = null     // la ruta que se está viendo
    private var bajando = false             // una descarga del GPX a la vez (el doble toque bajaba dos copias)

    init { vista.addView(scrollLista); vista.addView(scrollDetalle) }

    private fun url() = prefs.getString("url", null)
    private fun km(v: Double) = String.format(es, "%.1f", v)

    /** El nombre del sitio, del dominio del servidor (odegaard12.online → ODEGAARD12); sin dominio, «PARA EL RELOJ». */
    private fun sitio(): String {
        val h = try { Uri.parse(url() ?: "").host ?: "" } catch (e: Exception) { "" }
        val n = h.removePrefix("www.").substringBefore('.')
        return if (n.isEmpty() || n.all { it.isDigit() }) "PARA EL RELOJ" else n.uppercase()
    }

    private fun t(txt: String, size: Float, color: Int, fuente: Typeface? = null) = TextView(act).apply {
        text = txt; textSize = size; setTextColor(color); typeface = fuente ?: Typeface.DEFAULT_BOLD
    }

    /** Se aclara un poco al pulsarlo: se nota que ha respondido. */
    private fun pulsable(v: View) {
        v.isClickable = true
        v.setOnTouchListener { vista, e ->
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> vista.animate().alpha(0.7f).setDuration(80).start()
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> vista.animate().alpha(1f).setDuration(120).start()
            }
            false
        }
    }

    private fun botonCartel(txt: String, relleno: Boolean, accion: () -> Unit) = TextView(act).apply {
        text = txt.uppercase(); textSize = 20f; typeface = anton; gravity = Gravity.CENTER
        setTextColor(if (relleno) lima else tinta); minimumHeight = 56.px(); setPadding(16.px(), 12.px(), 16.px(), 12.px())
        background = GradientDrawable().apply {
            cornerRadius = 6.px().toFloat()
            if (relleno) setColor(tinta) else { setColor(Color.TRANSPARENT); setStroke(3.px(), tinta) }
        }
        setOnClickListener { accion() }
        pulsable(this)
    }

    private fun botonClaro(txt: String, accion: () -> Unit) = TextView(act).apply {
        text = txt.uppercase(); textSize = 20f; typeface = anton; gravity = Gravity.CENTER
        setTextColor(tinta); minimumHeight = 56.px(); setPadding(16.px(), 12.px(), 16.px(), 12.px())
        background = GradientDrawable().apply { cornerRadius = 6.px().toFloat(); setColor(lima) }
        setOnClickListener { accion() }
        pulsable(this)
    }

    // ---------------------------------------------------------------- la portada
    fun mostrar() {
        scrollDetalle.visibility = View.GONE
        scrollLista.visibility = View.VISIBLE
        val u = url()
        if (u == null) { pintarLista(null, false); return }
        if (cargando) return
        cargando = true
        thread {
            val r = Rutas.lista(act, u)
            act.runOnUiThread {
                cargando = false
                if (!act.isFinishing && !act.isDestroyed) pintarLista(r?.first, r?.second ?: false)
            }
        }
    }

    /** Vuelve de una ruta a la lista; false si ya estaba en la lista. */
    fun atras(): Boolean {
        if (scrollDetalle.visibility != View.VISIBLE) return false
        scrollDetalle.visibility = View.GONE
        scrollLista.visibility = View.VISIBLE
        return true
    }

    private fun cabeceraLista(): View {
        val c = LinearLayout(act).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(lima); setPadding(20.px(), 16.px(), 20.px(), 22.px()) }
        c.addView(t("RUTAS\n" + sitio(), 58f, tinta, anton).apply { setLineSpacing(0f, 0.95f); includeFontPadding = false })
        c.addView(t("Mira la ruta, descarga el GPX y sal.", 16f, tinta).apply { setPadding(0, 14.px(), 0, 0) })
        c.addView(t("Huawei · Amazfit · Garmin · Coros", 14f, tinta).apply { setPadding(0, 4.px(), 0, 0) })
        return c
    }

    private fun mensaje(txt: String) = t(txt, 17f, papel).apply { setPadding(0, 22.px(), 0, 14.px()); setLineSpacing(0f, 1.15f) }

    private fun pintarLista(rs: List<Rutas.Resumen>?, sinCobertura: Boolean) {
        contLista.removeAllViews()
        contLista.addView(cabeceraLista())
        val cuerpo = LinearLayout(act).apply { orientation = LinearLayout.VERTICAL; setPadding(16.px(), 8.px(), 16.px(), 28.px()) }
        when {
            url() == null -> {
                cuerpo.addView(mensaje("Conecta la app con tu servidor para ver aquí las rutas que se publican en la web."))
                cuerpo.addView(botonClaro("Ir a «Carrera»") { irACarrera() })
            }
            rs == null -> {
                cuerpo.addView(mensaje("No se pudieron cargar las rutas. Mira la cobertura y prueba otra vez."))
                cuerpo.addView(botonClaro("Reintentar") { mostrar() })
            }
            rs.isEmpty() -> cuerpo.addView(mensaje("Todavía no hay rutas publicadas."))
            else -> {
                if (sinCobertura) cuerpo.addView(t("Sin cobertura: estas son las últimas rutas que se bajaron.", 13f, apagado).apply { setPadding(0, 14.px(), 0, 4.px()) })
                rs.forEachIndexed { i, r -> cuerpo.addView(fila(r, i)) }
            }
        }
        contLista.addView(cuerpo)
    }

    private fun cifra(valor: String, unidad: String, ancho: Int) = LinearLayout(act).apply {
        orientation = LinearLayout.VERTICAL; gravity = Gravity.END
        addView(t(valor, 26f, papel, anton).apply { includeFontPadding = false; gravity = Gravity.END })
        addView(t(unidad, 11f, apagado).apply { gravity = Gravity.END })
        layoutParams = LinearLayout.LayoutParams(ancho.px(), -2)
    }

    private fun fila(r: Rutas.Resumen, i: Int): View {
        val f = LinearLayout(act).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(0, 14.px(), 0, 14.px()) }
        val nombre = LinearLayout(act).apply { orientation = LinearLayout.VERTICAL }
        nombre.addView(t(r.nombre.uppercase(), 24f, papel, anton).apply { includeFontPadding = false; setLineSpacing(0f, 0.95f) })
        if (r.autor.isNotEmpty()) nombre.addView(t("de ${r.autor}", 13f, apagado).apply { setPadding(0, 4.px(), 0, 0) })
        f.addView(nombre, LinearLayout.LayoutParams(0, -2, 1f))
        val traza = FrameLayout(act).apply {
            background = GradientDrawable().apply { cornerRadius = 4.px().toFloat(); setColor(lima) }
            addView(TrazaView(act, r.traza, tinta), FrameLayout.LayoutParams(-1, -1))
        }
        f.addView(traza, LinearLayout.LayoutParams(76.px(), 54.px()).apply { leftMargin = 10.px(); rightMargin = 10.px() })
        f.addView(cifra(km(r.km), "KM", 52))
        f.addView(cifra(r.desnivel.toString(), "D+", 50))
        f.setOnClickListener { abrir(r) }
        pulsable(f)
        f.alpha = 0f; f.translationY = 14.px().toFloat()
        f.animate().alpha(1f).translationY(0f).setStartDelay(55L * minOf(i, 10)).setDuration(380).setInterpolator(DecelerateInterpolator()).start()
        return f
    }

    // ---------------------------------------------------------------- una ruta
    private fun abrir(r: Rutas.Resumen) {
        scrollLista.visibility = View.GONE
        scrollDetalle.visibility = View.VISIBLE
        scrollDetalle.scrollTo(0, 0)
        abierta = r.id
        pintarDetalle(r, null, true)
        val u = url() ?: return
        thread {
            val d = Rutas.detalle(u, r.id)
            act.runOnUiThread {
                if (!act.isFinishing && !act.isDestroyed && scrollDetalle.visibility == View.VISIBLE && abierta == r.id) pintarDetalle(r, d, false)
            }
        }
    }

    private fun dato(valor: String, unidad: String) = LinearLayout(act).apply {
        orientation = LinearLayout.VERTICAL
        addView(t(valor, 44f, tinta, anton).apply { includeFontPadding = false })
        addView(t(unidad, 12f, tinta))
        setPadding(0, 0, 28.px(), 12.px())
    }

    private fun pintarDetalle(r: Rutas.Resumen, d: Rutas.Detalle?, cargandoAun: Boolean) {
        contDetalle.removeAllViews()
        val cab = LinearLayout(act).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(lima); setPadding(20.px(), 12.px(), 20.px(), 22.px()) }
        cab.addView(t("‹ RUTAS", 18f, tinta, anton).apply {
            setPadding(0, 4.px(), 0, 10.px()); minimumHeight = 44.px(); gravity = Gravity.CENTER_VERTICAL
            setOnClickListener { atras() }; pulsable(this)
        })
        cab.addView(t(r.nombre.uppercase(), if (r.nombre.length > 22) 34f else 46f, tinta, anton).apply { includeFontPadding = false; setLineSpacing(0f, 0.95f) })
        if (r.autor.isNotEmpty()) cab.addView(t("Ruta de ${r.autor}", 14f, tinta).apply { setPadding(0, 10.px(), 0, 0) })
        val datos = LinearLayout(act).apply { orientation = LinearLayout.HORIZONTAL; setPadding(0, 16.px(), 0, 6.px()) }
        datos.addView(dato(km(r.km), "KM")); datos.addView(dato(r.desnivel.toString(), "D+"))
        if (d != null && d.avits.isNotEmpty()) datos.addView(dato(d.avits.size.toString(), if (d.avits.size == 1) "AVIT." else "AVITS."))
        if (d != null && d.subidas.isNotEmpty()) datos.addView(dato(d.subidas.size.toString(), if (d.subidas.size == 1) "SUBIDA" else "SUBIDAS"))
        cab.addView(datos)
        cab.addView(botonCartel("Descargar GPX para el reloj", true) { bajarGpx(r) }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 8.px() })
        cab.addView(botonCartel("Ver el mapa en la web", false) { abrirEnNavegador("${url()}/r/${r.id}") }, LinearLayout.LayoutParams(-1, -2).apply { topMargin = 10.px() })
        contDetalle.addView(cab)

        val cuerpo = LinearLayout(act).apply { orientation = LinearLayout.VERTICAL; setPadding(16.px(), 18.px(), 16.px(), 32.px()) }
        when {
            cargandoAun -> cuerpo.addView(mensaje("Cargando la ruta…"))
            d == null -> cuerpo.addView(mensaje("No se pudo cargar el detalle: sin cobertura o la ruta ya no está publicada. El GPX se puede descargar igual si hay cobertura."))
            else -> {
                if (d.perfil.size >= 2) cuerpo.addView(PerfilView(act, d.perfil, d.avits.map { it.second }, lima, panel, apagado, tinta),
                    LinearLayout.LayoutParams(-1, 150.px()))
                if (d.avits.isNotEmpty()) {
                    cuerpo.addView(t("AVITUALLAMIENTOS", 28f, papel, anton).apply { setPadding(0, 26.px(), 0, 6.px()); includeFontPadding = false })
                    d.avits.forEach { cuerpo.addView(filaDato(it.first.uppercase(), "", km(it.second), "KM", km(maxOf(0.0, d.km - it.second)), "A META")) }
                }
                if (d.subidas.isNotEmpty()) {
                    cuerpo.addView(t("SUBIDAS", 28f, papel, anton).apply { setPadding(0, 26.px(), 0, 6.px()); includeFontPadding = false })
                    d.subidas.forEach {
                        cuerpo.addView(filaDato("SUBE ${it.n}", "km ${km(it.inicio)} a ${km(it.fin)} · ${String.format(es, "%.1f", it.pendiente)} %",
                            "+${it.desnivel}", "M", km(it.largo), "KM"))
                    }
                }
                cuerpo.addView(t("Los primeros y últimos metros de cada ruta no se muestran.", 12f, apagado).apply { setPadding(0, 26.px(), 0, 0) })
            }
        }
        contDetalle.addView(cuerpo)
    }

    private fun filaDato(nombre: String, sub: String, v1: String, u1: String, v2: String, u2: String): View {
        val f = LinearLayout(act).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER_VERTICAL; setPadding(0, 10.px(), 0, 10.px()) }
        val n = LinearLayout(act).apply { orientation = LinearLayout.VERTICAL }
        n.addView(t(nombre, 22f, papel, anton).apply { includeFontPadding = false })
        if (sub.isNotEmpty()) n.addView(t(sub, 13f, apagado).apply { setPadding(0, 4.px(), 0, 0) })
        f.addView(n, LinearLayout.LayoutParams(0, -2, 1f))
        f.addView(cifra(v1, u1, 64)); f.addView(cifra(v2, u2, 64))
        return f
    }

    // ---------------------------------------------------------------- el GPX para el reloj
    private fun bajarGpx(r: Rutas.Resumen) {
        val u = url() ?: return
        if (bajando) return
        bajando = true
        Toast.makeText(act, "Bajando la ruta…", Toast.LENGTH_SHORT).show()
        thread {
            val uri = Rutas.guardarGpx(act, u, r.id, r.nombre)
            act.runOnUiThread {
                bajando = false
                if (act.isFinishing || act.isDestroyed) return@runOnUiThread
                if (uri != null) {
                    avisar("Ruta guardada en Descargas",
                        "Ahora ábrela con la app de tu reloj:\n\n•  Huawei Health: Yo → Mi ruta → Importar ruta\n•  Zepp, Garmin Connect o Coros: importar GPX",
                        listOf("Abrir con…" to { abrirGpx(uri) }, "Compartir" to { compartirGpx(uri) }, "Cerrar" to {}))
                } else if (android.os.Build.VERSION.SDK_INT < android.os.Build.VERSION_CODES.Q) {
                    // Android 8 o 9: la app no puede guardar en Descargas; lo baja el navegador
                    abrirEnNavegador("$u/api/ruta-publica/reloj.gpx?id=${r.id}")
                } else {
                    avisar("No se pudo bajar la ruta", "Sin cobertura o la ruta ya no está publicada. Prueba otra vez cuando tengas red.",
                        listOf("Reintentar" to { bajarGpx(r) }, "Cerrar" to {}))
                }
            }
        }
    }

    private fun abrirGpx(uri: Uri) {
        try {
            val i = Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/gpx+xml").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            act.startActivity(Intent.createChooser(i, "Abrir la ruta con"))
        } catch (e: Exception) {
            avisar("No se pudo abrir", "Ábrela desde la app Archivos, en la carpeta Descargas.", listOf("Vale" to {}))
        }
    }

    private fun compartirGpx(uri: Uri) {
        try {
            val i = Intent(Intent.ACTION_SEND).setType("application/gpx+xml").putExtra(Intent.EXTRA_STREAM, uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            act.startActivity(Intent.createChooser(i, "Compartir la ruta"))
        } catch (e: Exception) {
            avisar("No se pudo compartir", "Ábrela desde la app Archivos, en la carpeta Descargas.", listOf("Vale" to {}))
        }
    }

    private fun abrirEnNavegador(direccion: String) {
        try { act.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(direccion))) }
        catch (e: Exception) { avisar("No se pudo abrir", "Abre esta dirección en el navegador:\n\n$direccion", listOf("Vale" to {})) }
    }
}
