import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.email_sender import obtener_config_email
from src.mercado_libre_api import cargar_config_mercadolibre
from src.telegram_notifier import cargar_config_telegram
from src.user_store import UserStore


class TestEnvConfig(unittest.TestCase):
    def test_env_example_exists_and_contains_keys(self):
        root = Path(__file__).resolve().parent.parent
        example_path = root / ".env.example"
        self.assertTrue(example_path.exists())
        content = example_path.read_text(encoding="utf-8")
        self.assertIn("STOCKAGENT_MASTER_USER", content)
        self.assertIn("STOCKAGENT_MASTER_PASSWORD", content)
        self.assertIn("STOCKAGENT_HOST", content)
        self.assertIn("STOCKAGENT_PORT", content)
        self.assertIn("STOCKAGENT_SMTP_PASSWORD", content)
        self.assertIn("STOCKAGENT_TELEGRAM_BOT_TOKEN", content)
        self.assertIn("STOCKAGENT_MELI_APP_ID", content)

    def test_user_store_master_env_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "users_test.sqlite3"
            with patch.dict(os.environ, {
                "STOCKAGENT_MASTER_USER": "SuperAdmin",
                "STOCKAGENT_MASTER_PASSWORD": "ClaveSuperSegura2026!"
            }):
                store = UserStore(db_path)
                res = store.authenticate("SuperAdmin", "ClaveSuperSegura2026!")
                self.assertIsNotNone(res)
                self.assertEqual(res.role, "master")

    def test_telegram_env_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            with patch.dict(os.environ, {
                "STOCKAGENT_TELEGRAM_BOT_TOKEN": "ENV_TOK_123",
                "STOCKAGENT_TELEGRAM_CHAT_ID": "ENV_CHAT_456"
            }):
                cfg = cargar_config_telegram(tmp_root)
                self.assertEqual(cfg["bot_token"], "ENV_TOK_123")
                self.assertEqual(cfg["chat_id"], "ENV_CHAT_456")

    def test_mercadolibre_env_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            with patch.dict(os.environ, {
                "STOCKAGENT_MELI_APP_ID": "ENV_APP_999",
                "STOCKAGENT_MELI_CLIENT_SECRET": "ENV_SEC_888",
                "STOCKAGENT_MELI_SELLER_ID": "ENV_SELL_777",
            }):
                cfg = cargar_config_mercadolibre(tmp_root)
                self.assertEqual(cfg["app_id"], "ENV_APP_999")
                self.assertEqual(cfg["client_secret"], "ENV_SEC_888")
                self.assertEqual(cfg["seller_id"], "ENV_SELL_777")

    def test_email_smtp_env_fallback(self):
        with patch.dict(os.environ, {
            "STOCKAGENT_SMTP_SERVER": "smtp.test.com",
            "STOCKAGENT_SMTP_PORT": "465",
            "STOCKAGENT_SMTP_USER": "user@test.com",
            "STOCKAGENT_SMTP_PASSWORD": "Password123!",
            "STOCKAGENT_SMTP_SENDER": "noreply@test.com",
        }):
            cfg = obtener_config_email()
            self.assertEqual(cfg["smtp_servidor"], "smtp.test.com")
            self.assertEqual(cfg["smtp_puerto"], 465)
            self.assertEqual(cfg["smtp_usuario"], "user@test.com")
            self.assertEqual(cfg["smtp_password"], "Password123!")
            self.assertEqual(cfg["remitente"], "noreply@test.com")
