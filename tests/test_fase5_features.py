"""Tests unitarios para las funcionalidades de la Fase 5:
1. Manifiesto PWA oficial completo (assets/manifest.json) con shortcuts, scope e iconos.
2. Service Worker PWA (assets/sw.js) con estrategia de caché offline y bypass de WebSocket.
3. Pantalla de contingencia offline (assets/offline.html) con auto-reconectador.
4. Cola resiliente de escaneos offline (assets/js/scanner.js) con buffer local y sincronización.
5. Registro y banner visual de microcortes en assets/index.html.
6. Mapeo de endpoints PWA en la inicialización web de src/flet_gui.py.
"""

import json
from pathlib import Path
import unittest

from src.paths import application_root


class TestFase5Features(unittest.TestCase):
    def setUp(self):
        self.root = application_root()
        self.assets_dir = self.root / "assets"

    def test_manifest_pwa_valido_y_completo(self):
        """Verifica que el manifiesto PWA contenga todos los atributos requeridos por estándares W3C/Lighthouse."""
        manifest_path = self.assets_dir / "manifest.json"
        self.assertTrue(manifest_path.exists(), "No se encontró assets/manifest.json")

        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data.get("display"), "standalone")
        self.assertIn("StockAgent", data.get("name", ""))
        self.assertEqual(data.get("short_name"), "StockAgent")
        self.assertEqual(data.get("theme_color"), "#D32F2F")
        self.assertEqual(data.get("background_color"), "#121212")
        self.assertEqual(data.get("start_url"), "/")
        self.assertEqual(data.get("scope"), "/")

        # Iconos
        icons = data.get("icons", [])
        self.assertGreaterEqual(len(icons), 2)
        sizes = [ic.get("sizes") for ic in icons]
        self.assertIn("192x192", sizes)
        self.assertIn("512x512", sizes)

        # Shortcuts para acceso rápido móvil
        shortcuts = data.get("shortcuts", [])
        self.assertGreaterEqual(len(shortcuts), 2)
        urls = [sc.get("url") for sc in shortcuts]
        self.assertIn("/scanner.html", urls)
        self.assertIn("/", urls)

    def test_service_worker_archivo_y_estructura(self):
        """Verifica que el Service Worker sw.js implemente ciclo de vida y caché offline."""
        sw_path = self.assets_dir / "sw.js"
        self.assertTrue(sw_path.exists(), "No se encontró assets/sw.js")

        content = sw_path.read_text(encoding="utf-8")
        self.assertIn("CACHE_NAME = 'stockagent-pwa-v1'", content)
        self.assertIn("addEventListener('install'", content)
        self.assertIn("addEventListener('activate'", content)
        self.assertIn("addEventListener('fetch'", content)
        self.assertIn("caches.open", content)
        self.assertIn("/offline.html", content)
        self.assertIn("/scanner.html", content)
        self.assertIn("url.pathname.startsWith('/ws')", content)  # Bypass WebSocket Flet

    def test_pagina_offline_html(self):
        """Verifica que la página de contingencia offline.html sea responsiva y contenga autoreconexión."""
        offline_path = self.assets_dir / "offline.html"
        self.assertTrue(offline_path.exists(), "No se encontró assets/offline.html")

        content = offline_path.read_text(encoding="utf-8")
        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn("viewport", content)
        self.assertIn("Sin Conexión", content)
        self.assertIn("/scanner.html", content)
        self.assertIn("window.addEventListener('online'", content)  # Auto-recarga al volver WiFi
        self.assertIn("window.location.reload()", content)

    def test_scanner_js_cola_offline_y_resiliencia(self):
        """Verifica que scanner.js contenga la cola local de escaneos y listeners de conectividad."""
        scanner_js_path = self.assets_dir / "js" / "scanner.js"
        self.assertTrue(scanner_js_path.exists(), "No se encontró assets/js/scanner.js")

        content = scanner_js_path.read_text(encoding="utf-8")
        self.assertIn("stockagent_offline_scan_queue", content)
        self.assertIn("guardarEnColaOffline", content)
        self.assertIn("sincronizarColaOffline", content)
        self.assertIn("actualizarIndicadorRed", content)
        self.assertIn("window.addEventListener(\"online\"", content)
        self.assertIn("window.addEventListener(\"offline\"", content)
        self.assertIn("navigator.serviceWorker.register", content)

    def test_index_html_registro_pwa_y_banner_resiliente(self):
        """Verifica que index.html registre el Service Worker y controle microcortes de red."""
        index_path = self.assets_dir / "index.html"
        self.assertTrue(index_path.exists(), "No se encontró assets/index.html")

        content = index_path.read_text(encoding="utf-8")
        self.assertIn('<link rel="manifest" href="manifest.json">', content)
        self.assertIn("navigator.serviceWorker.register('/sw.js'", content)
        self.assertIn("window.addEventListener('offline'", content)
        self.assertIn("window.addEventListener('online'", content)
        self.assertIn("offline-banner", content)

    def test_flet_gui_mapeo_endpoints_pwa(self):
        """Verifica que el código de flet_gui.py registre los manejadores estáticos de PWA."""
        flet_gui_path = self.root / "src" / "flet_gui.py"
        content = flet_gui_path.read_text(encoding="utf-8")

        self.assertIn('self.get("/sw.js")', content)
        self.assertIn('self.get("/service-worker.js")', content)
        self.assertIn('self.get("/manifest.json")', content)
        self.assertIn('self.get("/offline.html")', content)
        self.assertIn('self.get("/scanner.html")', content)
        self.assertIn('Service-Worker-Allowed', content)


if __name__ == "__main__":
    unittest.main()
