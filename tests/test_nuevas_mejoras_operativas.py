"""Pruebas unitarias para las 7 nuevas mejoras operativas de StockAgent:
1. Rótulos para impresoras térmicas en PDF continuo (100x150 mm).
2. Despacho masivo en lote (avanzar_estado_lote).
3. Campo de N° de Guía / Tracking ID y persistencia.
4. Generación de hoja de ruta con N° de guía.
5. Buscador rápido global (Command Palette Ctrl+K).
6. Feedback sonoro Web Audio API (reproducir_sonido).
7. Espejo de respaldo en red / carpeta secundaria.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock
import pypdf
import pytest

from src.backup_manager import crear_backup_sistema, guardar_config_backup, obtener_config_backup
from src.dispatch_manifest import generar_hoja_ruta_pdf
from src.label_generator import generar_etiquetas_termicas_pdf
from src.orders_store import OrderStore, Pedido
from src.ui.dialogs.dlg_command_palette import mostrar_command_palette
from src.user_store import User


def test_rotulos_termicos_continuos(tmp_path: Path):
    """Verifica que generar_etiquetas_termicas_pdf cree un PDF con dimensiones exactas por página."""
    ped = Pedido(
        id=10,
        nota_pedido="REM-TERMICO-001",
        numero_pedido="42",
        cliente="Comercial Pasteur S.A.",
        bultos=3,
        logistica="Transporte",
        armador="Operador1",
        tipo_archivo="pdf",
        nombre_archivo="remito.pdf",
        agregado=False,
        articulos_descontados=12,
        resumen_items="12 un.",
        created_at="2026-10-30 11:00:00",
        estado="descontado",
        numero_guia="GUIA-OCA-999888",
    )

    pdf_term = generar_etiquetas_termicas_pdf(
        pedido=ped,
        carpeta_destino=tmp_path,
        tamano_mm=(100.0, 150.0),
    )
    assert pdf_term.exists()
    assert "Rotulo_Termico_REM-TERMICO-001.pdf" in pdf_term.name

    reader = pypdf.PdfReader(str(pdf_term))
    assert len(reader.pages) == 3, "Deben generarse exactamente 3 páginas (1 por bulto)"

    p0 = reader.pages[0].extract_text()
    assert "BULTO 1 DE 3" in p0
    assert "GUIA-OCA-999888" in p0
    assert "Comercial Pasteur S.A." in p0

    p2 = reader.pages[2].extract_text()
    assert "BULTO 3 DE 3" in p2


def test_numero_guia_y_despacho_masivo_en_order_store(tmp_path: Path):
    """Verifica el guardado de numero_guia y el método de despacho masivo en lote."""
    db_file = tmp_path / "test_pedidos_lote.sqlite3"
    store = OrderStore(db_file)

    p1 = store.registrar_pedido(
        nota_pedido="R-101",
        numero_pedido="1",
        cliente="Cliente A",
        bultos=2,
        logistica="Transporte",
        armador="Lucas",
        tipo_archivo="pdf",
        nombre_archivo="doc1.pdf",
        numero_guia="ANDREANI-001",
    )
    p2 = store.registrar_pedido(
        nota_pedido="R-102",
        numero_pedido="2",
        cliente="Cliente B",
        bultos=1,
        logistica="Comisionista",
        armador="Lucas",
        tipo_archivo="pdf",
        nombre_archivo="doc2.pdf",
    )

    assert p1.numero_guia == "ANDREANI-001"
    assert p2.numero_guia == ""

    # Actualizar numero_guia de p2
    p2_act = store.actualizar_datos_pedido(pedido_id=p2.id, numero_guia="VIA-CARGO-777")
    assert p2_act.numero_guia == "VIA-CARGO-777"

    # Despacho en lote de ambos pedidos
    cant_desp = store.avanzar_estado_lote([p1.id, p2.id], "despachado", usuario="Supervisor")
    assert cant_desp == 2

    p1_check = store.buscar_pedido_por_nota("R-101")
    p2_check = store.buscar_pedido_por_nota("R-102")
    assert p1_check.estado_despacho == "despachado"
    assert p2_check.estado_despacho == "despachado"

    # Marcar entregados en lote
    cant_entreg = store.avanzar_estado_lote([p1.id, p2.id], "entregado", usuario="Supervisor")
    assert cant_entreg == 2
    assert store.buscar_pedido_por_nota("R-101").estado_despacho == "entregado"


def test_hoja_ruta_con_numero_guia(tmp_path: Path):
    """Verifica que la Hoja de Ruta incluya el número de guía de seguimiento."""
    ped = Pedido(
        id=1,
        nota_pedido="REM-999",
        numero_pedido="10",
        cliente="Distribuidora Sur",
        bultos=4,
        logistica="Transporte",
        armador="Lucas",
        tipo_archivo="pdf",
        nombre_archivo="rem.pdf",
        agregado=False,
        articulos_descontados=10,
        resumen_items="10 un.",
        created_at="2026-10-30",
        estado="descontado",
        numero_guia="TRACK-EXPRESO-444",
    )

    pdf_ruta = generar_hoja_ruta_pdf(
        cierre_id=12,
        pedidos=[ped],
        usuario="Lucas",
        carpeta_destino=tmp_path,
    )
    assert pdf_ruta.exists()
    reader = pypdf.PdfReader(str(pdf_ruta))
    text = reader.pages[0].extract_text()
    assert "TRACK-EXPRESO-444" in text


def test_command_palette_modal():
    """Verifica la construcción del diálogo de paleta de comandos sin errores."""
    interfaz = MagicMock()
    interfaz.usuario_actual = User(id=1, username="operador1", role="operador", active=True)
    interfaz.superficie = "#222222"
    interfaz.borde = "#333333"
    interfaz.texto = "#ffffff"
    interfaz.secundario = "#888888"
    interfaz.fondo = "#111111"
    interfaz.modo_oscuro = True
    interfaz.boton_dialogo = MagicMock(return_value=MagicMock())

    mostrar_command_palette(interfaz)
    assert interfaz.page.show_dialog.called


def test_espejo_backup_en_red(tmp_path: Path):
    """Verifica que crear_backup_sistema duplique el .zip en la carpeta espejo si está configurada."""
    carpeta_bk_principal = tmp_path / "backups"
    carpeta_espejo = tmp_path / "espejo_red"
    carpeta_espejo.mkdir()

    # Guardar configuración de carpeta secundaria
    guardar_config_backup(str(carpeta_espejo), max_backups=10)
    cfg = obtener_config_backup()
    assert cfg["carpeta_externa"] == str(carpeta_espejo)

    # Generar backup
    zip_gen = crear_backup_sistema(carpeta_destino=carpeta_bk_principal)
    assert zip_gen.exists()

    # Comprobar que existe la copia idéntica en la carpeta espejo
    zip_espejo = carpeta_espejo / zip_gen.name
    assert zip_espejo.exists()
    assert zip_espejo.stat().st_size == zip_gen.stat().st_size

    # Limpiar config
    guardar_config_backup("")
