"""Tests unitarios para la visualización inline de documentos y prevención de descarga forzada."""

import tempfile
import unittest
from pathlib import Path
from starlette.testclient import TestClient
from fastapi import FastAPI

from src.api.v1.documentos import router as documentos_router
from src.paths import application_root
from src.flet_gui import InterfazFlet
from src.user_store import User, UserRole


class TestDocumentosVisor(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(documentos_router)
        self.client = TestClient(self.app)
        self.app_root = Path(application_root()).resolve()

        # Crear archivo PDF de prueba en data/informes
        self.dir_informes = self.app_root / "data" / "informes"
        self.dir_informes.mkdir(parents=True, exist_ok=True)
        self.archivo_pdf_test = self.dir_informes / "_test_informe_cierre.pdf"
        self.archivo_pdf_test.write_bytes(b"%PDF-1.4 test content")

    def tearDown(self):
        if self.archivo_pdf_test.exists():
            self.archivo_pdf_test.unlink()

    def test_ver_documento_pdf_inline(self):
        """Valida que un PDF se sirva con Content-Disposition inline para visualización sin descarga previa."""
        rel_path = f"data/informes/{self.archivo_pdf_test.name}"
        response = self.client.get(f"/documentos/ver?p={rel_path}")

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/pdf", response.headers.get("content-type", ""))
        disposition = response.headers.get("content-disposition", "")
        self.assertTrue(disposition.startswith("inline;"), f"Expected inline disposition, got: {disposition}")
        self.assertIn(self.archivo_pdf_test.name, disposition)
        self.assertEqual(response.content, b"%PDF-1.4 test content")

    def test_ver_documento_con_parametro_descargar_true(self):
        """Valida que si se solicita explícitamente descargar=true, se sirva como attachment."""
        rel_path = f"data/informes/{self.archivo_pdf_test.name}"
        response = self.client.get(f"/documentos/ver?p={rel_path}&descargar=true")

        self.assertEqual(response.status_code, 200)
        disposition = response.headers.get("content-disposition", "")
        self.assertTrue(disposition.startswith("attachment;"), f"Expected attachment disposition, got: {disposition}")

    def test_busqueda_automatica_por_nombre_simple(self):
        """Valida que si solo se proporciona el nombre del archivo, lo localice en las carpetas comunes."""
        response = self.client.get(f"/documentos/ver?p={self.archivo_pdf_test.name}")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers.get("content-disposition", "").startswith("inline;"))

    def test_ver_documento_path_alias(self):
        """Valida la ruta directa /documentos/ver/{nombre_archivo}."""
        response = self.client.get(f"/documentos/ver/{self.archivo_pdf_test.name}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers.get("content-disposition", "").startswith("inline;"))

    def test_seguridad_path_traversal_bloqueado(self):
        """Valida que secuencias ../ hacia afuera de la aplicación retornen 403 Forbidden."""
        response = self.client.get("/documentos/ver?p=../../../../Windows/System32/cmd.exe")
        self.assertEqual(response.status_code, 403)

    def test_seguridad_archivos_sensibles_bloqueados(self):
        """Valida que accesos a archivos .env, .git o usuarios.sqlite3 retornen 403."""
        response_env = self.client.get("/documentos/ver?p=.env")
        self.assertEqual(response_env.status_code, 403)

    def test_seguridad_extensiones_no_permitidas(self):
        """Valida que extensiones ejecutables o de código (.py, .exe, .sh) sean bloqueadas."""
        response = self.client.get("/documentos/ver?p=main.py")
        self.assertEqual(response.status_code, 403)

    def test_documento_no_encontrado_404(self):
        """Valida que un archivo inexistente retorne 404."""
        response = self.client.get("/documentos/ver?p=inexistente_123456789.pdf")
        self.assertEqual(response.status_code, 404)


class TestFletGuiAbrirInforme(unittest.TestCase):
    def test_abrir_informe_modo_web_abre_url_inline(self):
        """Valida que en modo web abrir_informe invoque abrir_url_en_navegador en lugar de save_file."""
        from unittest.mock import MagicMock, patch
        from types import SimpleNamespace

        class MockPage:
            web = True
            controls = []
            services = []
            overlay = []
            drawer = None
            floating_action_button = None
            window = SimpleNamespace()

            def add(self, *c):
                pass

            def clean(self):
                pass

            def show_dialog(self, d):
                pass

            def pop_dialog(self):
                pass

            def update(self):
                pass

        page = MockPage()

        with patch("src.flet_gui.MenuAgente"), patch("src.flet_gui.UserStore"):
            interfaz = InterfazFlet(page)

        interfaz.usuario_actual = User(
            id=1,
            username="operador_test",
            role="operador",
            active=True,
            nombre="Operador Test",
        )

        urls_abiertas = []
        interfaz.abrir_url_en_navegador = lambda url: urls_abiertas.append(url)

        ruta_ficticia = Path(application_root()) / "data" / "informes" / "Cierre_20261112.pdf"
        interfaz.abrir_informe(ruta_especifica=ruta_ficticia)

        self.assertEqual(len(urls_abiertas), 1)
        url = urls_abiertas[0]
        self.assertTrue(url.startswith("/documentos/ver?p="))
        self.assertIn("Cierre_20261112.pdf", url)


if __name__ == "__main__":
    unittest.main()
