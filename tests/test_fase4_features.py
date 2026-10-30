"""Tests unitarios para las funcionalidades de la Fase 4:
1. Módulo analítico de detección de consumo anómalo (anomaly_detector.py).
2. Cálculo de media, desviación estándar muestral y Z-Score.
3. Detección de picos inusuales de demanda diaria (> μ + 2σ) con filtro de significancia.
4. Detección de descuentos masivos individuales (≥ 50% del stock disponible).
5. Estimación de velocidad de agotamiento (run-out run-rate ≤ 3 días de cobertura).
6. Registro de notificaciones de administración y alertas proactivas a Telegram.
"""

from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.anomaly_detector import (
    AlertaConsumoAnomalo,
    analizar_descuentos_masivos_individuales,
    analizar_desvios_consumo_diario,
    analizar_velocidad_agotamiento,
    calcular_media_y_desvio,
    ejecutar_diagnostico_integral_anomalias,
    notificar_anomalias_detectadas,
)
from src.product_store import ProductStore


class TestFase4Features(unittest.TestCase):
    def test_calcular_media_y_desvio(self):
        """Valida el cálculo estadístico de media y desviación estándar muestral."""
        # Caso vacío
        m0, d0 = calcular_media_y_desvio([])
        self.assertEqual(m0, 0.0)
        self.assertEqual(d0, 0.0)

        # Caso un solo elemento
        m1, d1 = calcular_media_y_desvio([10])
        self.assertEqual(m1, 10.0)
        self.assertEqual(d1, 0.0)

        # Caso muestra conocida [4, 6, 8] -> media=6.0, desvío=2.0
        m2, d2 = calcular_media_y_desvio([4, 6, 8])
        self.assertEqual(m2, 6.0)
        self.assertEqual(d2, 2.0)

    def test_analizar_desvios_consumo_diario_detecta_pico_anomalo(self):
        """Verifica que un consumo diario significativamente superior a la media histórica sea detectado."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            db_path = tmp_root / "test_products.sqlite3"
            store = ProductStore(db_path)

            # Insertar producto en base
            with closing(store._connect()) as conn, conn:
                conn.execute(
                    "INSERT INTO products (code, name, stock, active) VALUES (?, ?, ?, 1)",
                    ("101", "Creatina Micronizada 300g", 50),
                )

            hoy = datetime.now()
            hoy_str = hoy.strftime("%Y-%m-%d")

            # Registrar histórico regular en los 5 días previos (promedio ~5 unidades)
            movimientos_historicos = []
            for dias_atras, cant in enumerate([5, 6, 4, 5, 5], start=1):
                fecha_mov = (hoy - timedelta(days=dias_atras)).strftime("%Y-%m-%dT10:00:00")
                movimientos_historicos.append(("101", "Creatina Micronizada 300g", -cant, "descuento", fecha_mov))

            # Registrar consumo anómalo hoy: 28 unidades
            movimientos_historicos.append(("101", "Creatina Micronizada 300g", -28, "descuento", f"{hoy_str}T14:30:00"))

            with closing(store._connect()) as conn, conn:
                conn.executemany(
                    """
                    INSERT INTO stock_movements (product_code, product_name, quantity, movement_type, registered_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    movimientos_historicos,
                )

            # Ejecutar análisis
            alertas = analizar_desvios_consumo_diario(store, dias_historico=30, umbral_desvios=2.0, fecha_hoy=hoy_str)
            self.assertEqual(len(alertas), 1)
            alerta = alertas[0]
            self.assertEqual(alerta.codigo, "101")
            self.assertEqual(alerta.tipo, "PICO_ANOMALO")
            self.assertEqual(alerta.consumo_detectado, 28)
            self.assertEqual(alerta.promedio_historico, 5.0)
            self.assertIn("superó la media habitual", alerta.mensaje)

    def test_analizar_desvios_ignora_consumos_menores_al_umbral_minimo(self):
        """Evita falsos positivos en artículos con bajo volumen donde las cantidades no son significativas."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            db_path = tmp_root / "test_products.sqlite3"
            store = ProductStore(db_path)

            with closing(store._connect()) as conn, conn:
                conn.execute(
                    "INSERT INTO products (code, name, stock, active) VALUES (?, ?, ?, 1)",
                    ("202", "Shaker Metálico", 20),
                )

            hoy = datetime.now()
            hoy_str = hoy.strftime("%Y-%m-%d")

            movimientos = []
            for dias_atras in range(1, 5):
                fec = (hoy - timedelta(days=dias_atras)).strftime("%Y-%m-%dT10:00:00")
                movimientos.append(("202", "Shaker Metálico", -1, "descuento", fec))

            # Hoy salieron 2 (el doble de 1, pero < min_unidades_hoy=5)
            movimientos.append(("202", "Shaker Metálico", -2, "descuento", f"{hoy_str}T11:00:00"))

            with closing(store._connect()) as conn, conn:
                conn.executemany(
                    """
                    INSERT INTO stock_movements (product_code, product_name, quantity, movement_type, registered_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    movimientos,
                )

            alertas = analizar_desvios_consumo_diario(store, min_unidades_hoy=5, fecha_hoy=hoy_str)
            self.assertEqual(len(alertas), 0)

    def test_analizar_descuentos_masivos_individuales(self):
        """Verifica la detección de un pedido único que consume el 50% o más del stock disponible."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            db_path = tmp_root / "test_products.sqlite3"
            store = ProductStore(db_path)

            with closing(store._connect()) as conn, conn:
                conn.execute(
                    "INSERT INTO products (code, name, stock, active) VALUES (?, ?, ?, 1)",
                    ("303", "Proteina Isolate 2kg", 5),
                )
                cur_desp = conn.execute(
                    "INSERT INTO despachos (nombre_archivo, tipo_origen, total_articulos) VALUES (?, ?, ?)",
                    ("Remito_Mayorista_001.pdf", "Descuento", 15),
                )
                desp_id = cur_desp.lastrowid
                # Descuento de 15 sobre 20 disponibles (75% del stock)
                conn.execute(
                    """
                    INSERT INTO despacho_detalles (despacho_id, product_code, cantidad_descontada, stock_anterior, stock_nuevo)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (desp_id, "303", 15, 20, 5),
                )

            alertas = analizar_descuentos_masivos_individuales(store, umbral_pct=0.50, min_unidades=5)
            self.assertEqual(len(alertas), 1)
            alerta = alertas[0]
            self.assertEqual(alerta.codigo, "303")
            self.assertEqual(alerta.tipo, "DESCUENTO_MASIVO")
            self.assertEqual(alerta.consumo_detectado, 15)
            self.assertEqual(alerta.severidad, "CRITICA")
            self.assertIn("75%", alerta.mensaje)

    def test_analizar_velocidad_agotamiento_proyecta_cobertura(self):
        """Verifica que el run-rate proyecte con precisión los días de cobertura restantes."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            db_path = tmp_root / "test_products.sqlite3"
            store = ProductStore(db_path)

            # Stock actual de 6 unidades
            with closing(store._connect()) as conn, conn:
                conn.execute(
                    "INSERT INTO products (code, name, stock, stock_minimo, active) VALUES (?, ?, ?, ?, 1)",
                    ("404", "BCAA 500g", 6, 2),
                )

            hoy = datetime.now()
            # Salidas acumuladas de 28 unidades en los últimos 14 días (tasa = 2.0 un./día)
            movimientos = []
            for d in range(1, 15):
                fec = (hoy - timedelta(days=d)).strftime("%Y-%m-%dT10:00:00")
                movimientos.append(("404", "BCAA 500g", -2, "descuento", fec))

            with closing(store._connect()) as conn, conn:
                conn.executemany(
                    """
                    INSERT INTO stock_movements (product_code, product_name, quantity, movement_type, registered_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    movimientos,
                )

            # Proyección esperada: 6 unidades / 2.0 un./día = 3.0 días de cobertura
            alertas = analizar_velocidad_agotamiento(store, dias_analisis=14, umbral_dias_cobertura=3.0)
            self.assertEqual(len(alertas), 1)
            alerta = alertas[0]
            self.assertEqual(alerta.codigo, "404")
            self.assertEqual(alerta.tipo, "AGOTAMIENTO_ACELERADO")
            self.assertEqual(alerta.dias_cobertura, 3.0)
            self.assertIn("se agotará en aprox. 3.0 días", alerta.mensaje)

    def test_notificar_anomalias_detectadas_admin_y_telegram(self):
        """Verifica que las alertas se registren en admin_notifications y se envíen a Telegram."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            db_path = tmp_root / "test_products.sqlite3"
            store = ProductStore(db_path)

            alerta = AlertaConsumoAnomalo(
                codigo="101",
                nombre="Creatina Micronizada 300g",
                tipo="PICO_ANOMALO",
                consumo_detectado=30,
                promedio_historico=6.0,
                desviacion_estandar=1.5,
                stock_actual=10,
                dias_cobertura=1.2,
                severidad="CRITICA",
                mensaje="Pico crítico de consumo detectado.",
                fecha_deteccion=datetime.now().strftime("%Y-%m-%d"),
            )

            with patch("src.anomaly_detector.notificar_anomalia_demanda_telegram") as mock_tg:
                total = notificar_anomalias_detectadas([alerta], store, notificar_telegram=True, root_path=tmp_root)
                self.assertEqual(total, 1)
                mock_tg.assert_called_once()

            # Verificar persistencia en admin_notifications
            notifs = store.list_admin_notifications()
            self.assertEqual(len(notifs), 1)
            self.assertIn("PICO_ANOMALO", notifs[0]["title"])
            self.assertEqual(notifs[0]["notification_type"], "anomalia_demanda")


if __name__ == "__main__":
    unittest.main()
