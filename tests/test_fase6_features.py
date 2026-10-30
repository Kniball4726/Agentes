"""Pruebas unitarias para la Fase 6: Matriz de Rotación ABC, Heatmap de Depósito y Optimización de Slotting."""

import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

import flet as ft

from src.product_store import ProductStore
from src.warehouse_slotting import (
    DEFAULT_RACKS,
    SlotInfo,
    analizar_rotacion_abc,
    aplicar_reubicacion_slotting,
    calcular_metricas_deposito,
    generar_mapa_calor,
    generar_sugerencias_slotting,
    generar_ubicacion_default,
)


class TestFase6WarehouseSlotting(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_productos.sqlite3"
        self.store = ProductStore(self.db_path)

        # Poblar productos de prueba
        with closing(self.store._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO products (code, name, stock, active, ubicacion)
                VALUES 
                    ('SKU-A1', 'Artículo Estrella 1', 100, 1, 'D-04-3'),
                    ('SKU-A2', 'Artículo Estrella 2', 80, 1, 'C-02-1'),
                    ('SKU-B1', 'Artículo Medio 1', 50, 1, 'B-01-2'),
                    ('SKU-C1', 'Artículo Lento 1', 20, 1, 'A-01-2'),
                    ('SKU-C2', 'Artículo Lento 2', 10, 1, 'D-01-1')
                """
            )
            # Insertar movimientos históricos de salida (descuentos)
            conn.execute(
                """
                INSERT INTO stock_movements (product_code, product_name, quantity, movement_type, registered_at)
                VALUES
                    ('SKU-A1', 'Artículo Estrella 1', -50, 'descuento', '2026-10-25T10:00:00'),
                    ('SKU-A1', 'Artículo Estrella 1', -40, 'descuento', '2026-10-26T11:00:00'),
                    ('SKU-A1', 'Artículo Estrella 1', -30, 'descuento', '2026-10-27T12:00:00'),
                    ('SKU-A2', 'Artículo Estrella 2', -35, 'descuento', '2026-10-25T14:00:00'),
                    ('SKU-A2', 'Artículo Estrella 2', -25, 'descuento', '2026-10-26T15:00:00'),
                    ('SKU-B1', 'Artículo Medio 1', -15, 'descuento', '2026-10-25T16:00:00'),
                    ('SKU-C1', 'Artículo Lento 1', -2, 'descuento', '2026-10-25T17:00:00')
                """
            )

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_clasificacion_abc_pareto(self):
        """Verifica que el análisis clasifique correctamente en A, B y C según volumen de picks."""
        abc = analizar_rotacion_abc(self.store, dias=30)
        self.assertEqual(len(abc), 5)

        # SKU-A1 tiene 3 picks (mayor volumen)
        p_a1 = next(p for p in abc if p.codigo == "SKU-A1")
        self.assertEqual(p_a1.categoria_abc, "A")
        self.assertEqual(p_a1.total_despachos, 3)
        self.assertEqual(p_a1.unidades_despachadas, 120)

        # SKU-C2 tiene 0 picks -> Clase C
        p_c2 = next(p for p in abc if p.codigo == "SKU-C2")
        self.assertEqual(p_c2.categoria_abc, "C")
        self.assertEqual(p_c2.total_despachos, 0)

    def test_deteccion_desalineacion_slotting(self):
        """Verifica la detección de ineficiencias (Fast-Mover en fondo/altura y Slow-Mover en zona dorada)."""
        abc = analizar_rotacion_abc(self.store, dias=30)

        # SKU-A1 es Clase A pero está en D-04-3 (Rack D fondo, Nivel 3 altura) -> Desalineado
        p_a1 = next(p for p in abc if p.codigo == "SKU-A1")
        self.assertTrue(p_a1.desalineado)
        self.assertIn("fondo", p_a1.motivo_desalineacion.lower())

        # SKU-C1 es Clase C pero está en A-01-2 (Rack A cabecera, Nivel 2 dorada) -> Desalineado
        p_c1 = next(p for p in abc if p.codigo == "SKU-C1")
        self.assertTrue(p_c1.desalineado)
        self.assertIn("dorada", p_c1.motivo_desalineacion.lower())

        # SKU-C2 está en D-01-1 (Fondo nivel piso) -> No desalineado
        p_c2 = next(p for p in abc if p.codigo == "SKU-C2")
        self.assertFalse(p_c2.desalineado)

    def test_generacion_mapa_calor_layout(self):
        """Verifica la generación de la matriz de calor para todas las 48 ubicaciones estándar."""
        abc = analizar_rotacion_abc(self.store, dias=30)
        heatmap = generar_mapa_calor(abc)

        # 4 Racks x 4 Módulos x 3 Niveles = 48 slots
        self.assertEqual(len(heatmap), 48)

        # D-04-3 aloja a SKU-A1 (3 picks, máximo) -> Debe ser el más caliente
        slot_top = next(s for s in heatmap if s.ubicacion == "D-04-3")
        self.assertEqual(slot_top.picks_totales, 3)
        self.assertEqual(slot_top.heat_score, 100.0)
        self.assertEqual(slot_top.temperatura, "muy_caliente")
        self.assertEqual(slot_top.color_hex, "#D32F2F")

        # Un slot vacío debe ser frío
        slot_vacio = next(s for s in heatmap if s.ubicacion == "B-04-3")
        self.assertEqual(slot_vacio.picks_totales, 0)
        self.assertEqual(slot_vacio.temperatura, "frio")

    def test_generacion_sugerencias_slotting(self):
        """Verifica que se generen sugerencias accionables para los productos desalineados."""
        abc = analizar_rotacion_abc(self.store, dias=30)
        sugerencias = generar_sugerencias_slotting(abc)

        self.assertGreaterEqual(len(sugerencias), 2)
        # La primera sugerencia debe ser Clase A (alta prioridad)
        self.assertEqual(sugerencias[0].categoria_abc, "A")
        self.assertIn("SKU-A", sugerencias[0].sku)
        # La sugerencia debe recomendar reubicarlo a Rack A o B, Nivel 2
        self.assertTrue(sugerencias[0].ubicacion_sugerida.endswith("-2"))

    def test_persistencia_y_reubicacion_producto(self):
        """Verifica que aplicar_reubicacion_slotting persista la nueva ubicación en SQLite."""
        nueva_pos = "A-02-2"
        exito = aplicar_reubicacion_slotting(self.store, "SKU-A1", nueva_pos)
        self.assertTrue(exito)

        # Consultar producto
        row = self.store.get_product("SKU-A1")
        self.assertIsNotNone(row)
        self.assertEqual(row["ubicacion"], nueva_pos)

    def test_metricas_globales_deposito(self):
        """Verifica el cálculo de KPIs de eficiencia de slotting."""
        abc = analizar_rotacion_abc(self.store, dias=30)
        heatmap = generar_mapa_calor(abc)
        metricas = calcular_metricas_deposito(abc, heatmap)

        self.assertEqual(metricas.total_skus, 5)
        self.assertGreater(metricas.total_picks, 0)
        self.assertGreaterEqual(metricas.eficiencia_slotting_pct, 0.0)
        self.assertLessEqual(metricas.eficiencia_slotting_pct, 100.0)
        self.assertIn("D-04-3", metricas.zona_mas_caliente)


if __name__ == "__main__":
    unittest.main()
