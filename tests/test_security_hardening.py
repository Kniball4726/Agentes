"""Pruebas de endurecimiento de seguridad para autenticación, secretos, docs y sistema."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.deps import (
    SESSION_TTL_SECONDS,
    _doc_tokens,
    _hash_token,
    _sesiones_activas,
    crear_sesion,
    crear_token_documento,
    get_user_store,
)
from src.api.v1.router import api_v1_router
from src.auth.store import UserStore
from src.backup_manager import restaurar_backup_sistema
from src.integrations.mercado_libre_api import (
    cargar_config_mercadolibre,
    guardar_config_mercadolibre,
)
from src.integrations.telegram_notifier import (
    cargar_config_telegram,
    guardar_config_telegram,
)
from src.paths import application_root
from src.secretos import esta_cifrado
from src.webhook_manager import _validar_url_webhook, guardar_webhook


class TestAuthAndSistemaSecurity(unittest.TestCase):
    def setUp(self):
        _sesiones_activas.clear()
        _doc_tokens.clear()
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self._tmpdir.name) / "usuarios_sec.sqlite3"
        self.store = UserStore(self.db_path)
        self.master = next(
            (u for u in self.store.list_users(include_master=True) if u.role == "master"),
            None,
        ) or self.store.create_user(
            "sec_admin", "ClaveSegura123!", "administrador", creator_role="master"
        )
        self.operador = self.store.create_user(
            "sec_operador", "ClaveSegura123!", "operador", creator_role="master"
        )
        self.app = FastAPI()
        self.app.include_router(api_v1_router)
        self.app.dependency_overrides[get_user_store] = lambda: self.store
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.app.dependency_overrides.clear()
        _sesiones_activas.clear()
        _doc_tokens.clear()
        self._tmpdir.cleanup()

    def test_token_en_query_string_rechazado(self):
        token = crear_sesion(self.operador, self.store)

        res_query = self.client.get(f"/api/v1/auth/me?token={token}")
        self.assertEqual(res_query.status_code, 401)

        res_header = self.client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(res_header.status_code, 200)
        self.assertEqual(res_header.json()["username"], "sec_operador")

    def test_revocacion_inmediata_en_mutaciones_usuario(self):
        # 1. Desactivar usuario revoca sesión en SQLite y memoria caché
        t1 = crear_sesion(self.operador, self.store)
        self.assertEqual(
            self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t1}"}).status_code,
            200,
        )
        self.store.set_active(self.operador.id, False, updater_role="master")
        self.assertNotIn(_hash_token(t1), _sesiones_activas)
        self.assertEqual(
            self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t1}"}).status_code,
            401,
        )

        # 2. Cambiar rol revoca sesiones activas
        self.store.set_active(self.operador.id, True, updater_role="master")
        t2 = crear_sesion(self.store.get_user(self.operador.id), self.store)
        self.store.update_role(self.operador.id, "consulta", updater_role="master")
        self.assertEqual(
            self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t2}"}).status_code,
            401,
        )

        # 3. Cambio de contraseña revoca sesiones activas
        t3 = crear_sesion(self.store.get_user(self.operador.id), self.store)
        self.store.change_password(self.operador.id, "ClaveSegura123!", "NuevaClaveSegura456!")
        self.assertEqual(
            self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t3}"}).status_code,
            401,
        )

        # 4. Restablecimiento de contraseña revoca sesiones activas
        t4 = crear_sesion(self.store.get_user(self.operador.id), self.store)
        self.store.reset_password(self.operador.id, "ResetClaveSegura789!", updater_role="master")
        self.assertEqual(
            self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t4}"}).status_code,
            401,
        )

        # 5. Revocación masiva limpia todas las sesiones
        t5 = crear_sesion(self.store.get_user(self.operador.id), self.store)
        self.store.revoke_all_sessions()
        self.assertEqual(
            self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t5}"}).status_code,
            401,
        )

    def test_ttl_memoria_y_revalidacion_db_externa(self):
        token = crear_sesion(self.operador, self.store)
        th = _hash_token(token)

        # Simular actualización directa de rol en SQLite (sin invalidar memoria)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("UPDATE users SET role = 'picker' WHERE id = ?", (self.operador.id,))
            conn.commit()
        finally:
            conn.close()
        res_sync = self.client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(res_sync.status_code, 200)
        self.assertEqual(res_sync.json()["role"], "picker")

        # Simular desactivación directa en SQLite
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("UPDATE users SET active = 0 WHERE id = ?", (self.operador.id,))
            conn.commit()
        finally:
            conn.close()
        res_inactivo = self.client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(res_inactivo.status_code, 401)

        # Reactivar y probar expiración por TTL en memoria + DB
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("UPDATE users SET active = 1 WHERE id = ?", (self.operador.id,))
            conn.commit()
        finally:
            conn.close()
        t_exp = crear_sesion(self.store.get_user(self.operador.id), self.store)
        th_exp = _hash_token(t_exp)
        expirado = time.time() - (SESSION_TTL_SECONDS + 30)
        _sesiones_activas[th_exp]["last_active"] = expirado
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE api_sessions SET last_active = ? WHERE token_hash = ?",
                (expirado, th_exp),
            )
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(
            self.client.get(
                "/api/v1/auth/me", headers={"Authorization": f"Bearer {t_exp}"}
            ).status_code,
            401,
        )

    def test_api_key_rechaza_rol_invalido(self):
        with self.assertRaises(ValueError):
            self.store.create_api_key("cliente_invalido", "superadmin_falso")

        token_master = crear_sesion(self.master, self.store)
        res = self.client.post(
            "/api/v1/auth/api-keys",
            params={"client_name": "erp_externo", "role": "superadmin_falso"},
            headers={"Authorization": f"Bearer {token_master}"},
        )
        self.assertEqual(res.status_code, 400)

        res_ok = self.client.post(
            "/api/v1/auth/api-keys",
            params={"client_name": "erp_externo", "role": "operador"},
            headers={"Authorization": f"Bearer {token_master}"},
        )
        self.assertEqual(res_ok.status_code, 200)
        self.assertIn("api_key", res_ok.json())

    def test_sistema_estado_redacta_telemetria_sin_auth(self):
        res_anon = self.client.get("/api/v1/sistema/estado")
        self.assertEqual(res_anon.status_code, 200)
        anon_data = res_anon.json()
        self.assertTrue(anon_data["ok"])
        self.assertEqual(anon_data["ip_local"], "")
        self.assertEqual(anon_data["sesiones_activas"], 0)
        self.assertEqual(anon_data["servidor_hora"], "")
        self.assertEqual(anon_data["modo_conexion"], "")

        token = crear_sesion(self.operador, self.store)
        res_auth = self.client.get(
            "/api/v1/sistema/estado",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(res_auth.status_code, 200)
        auth_data = res_auth.json()
        self.assertTrue(auth_data["ip_local"])
        self.assertTrue(auth_data["servidor_hora"])
        self.assertTrue(auth_data["modo_conexion"])
        self.assertGreaterEqual(auth_data["sesiones_activas"], 1)

    def test_token_documento_expirado_invalido(self):
        from src.api.deps import validar_token_documento

        dt = crear_token_documento(self.operador, recurso="data/informes/test.pdf")
        _doc_tokens[_hash_token(dt)]["exp"] = time.time() - 5
        self.assertIsNone(
            validar_token_documento(dt, recurso_solicitado="data/informes/test.pdf", user_store=self.store)
        )

    def test_manual_web_adjunta_token_dt_acotado(self):
        import urllib.parse
        from types import SimpleNamespace
        from unittest.mock import patch
        from src.api.deps import validar_token_documento
        from src.ui.controllers.document_viewer_service import DocumentViewerService

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manual_pdf = root / "Documentacion" / "Manual_Operador.pdf"
            manual_pdf.parent.mkdir(parents=True, exist_ok=True)
            manual_pdf.write_bytes(b"%PDF-1.4 manual test")

            urls_abiertas: list[str] = []

            class _FakeHost:
                page = SimpleNamespace(web=True)
                usuario_actual = self.operador
                informes = []
                informe_seleccionado = None

                def abrir_url_en_navegador(self, url: str) -> None:
                    urls_abiertas.append(url)

                def notificar(self, _msg: str) -> None:
                    pass

            with patch("src.ui.controllers.document_viewer_service.application_root", return_value=root):
                DocumentViewerService(_FakeHost()).mostrar_manual_usuario()

            self.assertEqual(len(urls_abiertas), 1)
            parsed = urllib.parse.urlparse(urls_abiertas[0])
            self.assertEqual(parsed.path, "/documentacion/Manual_Operador.pdf")
            qs = urllib.parse.parse_qs(parsed.query)
            self.assertIn("dt", qs)
            dt = qs["dt"][0]
            self.assertIsNotNone(
                validar_token_documento(dt, recurso_solicitado="Manual_Operador.pdf", user_store=self.store)
            )
            self.assertIsNone(
                validar_token_documento(dt, recurso_solicitado="Manual_Master.pdf", user_store=self.store)
            )

    def test_documentos_rechaza_rutas_sensibles(self):
        from unittest.mock import patch

        token = crear_sesion(self.operador, self.store)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in (
                "data/certs/server.key",
                "data/certs/secreto.pdf",
                "data/backups/respaldo.pdf",
                "data/logs/stockagent.log",
                "data/.clave_secretos",
            ):
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("confidencial", encoding="utf-8")

            with patch("src.api.v1.documentos.application_root", return_value=root):
                for ruta in (
                    "data/certs/server.key",
                    "data/certs/secreto.pdf",
                    "data/backups/respaldo.pdf",
                    "data/logs/stockagent.log",
                    "data/.clave_secretos",
                    ".clave_secretos",
                ):
                    res = self.client.get(
                        "/api/v1/documentos/ver",
                        params={"p": ruta},
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    self.assertEqual(
                        res.status_code,
                        403,
                        f"Se esperaba 403 para {ruta}, obtuvo {res.status_code}",
                    )


class TestSecretsBackupAndWebhookHardening(unittest.TestCase):
    def test_mercadolibre_secretos_cifrados_y_migracion_legado(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = {
                "app_id": "123456",
                "client_secret": "ml_secret_super_privado",
                "access_token": "APP_USR-secret-token",
                "refresh_token": "TG-refresh-token",
                "seller_id": "987654",
            }
            guardar_config_mercadolibre(cfg, root_path=root)

            ruta_json = root / "data" / "config_mercadolibre.json"
            self.assertTrue(ruta_json.exists())
            raw_text = ruta_json.read_text(encoding="utf-8")
            self.assertNotIn("ml_secret_super_privado", raw_text)
            self.assertNotIn("APP_USR-secret-token", raw_text)
            self.assertNotIn("TG-refresh-token", raw_text)

            raw_obj = json.loads(raw_text)
            self.assertTrue(esta_cifrado(raw_obj["client_secret"]))
            self.assertTrue(esta_cifrado(raw_obj["access_token"]))
            self.assertTrue(esta_cifrado(raw_obj["refresh_token"]))

            cargado = cargar_config_mercadolibre(root_path=root)
            self.assertEqual(cargado["client_secret"], "ml_secret_super_privado")
            self.assertEqual(cargado["access_token"], "APP_USR-secret-token")
            self.assertEqual(cargado["refresh_token"], "TG-refresh-token")

            # Migración automática desde JSON heredado en texto plano
            ruta_json.write_text(
                json.dumps(
                    {
                        "app_id": "111",
                        "client_secret": "plano_legado_ml",
                        "access_token": "plano_access_ml",
                        "refresh_token": "",
                        "seller_id": "222",
                    }
                ),
                encoding="utf-8",
            )
            migrado = cargar_config_mercadolibre(root_path=root)
            self.assertEqual(migrado["client_secret"], "plano_legado_ml")
            raw_post = json.loads(ruta_json.read_text(encoding="utf-8"))
            self.assertTrue(esta_cifrado(raw_post["client_secret"]))
            self.assertTrue(esta_cifrado(raw_post["access_token"]))

    def test_telegram_secretos_cifrados_y_migracion_legado(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = {
                "bot_token": "999888777:AAFakeBotTokenSecreto",
                "chat_id": "-100123456",
                "habilitado": True,
            }
            guardar_config_telegram(cfg, root_path=root)

            ruta_json = root / "data" / "config_telegram.json"
            self.assertTrue(ruta_json.exists())
            raw_text = ruta_json.read_text(encoding="utf-8")
            self.assertNotIn("AAFakeBotTokenSecreto", raw_text)
            raw_obj = json.loads(raw_text)
            self.assertTrue(esta_cifrado(raw_obj["bot_token"]))

            cargado = cargar_config_telegram(root_path=root)
            self.assertEqual(cargado["bot_token"], "999888777:AAFakeBotTokenSecreto")

            # Migración automática desde texto plano
            ruta_json.write_text(
                json.dumps(
                    {
                        "bot_token": "111222:TokenLegadoPlano",
                        "chat_id": "12345",
                        "habilitado": True,
                    }
                ),
                encoding="utf-8",
            )
            migrado = cargar_config_telegram(root_path=root)
            self.assertEqual(migrado["bot_token"], "111222:TokenLegadoPlano")
            raw_post = json.loads(ruta_json.read_text(encoding="utf-8"))
            self.assertTrue(esta_cifrado(raw_post["bot_token"]))

    def test_backup_restore_rechaza_zip_slip(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            zip_traversal = tmp_path / "malicioso_rel.zip"
            with zipfile.ZipFile(zip_traversal, "w") as zf:
                zf.writestr("../../escape_traversal.txt", "malicioso")

            ok_rel, msg_rel, _ = restaurar_backup_sistema(zip_traversal)
            self.assertFalse(ok_rel)
            self.assertIn("rutas inválidas", msg_rel.lower())

            zip_abs = tmp_path / "malicioso_abs.zip"
            with zipfile.ZipFile(zip_abs, "w") as zf:
                zf.writestr("/etc/passwd", "malicioso")

            ok_abs, msg_abs, _ = restaurar_backup_sistema(zip_abs)
            self.assertFalse(ok_abs)
            self.assertIn("fuera del destino", msg_abs.lower())

    def test_webhook_rechaza_esquemas_no_http(self):
        with self.assertRaises(ValueError):
            guardar_webhook("file:///C:/Windows/win.ini")
        with self.assertRaises(ValueError):
            guardar_webhook("javascript:alert(1)")
        with self.assertRaises(ValueError):
            guardar_webhook("http:///sin-host")

        self.assertEqual(
            _validar_url_webhook("https://hooks.ejemplo.com/stockagent"),
            "https://hooks.ejemplo.com/stockagent",
        )

    def test_scripts_y_plantilla_endurecidos(self):
        root = application_root()
        env_example = (root / ".env.example").read_text(encoding="utf-8")
        self.assertIn("STOCKAGENT_ENABLE_API_DOCS=0", env_example)

        fw_bat = (root / "scripts" / "operacion" / "configurar_firewall_red.bat").read_text(encoding="utf-8")
        self.assertIn("profile=private", fw_bat)
        self.assertIn("-Profile Private", fw_bat)
        self.assertNotIn("profile=any", fw_bat)
        self.assertNotIn('add rule name="StockAgent Python"', fw_bat)

        movil_bat = (root / "stockagent_mobile" / "iniciar_servidor_movil.bat").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("main.py --http", movil_bat)
        self.assertNotIn("StockAgent.exe\" --http", movil_bat)

        cliente_bat = (root / "scripts" / "operacion" / "crear_acceso_directo_cliente.bat").read_text(
            encoding="utf-8"
        )
        self.assertIn('set "ESQUEMA=https"', cliente_bat)
        self.assertNotIn("set URL=http://", cliente_bat)
        self.assertIn("$env:STOCKAGENT_BROWSER_EXE", cliente_bat)


if __name__ == "__main__":
    unittest.main()
