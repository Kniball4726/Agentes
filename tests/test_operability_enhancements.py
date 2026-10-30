"""Tests unitarios para las mejoras de operatividad:
1. Prompt post-descuento con botón de imprimir rótulos A4 y advertencias de stock insuficiente.
2. Filtros rápidos en Historial de Pedidos (Todos, Solo Hoy, Pendientes, Despachados).
3. Hoja de ruta individual por transporte / logística.
4. Menú de usuario responsivo en el encabezado.
"""
from pathlib import Path
from unittest.mock import MagicMock
from reportlab.lib.pagesizes import A4
import pypdf

from src.dispatch_manifest import generar_hoja_ruta_pdf
from src.orders_store import Pedido
from src.ui.components.header import construir_encabezado
from src.user_store import User


def test_hoja_ruta_por_transporte(tmp_path: Path):
    """Verifica que generar_hoja_ruta_pdf con filtro_logistica genere el PDF solo con ese transporte."""
    ped1 = Pedido(
        id=1, nota_pedido="R-1", numero_pedido="1", cliente="Cli A",
        bultos=2, logistica="Transporte", armador="Lucas", tipo_archivo="pdf",
        nombre_archivo="doc1.pdf", agregado=False, articulos_descontados=5,
        resumen_items="5 un.", created_at="2026-10-30 10:00:00", estado="descontado"
    )
    ped2 = Pedido(
        id=2, nota_pedido="R-2", numero_pedido="2", cliente="Cli B",
        bultos=3, logistica="Canje", armador="Lucas", tipo_archivo="excel",
        nombre_archivo="doc2.xlsx", agregado=False, articulos_descontados=3,
        resumen_items="3 un.", created_at="2026-10-30 10:05:00", estado="descontado"
    )

    # 1. Hoja solo para "Transporte"
    pdf_tr = generar_hoja_ruta_pdf(
        cierre_id=5,
        pedidos=[ped1, ped2],
        usuario="Lucas",
        carpeta_destino=tmp_path,
        filtro_logistica="Transporte",
    )
    assert pdf_tr.exists()
    assert "_Transporte_" in pdf_tr.name
    reader = pypdf.PdfReader(str(pdf_tr))
    text = reader.pages[0].extract_text()
    assert "Cli A" in text
    assert "Cli B" not in text

    # 2. Hoja general (ambos)
    pdf_gen = generar_hoja_ruta_pdf(
        cierre_id=5,
        pedidos=[ped1, ped2],
        usuario="Lucas",
        carpeta_destino=tmp_path,
        filtro_logistica=None,
    )
    assert pdf_gen.exists()
    reader_gen = pypdf.PdfReader(str(pdf_gen))
    text_gen = reader_gen.pages[0].extract_text()
    assert "Cli A" in text_gen
    assert "Cli B" in text_gen


def test_encabezado_menu_usuario(tmp_path: Path):
    """Verifica que construir_encabezado genere correctamente el componente sin errores."""
    interfaz = MagicMock()
    interfaz.usuario_actual = User(
        id=1, username="operario1", role="operador", active=True,
        nombre="Juan Perez", email="juan@empresa.com"
    )
    interfaz.modo_oscuro = False
    interfaz.es_pantalla_movil = False
    interfaz.pendientes_texto = MagicMock()
    interfaz.contenedor_notificaciones = MagicMock()

    control = construir_encabezado(interfaz)
    assert control is not None


def test_restriccion_estricta_edicion_pedido_solo_operador():
    """Verifica que solo los usuarios con rol 'operador' puedan abrir la edición de pedidos."""
    from src.ui.dialogs.dlg_pedidos import mostrar_dialogo_editar_pedido

    interfaz = MagicMock()
    ped = Pedido(
        id=1, nota_pedido="R-1", numero_pedido="1", cliente="Cli A",
        bultos=2, logistica="Transporte", armador="Lucas", tipo_archivo="pdf",
        nombre_archivo="doc1.pdf", agregado=False, articulos_descontados=5,
        resumen_items="5 un.", created_at="2026-10-30 10:00:00", estado="descontado"
    )

    # 1. Administrador -> Bloqueado
    interfaz.usuario_actual = User(id=2, username="admin1", role="administrador", active=True)
    mostrar_dialogo_editar_pedido(interfaz, ped)
    interfaz.notificar.assert_called_with("La modificación de pedidos es una función exclusiva del rol Operador de depósito.")
    assert not interfaz.page.show_dialog.called

    # 2. Master -> Bloqueado
    interfaz.reset_mock()
    interfaz.usuario_actual = User(id=3, username="master1", role="master", active=True)
    mostrar_dialogo_editar_pedido(interfaz, ped)
    interfaz.notificar.assert_called_with("La modificación de pedidos es una función exclusiva del rol Operador de depósito.")
    assert not interfaz.page.show_dialog.called

    # 3. Operador -> Permitido (abre diálogo)
    interfaz.reset_mock()
    interfaz.usuario_actual = User(id=4, username="op1", role="operador", active=True)
    interfaz.boton_dialogo = MagicMock(return_value=MagicMock())
    mostrar_dialogo_editar_pedido(interfaz, ped)
    assert interfaz.page.show_dialog.called



def test_master_no_ve_pedidos_dashboard():
    """Verifica que el usuario Master no reciba la tarjeta de pedidos en el dashboard."""
    from src.ui.components.panels import construir_panel_informes_actividad

    interfaz = MagicMock()
    interfaz.texto = "#ffffff"
    interfaz.secundario = "#888888"
    interfaz.borde = "#333333"
    interfaz.superficie = "#222222"
    interfaz.fondo_acento = "#111111"
    interfaz.modo_oscuro = True
    interfaz.es_pantalla_movil = False
    interfaz.lista_informes = MagicMock()
    interfaz.lista_pedidos_preparados = MagicMock()
    interfaz.header_pedidos_fecha = MagicMock()
    interfaz.header_pedidos_subtitulo = MagicMock()
    interfaz.header_pedidos_bultos = MagicMock()
    interfaz.tarjeta = lambda contenido, expand=True: {"tipo": "tarjeta", "contenido": contenido}

    # 1. Master: devuelve solo tarjeta_der (eventos auditoría), sin tarjeta_izq (pedidos)
    interfaz.usuario_actual = User(id=1, username="master", role="master", active=True)
    res_master = construir_panel_informes_actividad(interfaz)
    assert isinstance(res_master, dict)
    assert res_master.get("tipo") == "tarjeta"

    # 2. Administrador: devuelve Row o Column con ambas tarjetas
    interfaz.usuario_actual = User(id=2, username="admin", role="administrador", active=True)
    res_admin = construir_panel_informes_actividad(interfaz)
    assert hasattr(res_admin, "controls")
    assert len(res_admin.controls) == 2


def test_master_bloqueado_en_historial_y_detalle_pedidos():
    """Verifica que el usuario Master no pueda ver el historial ni abrir el detalle de pedidos."""
    from src.ui.dialogs.dlg_historial_pedidos import mostrar_historial_pedidos, mostrar_detalle_pedido_modal

    interfaz = MagicMock()
    interfaz.usuario_actual = User(id=1, username="master", role="master", active=True)
    ped = Pedido(
        id=1, nota_pedido="R-1", numero_pedido="1", cliente="Cli A",
        bultos=2, logistica="Transporte", armador="Lucas", tipo_archivo="pdf",
        nombre_archivo="doc1.pdf", agregado=False, articulos_descontados=5,
        resumen_items="5 un.", created_at="2026-10-30 10:00:00", estado="descontado"
    )

    # Historial de pedidos
    mostrar_historial_pedidos(interfaz)
    interfaz.notificar.assert_called_with("No tienes permisos suficientes para acceder al historial de pedidos.")

    # Detalle de pedido modal
    interfaz.reset_mock()
    mostrar_detalle_pedido_modal(interfaz, ped)
    interfaz.notificar.assert_called_with("El usuario Master no tiene acceso a la visualización de pedidos operativos.")
