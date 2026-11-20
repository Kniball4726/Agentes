"""Tests unitarios y de integración para el rol `despachador` y el módulo exclusivo Despacho."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import flet as ft
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from src.auth import USER_ROLES, User, UserStore
from src.orders import OrderStore
from src.products import ProductStore
from src.ui.commands.command_registry import obtener_comandos_rol
from src.ui.components.floating_chat_intents import _validar_permiso_intencion
from src.ui.components.mobile_nav import construir_navigation_bar_movil
from src.ui.components.sidebar_sections import obtener_secciones_rol
from src.ui.dialogs.dlg_modulo_despacho import (
    construir_vista_modulo_despacho,
    mostrar_modulo_despacho,
)


def _crear_pedido_demo(
    store: OrderStore,
    nota: str,
    cliente: str = "Cliente Demo",
    bultos: int = 3,
    logistica: str = "Transporte",
):
    return store.registrar_pedido(
        nota_pedido=nota,
        numero_pedido=nota,
        cliente=cliente,
        bultos=bultos,
        logistica=logistica,
        armador="Armador 1",
        tipo_archivo="pdf",
        nombre_archivo=f"{nota}.pdf",
        articulos_descontados=5,
        items=[("SKU-1", "Producto 1", 5)],
    )


def _recolectar_textos_flet(control: object) -> list[str]:
    """Recorre recursivamente un árbol de controles Flet y recopila textos y etiquetas."""
    textos: list[str] = []
    if control is None:
        return textos
    for attr in ("value", "label", "hint_text"):
        v = getattr(control, attr, None)
        if isinstance(v, str) and v:
            textos.append(v)
    c = getattr(control, "content", None)
    if isinstance(c, str) and c:
        textos.append(c)
    elif c is not None:
        textos.extend(_recolectar_textos_flet(c))
    for attr in ("controls", "actions", "tabs"):
        hijos = getattr(control, attr, None)
        if isinstance(hijos, list):
            for h in hijos:
                textos.extend(_recolectar_textos_flet(h))
    return textos


def _crear_interfaz_falsa(order_store: OrderStore, rol: str) -> SimpleNamespace:
    notificaciones: list[str] = []
    dialogos_abiertos: list[ft.AlertDialog] = []

    def _show_dialog(dlg):
        dialogos_abiertos.append(dlg)

    def _pop_dialog():
        if dialogos_abiertos:
            dialogos_abiertos.pop()

    page = SimpleNamespace(
        show_dialog=_show_dialog,
        pop_dialog=_pop_dialog,
        update=lambda: None,
        web=False,
    )
    usuario = User(
        id=99,
        username=f"usr_{rol}",
        role=rol,  # type: ignore[arg-type]
        active=True,
        nombre=f"Usuario {rol.capitalize()}",
    )

    def exigir_roles(*roles: str) -> bool:
        if usuario.role not in roles:
            notificaciones.append("Tu rol no tiene permiso para realizar esta acción.")
            return False
        return True

    def boton_dialogo(texto: str, accion):
        return ft.Button(content=texto, on_click=accion)

    noop = lambda *_a, **_kw: None

    return SimpleNamespace(
        usuario_actual=usuario,
        order_store=order_store,
        page=page,
        modo_oscuro=True,
        es_pantalla_movil=False,
        texto=ft.Colors.WHITE,
        secundario=ft.Colors.GREY_400,
        superficie=ft.Colors.BLUE_GREY_900,
        borde=ft.Colors.BLUE_GREY_700,
        exigir_roles=exigir_roles,
        notificar=lambda m: notificaciones.append(m),
        boton_dialogo=boton_dialogo,
        sincronizar_sesiones=noop,
        notificaciones=notificaciones,
        dialogos_abiertos=dialogos_abiertos,
        # Métodos referenciados por sidebar_sections y command_registry
        mostrar_modulo_despacho=noop,
        alternar_chat_flotante=noop,
        mostrar_manual_usuario=noop,
        mostrar_command_palette=noop,
        mostrar_dialogo_ola_picking=noop,
        mostrar_picking_guiado_full=noop,
        mostrar_descuento_mercado_libre=noop,
        mostrar_descuento_mercado_full=noop,
        mostrar_cierre_mercado=noop,
        mostrar_control_ingreso_fabrica=noop,
        mostrar_dialogo_ingreso_rapido=noop,
        mostrar_ingreso_fabrica=noop,
        mostrar_dialogo_salida_rapida=noop,
        mostrar_crear_pedido=noop,
        mostrar_gestion_clientes=noop,
        mostrar_dialogo_inventario_vivo=noop,
        mostrar_cierre_jornada=noop,
        mostrar_centro_reportes=noop,
        mostrar_historial_pedidos=noop,
        abrir_informe=noop,
        compartir_correo=noop,
        compartir_whatsapp=noop,
        mostrar_historial_cierres_admin=noop,
        mostrar_dialogo_anomalias=noop,
        mostrar_dashboard_metricas=noop,
        mostrar_estadisticas=noop,
        mostrar_dialogo_heatmap=noop,
        mostrar_gestion_usuarios=noop,
        mostrar_dialogo_backup=noop,
        mostrar_gestion_api_keys=noop,
        mostrar_estado_api=noop,
        mostrar_sesiones_api=noop,
        mostrar_registro_auditoria=noop,
        mostrar_dialogo_api_keys=noop,
        mostrar_gestion_ambientes=noop,
        confirmar_restaurar=noop,
        mostrar_dialogo_archivo_historico=noop,
        mostrar_configuracion_smtp=noop,
        mostrar_configuracion_telegram=noop,
        mostrar_sincronizacion_mercadolibre=noop,
        mostrar_ver_stock=noop,
        mostrar_gestion_productos=noop,
        mostrar_planificar_ingreso_fabrica=noop,
        mostrar_comparativa_stock_fisico_admin=noop,
        sincronizar_catalogo_excel=noop,
        generar_pedido_fabrica=noop,
        mostrar_planificar_full=noop,
    )


# ---------------------------------------------------------------------------
# 1. Auth & Migración automática SQLite para el rol `despachador`
# ---------------------------------------------------------------------------


def test_auth_migracion_legacy_y_alta_rol_despachador(tmp_path: Path):
    assert "despachador" in USER_ROLES
    db_path = tmp_path / "usuarios_legacy.sqlite3"

    # Crear base heredada SIN 'despachador' en el CHECK constraint
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (
                    role IN ('master', 'administrador', 'operador', 'consulta', 'picker')
                ),
                active INTEGER NOT NULL DEFAULT 1,
                must_change_password INTEGER NOT NULL DEFAULT 0,
                nombre TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "INSERT INTO users (username, password_hash, role, nombre) VALUES ('oper1', 'h', 'operador', 'Oper 1')"
        )
        conn.commit()

    store = UserStore(db_path)
    creado = store.create_user(
        "desp1",
        "Despacho2026!",
        role="despachador",
        nombre="Carlos Despacho",
    )
    assert creado.role == "despachador"
    assert store.get_user_by_username("oper1") is not None

    auth = store.authenticate_detailed("desp1", "Despacho2026!")
    assert auth.status == "ok"
    assert auth.user is not None and auth.user.role == "despachador"


# ---------------------------------------------------------------------------
# 2. Lógica de escaneo QR por bultos y despacho manual en DispatchRepository
# ---------------------------------------------------------------------------


def test_qr_bultos_multiples_pasa_a_despachado_al_completar_todos(tmp_path: Path):
    store = OrderStore(tmp_path / "pedidos.sqlite3")
    ped = _crear_pedido_demo(store, nota="0001-00001001", cliente="Ferretería Sur", bultos=3)

    # Validar parser QR
    datos = store.extraer_datos_qr_despacho(
        "REMITO:0001-00001001|CLIENTE:Ferretería Sur|BULTO:2/3|LOGISTICA:Transporte"
    )
    assert datos == {"remito": "0001-00001001", "bulto_num": 2, "total_bultos": 3}

    # Escanear 1/3 -> sigue armado
    r1 = store.registrar_escaneo_bulto_despacho(
        "REMITO:0001-00001001|CLIENTE:Ferretería Sur|BULTO:1/3|LOGISTICA:Transporte",
        usuario="Carlos Despacho",
    )
    assert r1["ok"] is True
    assert r1["completado"] is False
    assert r1["bultos_escaneados"] == [1]
    assert store.buscar_pedido_por_nota("0001-00001001").estado_despacho == "armado"

    # Re-escanear 1/3 -> bloqueado por duplicado
    r1_dup = store.registrar_escaneo_bulto_despacho(
        "REMITO:0001-00001001|BULTO:1/3",
        usuario="Carlos Despacho",
    )
    assert r1_dup["ok"] is False
    assert r1_dup["duplicado"] is True

    # Rótulo con cantidad total inconsistente (1/5 vs 3) -> rechazado
    r_bad = store.registrar_escaneo_bulto_despacho(
        "REMITO:0001-00001001|BULTO:2/5",
        usuario="Carlos Despacho",
    )
    assert r_bad["ok"] is False

    # Remito plano en pedido multi-bulto -> pide escanear bultos o confirmar manual
    r_plano = store.registrar_escaneo_bulto_despacho("0001-00001001", usuario="Carlos Despacho")
    assert r_plano["ok"] is True
    assert r_plano["completado"] is False
    assert r_plano["requiere_confirmacion_bultos"] is True

    # Escanear 2/3 y 3/3 -> pasa automáticamente a DESPACHADO
    r2 = store.registrar_escaneo_bulto_despacho("REMITO:0001-00001001|BULTO:2/3", usuario="Carlos Despacho")
    assert r2["ok"] is True and r2["completado"] is False
    r3 = store.registrar_escaneo_bulto_despacho("REMITO:0001-00001001|BULTO:3/3", usuario="Carlos Despacho")
    assert r3["ok"] is True
    assert r3["completado"] is True
    assert r3["pedido"].estado_despacho == "despachado"
    assert r3["pedido"].despachado_por == "Carlos Despacho"
    assert r3["pedido"].despachado_at != ""

    # Un nuevo escaneo sobre pedido ya despachado NO lo pasa a entregado
    r_extra = store.registrar_escaneo_bulto_despacho("REMITO:0001-00001001|BULTO:1/3", usuario="Carlos Despacho")
    assert r_extra["ok"] is False
    assert r_extra["duplicado"] is True
    assert store.buscar_pedido_por_nota("0001-00001001").estado_despacho == "despachado"

    # Si un admin retrocede el pedido a armado, se limpian los bultos escaneados
    store.actualizar_estado_despacho(ped.id, "armado", usuario="Admin", permitir_retroceso=True)
    assert store.obtener_bultos_escaneados(ped.id) == []


def test_despacho_manual_y_remito_plano_un_bulto(tmp_path: Path):
    store = OrderStore(tmp_path / "pedidos_manual.sqlite3")
    ped_uno = _crear_pedido_demo(store, nota="0001-00002001", bultos=1)
    ped_multi = _crear_pedido_demo(store, nota="0001-00002002", bultos=4)

    # Pedido de 1 bulto con remito plano -> despachado inmediato
    res_uno = store.registrar_escaneo_bulto_despacho("0001-00002001", usuario="Despachador 1")
    assert res_uno["ok"] is True and res_uno["completado"] is True
    assert store.buscar_pedido_por_nota(ped_uno.nota_pedido).estado_despacho == "despachado"

    # Despacho manual con cantidad de bultos incorrecta -> bloqueado
    ok_mal, msg_mal, _ = store.despachar_pedido_manual(ped_multi.id, cantidad_bultos=3, usuario="Despachador 1")
    assert ok_mal is False
    assert "4 bulto" in msg_mal
    assert store.buscar_pedido_por_nota(ped_multi.nota_pedido).estado_despacho == "armado"

    # Despacho manual con cantidad exacta (4) -> DESPACHADO
    ok_bien, _, ped_upd = store.despachar_pedido_manual(ped_multi.id, cantidad_bultos=4, usuario="Despachador 1")
    assert ok_bien is True
    assert ped_upd is not None
    assert ped_upd.estado_despacho == "despachado"
    assert ped_upd.despachado_por == "Despachador 1"
    assert store.obtener_bultos_escaneados(ped_multi.id) == [1, 2, 3, 4]


# ---------------------------------------------------------------------------
# 3. Aislamiento estricto UI por rol (despachador / administrador / resto)
# ---------------------------------------------------------------------------


def test_sidebar_y_comandos_aislamiento_por_rol(tmp_path: Path):
    store = OrderStore(tmp_path / "pedidos_ui.sqlite3")

    # Despachador: ÚNICAMENTE sección DESPACHO (+ herramientas básicas sin manual/informes)
    itf_desp = _crear_interfaz_falsa(store, "despachador")
    secciones_desp = obtener_secciones_rol(itf_desp)
    titulos_desp = [s.titulo for s in secciones_desp]
    assert titulos_desp == ["DESPACHO", "HERRAMIENTAS"]
    assert [it[0] for it in secciones_desp[0].items] == ["Despacho"]

    cmds_desp = [c[0] for c in obtener_comandos_rol("despachador", itf_desp)]
    assert cmds_desp == ["Despacho"]

    # Barra móvil de despachador: solo Despacho + Chat
    nav_desp = construir_navigation_bar_movil(itf_desp)
    assert [d.label for d in nav_desp.destinations] == ["Despacho", "Chat"]

    # Administrador: ve "Despacho (Pedidos Despachados)" dentro de SUPERVISIÓN
    itf_admin = _crear_interfaz_falsa(store, "administrador")
    secciones_admin = obtener_secciones_rol(itf_admin)
    items_supervision = next(s.items for s in secciones_admin if s.titulo == "SUPERVISIÓN")
    assert any("Despacho (Pedidos Despachados)" == it[0] for it in items_supervision)

    # Master, Operador, Picker y Consulta NO ven el módulo Despacho
    for rol_excluido in ("master", "operador", "picker", "consulta"):
        itf_otro = _crear_interfaz_falsa(store, rol_excluido)
        todos_items = [it[0] for s in obtener_secciones_rol(itf_otro) for it in s.items]
        assert "Despacho" not in todos_items
        assert "Despacho (Pedidos Despachados)" not in todos_items
        cmds_otro = [c[0] for c in obtener_comandos_rol(rol_excluido, itf_otro)]
        assert "Despacho" not in cmds_otro
        assert "Despacho (Pedidos Despachados)" not in cmds_otro

    # Chat bloquea stock, auditoría, cierre e informes para despachador
    for intencion_bloq in ("buscar_stock", "auditoria", "cierre", "informes", "mercadolibre"):
        assert _validar_permiso_intencion("despachador", intencion_bloq) is not None
    assert _validar_permiso_intencion("despachador", "pedidos") is None


def test_modulo_despacho_solo_lectura_admin_y_bloqueo_otros_roles(tmp_path: Path):
    store = OrderStore(tmp_path / "pedidos_mod.sqlite3")
    p_pend = _crear_pedido_demo(store, nota="0001-00003001", cliente="Cliente Armado", bultos=2)
    p_desp = _crear_pedido_demo(store, nota="0001-00003002", cliente="Cliente Despachado", bultos=1)
    store.despachar_pedido_manual(p_desp.id, cantidad_bultos=1, usuario="Despachador 1")

    # Master, Operador, Picker y Consulta no pueden abrir mostrar_modulo_despacho
    for rol_sin_acceso in ("master", "operador", "picker", "consulta"):
        itf = _crear_interfaz_falsa(store, rol_sin_acceso)
        mostrar_modulo_despacho(itf)
        assert len(itf.dialogos_abiertos) == 0
        assert len(itf.notificaciones) == 1

    # Administrador abre en modo SOLO LECTURA y ve únicamente pedidos despachados
    itf_admin = _crear_interfaz_falsa(store, "administrador")
    mostrar_modulo_despacho(itf_admin)
    assert len(itf_admin.dialogos_abiertos) == 1
    textos_admin = " ".join(_recolectar_textos_flet(itf_admin.dialogos_abiertos[0].content))
    assert "solo lectura" in textos_admin.lower()
    assert p_desp.nota_pedido in textos_admin
    assert p_pend.nota_pedido not in textos_admin
    assert "Despachar manual" not in textos_admin
    assert "Pistola lectora QR" not in textos_admin

    # Despachador abre en modo operativo con pistola QR, pendientes y botón manual
    itf_desp = _crear_interfaz_falsa(store, "despachador")
    vista_desp, _ref = construir_vista_modulo_despacho(itf_desp, modo_dialogo=False)
    textos_desp = " ".join(_recolectar_textos_flet(vista_desp))
    assert "Pistola lectora QR" in textos_desp
    assert p_pend.nota_pedido in textos_desp
    assert "Despachar manual" in textos_desp


# ---------------------------------------------------------------------------
# 4. Aislamiento API REST para el rol `despachador`
# ---------------------------------------------------------------------------


def test_api_rest_despachador_solo_despacha_y_bloquea_productos(tmp_path: Path):
    from src.api import deps
    from src.api.v1 import auth as api_auth
    from src.api.v1 import despacho as api_despacho
    from src.api.v1 import productos as api_productos

    user_store = UserStore(tmp_path / "u_api.sqlite3")
    u_desp = user_store.create_user("desp_api", "DespachoApi123!", role="despachador", nombre="Desp API")
    user_store.reset_password(u_desp.id, "DespachoApi123!", updater_role="master", must_change=False)

    order_store = OrderStore(tmp_path / "o_api.sqlite3")
    product_store = ProductStore(tmp_path / "p_api.sqlite3")
    _crear_pedido_demo(order_store, nota="0001-00004001", bultos=2)

    app = FastAPI()
    app.include_router(api_auth.router, prefix="/api/v1")
    app.include_router(api_despacho.router, prefix="/api/v1")
    app.include_router(api_productos.router, prefix="/api/v1")
    app.dependency_overrides[deps.get_user_store] = lambda: user_store
    app.dependency_overrides[deps.get_order_store] = lambda: order_store
    app.dependency_overrides[deps.get_product_store] = lambda: product_store
    api_auth._ip_attempts.clear()

    client = TestClient(app)
    r_login = client.post(
        "/api/v1/auth/login",
        json={"username": "desp_api", "password": "DespachoApi123!"},
    )
    assert r_login.status_code == 200
    headers = {"Authorization": f"Bearer {r_login.json()['token']}"}

    # Bloqueado en endpoints de catálogo/stock
    assert client.get("/api/v1/productos/buscar", headers=headers).status_code == 403
    assert client.get("/api/v1/productos/SKU-1/stock", headers=headers).status_code == 403

    # Intento de pasar a 'entregado' rechazado para despachador
    r_ent = client.post(
        "/api/v1/despacho/escanear",
        json={"codigo": "REMITO:0001-00004001|BULTO:1/2", "nuevo_estado": "entregado"},
        headers=headers,
    )
    assert r_ent.status_code == 200
    assert r_ent.json()["ok"] is False

    # Escaneo bulto 1/2 y 2/2 -> pasa a 'despachado'
    r_b1 = client.post(
        "/api/v1/despacho/escanear",
        json={"codigo": "REMITO:0001-00004001|BULTO:1/2"},
        headers=headers,
    )
    assert r_b1.status_code == 200 and r_b1.json()["ok"] is True
    assert r_b1.json()["pedido"]["estado_despacho"] == "armado"

    r_b2 = client.post(
        "/api/v1/despacho/escanear",
        json={"codigo": "REMITO:0001-00004001|BULTO:2/2"},
        headers=headers,
    )
    assert r_b2.status_code == 200 and r_b2.json()["ok"] is True
    assert r_b2.json()["pedido"]["estado_despacho"] == "despachado"
