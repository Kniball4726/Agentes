import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import xlwt

from src.menu import MenuAgente


class RestorationTests(unittest.TestCase):
    def crear_menu(self, root: Path) -> MenuAgente:
        menu = MenuAgente.__new__(MenuAgente)
        menu.carpeta_mayoristas = root / "Mayoristas"
        menu.carpeta_canjes = root / "Canjes"
        menu.carpeta_mercado_libre = root / "MercadoLibre"
        menu.carpeta_descuentos = root / "descuentos"
        menu.carpeta_descontados = root / "descontados"
        for carpeta in (
            menu.carpeta_mayoristas,
            menu.carpeta_canjes,
            menu.carpeta_mercado_libre,
            menu.carpeta_descuentos,
            menu.carpeta_descontados / "Mayoristas",
            menu.carpeta_descontados / "Canjes",
            menu.carpeta_descontados / "MercadoLibre",
        ):
            carpeta.mkdir(parents=True)
        return menu

    @staticmethod
    def crear_informe(
        ruta: Path,
        documentos: list[tuple[str, str]],
        encabezado: str = "PEDIDOS CON PRODUCTOS DESCONTADOS",
        columna_encabezado: int = 0,
        encabezado_resumen: bool = False,
    ) -> None:
        libro = xlwt.Workbook()
        hoja = libro.add_sheet("Informe")
        fila_encabezado = 0
        if encabezado_resumen:
            hoja.write(0, 0, "PRODUCTOS CON DESCUENTO")
            hoja.write(0, columna_encabezado, encabezado)
            hoja.write(1, 0, 87)
            fila_encabezado = 3
        hoja.write(fila_encabezado, columna_encabezado, encabezado)
        fila_columnas = fila_encabezado + 1
        hoja.write(fila_columnas, 0, "TIPO")
        hoja.write(fila_columnas, 1, "CLIENTE")
        hoja.write(fila_columnas, 2, "N° REMITO / PEDIDO")
        for fila, (tipo, referencia) in enumerate(documentos, start=fila_columnas + 1):
            hoja.write(fila, 0, tipo)
            hoja.write(fila, 2, referencia)
        libro.save(str(ruta))

    def test_restores_only_documents_discounted_on_selected_date(self):
        with tempfile.TemporaryDirectory() as temporal:
            root = Path(temporal)
            menu = self.crear_menu(root)
            informe_22 = menu.carpeta_descuentos / "Descuento22-10-2026_12-00-00.xls"
            informe_21 = menu.carpeta_descuentos / "Descuento21-10-2026_12-00-00.xls"
            self.crear_informe(
                informe_22,
                [
                    ("Remito Mayorista", "0001-00012345"),
                    ("Canje", "CANJE-CANJE Ana"),
                ],
            )
            self.crear_informe(
                informe_21,
                [("Remito Mayorista", "0001-00023456")],
                encabezado="PEDIDOS PROCESADOS",
                columna_encabezado=2,
                encabezado_resumen=True,
            )
            (menu.carpeta_descuentos / "Descuento21-10-2026_12-00-00.pdf").write_bytes(
                b"PDF companion report"
            )

            archivados = menu.carpeta_descontados
            (archivados / "Mayoristas" / "12345.pdf").write_text("remito")
            (archivados / "Mayoristas" / "23456.pdf").write_text("otro remito")
            (archivados / "Canjes" / "CANJE Ana.xlsx").write_text("canje")

            self.assertEqual(
                menu.fechas_descuento_disponibles(),
                ["2026-10-22", "2026-10-21"],
            )
            self.assertEqual(
                len(menu._obtener_generados()),
                3,
            )
            with patch("builtins.print"):
                restaurados = menu.restaurar_para_pruebas("2026-10-22")

            self.assertEqual(restaurados, 2)
            self.assertTrue((menu.carpeta_mayoristas / "12345.pdf").exists())
            self.assertTrue((menu.carpeta_canjes / "CANJE Ana.xlsx").exists())
            self.assertFalse((menu.carpeta_mayoristas / "23456.pdf").exists())


if __name__ == "__main__":
    unittest.main()
