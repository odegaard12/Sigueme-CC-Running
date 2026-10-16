package cc.sigueme.app

import org.json.JSONObject
import kotlin.math.asin
import kotlin.math.cos
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sqrt

/** Plan de la carrera bajado del servidor (/api/plan). Sin Android: se prueba en la JVM.
 *  La misma lógica que tenía el servidor con ntfy, ahora en el móvil y sin cobertura. */
class Plan(json: String) {
    data class Aviso(val id: Int, val km: Double, val texto: String, val validoHasta: Double, val objetivoKm: Double?)
    data class Subida(val inicio: Double, val fin: Double, val desnivel: Int, val largo: Double)

    val nombre: String
    val horaSalida: String
    /** Hora oficial de salida (ms), o null si la carrera no la tiene. */
    val salida: Long?
    val distancia: Double
    val lat: DoubleArray
    val lon: DoubleArray
    val km: DoubleArray            // km de cada punto, escalado a la distancia oficial
    val avisos: List<Aviso>
    val subidas: List<Subida>
    private val restante: List<Pair<Double, Int>>

    init {
        val j = JSONObject(json)
        val c = j.optJSONObject("carrera") ?: JSONObject()
        nombre = c.optString("nombre", "Carrera")
        horaSalida = c.optString("hora_salida", "")
        salida = try {
            java.time.LocalDateTime.parse(c.getString("fecha") + "T" + horaSalida)
                .atZone(java.time.ZoneId.of(c.optString("zona_horaria", "Europe/Madrid"))).toInstant().toEpochMilli()
        } catch (e: Exception) { null }
        val r = j.getJSONArray("ruta")
        lat = DoubleArray(r.length()) { r.getJSONArray(it).getDouble(1) }
        lon = DoubleArray(r.length()) { r.getJSONArray(it).getDouble(0) }
        val cum = DoubleArray(lat.size)
        for (i in 1 until lat.size) cum[i] = cum[i - 1] + kmEntre(lat[i - 1], lon[i - 1], lat[i], lon[i])
        val medido = if (cum.isEmpty()) 0.0 else cum.last()
        distancia = c.optDouble("distancia_km", medido).takeIf { !it.isNaN() } ?: medido
        val f = if (medido > 0) distancia / medido else 1.0
        km = DoubleArray(cum.size) { cum[it] * f }
        val a = j.optJSONArray("avisos")
        avisos = (0 until (a?.length() ?: 0)).map {
            val o = a!!.getJSONObject(it)
            Aviso(o.getInt("id"), o.getDouble("km"), o.getString("texto"), o.optDouble("valido_hasta", o.getDouble("km") + 0.3),
                if (o.has("objetivo_km")) o.getDouble("objetivo_km") else null)
        }.sortedBy { it.km }
        val s = j.optJSONArray("subidas")
        subidas = (0 until (s?.length() ?: 0)).map {
            val o = s!!.getJSONObject(it)
            Subida(o.getDouble("inicio"), o.getDouble("fin"), o.getInt("desnivel_m"), o.getDouble("largo_km"))
        }
        val re = j.optJSONArray("restante")
        restante = (0 until (re?.length() ?: 0)).map { re!!.getJSONArray(it).let { p -> p.getDouble(0) to p.getInt(1) } }
    }

    /** ¿Esperando en la salida? Se puede dar a EMPEZAR antes de la hora (a las
     *  09:45 para salir a las 10:00): hasta la hora oficial ni km ni avisos. Otro
     *  día (una prueba) no espera. */
    fun antesDeSalir(ahora: Long): Boolean = salida != null && ahora < salida && salida - ahora < 12 * 3600_000L

    /** Km de ruta del punto, siempre hacia delante (salida y meta suelen estar
     *  juntas: buscar en toda la ruta saltaría a la meta en la salida). null si
     *  está a más de 150 m de la ruta.
     *  ⚠️ Ida y vuelta por el mismo camino: el punto MÁS cercano podía ser el de
     *  la vuelta y, como solo se avanza, se perdían los avisos de en medio. Vale
     *  la PRIMERA pasada por ese sitio (y dentro de ella, el punto más cercano). */
    fun kmEnRuta(la: Double, lo: Double, ultimo: Double): Double? {
        // la última ventana, sin tope: tras un corte muy largo o un reinicio a mitad de carrera
        for (ventana in doubleArrayOf(5.0, 40.0, Double.MAX_VALUE)) {
            var mejor = 0.15
            var res: Double? = null
            for (i in km.indices) {
                if (km[i] < ultimo - 0.5 || km[i] > ultimo + ventana) continue
                val d = kmEntre(la, lo, lat[i], lon[i])
                if (d < mejor) { mejor = d; res = km[i] }
                else if (res != null && d > 0.3) break        // se alejó: fin de la primera pasada
            }
            if (res != null) return res
        }
        return null
    }

    /** Por ESTADO, no por eventos: si te saltas varios avisos (GPS perdido, móvil
     *  apagado), sale el último que toca y, si ya no vale, cómo estás ahora. */
    fun avisoQueToca(k: Double, enviado: Int): Pair<Int, String>? {
        val a = avisos.lastOrNull { it.km <= k && it.id > enviado } ?: return null
        if (k > a.validoHasta) return a.id to textoEstado(k)
        val falta = (a.objetivoKm ?: k) - k
        return a.id to a.texto.replace("{dist}", if (falta > 0.05) "en " + kmTxt(falta) else "AQUÍ")
    }

    fun textoEstado(k: Double): String {
        subidas.firstOrNull { it.inicio <= k && k < it.fin }?.let {
            val queda = it.fin - k
            return "EN SUBIDA · quedan ${kmTxt(queda)} · +${(it.desnivel * queda / (if (it.largo > 0) it.largo else 1.0)).roundToInt()}m"
        }
        val resto = restante.firstOrNull { it.first >= k }?.second ?: 0
        return "KM ${k.roundToInt()} · faltan ${kmTxt(maxOf(0.0, distancia - k))} · +${resto}m"
    }

    companion object {
        fun kmTxt(k: Double): String =
            if (k < 1) "${(k * 1000 / 50).roundToInt() * 50}m" else String.format(java.util.Locale.ROOT, "%.1f", k).replace('.', ',') + "km"

        fun kmEntre(la1: Double, lo1: Double, la2: Double, lo2: Double): Double {
            val r = Math.PI / 180
            val h = sin((la2 - la1) * r / 2).let { it * it } + cos(la1 * r) * cos(la2 * r) * sin((lo2 - lo1) * r / 2).let { it * it }
            return 2 * 6371 * asin(sqrt(h))
        }
    }
}
