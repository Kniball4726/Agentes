"""Tests unitarios para las funcionalidades de la Fase 1:
1. Telemetría de infraestructura y salud del servidor (Rol Master).
2. Soporte Barcode Wedge y feedback acústico para colectores de depósito.
3. Archivador inteligente de comprobantes históricos en subcarpetas cronológicas.
"""

import os
import tempfile
import time
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from src.archive_manager import archivar_comprobantes_antiguos, obtener_estadisticas_almacenamiento
from src.orders_store import Pedido
from src.system_telemetry import TelemetriaSistema, obtener_telemetria_sistema
from src.ui.audio_feedback import emitir_tono_error, emitir_tono_exito, normalizar_codigo_lector
from src.ui.dialogs.dlg_historial_pedidos import buscar_archivo_comprobante, buscar_archivo_descuento


class TestFase1Features(unittest.TestCase):
    def test_telemetria_sistema_retorna_metricas_validas(self):
        """Verifica que el módulo de telemetría calcule correctamente almacenamiento y salud."""
        telem = obtener_telemetria_sistema()
        self.assertIsInstance(telem, TelemetriaSistema)
        self.assertGreater(telem.disco_total_gb, 0)
        self.assertGreaterEqual(telem.disco_libre_gb, 0)
        self.assertTrue(0 <= telem.disco_usado_pct <= 100)
        self.assertIsInstance(telem.disco_alerta, bool)
        self.assertGreater(telem.ram_total_gb, 0)
        self.assertTrue(0 <= telem.ram_carga_pct <= 100)
        self.assertGreaterEqual(telem.ram_proceso_mb, 0)
        self.assertIn(telem.estado_salud, ("Óptimo", "Atención", "Crítico"))
        self.assertTrue(len(telem.detalle_salud) > 0)

    def test_normalizar_codigo_lector_soporta_barcode_wedge_y_aim(self):
        """Verifica que se limpien prefijos AIM, saltos de línea y caracteres de control de pistolas."""
        # Código normal limpio
        self.assertEqual(normalizar_codigo_lector("7791234567890"), "7791234567890")
        # Con espacios y salto de línea de pistola láser
        self.assertEqual(normalizar_codigo_lector("  7791234567890 \r\n"), "7791234567890")
        # Con prefijo AIM de lectores industriales (]C1 = Code 128, ]e0 = EAN)
        self.assertEqual(normalizar_codigo_lector("]C17791234567890"), "7791234567890")
        self.assertEqual(normalizar_codigo_lector("]e0779888899990"), "779888899990")
        # Con caracteres de control invisibles
        self.assertEqual(normalizar_codigo_lector("SKU-100\x00\x07"), "SKU-100")
        # Caso vacío o nulo
        self.assertEqual(normalizar_codigo_lector(""), "")
        self.assertEqual(normalizar_codigo_lector(None), "")

    def test_feedback_acustico_no_genera_excepciones(self):
        """Verifica que las funciones de emisión de tono se ejecuten de manera segura."""
        with patch("winsound.Beep", return_value=None):
            emitir_tono_exito()
            emitir_tono_error()

    def test_archivador_comprobantes_historicos_organiza_por_anio_y_mes(self):
        """Verifica que los comprobantes antiguos se muevan correctamente a data/historico/YYYY/MM/."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            dir_pedidos = tmp_root / "data" / "pedidos_archivos"
            dir_descontados = tmp_root / "data" / "descontados"
            dir_pedidos.mkdir(parents=True, exist_ok=True)
            dir_descontados.mkdir(parents=True, exist_ok=True)

            # Archivo nuevo (hoy)
            archivo_nuevo = dir_pedidos / "remito_hoy.pdf"
            archivo_nuevo.write_text("contenido nuevo", encoding="utf-8")

            # Archivo antiguo (hace 45 días)
            archivo_antiguo_1 = dir_pedidos / "remito_antiguo.pdf"
            archivo_antiguo_1.write_text("contenido antiguo 1", encoding="utf-8")
            dt_45_dias = datetime.now() - timedelta(days=45)
            t_45 = dt_45_dias.timestamp()
            os.utime(archivo_antiguo_1, (t_45, t_45))

            # Archivo antiguo en descontados (hace 60 días)
            archivo_antiguo_2 = dir_descontados / "descuento_antiguo.xlsx"
            archivo_antiguo_2.write_text("contenido antiguo 2", encoding="utf-8")
            dt_60_dias = datetime.now() - timedelta(days=60)
            t_60 = dt_60_dias.timestamp()
            os.utime(archivo_antiguo_2, (t_60, t_60))

            # Verificar estadísticas antes de archivar
            stats_antes = obtener_estadisticas_almacenamiento(tmp_root)
            self.assertEqual(stats_antes["pedidos_archivos_cant"], 2)
            self.assertEqual(stats_antes["descontados_cant"], 1)
            self.assertEqual(stats_antes["historico_cant"], 0)

            # Ejecutar archivado con umbral de 30 días
            resultado = archivar_comprobantes_antiguos(dias_antiguedad=30, root_path=tmp_root)
            self.assertEqual(resultado["archivos_movidos"], 2)

            # El archivo nuevo debe permanecer en su lugar
            self.assertTrue(archivo_nuevo.exists())
            self.assertFalse(archivo_antiguo_1.exists())
            self.assertFalse(archivo_antiguo_2.exists())

            # Comprobar que existen en la carpeta historica YYYY/MM
            dir_hist = tmp_root / "data" / "historico"
            yyyy_1 = dt_45_dias.strftime("%Y")
            mm_1 = dt_45_dias.strftime("%m")
            dest_1 = dir_hist / yyyy_1 / mm_1 / "remito_antiguo.pdf"
            self.assertTrue(dest_1.exists())

            # Verificar estadísticas después del archivado
            stats_despues = obtener_estadisticas_almacenamiento(tmp_root)
            self.assertEqual(stats_despues["pedidos_archivos_cant"], 1)
            self.assertEqual(stats_despues["descontados_cant"], 0)
            self.assertEqual(stats_despues["historico_cant"], 2)

    def test_historial_pedidos_resuelve_archivos_en_carpeta_historica(self):
        """Verifica que buscar_archivo_comprobante encuentre comprobantes archivados en data/historico/."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            carpeta_hist = tmp_root / "data" / "historico" / "2026" / "05"
            carpeta_hist.mkdir(parents=True, exist_ok=True)

            archivo_remito = carpeta_hist / "Remito_Hist_9999.pdf"
            archivo_remito.write_text("PDF binario simulado", encoding="utf-8")

            archivo_desc = carpeta_hist / "Descuento_Hist_9999.pdf"
            archivo_desc.write_text("PDF descuento simulado", encoding="utf-8")

            pedido = types.SimpleNamespace(
                nombre_archivo="Remito_Hist_9999.pdf",
                archivo_descuento="Descuento_Hist_9999.pdf",
            )

            with patch("src.ui.dialogs.dlg_historial_pedidos.application_root", return_value=tmp_root):
                res_comprobante = buscar_archivo_comprobante(pedido)
                self.assertIsNotNone(res_comprobante)
                self.assertEqual(res_comprobante.name, "Remito_Hist_9999.pdf")

                res_descuento = buscar_archivo_descuento(pedido)
                self.assertIsNotNone(res_descuento)
                self.assertEqual(res_descuento.name, "Descuento_Hist_9999.pdf")


if __name__ == "__main__":
    unittest.main()
