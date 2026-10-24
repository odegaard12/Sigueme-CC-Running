package cc.sigueme.app

import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.text.Normalizer

/** Las rutas publicadas en la web (/api/rutas-publicas y /api/ruta-publica). Sin Android donde se
 *  puede (parseLista y parseDetalle), para probarlo en la JVM. */
object Rutas {
    class Resumen(val id: String, val nombre: String, val autor: String, val km: Double, val desnivel: Int,
                  val avituallamientos: Int, val traza: List<DoubleArray>)
    class Subida(val n: Int, val inicio: Double, val fin: Double, val desnivel: Int, val largo: Double, val pendiente: Double)
    class Detalle(val id: String, val nombre: String, val autor: String, val km: Double, val desnivel: Int,
                  val perfil: List<DoubleArray>, val avits: List<Pair<String, Double>>, val subidas: List<Subida>)

    private fun pares(a: JSONArray?): List<DoubleArray> =
        (0 until (a?.length() ?: 0)).map { i -> a!!.getJSONArray(i).let { doubleArrayOf(it.getDouble(0), it.getDouble(1)) } }

    fun parseLista(json: String): List<Resumen> {
        val a = JSONObject(json).optJSONArray("rutas") ?: return emptyList()
        return (0 until a.length()).map {
            val o = a.getJSONObject(it)
            Resumen(o.getString("id"), o.optString("nombre", "Ruta"), o.optString("autor", ""), o.optDouble("distancia_km", 0.0),
                o.optInt("desnivel_m", 0), o.optInt("avituallamientos", 0), pares(o.optJSONArray("traza")))
        }
    }

    fun parseDetalle(json: String): Detalle {
        val o = JSONObject(json)
        val av = o.optJSONArray("avituallamientos")
        val su = o.optJSONArray("subidas")
        return Detalle(o.getString("id"), o.optString("nombre", "Ruta"), o.optString("autor", ""), o.optDouble("distancia_km", 0.0),
            o.optInt("desnivel_m", 0), pares(o.optJSONArray("perfil")),
            (0 until (av?.length() ?: 0)).map { av!!.getJSONObject(it).let { a -> a.optString("name", "") to a.optDouble("km", 0.0) } },
            (0 until (su?.length() ?: 0)).map {
                val s = su!!.getJSONObject(it)
                Subida(s.optInt("n", it + 1), s.optDouble("inicio", 0.0), s.optDouble("fin", 0.0), s.optInt("desnivel_m", 0),
                    s.optDouble("largo_km", 0.0), s.optDouble("pendiente", 0.0))
            })
    }

    private fun get(url: String): ByteArray {
        val con = URL(url).openConnection() as HttpURLConnection
        con.connectTimeout = 15_000; con.readTimeout = 30_000
        try {
            if (con.responseCode != 200) throw java.io.IOException("HTTP ${con.responseCode}")
            return con.inputStream.use { it.readBytes() }
        } finally {
            con.disconnect()
        }
    }

    /** La lista de rutas; si no hay cobertura, la última que se bajó (el segundo valor es true). null = nada que enseñar. */
    fun lista(c: Context, url: String): Pair<List<Resumen>, Boolean>? {
        val cache = File(c.filesDir, "rutas.json")
        return try {
            val txt = String(get("$url/api/rutas-publicas"), Charsets.UTF_8)
            val rs = parseLista(txt)
            Seguimiento.escribirSeguro(cache, txt)
            rs to false
        } catch (e: Exception) {
            try { parseLista(cache.readText()) to true } catch (e2: Exception) { null }
        }
    }

    fun detalle(url: String, id: String): Detalle? =
        try { parseDetalle(String(get("$url/api/ruta-publica?id=$id"), Charsets.UTF_8)) } catch (e: Exception) { null }

    fun nombreFichero(nombre: String): String {
        val limpio = Normalizer.normalize(nombre, Normalizer.Form.NFD).replace(Regex("\\p{M}+"), "")
            .lowercase().replace(Regex("[^a-z0-9]+"), "-").trim('-')
        return (limpio.ifEmpty { "ruta" }) + "-reloj.gpx"
    }

    /** Baja el GPX para el reloj y lo deja en Descargas (Android 10 o más); devuelve su dirección, o null si no se pudo. */
    fun guardarGpx(c: Context, url: String, id: String, nombre: String): Uri? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return null
        val bytes = try { get("$url/api/ruta-publica/reloj.gpx?id=$id") } catch (e: Exception) { return null }
        val valores = ContentValues().apply {
            put(MediaStore.Downloads.DISPLAY_NAME, nombreFichero(nombre))
            put(MediaStore.Downloads.MIME_TYPE, "application/gpx+xml")
            put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
            put(MediaStore.Downloads.IS_PENDING, 1)
        }
        val uri = try { c.contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, valores) } catch (e: Exception) { null } ?: return null
        return try {
            c.contentResolver.openOutputStream(uri)!!.use { it.write(bytes) }
            c.contentResolver.update(uri, ContentValues().apply { put(MediaStore.Downloads.IS_PENDING, 0) }, null, null)
            uri
        } catch (e: Exception) {
            try { c.contentResolver.delete(uri, null, null) } catch (e2: Exception) {}
            null
        }
    }
}
