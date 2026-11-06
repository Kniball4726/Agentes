import sys
import unittest
from pathlib import Path
import tempfile
import flet as ft

from src.user_store import User, UserStore
from src.orders_store import OrderStore, Pedido
from src.ui.dialogs.dlg_cierre import (
    mostrar_dialogo_cierres_operarios,
    mostrar_detalle_pedidos_cierre,
)


class DummyWindow:
    def __init__(self):
        self.maximized = False
        self.icon = ""


class DummyPage:
    def __init__(self):
        self.controls = []
        self.dialogos = []
        self.snack_bar = None
        self.window = DummyWindow()
        self.web = False

    def show_dialog(self, dlg):
        self.dialogos.append(dlg)

    def pop_dialog(self):
        if self.dialogos:
            return self.dialogos.pop()
        return None

    def update(self):
        pass


class DummyMenu:
    def __init__(self, tmp_path: Path):
        self.carpeta_descuentos = tmp_path / "Descuentos"
        self.carpeta_descuentos.mkdir(parents=True, exist_ok=True)
        self.ruta_excel_base = tmp_path / "Productos.xlsx"


class DummyInterfaz:
    def __init__(self, db_path: Path, tmp_path: Path, role: str = "administrador"):
        self.order_store = OrderStore(db_path)
        self.user_store = UserStore(db_path)
        self.menu = DummyMenu(tmp_path)
        self.page = DummyPage()
        self.usuario_actual = User(id=1, username="admin1", role=role, active=True)
        self.modo_oscuro = False
        self.fondo_acento = "#ffffff"
        self.superficie = "#ffffff"
        self.borde = "#cccccc"
        self.texto = "#000000"
        self.secundario = "#666666"
        self.notificaciones = []
        self.es_pantalla_movil = False
        self.informes_abiertos = []
        self.ultima_actividad = None

    def __getattr__(self, name: str):
        return lambda *args, **kwargs: None

    def notificar(self, msg: str):
        self.notificaciones.append(msg)

    def boton(self, texto, icono, accion, ancho=218):
        return ft.Button(content=texto, icon=icono, on_click=accion, width=ancho)

    def boton_dialogo(self, texto, accion):
        return ft.Button(content=texto, on_click=accion)

    def abrir_informe(self, ruta_especifica=None):
        self.informes_abiertos.append(ruta_especifica)

    def exigir_roles(self, *roles):
        if not self.usuario_actual:
            return False
        if self.usuario_actual.role not in roles:
            self.notificar("Tu rol no tiene permiso para realizar esta acción.")
            return False
        return True

    def mostrar_historial_cierres_admin(self, _evento=None):
        if not self.exigir_roles("administrador", "master"):
            return
        mostrar_dialogo_cierres_operarios(self)


def extraer_textos(control):
    textos = []
    if isinstance(control, ft.Text) and control.value:
        textos.append(str(control.value))
    elif isinstance(control, ft.Button) and hasattr(control, "content") and isinstance(control.content, str):
        textos.append(str(control.content))
    if hasattr(control, "content") and control.content:
        textos.extend(extraer_textos(control.content))
    if hasattr(control, "controls") and control.controls:
        for c in control.controls:
            textos.extend(extraer_textos(c))
    return textos


class TestCierresOperariosAdmin(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.db_path = self.tmp_path / "test_app.sqlite3"
        self.interfaz = DummyInterfaz(self.db_path, self.tmp_path, role="administrador")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sidebar_administrador_incluye_boton_cierres_operarios(self):
        """Verifica que el menú lateral del rol administrador contenga el botón 'Cierres de Operarios'."""
        from src.ui.components.sidebar import construir_sidebar_controls
        controles = construir_sidebar_controls(self.interfaz)
        textos_botones = [
            b.content for c in controles for b in ([c] if isinstance(c, ft.Button) else getattr(c, "controls", []) or []) if hasattr(b, "content")
            if True
        ]
        self.assertIn("Cierres de Operarios", textos_botones)

    def test_orden_descendente_de_cierres(self):
        """Verifica que los cierres creados por operarios se listen en estricto orden descendente (más reciente primero)."""
        store = self.interfaz.order_store
        store.crear_cliente("Cliente A")
        store.crear_cliente("Cliente B")

        # Cierre 1 realizado por 'operario_juan'
        p1 = store.registrar_pedido(
            nota_pedido="REM-001",
            numero_pedido="PED-101",
            cliente="Cliente A",
            bultos=2,
            logistica="Transporte",
            armador="operario_juan",
            tipo_archivo="pdf",
            nombre_archivo="remito1.pdf",
            agregado=False,
            articulos_descontados=10,
            resumen_items="10x Articulo A",
        )
        cierre1_id = store.registrar_cierre(
            usuario="operario_juan",
            pedidos_ids=[p1.id],
            articulos_totales=10,
            resumen_pedidos="Cierre Turno Mañana Juan",
            archivo_pdf="Cierre_01.pdf",
            archivo_excel="Cierre_01.xlsx",
        )

        # Cierre 2 realizado posteriormente por 'operario_maria'
        p2 = store.registrar_pedido(
            nota_pedido="REM-002",
            numero_pedido="PED-102",
            cliente="Cliente B",
            bultos=5,
            logistica="Transporte",
            armador="operario_maria",
            tipo_archivo="pdf",
            nombre_archivo="remito2.pdf",
            agregado=False,
            articulos_descontados=25,
            resumen_items="25x Articulo B",
        )
        cierre2_id = store.registrar_cierre(
            usuario="operario_maria",
            pedidos_ids=[p2.id],
            articulos_totales=25,
            resumen_pedidos="Cierre Turno Tarde Maria",
            archivo_pdf="Cierre_02.pdf",
            archivo_excel="Cierre_02.xlsx",
        )

        # Abrir el diálogo como administrador
        self.interfaz.mostrar_historial_cierres_admin()
        self.assertEqual(len(self.interfaz.page.dialogos), 1)

        dlg = self.interfaz.page.dialogos[0]
        # El contenido es un Container cuyo content es un Column
        cuerpo = dlg.content.content
        self.assertIsInstance(cuerpo, ft.Column)

        # Buscar el ListView de cierres (índice 3 en cuerpo.controls)
        lista_container = cuerpo.controls[3]
        lista_cierres = lista_container.content
        self.assertIsInstance(lista_cierres, ft.ListView)

        # Deben haber 2 cierres renderizados
        self.assertEqual(len(lista_cierres.controls), 2)

        # El primer elemento de la lista debe ser el Cierre 2 (el más reciente, ID más alto)
        primer_item = lista_cierres.controls[0]
        segundo_item = lista_cierres.controls[1]

        # Validar orden descendente
        textos_primer_item = extraer_textos(primer_item)
        textos_segundo_item = extraer_textos(segundo_item)

        self.assertTrue(any(f"Cierre #{cierre2_id}" in t for t in textos_primer_item))
        self.assertTrue(any("operario_maria" in t for t in textos_primer_item))

        self.assertTrue(any(f"Cierre #{cierre1_id}" in t for t in textos_segundo_item))
        self.assertTrue(any("operario_juan" in t for t in textos_segundo_item))

    def test_ver_detalle_pedidos_de_un_cierre(self):
        """Verifica que el administrador pueda abrir el detalle de pedidos incluidos en un cierre específico."""
        store = self.interfaz.order_store
        store.crear_cliente("Cliente Detalle")
        p = store.registrar_pedido(
            nota_pedido="REM-999",
            numero_pedido="PED-999",
            cliente="Cliente Detalle",
            bultos=3,
            logistica="Transporte",
            armador="operario_carlos",
            tipo_archivo="pdf",
            nombre_archivo="rem_999.pdf",
            agregado=False,
            articulos_descontados=50,
            resumen_items="50x Producto Especial",
        )
        cierre_id = store.registrar_cierre(
            usuario="operario_carlos",
            pedidos_ids=[p.id],
            articulos_totales=50,
            resumen_pedidos="Cierre Especial Carlos",
            archivo_pdf="Cierre_Esp.pdf",
            archivo_excel="Cierre_Esp.xlsx",
        )
        cierre_obj = store.listar_cierres(limit=1)[0]

        # Abrir submodal de pedidos del cierre
        mostrar_detalle_pedidos_cierre(self.interfaz, cierre_obj)
        self.assertEqual(len(self.interfaz.page.dialogos), 1)

        dlg_detalle = self.interfaz.page.dialogos[0]
        self.assertIn(f"Pedidos del Cierre #{cierre_id}", str(dlg_detalle.title.__dict__))

        # El ListView debe listar el pedido
        lv = dlg_detalle.content.content
        self.assertEqual(len(lv.controls), 1)
        pedido_item = lv.controls[0]
        textos_pedido = extraer_textos(pedido_item)
        self.assertTrue(any("REM-999" in t for t in textos_pedido))
        self.assertTrue(any("Cliente Detalle" in t for t in textos_pedido))
        self.assertTrue(any("Transporte" in t for t in textos_pedido))

    def test_restringe_rol_no_autorizado(self):
        """Verifica que roles no autorizados (ej: consulta u operador) no puedan usar la vista administrativa."""
        self.interfaz.usuario_actual = User(id=2, username="operador1", role="operador", active=True)
        self.interfaz.mostrar_historial_cierres_admin()
        self.assertEqual(len(self.interfaz.page.dialogos), 0)
        self.assertIn("Tu rol no tiene permiso para realizar esta acción.", self.interfaz.notificaciones)

    def test_filtrar_cierres_por_operario(self):
        """Verifica que se puedan filtrar los cierres en tiempo real por el nombre del operario."""
        store = self.interfaz.order_store
        store.crear_cliente("Cliente Test")
        p1 = store.registrar_pedido(
            nota_pedido="R-1", numero_pedido="P-1", cliente="Cliente Test", bultos=1,
            logistica="Transporte", armador="lucas", tipo_archivo="pdf", nombre_archivo="f1.pdf"
        )
        store.registrar_cierre(usuario="lucas", pedidos_ids=[p1.id], articulos_totales=5, resumen_pedidos="Cierre Lucas")

        p2 = store.registrar_pedido(
            nota_pedido="R-2", numero_pedido="P-2", cliente="Cliente Test", bultos=1,
            logistica="Transporte", armador="esteban", tipo_archivo="pdf", nombre_archivo="f2.pdf"
        )
        store.registrar_cierre(usuario="esteban", pedidos_ids=[p2.id], articulos_totales=8, resumen_pedidos="Cierre Esteban")

        self.interfaz.mostrar_historial_cierres_admin()
        dlg = self.interfaz.page.dialogos[0]
        cuerpo = dlg.content.content
        filtro_row = cuerpo.controls[1]
        filtro_input = filtro_row.controls[0]
        lista_cierres = cuerpo.controls[3].content

        self.assertEqual(len(lista_cierres.controls), 2)

        # Simular tipeo de 'lucas'
        filtro_input.value = "lucas"
        filtro_input.on_change(type("DummyEvent", (), {"control": filtro_input})())

        self.assertEqual(len(lista_cierres.controls), 1)
        textos = extraer_textos(lista_cierres.controls[0])
        self.assertTrue(any("lucas" in t.lower() for t in textos))
        self.assertFalse(any("esteban" in t.lower() for t in textos))


if __name__ == "__main__":
    unittest.main()
