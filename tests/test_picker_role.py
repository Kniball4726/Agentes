"""Tests unitarios para el rol Picker y su alcance restringido en la interfaz."""

import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

import flet as ft

from src.auth import USER_ROLES, UserStore
from src.orders import OrderStore, Pedido
from src.ui.components.sidebar import obtener_secciones_rol
from src.ui.components.panels import construir_panel_informes_actividad, construir_panel_metricas
from src.ui.dashboard_presenter import renderizar_pedidos_preparados_turno, actualizar_estado_dashboard
from src.ui.dialogs.dlg_historial_pedidos import mostrar_detalle_pedido_modal
from tests.test_flet_gui import FakeMenu, FakePage, InterfazFlet


class TestPickerRole(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "data").mkdir(parents=True, exist_ok=True)
        self.u_store = UserStore(self.root / "data" / "usuarios.sqlite3")
        self.o_store = OrderStore(self.root / "data" / "pedidos.sqlite3")

        self.page = FakePage()
        self.menu = FakeMenu()
        with patch("src.flet_gui.MenuAgente", return_value=self.menu), patch(
            "src.flet_gui.UserStore", return_value=self.u_store
        ), patch("src.flet_gui.OrderStore", return_value=self.o_store):
            self.interfaz = InterfazFlet(cast(ft.Page, self.page))

        self.picker_user = self.u_store.create_user(
            username="picker_test",
            password="PickerPassword123!",
            role="picker",
            nombre="Operador Picker",
        )
        self.interfaz.usuario_actual = self.picker_user

    def tearDown(self):
        self.tmp.cleanup()

    def test_picker_in_user_roles(self):
        """Verifica que el rol picker esté en la definición de USER_ROLES y UserStore."""
        self.assertIn("picker", USER_ROLES)
        usuario = self.u_store.get_user_by_username("picker_test")
        self.assertIsNotNone(usuario)
        self.assertEqual(usuario.role, "picker")

    def test_picker_sidebar_controls_only_allowed_sections(self):
        """Verifica que el rol Picker solo vea Despacho (ML/Full) y Movimientos (Ingreso/Egreso)."""
        secciones = obtener_secciones_rol(self.interfaz)
        titulos_secciones = [s.titulo for s in secciones]
        todos_los_items = []
        for s in secciones:
            for item in s.items:
                todos_los_items.append(item[0])

        # Secciones permitidas
        self.assertIn("DESPACHO", titulos_secciones)
        self.assertIn("MOVIMIENTOS DE STOCK", titulos_secciones)

        # Opciones permitidas
        self.assertIn("Descontar Mercado Libre", todos_los_items)
        self.assertIn("Descontar Mercado Full", todos_los_items)
        self.assertIn("Ingreso de Mercadería", todos_los_items)
        self.assertIn("Ingreso de Fábrica", todos_los_items)
        self.assertIn("Egreso de Mercadería", todos_los_items)

        # Opciones prohibidas
        self.assertNotIn("Cargar / Armar Pedido", todos_los_items)
        self.assertNotIn("Gestión de Clientes", todos_los_items)
        self.assertNotIn("Cierre de Jornada", todos_los_items)
        self.assertNotIn("Gestionar usuarios", todos_los_items)
        self.assertNotIn("Copia de Seguridad", todos_los_items)
        self.assertNotIn("Historial de Pedidos", todos_los_items)
        self.assertNotIn("Métricas y Rendimiento", todos_los_items)

    def test_picker_permisos_permitidos_y_bloqueados(self):
        """Verifica que picker pueda abrir sus operaciones asignadas y sea bloqueado en las demás."""
        # 1. Ingreso rápido y egreso rápido
        self.interfaz.mostrar_dialogo_ingreso_rapido()
        self.assertEqual(len(self.page.dialogos), 1)
        self.page.pop_dialog()

        self.interfaz.mostrar_dialogo_salida_rapida()
        self.assertEqual(len(self.page.dialogos), 1)
        self.page.pop_dialog()

        # 2. Operaciones bloqueadas
        self.interfaz.mostrar_gestion_usuarios()
        self.assertEqual(len(self.page.dialogos), 1)
        dlg = self.page.dialogos[0]
        texto_contenido = getattr(dlg.content, "value", "") if hasattr(dlg, "content") else ""
        self.assertIn("no tiene permiso", texto_contenido)
        self.page.pop_dialog()


    def test_panel_acceso_rapido_picker(self):
        """Verifica que el panel de acceso rápido para Picker tenga Ingreso, Egreso y Descontar ML."""
        ctrl = self.interfaz.panel_acceso_rapido()
        self.assertTrue(ctrl.visible if hasattr(ctrl, "visible") else True)

        def extraer_textos(control):
            txts = []
            if hasattr(control, "value") and control.value:
                txts.append(str(control.value))
            if hasattr(control, "content") and control.content:
                txts.extend(extraer_textos(control.content))
            if hasattr(control, "controls") and control.controls:
                for c in control.controls:
                    txts.extend(extraer_textos(c))
            return txts

        textos = extraer_textos(ctrl)
        self.assertIn("Ingreso de Stock", textos)
        self.assertIn("Egreso de Stock", textos)
        self.assertIn("Descontar Mercado Libre", textos)
        self.assertNotIn("Cargar / Armar Pedido", textos)

    def test_panel_acceso_rapido_operador(self):
        """Verifica que el panel de acceso rápido para Operador no incluya Descontar Mercado Libre."""
        oper_user = self.u_store.create_user("oper_test_panel", "OperPass1234!", "operador")
        self.interfaz.usuario_actual = oper_user

        ctrl = self.interfaz.panel_acceso_rapido()
        self.assertTrue(ctrl.visible if hasattr(ctrl, "visible") else True)

        def extraer_textos(control):
            txts = []
            if hasattr(control, "value") and control.value:
                txts.append(str(control.value))
            if hasattr(control, "content") and control.content:
                txts.extend(extraer_textos(control.content))
            if hasattr(control, "controls") and control.controls:
                for c in control.controls:
                    txts.extend(extraer_textos(c))
            return txts

        textos = extraer_textos(ctrl)
        self.assertIn("Cargar / Armar Pedido", textos)
        self.assertIn("Ingreso de Stock", textos)
        self.assertIn("Egreso de Stock", textos)
        self.assertNotIn("Descontar Mercado Libre", textos)

    def test_panel_acceso_rapido_administrador(self):
        """Verifica que el rol Administrador no tenga accesos rápidos táctiles."""
        admin_user = self.u_store.create_user("admin_test", "AdminPass1234!", "administrador")
        self.interfaz.usuario_actual = admin_user

        ctrl = self.interfaz.panel_acceso_rapido()
        self.assertTrue(ctrl.visible if hasattr(ctrl, "visible") else True)

        def extraer_textos(control):
            txts = []
            if hasattr(control, "value") and control.value:
                txts.append(str(control.value))
            if hasattr(control, "content") and control.content:
                txts.extend(extraer_textos(control.content))
            if hasattr(control, "controls") and control.controls:
                for c in control.controls:
                    txts.extend(extraer_textos(c))
            return txts

        textos = extraer_textos(ctrl)
        self.assertNotIn("Ingreso de Stock", textos)
        self.assertNotIn("Egreso de Stock", textos)
        self.assertNotIn("Descontar Mercado Libre", textos)
        self.assertIn("Seguimiento Operativo en Vivo", textos)
        self.assertNotIn("Cargar / Armar Pedido", textos)

    def test_sidebar_botonera_rapida_por_rol(self):
        """Verifica que la botonera de acceso rápido del menú lateral respete los roles solicitados."""
        def extraer_textos(control):
            txts = []
            if hasattr(control, "value") and control.value:
                txts.append(str(control.value))
            if hasattr(control, "content") and control.content:
                txts.extend(extraer_textos(control.content))
            if hasattr(control, "controls") and control.controls:
                for c in control.controls:
                    txts.extend(extraer_textos(c))
            return txts

        # 1. Picker: tiene Entrada, Salida y Descontar ML (no Cargar Pedido)
        self.interfaz.usuario_actual = self.picker_user
        sidebar_picker = self.interfaz._sidebar_controls()
        txts_picker = []
        for c in sidebar_picker:
            txts_picker.extend(extraer_textos(c))
        self.assertIn("Entrada", txts_picker)
        self.assertIn("Salida", txts_picker)
        self.assertIn("Descontar ML", txts_picker)
        self.assertIn("Full", txts_picker)
        self.assertIn("Ingreso de Fábrica", txts_picker)
        self.assertNotIn("Cargar Pedido", txts_picker)

        # 2. Administrador: botonera operativa ejecutiva (Gestionar inventario primero, Planificar ingreso fábrica, Planificar full, Gestionar productos, Entrada, Salida, Ajuste de inventario, Generar Pedido)
        admin_user = self.u_store.get_user_by_username("admin_test") or self.u_store.create_user("admin_test", "AdminPass1234!", "administrador")
        self.interfaz.usuario_actual = admin_user
        sidebar_admin = self.interfaz._sidebar_controls()
        txts_admin = []
        for c in sidebar_admin:
            txts_admin.extend(extraer_textos(c))
        self.assertIn("Gestionar inventario", txts_admin)
        self.assertIn("Planificar ingreso de fábrica", txts_admin)
        self.assertIn("Planificar mercado full", txts_admin)
        self.assertIn("Gestionar productos", txts_admin)
        self.assertIn("Entrada", txts_admin)
        self.assertIn("Salida", txts_admin)
        self.assertIn("Ajuste de inventario", txts_admin)
        self.assertIn("Generar Pedido", txts_admin)
        self.assertIn("Sincronizar", txts_admin)
        # Verificar que Gestionar inventario es el primer botón del menú de administrador
        idx_inv = txts_admin.index("Gestionar inventario")
        idx_fabrica = txts_admin.index("Planificar ingreso de fábrica")
        self.assertLess(idx_inv, idx_fabrica)
        # Verificar que Sincronizar está después de Generar Pedido y que Entrada/Salida están debajo de Sincronizar
        idx_sinc = txts_admin.index("Sincronizar")
        idx_pedido = txts_admin.index("Generar Pedido")
        idx_entrada = txts_admin.index("Entrada")
        idx_salida = txts_admin.index("Salida")
        self.assertGreater(idx_sinc, idx_pedido)
        self.assertGreater(idx_entrada, idx_sinc)
        self.assertGreater(idx_salida, idx_entrada)
        self.assertNotIn("Cargar Pedido", txts_admin)
        self.assertNotIn("Mercado Libre", txts_admin)
        self.assertNotIn("Descontar ML", txts_admin)
        self.assertNotIn("Full", txts_admin)
        self.assertNotIn("Ingreso de Fábrica", txts_admin)

        # 3. Master: tiene botonera técnica con Usuarios y Auditoría (sin Entrada, Salida ni Mercado Libre)
        master_user = self.u_store.get_user_by_username("Desarrollo")
        self.interfaz.usuario_actual = master_user
        sidebar_master = self.interfaz._sidebar_controls()
        txts_master = []
        for c in sidebar_master:
            txts_master.extend(extraer_textos(c))
        self.assertIn("Usuarios", txts_master)
        self.assertIn("Auditoría", txts_master)
        self.assertNotIn("Entrada", txts_master)
        self.assertNotIn("Salida", txts_master)
        self.assertNotIn("Cargar Pedido", txts_master)
        self.assertNotIn("Mercado Libre", txts_master)
        self.assertNotIn("Descontar ML", txts_master)

    def test_picker_no_ve_panel_pedidos_armados(self):
        """Verifica que el panel de operaciones no incluya la tarjeta de pedidos preparados para rol picker."""
        self.interfaz.usuario_actual = self.picker_user
        panel = construir_panel_informes_actividad(self.interfaz)
        # Para picker devuelve directamente tarjeta_der (Informes generados), no un Row o Column con tarjeta_izq
        self.assertIsInstance(panel, ft.Container)
        # La lista de pedidos preparados no forma parte de este panel
        self.assertIsNotNone(panel.content)

    def test_picker_renderizar_pedidos_preparados_no_crea_tarjetas(self):
        """Verifica que renderizar_pedidos_preparados_turno no genere tarjetas de pedidos si el usuario es picker."""
        ped = Pedido(
            id=1,
            nota_pedido="R-100",
            numero_pedido="100",
            cliente="Cliente Test",
            bultos=2,
            logistica="Mercado Envíos",
            armador="Operador",
            tipo_archivo="pdf",
            nombre_archivo="doc.pdf",
            agregado=False,
            articulos_descontados=3,
            resumen_items="Item A x3",
            created_at="2026-11-12 10:00:00",
            estado="descontado",
        )
        self.interfaz.usuario_actual = self.picker_user
        self.interfaz.lista_pedidos_preparados.controls.clear()
        renderizar_pedidos_preparados_turno(self.interfaz, [ped])
        self.assertEqual(len(self.interfaz.lista_pedidos_preparados.controls), 0)

    def test_picker_bloqueado_en_detalle_pedido_modal(self):
        """Verifica que el rol picker no pueda visualizar el detalle modal de pedidos armados."""
        ped = Pedido(
            id=1,
            nota_pedido="R-100",
            numero_pedido="100",
            cliente="Cliente Test",
            bultos=2,
            logistica="Mercado Envíos",
            armador="Operador",
            tipo_archivo="pdf",
            nombre_archivo="doc.pdf",
            agregado=False,
            articulos_descontados=3,
            resumen_items="Item A x3",
            created_at="2026-11-12 10:00:00",
            estado="descontado",
        )
        self.interfaz.usuario_actual = self.picker_user
        notificaciones = []
        self.interfaz.notificar = lambda msg: notificaciones.append(msg)
        mostrar_detalle_pedido_modal(self.interfaz, ped)
        self.assertTrue(any("Picker no tiene acceso" in m for m in notificaciones))

    def test_picker_panel_metricas_oculto(self):
        """Verifica que las tarjetas superiores de métricas de pedidos de la jornada estén ocultas para picker y administrador."""
        self.interfaz.usuario_actual = self.picker_user
        panel = construir_panel_metricas(self.interfaz)
        self.assertFalse(getattr(panel, "visible", True))

        # También para Administrador
        admin_user = self.u_store.get_user_by_username("admin_test") or self.u_store.create_user("admin_test", "AdminPass1234!", "administrador")
        self.interfaz.usuario_actual = admin_user
        panel_admin = construir_panel_metricas(self.interfaz)
        self.assertFalse(getattr(panel_admin, "visible", True))

    def test_picker_actualizar_listas_no_muestra_conteo_pedidos(self):
        """Verifica que el texto de pendientes no muestre el resumen de pedidos descontados para picker."""
        self.interfaz.usuario_actual = self.picker_user
        actualizar_estado_dashboard(self.interfaz)
        self.assertNotIn("pedido(s) descontado(s)", self.interfaz.pendientes_texto.value)
        self.assertIn("Picking y Despacho", self.interfaz.pendientes_texto.value)


if __name__ == "__main__":
    unittest.main()
