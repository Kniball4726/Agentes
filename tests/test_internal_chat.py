import unittest
from pathlib import Path

from src.internal_chat import (
    detectar_intencion,
    extraer_termino_busqueda,
    formatear_diagnostico_archivos,
    formatear_respuesta_criticos,
    formatear_respuesta_stock,
    formatear_ultimo_informe,
)


class InternalChatTests(unittest.TestCase):
    def test_detects_simulation_requests_in_natural_language(self):
        for mensaje in (
            "/simular",
            "Simula los documentos pendientes",
            "Quiero hacer una simulación",
        ):
            with self.subTest(mensaje=mensaje):
                self.assertEqual(detectar_intencion(mensaje), "simular")

    def test_detects_local_status_and_report_questions(self):
        self.assertEqual(detectar_intencion("¿Qué archivos están pendientes?"), "estado")
        self.assertEqual(detectar_intencion("Muéstrame los informes"), "informes")
        self.assertEqual(detectar_intencion("/estado"), "estado")
        self.assertEqual(detectar_intencion("/informes"), "informes")

    def test_detects_help_and_greetings(self):
        self.assertEqual(detectar_intencion("Hola"), "saludo")
        self.assertEqual(detectar_intencion("¿Qué puedes hacer?"), "ayuda")
        self.assertEqual(detectar_intencion("AYUDA"), "ayuda")

    def test_detects_extended_intents(self):
        self.assertEqual(detectar_intencion("/criticos"), "criticos")
        self.assertEqual(detectar_intencion("hay productos sin stock?"), "criticos")
        self.assertEqual(detectar_intencion("/diagnostico"), "diagnostico")
        self.assertEqual(detectar_intencion("revisar archivos pendientes"), "diagnostico")
        self.assertEqual(detectar_intencion("/ultimo"), "ultimo_informe")
        self.assertEqual(detectar_intencion("cuál fue el último informe"), "ultimo_informe")
        self.assertEqual(detectar_intencion("/stock 1002"), "buscar_stock")
        self.assertEqual(detectar_intencion("cuánto stock queda de filtro"), "buscar_stock")
        self.assertEqual(detectar_intencion("/limpiar"), "limpiar")

    def test_extracts_search_term_correctly(self):
        self.assertEqual(extraer_termino_busqueda("/stock 1002"), "1002")
        self.assertEqual(extraer_termino_busqueda("/buscar arandela de presión"), "arandela de presión")
        self.assertEqual(extraer_termino_busqueda("¿cuánto stock queda de amortiguador?"), "amortiguador")

    def test_formats_stock_response(self):
        productos = [
            {"code": "1001", "name": "Filtro de Aceite", "stock": 10, "active": 1},
            {"code": "1002", "name": "Bujía Premium", "stock": 2, "active": 1},
            {"code": "1003", "name": "Correa de Distribución", "stock": 0, "active": 0},
        ]
        res_exacta = formatear_respuesta_stock("1001", productos)
        self.assertIn("Filtro de Aceite", res_exacta)
        self.assertIn("10 unidades", res_exacta)

        res_critico = formatear_respuesta_stock("1002", productos)
        self.assertIn("STOCK BAJO", res_critico)

        res_no_existe = formatear_respuesta_stock("9999", productos)
        self.assertIn("No encontré ningún producto", res_no_existe)

    def test_formats_critical_products_response(self):
        productos = [
            {"code": "1001", "name": "Filtro de Aceite", "stock": 10, "active": 1},
            {"code": "1002", "name": "Bujía Premium", "stock": 2, "active": 1},
            {"code": "1003", "name": "Correa de Distribución", "stock": 0, "active": 1},
            {"code": "1004", "name": "Inactivo pero sin stock", "stock": 0, "active": 0},
        ]
        res = formatear_respuesta_criticos(productos, umbral=5)
        self.assertIn("Bujía Premium", res)
        self.assertIn("Correa de Distribución", res)
        self.assertNotIn("Inactivo pero sin stock", res)

    def test_formats_diagnostics_and_last_report(self):
        p1, p2, p3 = Path("a.pdf"), Path("b.xlsx"), Path("c.docx")
        diag = formatear_diagnostico_archivos([p1], [p2], [p3])
        self.assertIn("Mayoristas", diag)
        self.assertIn("Canjes", diag)
        self.assertIn("Mercado Libre", diag)

        diag_vacio = formatear_diagnostico_archivos([], [], [])
        self.assertIn("No hay archivos pendientes", diag_vacio)

        informe = Path("Descuentos_2026.pdf")
        res_info = formatear_ultimo_informe([informe])
        self.assertIn("Descuentos_2026.pdf", res_info)

    def test_returns_unknown_for_unsupported_messages(self):
        self.assertEqual(detectar_intencion("¿Qué tiempo hace mañana?"), "desconocido")
        self.assertEqual(detectar_intencion("   "), "desconocido")


if __name__ == "__main__":
    unittest.main()
