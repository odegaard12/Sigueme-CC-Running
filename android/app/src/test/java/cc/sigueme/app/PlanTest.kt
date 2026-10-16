package cc.sigueme.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Ruta recta de 10 km hacia el norte, una subida y un avituallamiento. */
class PlanTest {
    private val gradoKm = 1 / 111.195          // grados de latitud por km
    private val plan = Plan("""{
      "carrera": {"nombre": "Prueba", "distancia_km": 10},
      "ruta": [${(0..100).joinToString(",") { "[-4.0, ${40.0 + it * 0.1 * gradoKm}]" }}],
      "avisos": [
        {"id": 1, "km": 2.0, "texto": "SUBIDA · 1,2km", "valido_hasta": 2.6},
        {"id": 2, "km": 5.0, "texto": "AVITUALLAMIENTO {dist} · A", "valido_hasta": 5.5, "objetivo_km": 5.3}],
      "subidas": [{"inicio": 2.3, "fin": 3.5, "desnivel_m": 60, "largo_km": 1.2}],
      "restante": [[0, 60], [4, 0]]
    }""")

    private fun punto(km: Double) = 40.0 + km * gradoKm

    @Test fun kmEnRuta() {
        assertEquals(4.0, plan.kmEnRuta(punto(4.0), -4.0, 3.5)!!, 0.06)
        assertEquals(9.0, plan.kmEnRuta(punto(9.0), -4.0, 0.0)!!, 0.06)   // salto largo: segunda ventana
        assertNull(plan.kmEnRuta(punto(4.0), -3.99, 3.5))                // a 850 m de la ruta
    }

    @Test fun retomarAMitadDeCarrera() {
        // 60 km rectos; la app vuelve a empezar (km 0) estando en el km 50
        val largo = Plan("""{"carrera": {"distancia_km": 60}, "ruta": [${(0..600).joinToString(",") { "[-4.0, ${40.0 + it * 0.1 * gradoKm}]" }}]}""")
        assertEquals(50.0, largo.kmEnRuta(punto(50.0), -4.0, 0.0)!!, 0.1)
    }

    @Test fun idaYVueltaPorElMismoCamino() {
        // 3 km al norte y vuelta por un camino a 40 m (0.0005° de longitud)
        val ida = (0..30).map { "[-4.0, ${40.0 + it * 0.1 * gradoKm}]" }
        val vuelta = (30 downTo 0).map { "[-3.9995, ${40.0 + it * 0.1 * gradoKm}]" }
        val p = Plan("""{"carrera": {"distancia_km": 6.2}, "ruta": [${(ida + vuelta).joinToString(",")}]}""")
        // en la ida (km 1) con el GPS desviado hacia la vuelta: sigue siendo el km 1, no el 5
        assertEquals(1.0, p.kmEnRuta(punto(1.0), -3.9996, 0.8)!!, 0.1)
        // ya en la vuelta, la ida queda detrás y vale la vuelta
        assertEquals(5.2, p.kmEnRuta(punto(1.0), -3.9996, 4.9)!!, 0.15)
    }

    @Test fun avisoPorEstado() {
        assertEquals(1 to "SUBIDA · 1,2km", plan.avisoQueToca(2.1, 0))
        // llega tarde (sin GPS un rato): el estado de ahora, no el aviso viejo
        assertEquals(1 to "EN SUBIDA · quedan 500m · +25m", plan.avisoQueToca(3.0, 0))
        assertEquals(2 to "AVITUALLAMIENTO en 200m · A", plan.avisoQueToca(5.1, 1))
        assertEquals(2 to "AVITUALLAMIENTO AQUÍ · A", plan.avisoQueToca(5.3, 1))
        assertNull(plan.avisoQueToca(5.3, 2))
        assertEquals(2 to "KM 6 · faltan 4,0km · +0m", plan.avisoQueToca(6.0, 1))
    }

    @Test fun esperaALaHoraDeSalida() {
        val p = Plan("""{"carrera": {"fecha": "2027-05-16", "hora_salida": "10:00", "zona_horaria": "Europe/Madrid"}, "ruta": []}""")
        val diez = java.time.ZonedDateTime.of(2027, 5, 16, 10, 0, 0, 0, java.time.ZoneId.of("Europe/Madrid")).toInstant().toEpochMilli()
        assertEquals(diez, p.salida)
        assertEquals(true, p.antesDeSalir(diez - 15 * 60_000))        // 09:45: esperando en la salida
        assertEquals(false, p.antesDeSalir(diez + 1))                 // ya salió
        assertEquals(false, p.antesDeSalir(diez - 3 * 86400_000L))    // tres días antes: una prueba, sin esperar
    }

    @Test fun formatoParaLaPulsera() {
        assertEquals("Subida larga" to "1,2 km · 7 %\n+84 m\nRampa 19 %", Plan.notificacion("SUBIDA LARGA · 1,2km · 7% · +84m · rampa 19%"))
        assertEquals("Cima" to "Bajada 2,9 km · −215 m\nQuedan +185 m", Plan.notificacion("CIMA · bajada 2,9km · -215m · quedan +185m"))
        assertEquals("Avituallamiento en 300 m" to "Fuente del Pinar", Plan.notificacion("AVITUALLAMIENTO en 300m · Fuente del Pinar"))
        assertEquals("Último km" to "¡a por ello!", Plan.notificacion("ÚLTIMO KM · ¡a por ello!"))
        assertEquals("Prueba de Sígueme CC" to "Si lo ves en la pulsera · Los avisos funcionan",
            Plan.notificacion("Prueba de Sígueme CC · si lo ves en la pulsera · los avisos funcionan"))
    }

    @Test fun subidaConDistancia() {
        val p = Plan("""{"carrera": {"distancia_km": 10}, "ruta": [${(0..100).joinToString(",") { "[-4.0, ${40.0 + it * 0.1 * gradoKm}]" }}],
          "avisos": [{"id": 1, "km": 2.0, "tipo": "subida", "texto": "SUBIDA LARGA · 1,2km · 7%", "valido_hasta": 2.6}],
          "subidas": [{"inicio": 2.3, "fin": 3.5, "desnivel_m": 84, "largo_km": 1.2}]}""")
        assertEquals(1 to "SUBIDA LARGA en 300m · 1,2km · 7%", p.avisoQueToca(2.0, 0))
    }

    @Test fun textos() {
        assertEquals("250m", Plan.kmTxt(0.26))
        assertEquals("2,3km", Plan.kmTxt(2.34))
    }
}
