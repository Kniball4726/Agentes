import tempfile
import unittest
from pathlib import Path
import openpyxl

from src.mercado_full_parser import parsear_archivo_mercado_full


class TestMercadoFullParser(unittest.TestCase):
    def test_parsear_archivo_mercado_full_xlsx(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            archivo = Path(tmp_dir) / "Envio_Full_Test.xlsx"
            wb = openpyxl.Workbook()
            ws = wb.active
            assert ws is not None
            ws.title = "Envío Full"

            # Encabezados
            ws.append(["Plan de Envío #12345 - Mercado Libre Full"])
            ws.append(["Fecha: 24/10/2026"])
            ws.append(["SKU", "Título de la publicación", "Unidades enviadas"])
            # Datos
            ws.append(["ART-001", "Filtro de Aceite Universal", 10])
            ws.append(["ART-002", "Pastillas de Freno Delanteras", 5])
            ws.append(["ART-001", "Filtro de Aceite Universal (Bulto 2)", 15])
            ws.append(["TOTAL", "", 30])
            wb.save(archivo)

            totales, detalle = parsear_archivo_mercado_full(archivo)

            self.assertEqual(len(totales), 2)
            self.assertEqual(totales["ART-001"], 25)
            self.assertEqual(totales["ART-002"], 5)
            self.assertEqual(len(detalle), 3)

    def test_parsear_archivo_mercado_full_headers_variados(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            archivo = Path(tmp_dir) / "Manifest_Full.xlsx"
            wb = openpyxl.Workbook()
            ws = wb.active
            assert ws is not None
            ws.append(["Código", "Descripción", "Cantidad"])
            ws.append(["1001", "Bujía NGK", 20])
            ws.append(["1002", "Cable de Bujía", 4])
            wb.save(archivo)

            totales, detalle = parsear_archivo_mercado_full(archivo)

            self.assertEqual(totales["1001"], 20)
            self.assertEqual(totales["1002"], 4)

    def test_archivo_no_existente(self):
        with self.assertRaises(FileNotFoundError):
            parsear_archivo_mercado_full("archivo_fantasma.xlsx")

    def test_extension_invalida(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            archivo = Path(tmp_dir) / "test.txt"
            archivo.write_text("dummy")
            with self.assertRaises(ValueError):
                parsear_archivo_mercado_full(archivo)


if __name__ == "__main__":
    unittest.main()
