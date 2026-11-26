"""Pruebas integrales de Etapa B: reservas en pedidos individuales, conflictos, baja y despacho."""

from __future__ import annotations

from contextlib import closing
from datetime import date, timedelta
import gc
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

import flet as ft

from src.auth import User
from src.core.stock_order_tx import (
    consolidar_reserva_pedido_si_existe,
    detectar_conflictos_stock_y_reservas,
    ejecutar_reserva_y_registro_atomico,
)
from src.orders import OrderStore
from src.products import ProductStore
from src.ui.dialogs.despacho_acciones import aplicar_resultado_escaneo_qr
from src.ui.dialogs.pedidos_baja import (
    mostrar_dialogo_confirmar_anulacion_pedido,
    mostrar_dialogo_confirmar_desarmar_pedido,
    mostrar_dialogo_confirmar_eliminacion_pedido,
)
from src.ui.dialogs.pedidos_crear import mostrar_dialogo_crear_pedido
from src.ui.dialogs.pedidos_crear_modales import _mostrar_alerta_preventiva_quiebre


def _crear_interfaz_falsa(order_store: OrderStore, product_store: ProductStore) -> tuple[Any, list[Any]]:  # type: ignore[name-defined]
    dialogos: list = []

    class FakePage:
        width = 1280
        height = 800

        def show_dialog(self, dlg):
            dialogos.append(dlg)

        def pop_dialog(self):
            if dialogos:
                dialogos.pop()

        def update(self):
            pass

    sm_fake = MagicMock()
    sm_fake.product_store = product_store
    sm_fake.registrar_ingreso_fabrica.side_effect = (
        lambda devs, sobrescribir=False: product_store.catalog_write.register_factory_entries(
            devs, overwrite=sobrescribir
        )
        if hasattr(product_store.catalog_write, "register_factory_entries")
        else None
    )

    class _FakeInterfaz:
        page = FakePage()
        usuario_actual = User(1, "operario1", "operador", True, nombre="Operario Uno")
        modo_oscuro = False
        borde = "#cccccc"
        fondo = "#ffffff"
        fondo_acento = "#eeeeee"
        texto = "#000000"
        secundario = "#666666"
        es_pantalla_movil = False
        menu = SimpleNamespace(ruta_excel_base="Productos.xlsx", carpeta_descuentos="Descuentos")

        def __init__(self) -> None:
            self.order_store = order_store
            self.product_store = product_store
            self.notificaciones: list[str] = []
            self._deps = SimpleNamespace(
                stock_manager_factory=lambda **_kwargs: sm_fake,
            )

        def exigir_roles(self, *roles: str) -> bool:
            return bool(self.usuario_actual and self.usuario_actual.role in roles)

        def notificar(self, mensaje: str, *_args, **_kwargs) -> None:
            self.notificaciones.append(mensaje)

        def boton_dialogo(self, texto: str, on_click) -> ft.TextButton:
            return ft.TextButton(texto, on_click=on_click)

        def ancho_adaptable(self, ancho: int) -> int:
            return ancho

        def actualizar_listas(self) -> None:
            pass

        def sincronizar_sesiones(self, **_kwargs) -> None:
            pass

        def reproducir_sonido(self, _tipo: str) -> None:
            pass

    return _FakeInterfaz(), dialogos


from typing import Any  # noqa: E402


def _fake_stock_mgr_factory(product_store: ProductStore, descuentos: list[Any]):
    sm = MagicMock()
    sm.product_store = product_store
    reporte = SimpleNamespace(
        reporte_stock=SimpleNamespace(descuentos_aplicados=descuentos),
        documentos_verificados=[],
    )
    return lambda: (sm, reporte)


class TestEtapaBOrderReservations(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        self.product_store = ProductStore(self.base / "productos.sqlite3")
        self.order_store = OrderStore(self.base / "pedidos.sqlite3")
        with closing(self.product_store._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO products (code, name, stock, stock_minimo, stock_maximo, active, ubicacion)
                VALUES ('BOLT', 'Bulón Hexagonal', 10, 2, 30, 1, 'A-01-1')
                """
            )

    def tearDown(self) -> None:
        del self.order_store
        del self.product_store
        gc.collect()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_01_detectar_conflictos_protege_stock_reservado_por_olas(self) -> None:
        self.product_store.reservar_stock({"BOLT": 7}, referencia_id="OLA-PRE", referencia_tipo="ola_picking")

        # Pedido pide 5: físicamente quedarían 5 (>0), pero disponible neto es 3 (<5)
        descuento_sim = SimpleNamespace(
            codigo="BOLT",
            nombre_producto="Bulón Hexagonal",
            stock_anterior=10,
            cantidad_descontada=5,
            stock_nuevo=5,
        )
        conflictos = detectar_conflictos_stock_y_reservas([descuento_sim], self.product_store)
        self.assertEqual(len(conflictos), 1)
        self.assertEqual(conflictos[0]["tipo"], "CONFLICTO_RESERVA")
        self.assertEqual(conflictos[0]["stock_reservado"], 7)
        self.assertEqual(conflictos[0]["stock_disponible"], 3)

        interfaz, dialogos = _crear_interfaz_falsa(self.order_store, self.product_store)
        # En modo solo_reservar no habilita forzado de descuento
        _mostrar_alerta_preventiva_quiebre(
            interfaz,
            "REM-CONFL",
            "Cliente Sur",
            conflictos,
            lambda: None,
            solo_reservar=True,
        )
        dlg = dialogos[-1]
        self.assertIsInstance(dlg, ft.AlertDialog)
        self.assertIn("Comprometido en Reservas", dlg.title.controls[1].value)
        self.assertEqual(len(dlg.actions), 1)

        # En modo descuento tradicional sí permite "Autorizar y Descontar" explícitamente
        _mostrar_alerta_preventiva_quiebre(
            interfaz,
            "REM-CONFL",
            "Cliente Sur",
            conflictos,
            lambda: None,
            solo_reservar=False,
        )
        dlg_desc = dialogos[-1]
        self.assertEqual(len(dlg_desc.actions), 2)
        self.assertEqual(dlg_desc.actions[0].content, "Autorizar y Descontar")

    def test_02_reserva_individual_atomica_y_rollback_si_falla_order_store(self) -> None:
        self.product_store.reservar_stock({"BOLT": 7}, referencia_id="OLA-PRE", referencia_tipo="ola_picking")
        descuento_ok = [
            SimpleNamespace(
                codigo="BOLT",
                nombre_producto="Bulón Hexagonal",
                stock_anterior=10,
                cantidad_descontada=3,
                stock_nuevo=7,
            )
        ]

        res = ejecutar_reserva_y_registro_atomico(
            order_store=self.order_store,
            stock_mgr_factory=_fake_stock_mgr_factory(self.product_store, descuento_ok),
            tx_id="PEDRES_REM-1",
            remito="REM-RES-1",
            num_ped="101",
            cli="Ferretería Oeste",
            bultos_val=1,
            log="Domicilio",
            f_retiro="Sin fecha",
            armador_nom="Operario Uno",
            es_agregado=False,
            tipo_archivo="pdf",
            nombre_archivo="r1.pdf",
            hash_comprobante="h1",
        )
        self.assertIsNotNone(res)
        resumen = self.product_store.obtener_resumen_stock_disponible("BOLT")
        self.assertEqual(resumen["stock_fisico"], 10)
        self.assertEqual(resumen["stock_reservado"], 10)
        self.assertEqual(resumen["stock_disponible"], 0)
        self.assertIsNotNone(self.order_store.buscar_pedido_por_nota("REM-RES-1"))

        # Idempotencia por tx_id
        res_dup = ejecutar_reserva_y_registro_atomico(
            order_store=self.order_store,
            stock_mgr_factory=_fake_stock_mgr_factory(self.product_store, descuento_ok),
            tx_id="PEDRES_REM-1",
            remito="REM-RES-1-BIS",
            num_ped="102",
            cli="Ferretería Oeste",
            bultos_val=1,
            log="Domicilio",
            f_retiro="Sin fecha",
            armador_nom="Operario Uno",
            es_agregado=False,
            tipo_archivo="pdf",
            nombre_archivo="r1b.pdf",
            hash_comprobante="h1b",
        )
        self.assertIsNone(res_dup)

        # Liberar OLA-PRE para dejar saldo libre y probar rollback compensatorio ante falla de OrderStore
        self.product_store.liberar_reserva("OLA-PRE", referencia_tipo="ola_picking")
        order_store_fallo = MagicMock()
        order_store_fallo.existe_nota_pedido.return_value = False
        order_store_fallo.registrar_transaccion_idempotente.return_value = True
        order_store_fallo.registrar_pedido.side_effect = RuntimeError("Falla SQLite pedidos")

        with self.assertRaises(RuntimeError):
            ejecutar_reserva_y_registro_atomico(
                order_store=order_store_fallo,
                stock_mgr_factory=_fake_stock_mgr_factory(self.product_store, descuento_ok),
                tx_id="PEDRES_FALLO",
                remito="REM-FALLO",
                num_ped="103",
                cli="Cliente Falla",
                bultos_val=1,
                log="Domicilio",
                f_retiro="Sin fecha",
                armador_nom="Operario Uno",
                es_agregado=False,
                tipo_archivo="pdf",
                nombre_archivo="rfallo.pdf",
                hash_comprobante="hf",
            )

        # Rollback debe haber liberado la reserva temporal de REM-FALLO
        self.assertEqual(
            self.product_store.listar_reservas(estado="activa", referencia_tipo="pedido", referencia_id="REM-FALLO"),
            [],
        )
        order_store_fallo.liberar_transaccion_idempotente.assert_called_once_with("PEDRES_FALLO")

    def test_03_baja_anular_desarmar_eliminar_libera_reserva_sin_duplicar_stock(self) -> None:
        interfaz, dialogos = _crear_interfaz_falsa(self.order_store, self.product_store)

        def _crear_reservado(remito: str, cant: int):
            desc = [
                SimpleNamespace(
                    codigo="BOLT",
                    nombre_producto="Bulón Hexagonal",
                    stock_anterior=10,
                    cantidad_descontada=cant,
                    stock_nuevo=10 - cant,
                )
            ]
            _, _, _, ped, _ = ejecutar_reserva_y_registro_atomico(
                order_store=self.order_store,
                stock_mgr_factory=_fake_stock_mgr_factory(self.product_store, desc),
                tx_id=f"TX_{remito}",
                remito=remito,
                num_ped=remito,
                cli="Cliente Baja",
                bultos_val=1,
                log="Domicilio",
                f_retiro="Sin fecha",
                armador_nom="Operario Uno",
                es_agregado=False,
                tipo_archivo="pdf",
                nombre_archivo=f"{remito}.pdf",
                hash_comprobante=f"hash_{remito}",
            )
            return ped

        # 1) Anulación directa
        p1 = _crear_reservado("REM-ANU-1", 4)
        self.assertEqual(self.product_store.obtener_resumen_stock_disponible("BOLT")["stock_disponible"], 6)
        mostrar_dialogo_confirmar_anulacion_pedido(interfaz, p1)
        dialogos[-1].actions[0].on_click(None)
        res1 = self.product_store.obtener_resumen_stock_disponible("BOLT")
        self.assertEqual(res1["stock_fisico"], 10)
        self.assertEqual(res1["stock_reservado"], 0)
        self.assertEqual(res1["stock_disponible"], 10)
        self.assertEqual(self.order_store.buscar_pedido_por_nota("REM-ANU-1").estado, "anulado")

        # 2) Desarmado lógico
        p2 = _crear_reservado("REM-DES-2", 3)
        mostrar_dialogo_confirmar_desarmar_pedido(interfaz, p2)
        dialogos[-1].actions[0].on_click(None)
        res2 = self.product_store.obtener_resumen_stock_disponible("BOLT")
        self.assertEqual(res2["stock_fisico"], 10)
        self.assertEqual(res2["stock_disponible"], 10)
        self.assertEqual(self.order_store.buscar_pedido_por_nota("REM-DES-2").estado, "anulado")

        # 3) Eliminación física
        p3 = _crear_reservado("REM-DEL-3", 2)
        mostrar_dialogo_confirmar_eliminacion_pedido(interfaz, p3)
        dialogos[-1].actions[0].on_click(None)
        res3 = self.product_store.obtener_resumen_stock_disponible("BOLT")
        self.assertEqual(res3["stock_fisico"], 10)
        self.assertEqual(res3["stock_disponible"], 10)
        self.assertIsNone(self.order_store.buscar_pedido_por_nota("REM-DEL-3"))

        # 4) Confirmar que un pedido tradicional SIN reserva activa SÍ restituye stock físico
        with closing(self.product_store._connect()) as conn, conn:
            conn.execute("UPDATE products SET stock = 7 WHERE code = 'BOLT'")
        p_trad = self.order_store.registrar_pedido(
            nota_pedido="REM-TRAD-4",
            numero_pedido="T4",
            cliente="Cliente Tradicional",
            bultos=1,
            logistica="Domicilio",
            armador="Operario Uno",
            tipo_archivo="pdf",
            nombre_archivo="t4.pdf",
            articulos_descontados=3,
            items=[("BOLT", "Bulón Hexagonal", 3)],
        )
        interfaz_real_sm, dlgs_t = _crear_interfaz_falsa(self.order_store, self.product_store)

        class _SmIngreso:
            product_store = self.product_store

            def registrar_ingreso_fabrica(self, devs: dict[str, int], sobrescribir: bool = False):
                with closing(self.product_store._connect()) as conn, conn:
                    for cod, qty in devs.items():
                        conn.execute("UPDATE products SET stock = stock + ? WHERE code = ?", (qty, cod))

        interfaz_real_sm._deps = SimpleNamespace(stock_manager_factory=lambda **_kw: _SmIngreso())
        mostrar_dialogo_confirmar_anulacion_pedido(interfaz_real_sm, p_trad)
        dlgs_t[-1].actions[0].on_click(None)
        self.assertEqual(self.product_store.obtener_resumen_stock_disponible("BOLT")["stock_fisico"], 10)

    def test_04_despacho_qr_consolida_reserva_y_checkbox_ui(self) -> None:
        fv = (date.today() + timedelta(days=10)).isoformat()
        self.product_store.registrar_lote("BOLT", "L-ORD-1", 6, fecha_vencimiento=fv, ubicacion="A-01-1")

        desc = [
            SimpleNamespace(
                codigo="BOLT",
                nombre_producto="Bulón Hexagonal",
                stock_anterior=10,
                cantidad_descontada=4,
                stock_nuevo=6,
            )
        ]
        _, _, _, ped, _ = ejecutar_reserva_y_registro_atomico(
            order_store=self.order_store,
            stock_mgr_factory=_fake_stock_mgr_factory(self.product_store, desc),
            tx_id="TX_DISP_1",
            remito="REM-DISP-1",
            num_ped="D1",
            cli="Cliente Despacho",
            bultos_val=1,
            log="Domicilio",
            f_retiro="Sin fecha",
            armador_nom="Operario Uno",
            es_agregado=False,
            tipo_archivo="pdf",
            nombre_archivo="d1.pdf",
            hash_comprobante="hd1",
        )
        interfaz, dialogos = _crear_interfaz_falsa(self.order_store, self.product_store)
        estado_ui = {"vista": "pendientes", "pedido_destacado_id": ped.id}
        aplicar_resultado_escaneo_qr(
            interfaz,
            {"completado": True, "pedido": ped, "mensaje": "Despachado OK"},
            estado_ui,
            lambda *_a, **_kw: None,
        )

        resumen_post = self.product_store.obtener_resumen_stock_disponible("BOLT")
        self.assertEqual(resumen_post["stock_fisico"], 6)
        self.assertEqual(resumen_post["stock_reservado"], 0)
        lote_post = self.product_store.listar_lotes_fefo("BOLT")[0]
        self.assertEqual(lote_post["stock"], 2)

        # Llamado directo también es idempotente
        self.assertIsNone(consolidar_reserva_pedido_si_existe(self.product_store, "REM-DISP-1"))

        # Verificar checkbox "Solo reservar stock" en mostrar_dialogo_crear_pedido
        mostrar_dialogo_crear_pedido(interfaz)
        dlg_crear = dialogos[-1]
        col = dlg_crear.content.content
        chk = [c for c in col.controls if isinstance(c, ft.Checkbox) and "reservar" in (c.label or "").lower()][0]
        btn_conf = dlg_crear.actions[0]
        self.assertEqual(btn_conf.content, "Confirmar y Descontar")
        chk.value = True
        chk.on_change(None)
        self.assertEqual(btn_conf.content, "Confirmar y Reservar")


if __name__ == "__main__":
    unittest.main()
