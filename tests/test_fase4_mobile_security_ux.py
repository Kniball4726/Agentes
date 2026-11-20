"""Suite de verificación integral para la Fase 4:
Seguridad, Criptografía, Resiliencia Offline y Ergonomía de StockAgent Móvil.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.server_app import static_routes

ROOT_DIR = Path(__file__).resolve().parent.parent
MOBILE_DIR = ROOT_DIR / "stockagent_mobile"


class TestFase4MobileSecurityUX(unittest.TestCase):
    """Valida los controles de seguridad, integridad OTA y UX móvil de la Fase 4."""

    def test_ota_endpoint_expone_sha256_y_cache_por_mtime(self):
        """Verifica que /actualizaciones/version.json y /api/version incluyan sha256 real del APK."""
        fake_apk_bytes = b"PK\x03\x04StockAgentFakeApkContentFase4"
        expected_sha256 = hashlib.sha256(fake_apk_bytes).hexdigest()

        tmp_root = ROOT_DIR / "tests" / "_tmp_ota_fase4"
        tmp_dir = tmp_root / "dist_movil"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        apk_file = tmp_dir / "StockAgent.apk"
        version_file = tmp_dir / "version.json"

        try:
            apk_file.write_bytes(fake_apk_bytes)
            version_file.write_text(
                '{"version_code": 7, "version_name": "2.4.0", "apk_url": "/actualizaciones/StockAgent.apk"}',
                encoding="utf-8",
            )

            calc_hash = static_routes._calcular_sha256_apk(apk_file)
            self.assertEqual(calc_hash, expected_sha256)

            app = FastAPI()
            with patch.object(static_routes, "application_root", return_value=str(tmp_root)):
                static_routes.registrar_rutas_ota(app)
                client = TestClient(app)
                res_ver = client.get("/actualizaciones/version.json")
                self.assertEqual(res_ver.status_code, 200)
                payload = res_ver.json()
                self.assertEqual(payload.get("sha256"), expected_sha256)
                self.assertEqual(payload.get("version_code"), 7)
                self.assertGreater(payload.get("file_size", 0), 0)

                res_api = client.get("/api/version")
                self.assertEqual(res_api.status_code, 200)
                self.assertEqual(res_api.json().get("sha256"), expected_sha256)
        finally:
            for f in (apk_file, version_file):
                if f.exists():
                    f.unlink()
            if tmp_dir.exists():
                tmp_dir.rmdir()
            if tmp_root.exists():
                tmp_root.rmdir()

    def test_tls_pinning_y_prevencion_downgrade_https(self):
        """Verifica eliminación de badCertificateCallback => true global y protección anti-downgrade."""
        pinning_src = (MOBILE_DIR / "lib" / "services" / "tls_pinning_service.dart").read_text(
            encoding="utf-8"
        )
        api_src = (MOBILE_DIR / "lib" / "services" / "api_service.dart").read_text(
            encoding="utf-8"
        )
        net_src = (MOBILE_DIR / "lib" / "services" / "network_service.dart").read_text(
            encoding="utf-8"
        )
        cfg_src = (MOBILE_DIR / "lib" / "models" / "server_config.dart").read_text(
            encoding="utf-8"
        )

        # Protocolo por defecto debe ser HTTPS
        self.assertIn("defaultProtocol = 'https'", cfg_src)
        self.assertIn("final String? certSha256;", cfg_src)

        # Ningún servicio debe tener aceptación ciega (cert, host, port) => true
        self.assertNotIn("badCertificateCallback = (cert, host, port) => true", api_src)
        self.assertNotIn("badCertificateCallback = (cert, host, port) => true", net_src)

        # Deben delegar en TlsPinningService
        self.assertIn("TlsPinningService.createPinnedHttpClient", api_src)
        self.assertIn("TlsPinningService.verifyServerCertificate", net_src)
        self.assertIn("verifyServerCertificate", pinning_src)
        self.assertIn("cert.startValidity", pinning_src)
        self.assertIn("cert.endValidity", pinning_src)

        # Prevención de downgrade silencioso HTTPS -> HTTP
        self.assertIn("config.normalizedProtocol == 'https'\n        ? <ServerConfig>[config]", net_src)

    def test_almacenamiento_seguro_keystore_y_aislamiento_por_usuario(self):
        """Verifica cifrado de token en Android Keystore, no duplicación en JSON y scoping por usuario."""
        auth_src = (MOBILE_DIR / "lib" / "models" / "auth_user.dart").read_text(encoding="utf-8")
        storage_src = (MOBILE_DIR / "lib" / "services" / "storage_service.dart").read_text(
            encoding="utf-8"
        )
        kt_src = (
            MOBILE_DIR
            / "android"
            / "app"
            / "src"
            / "main"
            / "kotlin"
            / "com"
            / "stockagent"
            / "mobile"
            / "MainActivity.kt"
        ).read_text(encoding="utf-8")

        # AuthUser.toJson() no debe serializar el token en texto plano dentro del perfil
        self.assertNotIn("if (token != null) 'token': token", auth_src)

        # StorageService debe usar el canal nativo com.stockagent.mobile/secure_storage
        self.assertIn("com.stockagent.mobile/secure_storage", storage_src)
        self.assertIn("writeSecure", storage_src)
        self.assertIn("readSecure", storage_src)
        self.assertIn("deleteSecure", storage_src)
        self.assertIn("_scopedKey", storage_src)

        # MainActivity.kt debe usar AndroidKeyStore con AES/GCM/NoPadding
        self.assertIn("AndroidKeyStore", kt_src)
        self.assertIn("AES/GCM/NoPadding", kt_src)
        self.assertIn("KeyGenParameterSpec", kt_src)

    def test_hardening_android_ios_y_verificacion_ota_sha256(self):
        """Verifica AndroidManifest, network_security_config, file_paths, Info.plist y OTA SHA-256."""
        manifest_src = (
            MOBILE_DIR / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
        ).read_text(encoding="utf-8")
        net_sec_src = (
            MOBILE_DIR
            / "android"
            / "app"
            / "src"
            / "main"
            / "res"
            / "xml"
            / "network_security_config.xml"
        ).read_text(encoding="utf-8")
        file_paths_src = (
            MOBILE_DIR / "android" / "app" / "src" / "main" / "res" / "xml" / "file_paths.xml"
        ).read_text(encoding="utf-8")
        gradle_src = (MOBILE_DIR / "android" / "app" / "build.gradle").read_text(encoding="utf-8")
        plist_src = (MOBILE_DIR / "ios" / "Runner" / "Info.plist").read_text(encoding="utf-8")
        update_src = (MOBILE_DIR / "lib" / "services" / "update_service.dart").read_text(
            encoding="utf-8"
        )
        kt_src = (
            MOBILE_DIR
            / "android"
            / "app"
            / "src"
            / "main"
            / "kotlin"
            / "com"
            / "stockagent"
            / "mobile"
            / "MainActivity.kt"
        ).read_text(encoding="utf-8")

        self.assertIn('android:allowBackup="false"', manifest_src)
        self.assertIn('android:networkSecurityConfig="@xml/network_security_config"', manifest_src)
        self.assertNotIn('android:usesCleartextTraffic="true"', manifest_src)

        self.assertIn('cleartextTrafficPermitted="false"', net_sec_src)
        self.assertIn('path="updates/"', file_paths_src)
        self.assertIn('path="picker_uploads/"', file_paths_src)
        self.assertNotIn('path="."', file_paths_src)

        self.assertIn("key.properties", gradle_src)
        self.assertIn("minifyEnabled true", gradle_src)
        self.assertTrue((MOBILE_DIR / "android" / "app" / "proguard-rules.pro").exists())

        self.assertIn("<key>NSAllowsArbitraryLoads</key>\n\t\t<false/>", plist_src)
        self.assertIn("<key>NSAllowsLocalNetworking</key>\n\t\t<true/>", plist_src)

        self.assertIn("expectedSha256", update_src)
        self.assertIn("isValidSameOriginUrl", update_src)
        self.assertIn("computeFileSha256", kt_src)
        self.assertIn("getPackageArchiveInfo", kt_src)

    def test_colas_fifo_persistencia_offline_y_no_encolar_errores_4xx(self):
        """Verifica colas FIFO en controladores, persistencia offline y filtrado de errores 4xx."""
        inv_ctrl = (
            MOBILE_DIR / "lib" / "controllers" / "inventory_controller.dart"
        ).read_text(encoding="utf-8")
        disp_ctrl = (
            MOBILE_DIR / "lib" / "controllers" / "dispatch_controller.dart"
        ).read_text(encoding="utf-8")

        # Cola FIFO en inventario + soporte offline + deshacer eliminación
        self.assertIn("_colaEscaneos", inv_ctrl)
        self.assertIn("_drenarColaEscaneos", inv_ctrl)
        self.assertIn("deshacerEliminacion", inv_ctrl)
        self.assertIn("Guardado offline", inv_ctrl)

        # Cola FIFO en despacho + persistencia offline + solo errores de red en colaOffline
        self.assertIn("_colaEscaneos", disp_ctrl)
        self.assertIn("_cargarColaOfflinePersistida", disp_ctrl)
        self.assertIn("_guardarColaOffline", disp_ctrl)
        self.assertIn("esFallaDeRed", disp_ctrl)
        self.assertNotIn("_legacy_close", disp_ctrl)

    def test_ergonomia_ux_foco_tabs_y_tema_alto_contraste(self):
        """Verifica mejoras UX: ValueListenableBuilder, >= 48dp, tema claro/oscuro, láser y RBAC."""
        barcode_src = (
            MOBILE_DIR / "lib" / "widgets" / "barcode_scan_field.dart"
        ).read_text(encoding="utf-8")
        inv_tab = (
            MOBILE_DIR / "lib" / "screens" / "tabs" / "inventory_tab.dart"
        ).read_text(encoding="utf-8")
        disp_tab = (
            MOBILE_DIR / "lib" / "screens" / "tabs" / "dispatch_tab.dart"
        ).read_text(encoding="utf-8")
        cat_tab = (
            MOBILE_DIR / "lib" / "screens" / "tabs" / "catalog_tab.dart"
        ).read_text(encoding="utf-8")
        home_src = (MOBILE_DIR / "lib" / "screens" / "home_screen.dart").read_text(
            encoding="utf-8"
        )
        theme_src = (MOBILE_DIR / "lib" / "theme" / "app_theme.dart").read_text(
            encoding="utf-8"
        )

        self.assertIn("ValueListenableBuilder<TextEditingValue>", barcode_src)
        self.assertIn("laserMode", barcode_src)
        self.assertIn("minHeight: 48", barcode_src)

        self.assertIn("DESHACER", inv_tab)
        self.assertIn("PopScope", inv_tab)
        self.assertIn("minHeight: 48", inv_tab)

        self.assertIn("canRevertDispatchState", disp_tab)
        self.assertIn("RefreshIndicator", disp_tab)
        self.assertIn("reconnectSyncTrigger", disp_tab)

        self.assertIn("ValueListenableBuilder<TextEditingValue>", cat_tab)
        self.assertIn("keyboardType: TextInputType.text", cat_tab)
        self.assertNotIn("keyboardType: TextInputType.number", cat_tab)
        self.assertIn("canEditCatalog", cat_tab)

        self.assertIn("onUnauthorized: _manejarSesionExpirada", home_src)
        self.assertIn("ONLINE", home_src)
        self.assertIn("OFFLINE", home_src)
        self.assertIn("lightTheme", theme_src)
        self.assertIn("themeModeNotifier", theme_src)


if __name__ == "__main__":
    unittest.main()
