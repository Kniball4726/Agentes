import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.remito_parser import parsear_remito


class RemitoParserTests(unittest.TestCase):
    def test_ignores_repeated_page_header_when_reading_quantity(self):
        pages = [
            SimpleNamespace(
                extract_text=lambda: (
                    "Operacion:1-VENTAS A PREPARAR\n"
                    "SUPPLEMENTS SRL\n"
                    "2295 COLAGENO VITAFLEX X 360 G\n"
                    "SABOR ARANDANOS\n"
                    "VITATECH 2\n"
                    "P\uFFFDgina 1 de 2"
                )
            ),
            SimpleNamespace(
                extract_text=lambda: (
                    "55555\n"
                    "11 7123-1530\n"
                    "0001-00024645\n"
                    "Operacion:1-VENTAS A PREPARAR\n"
                    "SUPPLEMENTS SRL\n"
                    "100 PRODUCTO DE PRUEBA 1\n"
                    "OBSERVACIONES\n"
                    "Cant. Articulos: 3\n"
                    "P\uFFFDgina 2 de 2"
                )
            ),
        ]

        with patch(
            "src.remito_parser.PdfReader",
            return_value=SimpleNamespace(pages=pages),
        ):
            resultado = parsear_remito(Path("remito.pdf"))

        self.assertEqual(
            [(item.codigo, item.cantidad) for item in resultado.items],
            [("2295", 2), ("100", 1)],
        )
        self.assertEqual(resultado.articulos_declarados, 3)
        self.assertEqual(resultado.articulos_extraidos, 3)
        self.assertTrue(resultado.verificacion_ok)


if __name__ == "__main__":
    unittest.main()
