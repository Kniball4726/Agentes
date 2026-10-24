import tempfile
import unittest
from pathlib import Path
import openpyxl

from src.physical_stock_parser import parsear_excel_stock_fisico


class TestPhysicalStockParser(unittest.TestCase):
    def test_parsear_excel_stock_fisico_incluye_cero_y_prioriza_columna(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            archivo = Path(tmp_dir) / "Relevamiento_Fisico.xlsx"
            wb = openpyxl.Workbook()
            ws = wb.active
            assert ws is not None
            ws.append(["Relevamiento de Inventario Físico - Depósito"])
            ws.append(["Código", "Producto", "Stock Digital", "Stock Físico"])
            ws.append(["101", "Filtro de Aire", 15, 12])
            ws.append(["102", "Bujía Encendido", 8, 0])
            ws.append(["103", "Correa Distribución", 5, 7])
            ws.append(["TOTAL", "", 28, 19])
            wb.save(archivo)

            totales, detalle = parsear_excel_stock_fisico(archivo)

            self.assertEqual(totales["101"], 12)
            self.assertEqual(totales["102"], 0)
            self.assertEqual(totales["103"], 7)
            self.assertEqual(len(detalle), 3)


if __name__ == "__main__":
    unittest.main()
