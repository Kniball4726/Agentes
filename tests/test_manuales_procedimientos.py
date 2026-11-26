import unittest
from pathlib import Path
import tempfile
from Documentacion.generar_presentacion_tren_ejecutivo import (
    generar_presentacion_tren_ejecutivo,
)
from Documentacion.manuales_procedimientos import generar_todos_los_manuales


class TestManualesProcedimientos(unittest.TestCase):
    def test_generacion_todos_los_manuales_pdf(self):
        """Verifica que se compilen todos los manuales de procedimiento botón por botón en PDF."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            rutas = generar_todos_los_manuales(tmp_path)

            roles_esperados = [
                "operador",
                "picker",
                "despachador",
                "administrador",
                "master",
                "consulta",
                "general",
                "maestro",
            ]
            for rol in roles_esperados:
                self.assertIn(rol, rutas)
                pdf_file = rutas[rol]
                self.assertTrue(pdf_file.exists(), f"El manual para {rol} no fue creado")
                self.assertGreater(pdf_file.stat().st_size, 5000, f"El manual para {rol} es demasiado pequeño")

    def test_manual_administrador_incluye_cierres_de_operarios(self):
        """Verifica que el manual de administrador contenga el procedimiento del nuevo botón 'Cierres de Operarios'."""
        import pypdf
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            rutas = generar_todos_los_manuales(tmp_path)
            admin_pdf = rutas["administrador"]

            reader = pypdf.PdfReader(str(admin_pdf))
            texto = "".join(p.extract_text() for p in reader.pages)
            self.assertIn("Cierres de Operarios", texto)
            self.assertIn("Gestionar productos", texto)
            self.assertIn("VENTAS Y DESPACHOS", texto)

    def test_manual_operador_incluye_cierre_de_jornada(self):
        """Verifica que el manual de operador contenga el procedimiento del botón 'Cierre de Jornada'."""
        import pypdf
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            rutas = generar_todos_los_manuales(tmp_path)
            ope_pdf = rutas["operador"]

            reader = pypdf.PdfReader(str(ope_pdf))
            texto = "".join(p.extract_text() for p in reader.pages)
            self.assertIn("Cierre de Jornada", texto)
            self.assertIn("Cargar / Armar Pedido", texto)
            self.assertIn("Desarmar", texto)
            self.assertIn("Eliminar", texto)

    def test_manual_despachador_y_maestro_actualizados(self):
        """Verifica que existan procedimientos de Despachador e incluyan el 6to rol en el Maestro."""
        import pypdf
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            rutas = generar_todos_los_manuales(tmp_path)

            txt_dsp = "".join(p.extract_text() for p in pypdf.PdfReader(str(rutas["despachador"])).pages)
            self.assertIn("Despacho de Pedidos", txt_dsp)
            self.assertIn("QR", txt_dsp)

            txt_mae = "".join(p.extract_text() for p in pypdf.PdfReader(str(rutas["maestro"])).pages)
            self.assertIn("6 Roles", txt_mae)
            self.assertIn("Despach", txt_mae)

    def test_presentacion_ejecutiva_actualizada(self):
        """Verifica que la presentación ejecutiva compile con datos de la arquitectura vigente."""
        import pypdf
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            rutas = generar_todos_los_manuales(tmp_path)
            self.assertIn("presentacion", rutas)
            pres_pdf = rutas["presentacion"]
            self.assertTrue(pres_pdf.exists())
            self.assertGreater(pres_pdf.stat().st_size, 15000)

            reader = pypdf.PdfReader(str(pres_pdf))
            self.assertEqual(len(reader.pages), 7)
            texto = "".join(p.extract_text() for p in reader.pages)
            self.assertIn("SQLite-First", texto)
            self.assertIn("Mayoristas", texto)
            self.assertIn("Mercado Libre", texto)
            self.assertIn("360", texto)

    def test_presentacion_tren_ejecutivo_12_diapositivas(self):
        """Verifica la presentación panorámica 16:9 de 12 diapositivas para el Tren Ejecutivo."""
        import pypdf

        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_out = Path(tmp_dir) / "Presentacion_Tren_Ejecutivo_StockAgent.pdf"
            ruta = generar_presentacion_tren_ejecutivo(pdf_out)
            self.assertTrue(ruta.exists())
            self.assertGreater(ruta.stat().st_size, 20000)

            reader = pypdf.PdfReader(str(ruta))
            self.assertEqual(len(reader.pages), 12)
            texto = "".join(p.extract_text() for p in reader.pages)
            self.assertIn("Tren Ejecutivo", texto)
            self.assertIn("Heatmap", texto)
            self.assertIn("API REST v1", texto)


if __name__ == "__main__":
    unittest.main()
