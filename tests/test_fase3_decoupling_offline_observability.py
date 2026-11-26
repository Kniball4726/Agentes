"""Pruebas de Fase 3: desacoplamiento sin sys.modules, modo offline LAN y observabilidad."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import FastAPI
from starlette.testclient import TestClient

from src.api.stores import (
    ApiStoreContext,
    crear_contexto_api,
    get_order_store,
    get_product_store,
    get_user_store,
    usar_contexto_api,
)
from src.api.tokens import crear_sesion
from src.api.v1 import auth as api_auth, sistema as api_sistema
from src.auth import UserStore
from src.flet_gui import InterfazFlet
from src.orders import OrderStore
from src.products import ProductStore
from src.server_app import (
    configurar_middlewares_http,
    construir_csp_app_web,
    crear_aplicacion_asgi,
)
from src.ui.controllers.session_sync_service import SessionSyncService
from src.ui.dialogs._shared import resolve_app_root, resolve_stock_manager
from src.ui.protocols import AppDependencies


def _crear_page_mock() -> MagicMock:
    page = MagicMock()
    page.width = 1280
    page.height = 800
    page.overlay = []
    page.services = []
    page.controls = []
    page.window = SimpleNamespace()
    return page


def test_inyeccion_app_dependencies_y_sin_acoplamiento_sys_modules(tmp_path: Path) -> None:
    lock_state = {"activo": False}
    descartadas: list[object] = []

    class _FakeStockMgr:
        def __init__(self, ruta_excel_base) -> None:
            self.ruta = ruta_excel_base

    fake_user_store = MagicMock()
    fake_user_store.has_users = True
    fake_user_store.list_users.return_value = []
    fake_order_store = MagicMock()
    fake_order_store.contar_pedidos_pendientes_cierre_por_tipo.return_value = {"total": 0}
    fake_order_store.contar_mensajes_no_leidos.return_value = 0
    fake_product_store = MagicMock()
    fake_menu = MagicMock()
    fake_menu.ruta_excel_base = tmp_path / "Productos.xlsx"

    deps = AppDependencies(
        user_store=fake_user_store,
        order_store=fake_order_store,
        product_store=fake_product_store,
        menu=fake_menu,
        stock_manager_factory=_FakeStockMgr,
        app_root_fn=lambda: tmp_path,
        get_global_lock_fn=lambda: lock_state["activo"],
        set_global_lock_fn=lambda v: lock_state.__setitem__("activo", bool(v)),
        sessions_provider=lambda: [],
        session_discard_fn=lambda s: descartadas.append(s),
        inactivity_limit_fn=lambda: 45,
    )

    interfaz = InterfazFlet(_crear_page_mock(), deps=deps)
    assert resolve_stock_manager(interfaz) is _FakeStockMgr
    assert resolve_app_root(interfaz) == tmp_path
    assert interfaz.auth_ctrl._inactivity_limit_fn() == 45

    interfaz.batch_ctrl._set_lock_fn(True)
    assert interfaz.batch_ctrl._get_lock_fn() is True
    interfaz.batch_ctrl._set_lock_fn(False)

    # Verificar que un fallo en sesión remota invoque session_discard_fn inyectado sin usar sys.modules
    sesion_rota = MagicMock()
    sesion_rota.usuario_actual = SimpleNamespace(username="op1")
    sesion_rota.page.update.side_effect = RuntimeError("Socket cerrado")
    sync = SessionSyncService(
        interfaz,
        sessions_provider=lambda: [sesion_rota],
        session_discard_fn=lambda s: descartadas.append(s),
    )
    sync.sincronizar_sesiones()
    assert sesion_rota in descartadas

    # Verificar que resolve_stock_manager ignorando atributos auto-generados de MagicMock usa fallback limpio
    mock_sin_inyeccion = MagicMock()
    assert callable(resolve_stock_manager(mock_sin_inyeccion))

    # Ninguno de los módulos desacoplados debe leer sys.modules
    raiz_src = Path(__file__).resolve().parent.parent / "src"
    for rel in (
        "ui/dialogs/_shared.py",
        "ui/controllers/batch_controller.py",
        "ui/controllers/auth_controller.py",
        "ui/controllers/session_sync_service.py",
        "ui/components/floating_chat_intents.py",
        "ui/dialogs/historial_archivos.py",
        "ui/dialogs/movimientos_rapidos_ops.py",
        "ui/dialogs/cierre/cierre_operario_exec.py",
    ):
        assert "sys.modules" not in (raiz_src / rel).read_text(encoding="utf-8")


def test_api_store_context_aislado_por_instancia_servidor(tmp_path: Path, monkeypatch) -> None:
    dir_a = tmp_path / "instancia_a"
    dir_b = tmp_path / "instancia_b"
    (dir_a / "data").mkdir(parents=True)
    (dir_b / "data").mkdir(parents=True)

    ctx_a = crear_contexto_api("servidor_a")
    ctx_b = crear_contexto_api("servidor_b")

    monkeypatch.setenv("STOCKAGENT_QA_MODE", "0")
    with usar_contexto_api(ctx_a):
        monkeypatch.setattr("src.api.stores.get_db_path", lambda nombre: dir_a / "data" / nombre)
        us_a = get_user_store()
        us_a.create_user("usuario_a", "ClaveSegura123!", "operador")

    with usar_contexto_api(ctx_b):
        monkeypatch.setattr("src.api.stores.get_db_path", lambda nombre: dir_b / "data" / nombre)
        us_b = get_user_store()
        us_b.create_user("usuario_b", "ClaveSegura123!", "operador")

    assert us_a is not us_b
    assert us_a.get_user_by_username("usuario_b") is None
    assert us_b.get_user_by_username("usuario_a") is None

    # Dos apps ASGI independientes mantienen su propio ApiStoreContext vía _ApiContextMiddleware
    app_a = crear_aplicacion_asgi(lambda _p: None, store_context=ctx_a)
    app_b = crear_aplicacion_asgi(lambda _p: None, store_context=ctx_b)
    assert isinstance(app_a.state.api_store_context, ApiStoreContext)
    assert app_a.state.api_store_context is ctx_a
    assert app_b.state.api_store_context is ctx_b

    client_a = TestClient(app_a)
    client_b = TestClient(app_b)
    with usar_contexto_api(ctx_a):
        tok_a = crear_sesion(us_a.get_user_by_username("usuario_a"), us_a)
    with usar_contexto_api(ctx_b):
        tok_b = crear_sesion(us_b.get_user_by_username("usuario_b"), us_b)

    r_me_a = client_a.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok_a}"})
    r_me_b = client_b.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok_b}"})
    assert r_me_a.status_code == 200 and r_me_a.json()["username"] == "usuario_a"
    assert r_me_b.status_code == 200 and r_me_b.json()["username"] == "usuario_b"

    # Token de la instancia B no existe en la BD de usuarios de la instancia A
    r_cruzado = client_a.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok_b}"})
    assert r_cruzado.status_code == 401


def test_flet_web_offline_no_cdn_por_defecto_y_csp_local_estricta() -> None:
    # Política por defecto sin CDNs externos
    csp_local = construir_csp_app_web(no_cdn=True)
    for cdn_externo in ("gstatic.com", "cdn.jsdelivr.net", "fonts.googleapis.com", "fonts.gstatic.com"):
        assert cdn_externo not in csp_local

    # Modo con CDN opcional explícito
    csp_cdn = construir_csp_app_web(no_cdn=False)
    assert "https://www.gstatic.com" in csp_cdn

    app = crear_aplicacion_asgi(lambda _p: None)
    client = TestClient(app)

    resp_index = client.get("/")
    assert resp_index.status_code == 200
    assert "flet.noCdn=true;" in resp_index.text
    assert 'flet.canvasKitBaseUrl="/canvaskit/";' in resp_index.text
    assert "gstatic.com" not in resp_index.headers["content-security-policy"]
    assert "cdn.jsdelivr.net" not in resp_index.headers["content-security-policy"]
    assert "fonts.googleapis.com" not in resp_index.headers["content-security-policy"]

    # CanvasKit, fuente Roboto y FontManifest servidos 100% desde el servidor local
    resp_ck = client.get("/canvaskit/canvaskit.js")
    assert resp_ck.status_code == 200
    resp_font = client.get("/assets/fonts/roboto.woff2")
    assert resp_font.status_code == 200
    resp_manifest = client.get("/assets/FontManifest.json")
    assert resp_manifest.status_code == 200
    assert any(item.get("family") == "Roboto" for item in resp_manifest.json())


def test_observabilidad_middleware_logging_estructurado_y_estado_enriquecido(
    tmp_path: Path,
    caplog,
    capsys,
) -> None:
    user_store = UserStore(tmp_path / "usuarios.sqlite3")
    prod_store = ProductStore(tmp_path / "productos.sqlite3")
    ord_store = OrderStore(tmp_path / "pedidos.sqlite3")
    oper = user_store.create_user("oper_obs", "ClaveSegura123!", "operador")
    token = crear_sesion(oper, user_store)

    app = FastAPI()
    configurar_middlewares_http(app, no_cdn=True)
    app.include_router(api_auth.router, prefix="/api/v1")
    app.include_router(api_sistema.router, prefix="/api/v1")
    app.dependency_overrides[get_user_store] = lambda: user_store
    app.dependency_overrides[get_product_store] = lambda: prod_store
    app.dependency_overrides[get_order_store] = lambda: ord_store

    client = TestClient(app)

    # 1. Middleware emite logging estructurado con request_id, status y duration_ms, sin usar print
    with caplog.at_level(logging.INFO, logger="stockagent.server"):
        res_anon = client.get("/api/v1/sistema/estado", headers={"X-Request-ID": "req-obs-001"})
    stdout_capturado = capsys.readouterr().out
    assert "[RED]" not in stdout_capturado
    assert res_anon.status_code == 200
    assert res_anon.headers.get("x-request-id") == "req-obs-001"
    assert any(
        "request_id=req-obs-001" in r.message and "status=200" in r.message and "duration_ms=" in r.message
        for r in caplog.records
    )

    # Sin auth se redactan las métricas operativas
    anon_json = res_anon.json()
    assert anon_json["sqlite_latencia_ms"] == {}
    assert anon_json["colas_y_logs"] == {}
    assert anon_json["planificador_alertas"] == {}
    assert anon_json["salud_sistema"] == ""

    # 2. Con auth expone latencia SQLite, colas/logs, planificador de alertas y salud
    res_auth = client.get(
        "/api/v1/sistema/estado",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_auth.status_code == 200
    assert len(res_auth.headers.get("x-request-id", "")) == 12
    data = res_auth.json()
    assert data["sqlite_latencia_ms"]["usuarios_ms"] is not None
    assert data["sqlite_latencia_ms"]["productos_ms"] is not None
    assert data["sqlite_latencia_ms"]["pedidos_ms"] is not None
    assert data["sqlite_latencia_ms"]["promedio_ms"] >= 0.0
    assert "excel_sync_pendientes" in data["colas_y_logs"]
    assert "log_principal_bytes" in data["colas_y_logs"]
    assert "habilitado" in data["planificador_alertas"]
    assert "hora_programada" in data["planificador_alertas"]
    assert data["salud_sistema"] in ("Óptimo", "Atención", "Crítico")
