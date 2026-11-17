"""Tests unitarios para la consolidación y diálogo de Ola de Picking (Wave Picking)."""

import unittest
from unittest.mock import MagicMock

from src.auth import User
from src.orders import Pedido, consolidar_ola_picking
from src.ui.dialogs.dlg_ola_picking import mostrar_dialogo_ola_picking


class TestOlaPicking(unittest.TestCase):
    def test_consolidar_ola_picking_agrupa_items_y_ordena_por_ubicacion(self):
        """Verifica que consolidar_ola_picking sume cantidades y ordene por ubicación física."""
        order_store = MagicMock()
        p1 = Pedido(
            id=1,
            nota_pedido="REM-001",
            numero_pedido="1",
            cliente="Cliente Uno",
            bultos=1,
            logistica="Expreso",
            armador="Lucas",
            tipo_archivo="pdf",
            nombre_archivo="doc1.pdf",
            agregado=False,
            articulos_descontados=3,
            resumen_items="3 un.",
            created_at="2026-11-17 10:00:00",
            estado="descontado",
        )
        p2 = Pedido(
            id=2,
            nota_pedido="REM-002",
            numero_pedido="2",
            cliente="Cliente Dos",
            bultos=1,
            logistica="Canje",
            armador="Lucas",
            tipo_archivo="pdf",
            nombre_archivo="doc2.pdf",
            agregado=False,
            articulos_descontados=5,
            resumen_items="5 un.",
            created_at="2026-11-17 10:30:00",
            estado="descontado",
        )

        order_store.obtener_items_pedido.side_effect = lambda ped_id: (
            [("SKU-B", "Producto B", 2), ("SKU-A", "Producto A", 1)]
            if ped_id == 1
            else [("SKU-B", "Producto B", 3), ("SKU-C", "Producto C", 2)]
        )

        product_store = MagicMock()
        product_store.get_product.side_effect = lambda cod: (
            {"ubicacion": "Pasillo 1 - Estante A"}
            if cod == "SKU-A"
            else ({"ubicacion": "Pasillo 2 - Estante B"} if cod == "SKU-B" else {"ubicacion": ""})
        )

        resultado = consolidar_ola_picking(order_store, [p1, p2], product_store=product_store)

        self.assertEqual(len(resultado), 3)

        # SKU-B debe sumar 2 + 3 = 5 unidades
        item_b = next(it for it in resultado if it["codigo"] == "SKU-B")
        self.assertEqual(item_b["total_unidades"], 5)
        self.assertEqual(len(item_b["pedidos"]), 2)

        # SKU-A debe tener 1 unidad
        item_a = next(it for it in resultado if it["codigo"] == "SKU-A")
        self.assertEqual(item_a["total_unidades"], 1)

        # SKU-C debe tener 2 unidades
        item_c = next(it for it in resultado if it["codigo"] == "SKU-C")
        self.assertEqual(item_c["total_unidades"], 2)

        # El orden debe priorizar los que tienen ubicación (Pasillo 1 antes que Pasillo 2, y al final los sin ubicación)
        codigos_ordenados = [it["codigo"] for it in resultado]
        self.assertEqual(codigos_ordenados, ["SKU-A", "SKU-B", "SKU-C"])

    def test_mostrar_dialogo_ola_picking_abre_modal(self):
        """Verifica la apertura del diálogo modal de ola de picking."""
        interfaz = MagicMock()
        interfaz.usuario_actual = User(id=2, username="picker1", role="picker", active=True)
        interfaz.exigir_roles.return_value = True
        interfaz.superficie = "#222222"
        interfaz.borde = "#333333"
        interfaz.texto = "#ffffff"
        interfaz.secundario = "#888888"

        p1 = Pedido(
            id=10,
            nota_pedido="REM-10",
            numero_pedido="10",
            cliente="Cliente Test",
            bultos=1,
            logistica="Expreso",
            armador="Lucas",
            tipo_archivo="pdf",
            nombre_archivo="doc.pdf",
            agregado=False,
            articulos_descontados=2,
            resumen_items="2 un.",
            created_at="2026-11-17 10:00:00",
            estado="descontado",
        )
        interfaz.order_store.listar_pedidos_pendientes_cierre.return_value = [p1]
        interfaz.order_store.obtener_items_pedido.return_value = [("COD-1", "Prod 1", 2)]

        mostrar_dialogo_ola_picking(interfaz)
        self.assertTrue(interfaz.page.show_dialog.called)
        dlg = interfaz.page.show_dialog.call_args[0][0]
        self.assertIn("Ola de Picking", dlg.title.controls[1].controls[0].value)
