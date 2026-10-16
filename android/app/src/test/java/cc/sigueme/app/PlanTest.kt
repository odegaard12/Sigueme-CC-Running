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

    @Test fun avisoPorEstado() {
        assertEquals(1 to "SUBIDA · 1,2km", plan.avisoQueToca(2.1, 0))
        // llega tarde (sin GPS un rato): el estado de ahora, no el aviso viejo
        assertEquals(1 to "EN SUBIDA · quedan 500m · +25m", plan.avisoQueToca(3.0, 0))
        assertEquals(2 to "AVITUALLAMIENTO en 200m · A", plan.avisoQueToca(5.1, 1))
        assertEquals(2 to "AVITUALLAMIENTO AQUÍ · A", plan.avisoQueToca(5.3, 1))
        assertNull(plan.avisoQueToca(5.3, 2))
        assertEquals(2 to "KM 6 · faltan 4,0km · +0m", plan.avisoQueToca(6.0, 1))
    }

    @Test fun textos() {
        assertEquals("250m", Plan.kmTxt(0.26))
        assertEquals("2,3km", Plan.kmTxt(2.34))
    }
}
