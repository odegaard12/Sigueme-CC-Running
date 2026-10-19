package cc.sigueme.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class RutasTest {
    @Test fun leeLaLista() {
        val rs = Rutas.parseLista("""{"rutas":[{"id":"a1b2c3d4e5f6","nombre":"Hoces del río","autor":"Ana","distancia_km":21.1,
            "desnivel_m":299,"avituallamientos":2,"traza":[[-4.0,40.8],[-3.99,40.81]],"perfil":[[0,900],[21.1,950]]},
            {"id":"b1b2c3d4e5f6","nombre":"Sin más datos"}]}""")
        assertEquals(2, rs.size)
        assertEquals("Hoces del río", rs[0].nombre); assertEquals("Ana", rs[0].autor)
        assertEquals(21.1, rs[0].km, 0.001); assertEquals(299, rs[0].desnivel); assertEquals(2, rs[0].avituallamientos)
        assertEquals(2, rs[0].traza.size); assertEquals(-4.0, rs[0].traza[0][0], 0.0); assertEquals(40.81, rs[0].traza[1][1], 0.0)
        // una ruta con campos que faltan no tumba la lista
        assertEquals("", rs[1].autor); assertEquals(0.0, rs[1].km, 0.0); assertTrue(rs[1].traza.isEmpty())
    }

    @Test fun listaVaciaOSinRutas() {
        assertTrue(Rutas.parseLista("""{"rutas":[]}""").isEmpty())
        assertTrue(Rutas.parseLista("{}").isEmpty())
    }

    @Test fun leeElDetalle() {
        val d = Rutas.parseDetalle("""{"id":"a1b2c3d4e5f6","nombre":"Hoces","autor":"","distancia_km":21.1,"desnivel_m":299,
            "perfil":[[0,900],[10,950],[21.1,920]],"avituallamientos":[{"name":"Fuente","km":7.5}],
            "subidas":[{"n":1,"inicio":3.2,"fin":5.2,"desnivel_m":120,"largo_km":2.0,"pendiente":6.0}]}""")
        assertEquals("Hoces", d.nombre); assertEquals(3, d.perfil.size); assertEquals(950.0, d.perfil[1][1], 0.0)
        assertEquals("Fuente", d.avits[0].first); assertEquals(7.5, d.avits[0].second, 0.0)
        assertEquals(1, d.subidas[0].n); assertEquals(120, d.subidas[0].desnivel); assertEquals(6.0, d.subidas[0].pendiente, 0.0)
    }

    @Test fun nombreDelFichero() {
        assertEquals("hoces-del-rio-reloj.gpx", Rutas.nombreFichero("Hoces del Río"))
        assertEquals("ruta-reloj.gpx", Rutas.nombreFichero("¿¿??"))
        assertEquals("a-b-reloj.gpx", Rutas.nombreFichero("  A / B  "))
    }
}
