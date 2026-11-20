"""Tests de regresión de Fase 2: Endurecimiento Backend, Integraciones, PKI y Parsers."""

from __future__ import annotations

import asyncio
import datetime
import io
import json
import re
import ssl
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from cryptography import x509
from fastapi import FastAPI
from starlette.testclient import TestClient

from src.auth import UserStore
from src.core.network_security import (
    NoRedirectHandler,
    SSRFBlockedError,
    crear_contexto_tls_estricto,
    es_ip_prohibida,
    firmar_payload_hmac,
    sanitizar_cabecera_mime,
    validar_url_externa_segura,
)
from src.core.sanitize_utils import (
    escapar_html_telegram,
    escapar_texto_reportlab,
    sanitizar_celda_excel,
    sanitizar_fila_excel,
)
from src.integrations import email_sender, mercado_libre_auth, telegram_notifier
from src.parsers import safe_loader
from src.server_app.middleware import (
    _CORS_ORIGIN_REGEX_LAN_TAILSCALE,
    configurar_middlewares_http,
)
from src.ui.controllers.batch_controller import BatchTaskController
from src.ui.controllers.file_transfer_service import (
    _reservar_destino_exclusivo,
    _validar_magic_bytes,
)
from src import ssl_manager, webhook_manager


# ---------------------------------------------------------------------------
# 1. Seguridad de red: Anti-SSRF, TLS estricto, NoRedirectHandler, HMAC, MIME
# ---------------------------------------------------------------------------


def test_network_security_bloquea_destinos_internos_y_metadata():
    for url_peligrosa in (
        "http://127.0.0.1:8080/admin",
        "http://localhost/interno",
        "http://sub.localhost/test",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://[::1]:8000/",
        "http://10.0.0.5/hook",
        "http://192.168.1.20/hook",
        "https://user:pass@hooks.ejemplo.com/x",
    ):
        with pytest.raises(SSRFBlockedError):
            validar_url_externa_segura(url_peligrosa, resolver_dns=False)

    # Con permitir_lan_privada=True permite RFC1918 pero sigue bloqueando loopback y metadata
    assert validar_url_externa_segura("http://192.168.1.20/hook", permitir_lan_privada=True)
    assert es_ip_prohibida("169.254.169.254", permitir_lan_privada=True)
    assert es_ip_prohibida("127.0.0.1", permitir_lan_privada=True)
    assert es_ip_prohibida("::ffff:127.0.0.1", permitir_lan_privada=True)


def test_network_security_dns_rebinding_y_no_redirect():
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("169.254.169.254", 443))]):
        with pytest.raises(SSRFBlockedError):
            validar_url_externa_segura("https://rebind.ejemplo.com/hook", resolver_dns=True)

    handler = NoRedirectHandler()
    req = urllib.request.Request("https://hooks.ejemplo.com/start")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        handler.redirect_request(req, None, 302, "Found", {}, "http://169.254.169.254/")
    assert exc_info.value.code == 302


def test_tls_estricto_hmac_y_mime():
    ctx = crear_contexto_tls_estricto()
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True

    cab = sanitizar_cabecera_mime("Informe\r\nBcc: atacante@evil.com\nX-Inject: 1")
    assert "\r" not in cab and "\n" not in cab

    firmas = firmar_payload_hmac(b'{"evento":"TEST"}', "mi-secreto-2026", timestamp="1700000000")
    assert firmas["X-StockAgent-Timestamp"] == "1700000000"
    assert firmas["X-StockAgent-Signature"].startswith("sha256=")
    assert len(firmas["X-StockAgent-Signature"]) == len("sha256=") + 64


# ---------------------------------------------------------------------------
# 2. SMTP TLS estricto, MIME injection y SSRF guard
# ---------------------------------------------------------------------------


def test_email_sender_usa_tls_estricto_sanitiza_cabeceras_y_bloquea_metadata(tmp_path):
    ok_meta, msg_meta = email_sender.probar_conexion_smtp(
        {
            "smtp_servidor": "169.254.169.254",
            "smtp_puerto": 465,
            "smtp_usuario": "bot@empresa.com",
            "smtp_password": "secreto",
            "smtp_usar_ssl": True,
        }
    )
    assert ok_meta is False
    assert "bloqueado" in msg_meta.lower() or "smtp" in msg_meta.lower()

    adjunto = tmp_path / "reporte.txt"
    adjunto.write_text("ok", encoding="utf-8")

    mock_smtp = MagicMock()
    mock_smtp.__enter__.return_value = mock_smtp

    with patch("smtplib.SMTP_SSL", return_value=mock_smtp) as mock_cls:
        ok, _ = email_sender.enviar_via_smtp(
            destinatarios=["cliente@empresa.com\r\nBcc: spy@evil.com"],
            asunto="Cierre\r\nX-Evil: yes",
            cuerpo="Detalle seguro",
            adjuntos=[adjunto],
            config={
                "smtp_servidor": "smtp.gmail.com",
                "smtp_puerto": 465,
                "smtp_usuario": "sender@empresa.com",
                "smtp_password": "app-pass",
                "smtp_usar_ssl": True,
            },
        )
    assert ok is True
    assert mock_cls.called
    ctx_usado = mock_cls.call_args.kwargs.get("context")
    assert isinstance(ctx_usado, ssl.SSLContext)
    assert ctx_usado.verify_mode == ssl.CERT_REQUIRED
    assert ctx_usado.check_hostname is True
    raw_msg = mock_smtp.sendmail.call_args.args[2]
    assert "\r\nBcc: spy@evil.com" not in raw_msg
    assert "\r\nX-Evil: yes" not in raw_msg


# ---------------------------------------------------------------------------
# 3. Webhooks anti-SSRF y firma HMAC-SHA256
# ---------------------------------------------------------------------------


def test_webhook_bloquea_ssrf_y_firma_hmac(tmp_path, monkeypatch):
    ruta_wh = tmp_path / "webhooks.json"
    monkeypatch.setattr(webhook_manager, "_ruta_webhooks", lambda: ruta_wh)

    with pytest.raises(SSRFBlockedError):
        webhook_manager.guardar_webhook("http://169.254.169.254/latest/meta-data/")

    captured_reqs: list[urllib.request.Request] = []
    mock_resp = MagicMock()
    mock_resp.getcode.return_value = 200
    mock_opener = MagicMock()

    def fake_open(req, timeout=8):
        captured_reqs.append(req)
        cm = MagicMock()
        cm.__enter__.return_value = mock_resp
        return cm

    mock_opener.open.side_effect = fake_open

    with (
        patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]),
        patch("urllib.request.build_opener", return_value=mock_opener) as mock_build,
    ):
        ok, msg = webhook_manager.probar_webhook("https://hooks.ejemplo.com/ev", secreto="clave-wh")

    assert ok is True
    assert "200" in msg
    assert any(isinstance(h, NoRedirectHandler) for h in mock_build.call_args.args)
    assert len(captured_reqs) == 1
    headers_lower = {k.lower(): v for k, v in captured_reqs[0].header_items()}
    assert headers_lower["x-stockagent-signature"].startswith("sha256=")
    assert headers_lower["x-stockagent-timestamp"].isdigit()


# ---------------------------------------------------------------------------
# 4. Telegram HTML Escape & Mercado Libre OAuth sin recursión infinita
# ---------------------------------------------------------------------------


def test_telegram_escapa_html_y_valida_token():
    assert escapar_html_telegram('<a href="x">admin</a> & <script>') == (
        '&lt;a href="x"&gt;admin&lt;/a&gt; &amp; &lt;script&gt;'
    )

    enviados: list[str] = []
    with (
        patch.object(
            telegram_notifier,
            "cargar_config_telegram",
            return_value={
                "activo": True,
                "bot_token": "123456:ABCDEF_valid_token",
                "chat_id": "99999",
                "notificar_quiebres": True,
            },
        ),
        patch.object(
            telegram_notifier,
            "enviar_mensaje_telegram",
            side_effect=lambda texto, **_kw: enviados.append(texto) or (True, "OK"),
        ),
    ):
        telegram_notifier.notificar_quiebre_stock_telegram(
            codigo="SKU-<1>",
            nombre='<b>Malicioso</b> & "test"',
            stock_actual=0,
            stock_minimo=5,
        )

    assert len(enviados) == 1
    assert "<b>Malicioso</b>" not in enviados[0]
    assert "&lt;b&gt;Malicioso&lt;/b&gt;" in enviados[0]
    assert "SKU-&lt;1&gt;" in enviados[0]

    ok_bad, _ = telegram_notifier.enviar_mensaje_telegram(
        "hola",
        config={"bot_token": "bad/../../token", "chat_id": "123"},
        sync=True,
    )
    assert ok_bad is False


def test_mercado_libre_401_no_entra_en_recursion_infinita():
    llamadas_refresh = 0

    def fake_refresh(_cfg, root_path=None):
        nonlocal llamadas_refresh
        llamadas_refresh += 1
        return True, "refreshed", "tok_renovado"

    err_401 = urllib.error.HTTPError(
        "https://api.mercadolibre.com/users/me", 401, "Unauthorized", {}, None
    )

    with (
        patch.object(
            mercado_libre_auth,
            "cargar_config_mercadolibre",
            return_value={"access_token": "tok_vencido", "refresh_token": "ref_1"},
        ),
        patch.object(mercado_libre_auth, "renovar_token_ml", side_effect=fake_refresh),
        patch("urllib.request.urlopen", side_effect=err_401),
    ):
        ok, msg, _data = mercado_libre_auth.verificar_credenciales_ml()

    assert ok is False
    assert llamadas_refresh == 1
    assert "401" in msg or "unauthorized" in msg.lower()


# ---------------------------------------------------------------------------
# 5. Sanitización Excel (Formula Injection) & ReportLab XML Escape
# ---------------------------------------------------------------------------


def test_sanitizar_celda_excel_y_reportlab_escape(tmp_path):
    assert sanitizar_celda_excel("=CMD|' /C calc'!A0") == "'=CMD|' /C calc'!A0"
    assert sanitizar_celda_excel("+1+1") == "'+1+1"
    assert sanitizar_celda_excel("@SUM(A1:A2)") == "'@SUM(A1:A2)"
    assert sanitizar_celda_excel("-2+3") == "'-2+3"
    assert sanitizar_celda_excel("   =HYPERLINK(\"http://evil\")") == "'   =HYPERLINK(\"http://evil\")"
    # Valores numéricos y placeholder "-" deben quedar intactos
    assert sanitizar_celda_excel(42) == 42
    assert sanitizar_celda_excel(-5) == -5
    assert sanitizar_celda_excel(3.14) == 3.14
    assert sanitizar_celda_excel("-") == "-"
    assert sanitizar_celda_excel("Producto Normal") == "Producto Normal"
    assert sanitizar_fila_excel(["=1+1", 10, "-"]) == ["'=1+1", 10, "-"]

    # Verificar que ReportLab compila un PDF sin explotar con etiquetas maliciosas
    from reportlab.platypus import Paragraph
    from src.stock.report_styles import compilar_pdf_reporte, crear_estilos_pdf

    st = crear_estilos_pdf()
    peligroso = '<img src="/etc/passwd"/> <b>Sin cerrar & "comillas"'
    p = Paragraph(escapar_texto_reportlab(peligroso), st["td"])
    pdf_out = tmp_path / "seguro.pdf"
    compilar_pdf_reporte(
        pdf_out,
        titulo_doc="<script>alert(1)</script>",
        subtitulo_html="Subtítulo seguro",
        titulo_canvas="Reporte Test",
        fecha_legible="20/11/2026",
        cuerpo_extra=[p],
        st=st,
    )
    assert pdf_out.exists()
    assert pdf_out.read_bytes().startswith(b"%PDF-")


# ---------------------------------------------------------------------------
# 6. PKI local (CA separada + NameConstraints + hoja <= 365 días)
# ---------------------------------------------------------------------------


def test_ssl_manager_genera_ca_restringida_y_certificado_hoja_no_ca(tmp_path, monkeypatch):
    monkeypatch.setattr(ssl_manager, "application_root", lambda: tmp_path)

    cert_path_str, key_path_str = ssl_manager.asegurar_certificado_ssl()
    cert_path = Path(cert_path_str)
    key_path = Path(key_path_str)
    ca_path = cert_path.parent / "stockagent_ca.crt"

    assert cert_path.exists() and key_path.exists() and ca_path.exists()

    leaf_cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    ca_cert = x509.load_pem_x509_certificate(ca_path.read_bytes())

    leaf_bc = leaf_cert.extensions.get_extension_for_class(x509.BasicConstraints).value
    assert leaf_bc.ca is False

    leaf_ku = leaf_cert.extensions.get_extension_for_class(x509.KeyUsage).value
    assert leaf_ku.key_cert_sign is False
    assert leaf_ku.digital_signature is True

    exp = getattr(leaf_cert, "not_valid_after_utc", None) or leaf_cert.not_valid_after.replace(
        tzinfo=datetime.timezone.utc
    )
    inicio = getattr(leaf_cert, "not_valid_before_utc", None) or leaf_cert.not_valid_before.replace(
        tzinfo=datetime.timezone.utc
    )
    assert (exp - inicio).days <= 366

    ca_bc = ca_cert.extensions.get_extension_for_class(x509.BasicConstraints).value
    assert ca_bc.ca is True
    assert ca_bc.path_length == 0
    nc_ext = ca_cert.extensions.get_extension_for_class(x509.NameConstraints)
    assert nc_ext.critical is True
    assert len(nc_ext.value.permitted_subtrees or []) >= 5


# ---------------------------------------------------------------------------
# 7. CORS Tailscale estricto y cabeceras HTTP de seguridad (CSP, HSTS, etc.)
# ---------------------------------------------------------------------------


def test_middleware_cors_tailscale_estricto_y_cabeceras_seguridad():
    patron = re.compile(_CORS_ORIGIN_REGEX_LAN_TAILSCALE)
    assert patron.match("https://100.64.0.1:8550")
    assert patron.match("https://100.127.255.254:8550")
    assert patron.match("http://192.168.1.10:8550")
    assert patron.match("http://localhost:8550")
    # IPs públicas fuera del bloque CGNAT Tailscale 100.64.0.0/10 deben ser rechazadas
    assert not patron.match("https://100.63.255.254:8550")
    assert not patron.match("https://100.128.0.1:8550")
    assert not patron.match("https://evil.example.com")

    app = FastAPI()
    configurar_middlewares_http(app)

    @app.get("/api/v1/ping")
    def api_ping():
        return {"ok": True}

    @app.get("/")
    def root():
        return {"ok": True}

    client = TestClient(app, base_url="https://testserver")
    resp_api = client.get("/api/v1/ping")
    assert resp_api.headers["referrer-policy"] == "no-referrer"
    assert "camera=(self)" in resp_api.headers["permissions-policy"]
    assert "default-src 'self'" in resp_api.headers["content-security-policy"]
    assert "unsafe-eval" not in resp_api.headers["content-security-policy"]
    assert "max-age=" in resp_api.headers["strict-transport-security"]

    resp_root = client.get("/")
    assert "wasm-unsafe-eval" in resp_root.headers["content-security-policy"]


# ---------------------------------------------------------------------------
# 8. Auth timing/DoS, REST must_change_password, API Keys en JSON, TTL absoluto
# ---------------------------------------------------------------------------


def test_auth_store_dummy_hash_cacheado_y_limite_longitud(tmp_path):
    store = UserStore(tmp_path / "usuarios.sqlite3")
    with patch("src.auth.store.hash_clave") as mock_hash:
        res_unknown = store.authenticate_detailed("usuario_inexistente_xyz", "clave123")
        assert res_unknown.status == "invalid"
        # No debe generar un nuevo hash en cada login inválido (precomputado una sola vez)
        assert mock_hash.call_count <= 1

    # Contraseña gigantesca (>256 chars) rechazada antes de PBKDF2
    res_long = store.authenticate_detailed("admin", "A" * 500)
    assert res_long.status == "invalid"


def test_api_auth_must_change_password_api_key_body_y_ttl_absoluto(tmp_path):
    from pydantic import ValidationError
    from src.api import deps
    from src.api.schemas import EscanearLoteRequest
    from src.api.v1 import auth as api_auth

    store = UserStore(tmp_path / "usuarios_api.sqlite3")
    u_oper = store.create_user("oper_nuevo", "Operador123!", role="operador")
    store.reset_password(u_oper.id, "Operador123!", updater_role="master", must_change=True)
    u_master = store.create_user("master_api", "MasterSegura123!", role="master")
    store.reset_password(u_master.id, "MasterSegura123!", updater_role="master", must_change=False)

    app = FastAPI()
    app.include_router(api_auth.router, prefix="/api/v1")
    app.dependency_overrides[deps.get_user_store] = lambda: store
    api_auth._ip_attempts.clear()

    client = TestClient(app)

    # Usuario con must_change_password=True bloqueado en API REST
    r_blocked = client.post(
        "/api/v1/auth/login",
        json={"username": "oper_nuevo", "password": "Operador123!"},
    )
    assert r_blocked.status_code == 403

    # Master válido inicia sesión y crea API key vía JSON body
    r_login = client.post(
        "/api/v1/auth/login",
        json={"username": "master_api", "password": "MasterSegura123!"},
    )
    assert r_login.status_code == 200
    token = r_login.json()["token"]

    r_key = client.post(
        "/api/v1/auth/api-keys",
        json={"client_name": "ERP-Integracion", "role": "operador"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_key.status_code == 200
    assert r_key.json()["client_name"] == "ERP-Integracion"
    assert r_key.json()["api_key"].startswith("sk_live_")

    # TTL absoluto (7 días): incluso con last_active reciente, si created_at superó 7d expira
    ahora = time.time()
    sesion_vieja = {
        "created_at": ahora - deps.SESSION_ABSOLUTE_TTL_SECONDS - 10,
        "last_active": ahora - 5,
    }
    assert deps._sesion_expirada(sesion_vieja, ahora) is True

    # Límites max_length en schemas Pydantic contra payloads masivos
    with pytest.raises(ValidationError):
        EscanearLoteRequest(items=[{"codigo": "A", "cantidad": 1}] * 501)


# ---------------------------------------------------------------------------
# 9. Parsers anti-XXE / Zip Bomb / PDF inválido
# ---------------------------------------------------------------------------


def test_safe_loader_bloquea_xxe_zip_bomb_y_pdf_falso(tmp_path):
    # 1. OOXML con DOCTYPE/ENTITY (XXE)
    xxe_xlsx = tmp_path / "xxe.xlsx"
    with zipfile.ZipFile(xxe_xlsx, "w") as zf:
        zf.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><a/>',
        )
    with pytest.raises(ValueError, match="DOCTYPE|ENTITY|inseguro"):
        safe_loader.validar_ooxml_seguro(xxe_xlsx)

    # 2. OOXML con demasiadas entradas
    many_zip = tmp_path / "muchas_entradas.xlsx"
    with zipfile.ZipFile(many_zip, "w") as zf:
        for i in range(safe_loader.MAX_OOXML_ENTRIES + 5):
            zf.writestr(f"d/f{i}.txt", "x")
    with pytest.raises(ValueError, match="entradas"):
        safe_loader.validar_ooxml_seguro(many_zip)

    # 3. PDF con cabecera falsa
    fake_pdf = tmp_path / "falso.pdf"
    fake_pdf.write_bytes(b"<html>not a pdf</html>")
    with pytest.raises(ValueError, match="cabecera PDF"):
        safe_loader.validar_pdf_seguro(fake_pdf)


# ---------------------------------------------------------------------------
# 10. FileTransferService (reserva exclusiva + magic bytes) & BatchController
# ---------------------------------------------------------------------------


def test_file_transfer_magic_bytes_y_reserva_atomica_sin_sobrescritura(tmp_path):
    assert _validar_magic_bytes("pdf", b"%PDF-1.7\n") is True
    assert _validar_magic_bytes("pdf", b"<html>fake</html>") is False
    assert _validar_magic_bytes("xlsx", b"PK\x03\x04...") is True
    assert _validar_magic_bytes("xlsx", b"MZ\x90\x00exe") is False

    p1 = _reservar_destino_exclusivo(tmp_path, "remito", ".pdf")
    p1.write_bytes(b"%PDF-1")
    p2 = _reservar_destino_exclusivo(tmp_path, "remito", ".pdf")
    p2.write_bytes(b"%PDF-2")

    assert p1.name == "remito.pdf"
    assert p2.name == "remito_1.pdf"
    assert p1.read_bytes() == b"%PDF-1"
    assert p2.read_bytes() == b"%PDF-2"


def test_batch_controller_no_filtra_traceback_en_ui():
    host = SimpleNamespace(
        ocupado=False,
        progreso_barra=SimpleNamespace(visible=False, value=None),
        estado_tarea=SimpleNamespace(value=""),
        actividad=SimpleNamespace(controls=[]),
        modo_oscuro=False,
        texto="#000000",
        controles_tarea=[],
        page=SimpleNamespace(update=lambda: None),
        order_store=None,
    )
    ctrl = BatchTaskController(
        host,
        get_global_lock_fn=lambda: False,
        set_global_lock_fn=lambda _v: None,
        notify_fn=lambda _m: None,
        refresh_dashboard_fn=lambda: None,
        sync_sessions_fn=lambda: None,
    )

    def fallar():
        raise RuntimeError("Fallo interno con ruta C:\\secret\\db.sqlite3")

    ok = asyncio.run(ctrl.ejecutar_tarea("PruebaError", fallar))
    assert ok is False
    assert len(host.actividad.controls) == 1
    texto_ui = host.actividad.controls[0].value
    assert "Traceback (most recent call last)" not in texto_ui
    assert "C:\\secret\\db.sqlite3" not in texto_ui
    assert "RuntimeError" in texto_ui
