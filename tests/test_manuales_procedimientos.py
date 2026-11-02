import unittest
from pathlib import Path
import tempfile
from Documentacion.manuales_procedimientos import generar_todos_los_manuales


class TestManualesProcedimientos(unittest.TestCase):
    def test_generacion_todos_los_manuales_pdf(self):
        """Verifica que se compilen todos los manuales de procedimiento botón por botón en PDF."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            rutas = generar_todos_los_manuales(tmp_path)

            roles_esperados = ["operador", "administrador", "master", "consulta", "general", "maestro"]
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


if __name__ == "__main__":
    unittest.main()
