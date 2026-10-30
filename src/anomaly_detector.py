"""Módulo Analítico de Detección de Consumo Anómalo y Alertas Inteligentes de Demanda.

Detecta preventivamente:
1. Picos Anómalos de Demanda Diaria:
   Salida del día actual significativamente superior a la media histórica (Z-score > 2.0 / > μ + 2σ).
2. Descuentos Masivos Individuales:
   Un único comprobante o pedido que descuenta más del 50% de las existencias actuales de un SKU.
3. Velocidad Acelerada de Agotamiento (Run-out Run-rate):
   Proyección de días de cobertura de stock restantes < 3 días según el ritmo de consumo reciente.
"""

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .paths import application_root
from .telegram_notifier import notificar_anomalia_demanda_telegram


@dataclass
class AlertaConsumoAnomalo:
    codigo: str
    nombre: str
    tipo: str  # "PICO_ANOMALO" | "DESCUENTO_MASIVO" | "AGOTAMIENTO_ACELERADO"
    consumo_detectado: int
    promedio_historico: float
    desviacion_estandar: float
    stock_actual: int
    dias_cobertura: Optional[float]
    severidad: str  # "CRITICA" | "ALTA" | "ADVERTENCIA"
    mensaje: str
    fecha_deteccion: str = ""


def calcular_media_y_desvio(valores: list[int | float]) -> tuple[float, float]:
    """Calcula la media aritmética (μ) y la desviación estándar muestral (s)."""
    n = len(valores)
    if n == 0:
        return 0.0, 0.0
    media = sum(valores) / n
    if n < 2:
        return media, 0.0
    varianza = sum((x - media) ** 2 for x in valores) / (n - 1)
    return media, math.sqrt(varianza)


def analizar_desvios_consumo_diario(
    product_store: Any,
    dias_historico: int = 30,
    umbral_desvios: float = 2.0,
    min_unidades_hoy: int = 5,
    fecha_hoy: str | None = None,
) -> list[AlertaConsumoAnomalo]:
    """Detecta artículos cuya salida acumulada en el día supera la media histórica en más de N desvíos estándar."""
    hoy_str = fecha_hoy or datetime.now().strftime("%Y-%m-%d")
    desde_dt = datetime.strptime(hoy_str, "%Y-%m-%d") - timedelta(days=dias_historico)
    desde_str = desde_dt.strftime("%Y-%m-%d")

    alertas: list[AlertaConsumoAnomalo] = []

    with closing(product_store._connect()) as conn:
        # Agrupar salidas diarias de los últimos N días por código y fecha
        rows = conn.execute(
            """
            SELECT 
                m.product_code,
                m.product_name,
                substr(m.registered_at, 1, 10) as fecha,
                SUM(ABS(m.quantity)) as total_dia,
                p.stock as stock_actual
            FROM stock_movements m
            LEFT JOIN products p ON p.code = m.product_code
            WHERE m.movement_type = 'descuento'
              AND substr(m.registered_at, 1, 10) >= ?
              AND substr(m.registered_at, 1, 10) <= ?
            GROUP BY m.product_code, substr(m.registered_at, 1, 10)
            ORDER BY m.product_code, fecha ASC
            """,
            (desde_str, hoy_str),
        ).fetchall()

    # Organizar consumos por producto: {codigo: {"nombre": ..., "stock": ..., "historico": [...], "hoy": int}}
    datos_prod: dict[str, dict[str, Any]] = {}
    for r in rows:
        cod = str(r["product_code"]).strip()
        fec = str(r["fecha"]).strip()
        cant = int(r["total_dia"])
        stk = int(r["stock_actual"] or 0)
        nom = str(r["product_name"] or cod).strip()

        if cod not in datos_prod:
            datos_prod[cod] = {
                "nombre": nom,
                "stock": stk,
                "historico": [],
                "hoy": 0,
            }

        if fec == hoy_str:
            datos_prod[cod]["hoy"] += cant
        else:
            datos_prod[cod]["historico"].append(cant)

    for cod, info in datos_prod.items():
        consumo_hoy = info["hoy"]
        hist = info["historico"]
        stk = info["stock"]
        nom = info["nombre"]

        # Si hoy no hubo consumo o el consumo es menor al mínimo de significancia estadística, saltar
        if consumo_hoy < min_unidades_hoy:
            continue

        # Necesitamos al menos 3 días previos registrados para tener significancia estadística
        if len(hist) < 3:
            # Fallback para productos con poco historial: si hoy salió más del doble del stock restante
            if stk > 0 and consumo_hoy >= 2 * stk:
                alertas.append(
                    AlertaConsumoAnomalo(
                        codigo=cod,
                        nombre=nom,
                        tipo="PICO_ANOMALO",
                        consumo_detectado=consumo_hoy,
                        promedio_historico=float(sum(hist) / max(1, len(hist))),
                        desviacion_estandar=0.0,
                        stock_actual=stk,
                        dias_cobertura=None,
                        severidad="ALTA",
                        mensaje=f"Salida súbita de {consumo_hoy} un. sin suficiente historial comparativo previo.",
                        fecha_deteccion=hoy_str,
                    )
                )
            continue

        media, desvio = calcular_media_y_desvio(hist)

        # Umbral dinámico: media + (umbral * desvio)
        limite_anomalia = media + (umbral_desvios * desvio)
        # Si la desviación estándar es 0 (ventas constantes), usamos 2 * media como umbral
        if desvio < 0.01:
            limite_anomalia = max(limite_anomalia, media * 2.0)

        if consumo_hoy > limite_anomalia:
            z_score = (consumo_hoy - media) / desvio if desvio > 0 else (consumo_hoy / max(0.1, media))
            severidad = "CRITICA" if z_score >= 3.0 or consumo_hoy >= stk else "ALTA"
            dias_cobertura = (stk / (consumo_hoy / 1.0)) if consumo_hoy > 0 else None

            mensaje = (
                f"Consumo de hoy ({consumo_hoy} un.) superó la media habitual de {media:.1f} un. "
                f"(Desvío: +{z_score:.1f}σ, Umbral alerta: {limite_anomalia:.1f} un.)."
            )

            alertas.append(
                AlertaConsumoAnomalo(
                    codigo=cod,
                    nombre=nom,
                    tipo="PICO_ANOMALO",
                    consumo_detectado=consumo_hoy,
                    promedio_historico=round(media, 1),
                    desviacion_estandar=round(desvio, 1),
                    stock_actual=stk,
                    dias_cobertura=round(dias_cobertura, 1) if dias_cobertura is not None else None,
                    severidad=severidad,
                    mensaje=mensaje,
                    fecha_deteccion=hoy_str,
                )
            )

    return sorted(alertas, key=lambda a: (a.severidad == "CRITICA", a.consumo_detectado), reverse=True)


def analizar_descuentos_masivos_individuales(
    product_store: Any,
    fecha_iso: str | None = None,
    umbral_pct: float = 0.50,
    min_unidades: int = 5,
) -> list[AlertaConsumoAnomalo]:
    """Detecta si un solo pedido o comprobante descontó el 50% o más de las existencias disponibles de un producto."""
    hoy_str = fecha_iso or datetime.now().strftime("%Y-%m-%d")
    alertas: list[AlertaConsumoAnomalo] = []

    with closing(product_store._connect()) as conn:
        rows = conn.execute(
            """
            SELECT 
                dd.product_code,
                p.name as product_name,
                dd.cantidad_descontada,
                dd.stock_anterior,
                dd.stock_nuevo,
                d.nombre_archivo,
                d.fecha,
                d.usuario
            FROM despacho_detalles dd
            JOIN despachos d ON d.id = dd.despacho_id
            LEFT JOIN products p ON p.code = dd.product_code
            WHERE substr(d.fecha, 1, 10) = ?
              AND dd.cantidad_descontada >= ?
              AND dd.stock_anterior > 0
              AND (CAST(dd.cantidad_descontada AS REAL) / dd.stock_anterior) >= ?
            ORDER BY dd.cantidad_descontada DESC
            """,
            (hoy_str, min_unidades, umbral_pct),
        ).fetchall()

    for r in rows:
        cod = str(r["product_code"]).strip()
        nom = str(r["product_name"] or cod).strip()
        cant = int(r["cantidad_descontada"])
        stk_ant = int(r["stock_anterior"])
        stk_post = int(r["stock_nuevo"])
        arch = str(r["nombre_archivo"])
        porcentaje = (cant / stk_ant) * 100.0 if stk_ant > 0 else 100.0

        severidad = "CRITICA" if porcentaje >= 75.0 or stk_post <= 0 else "ALTA"
        mensaje = (
            f"Descuento individual del {porcentaje:.0f}% del inventario disponible "
            f"({cant} de {stk_ant} un.) en el comprobante '{arch}' (Stock restante: {stk_post} un.)."
        )

        alertas.append(
            AlertaConsumoAnomalo(
                codigo=cod,
                nombre=nom,
                tipo="DESCUENTO_MASIVO",
                consumo_detectado=cant,
                promedio_historico=float(stk_ant),
                desviacion_estandar=0.0,
                stock_actual=stk_post,
                dias_cobertura=None,
                severidad=severidad,
                mensaje=mensaje,
                fecha_deteccion=str(r["fecha"]),
            )
        )

    return alertas


def analizar_velocidad_agotamiento(
    product_store: Any,
    dias_analisis: int = 14,
    umbral_dias_cobertura: float = 3.0,
) -> list[AlertaConsumoAnomalo]:
    """Estima la velocidad de agotamiento (run-out) proyectada según el ritmo de consumo reciente."""
    hoy_dt = datetime.now()
    desde_str = (hoy_dt - timedelta(days=dias_analisis)).strftime("%Y-%m-%d")
    hoy_str = hoy_dt.strftime("%Y-%m-%d")

    alertas: list[AlertaConsumoAnomalo] = []

    with closing(product_store._connect()) as conn:
        rows = conn.execute(
            """
            SELECT 
                p.code as product_code,
                p.name as product_name,
                p.stock as stock_actual,
                p.stock_minimo,
                COALESCE(SUM(ABS(m.quantity)), 0) as total_descontado
            FROM products p
            LEFT JOIN stock_movements m 
                ON m.product_code = p.code 
               AND m.movement_type = 'descuento'
               AND substr(m.registered_at, 1, 10) >= ?
               AND substr(m.registered_at, 1, 10) <= ?
            WHERE p.active = 1
              AND p.stock > 0
            GROUP BY p.code
            HAVING total_descontado > 0
            """,
            (desde_str, hoy_str),
        ).fetchall()

    for r in rows:
        cod = str(r["product_code"]).strip()
        nom = str(r["product_name"] or cod).strip()
        stk = int(r["stock_actual"])
        total_desc = int(r["total_descontado"])

        consumo_diario = total_desc / float(dias_analisis)
        if consumo_diario <= 0:
            continue

        dias_cobertura = stk / consumo_diario

        if dias_cobertura <= umbral_dias_cobertura:
            severidad = "CRITICA" if dias_cobertura <= 1.5 else "ADVERTENCIA"
            mensaje = (
                f"Ritmo de salida de {consumo_diario:.1f} un./día en los últimos {dias_analisis} días. "
                f"El stock actual de {stk} un. se agotará en aprox. {dias_cobertura:.1f} días de trabajo."
            )

            alertas.append(
                AlertaConsumoAnomalo(
                    codigo=cod,
                    nombre=nom,
                    tipo="AGOTAMIENTO_ACELERADO",
                    consumo_detectado=total_desc,
                    promedio_historico=round(consumo_diario, 2),
                    desviacion_estandar=0.0,
                    stock_actual=stk,
                    dias_cobertura=round(dias_cobertura, 1),
                    severidad=severidad,
                    mensaje=mensaje,
                    fecha_deteccion=hoy_str,
                )
            )

    return sorted(alertas, key=lambda a: a.dias_cobertura or 999)


def ejecutar_diagnostico_integral_anomalias(
    product_store: Any,
    fecha_hoy: str | None = None,
) -> dict[str, list[AlertaConsumoAnomalo]]:
    """Ejecuta los tres análisis analíticos y retorna las anomalías clasificadas."""
    picos = analizar_desvios_consumo_diario(product_store, fecha_hoy=fecha_hoy)
    masivos = analizar_descuentos_masivos_individuales(product_store, fecha_iso=fecha_hoy)
    agotamiento = analizar_velocidad_agotamiento(product_store)

    return {
        "picos": picos,
        "descuentos_masivos": masivos,
        "agotamiento": agotamiento,
        "total_anomalias": len(picos) + len(masivos) + len(agotamiento),
    }


def notificar_anomalias_detectadas(
    alertas: list[AlertaConsumoAnomalo],
    product_store: Any,
    notificar_telegram: bool = True,
    root_path: Path | None = None,
) -> int:
    """Registra las anomalías críticas en las notificaciones del administrador y las despacha por Telegram."""
    total_notificadas = 0
    for a in alertas:
        try:
            # Registrar en admin_notifications
            product_store.create_admin_notification(
                title=f"⚠️ {a.tipo}: [{a.codigo}] {a.nombre[:30]}",
                message=a.mensaje,
                operator_username="Sistema Analítico",
                notification_type="anomalia_demanda",
                details=f"Consumo: {a.consumo_detectado} | Promedio: {a.promedio_historico} | Stock: {a.stock_actual}",
            )
            total_notificadas += 1

            # Despachar a Telegram si está activo y es severidad Alta/Crítica
            if notificar_telegram and a.severidad in ("CRITICA", "ALTA"):
                notificar_anomalia_demanda_telegram(
                    codigo=a.codigo,
                    nombre=a.nombre,
                    tipo_anomalia=a.tipo,
                    consumo_actual=a.consumo_detectado,
                    promedio_historico=a.promedio_historico,
                    mensaje=a.mensaje,
                    root_path=root_path,
                )
        except Exception as e:
            print(f"[AVISO] Error al registrar notificación de anomalía: {e}")

    return total_notificadas
