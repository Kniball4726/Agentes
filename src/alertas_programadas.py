"""Alertas automáticas por correo: resumen diario de stock crítico, pedidos y despachos.

Se ejecuta en un hilo de fondo dentro del servidor. Solo envía por SMTP (no depende de que haya
un usuario con la interfaz abierta). La configuración vive en ``data/email_config.json`` bajo la
clave ``alertas`` y se edita desde Administración → Configurar correo.
"""

from __future__ import annotations

import logging
import threading
from datetime import date, datetime
from pathlib import Path

from .email_sender import enviar_via_smtp, guardar_config_email, obtener_config_email
from .orders_store import OrderStore
from .paths import application_root
from .product_store import ProductStore

logger = logging.getLogger("stockagent.alertas")


def construir_resumen(
    ruta_productos_db: Path | None = None,
    ruta_pedidos_db: Path | None = None,
) -> tuple[str, str, int]:
    """Arma (asunto, cuerpo, cantidad_de_alertas) con el estado actual del depósito."""
    raiz = application_root() / "data"
    productos = ProductStore(ruta_productos_db or raiz / "productos.sqlite3")
    pedidos = OrderStore(ruta_pedidos_db or raiz / "pedidos.sqlite3")

    hoy = date.today().isoformat()
    criticos = productos.get_replenishment_analysis(only_critical=True)
    metricas_hoy = pedidos.obtener_metricas_dashboard(hoy, hoy)
    pendientes_cierre = len(pedidos.listar_pedidos_pendientes_cierre())
    despacho = metricas_hoy["estados_despacho"]

    agotados = [r for r in criticos if r["estado_inventario"] == "AGOTADO"]
    inminentes = [r for r in criticos if r["estado_inventario"] != "AGOTADO"]

    lineas = [
        f"Resumen diario del depósito - {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
        "PEDIDOS DE HOY",
        f"• Pedidos cargados: {metricas_hoy['total_pedidos']} ({metricas_hoy['total_bultos']} bultos)",
        f"• Pendientes de cierre de jornada: {pendientes_cierre}",
        f"• Armados: {despacho['armado']} | Despachados: {despacho['despachado']} | "
        f"Entregados: {despacho['entregado']}",
        "",
        f"STOCK CRÍTICO ({len(criticos)} producto(s))",
    ]
    if not criticos:
        lineas.append("• Sin productos en quiebre ni bajo el mínimo de seguridad.")
    for titulo, grupo in (("AGOTADOS", agotados), ("QUIEBRE INMINENTE", inminentes)):
        if not grupo:
            continue
        lineas.append(f"-- {titulo} --")
        for r in grupo[:25]:
            lineas.append(
                f"• [{r['code']}] {r['name']}: stock {r['stock']} "
                f"(mín {r['stock_minimo']}) → sugerido pedir +{r['cantidad_sugerida_pedir']}"
            )
        if len(grupo) > 25:
            lineas.append(f"  ... y {len(grupo) - 25} más.")
    lineas += ["", "Mensaje generado automáticamente por StockAgent."]
    asunto = (
        f"[StockAgent] {len(criticos)} alerta(s) de stock - {datetime.now().strftime('%d/%m/%Y')}"
        if criticos
        else f"[StockAgent] Resumen diario sin alertas - {datetime.now().strftime('%d/%m/%Y')}"
    )
    return asunto, "\n".join(lineas), len(criticos)


def enviar_resumen_ahora(destinatarios: list[str] | None = None) -> tuple[bool, str]:
    """Envía el resumen inmediatamente usando la configuración SMTP guardada."""
    config = obtener_config_email()
    if not destinatarios:
        destinatarios = [
            d.strip()
            for d in str(config["alertas"].get("destinatarios", "")).replace(";", ",").split(",")
            if d.strip()
        ]
    if not destinatarios:
        return False, "No hay destinatarios configurados para las alertas."
    asunto, cuerpo, _ = construir_resumen()
    return enviar_via_smtp(destinatarios, asunto, cuerpo, [], config)


class PlanificadorAlertas(threading.Thread):
    """Revisa cada minuto si corresponde enviar el resumen diario."""

    def __init__(self) -> None:
        super().__init__(name="PlanificadorAlertas", daemon=True)
        self._detener = threading.Event()

    def detener(self) -> None:
        self._detener.set()

    def run(self) -> None:
        while not self._detener.wait(60):
            try:
                self.revisar()
            except Exception:  # noqa: BLE001 - el hilo nunca debe morir
                logger.exception("Error en el planificador de alertas")

    @staticmethod
    def revisar(ahora: datetime | None = None) -> bool:
        """Envía el resumen si está activo, es la hora y aún no se envió hoy. Devuelve si envió."""
        ahora = ahora or datetime.now()
        config = obtener_config_email()
        alertas = config["alertas"]
        if not alertas.get("activo"):
            return False
        if alertas.get("ultimo_envio") == ahora.date().isoformat():
            return False
        try:
            hh, mm = (int(x) for x in str(alertas.get("hora", "08:00")).split(":", 1))
        except ValueError:
            hh, mm = 8, 0
        if (ahora.hour, ahora.minute) < (hh, mm):
            return False
        ok, mensaje = enviar_resumen_ahora()
        if ok:
            alertas["ultimo_envio"] = ahora.date().isoformat()
            config["alertas"] = alertas
            guardar_config_email(config)
            logger.info("Resumen diario enviado: %s", mensaje)
            return True
        logger.warning("No se pudo enviar el resumen diario: %s", mensaje)
        return False


_planificador: PlanificadorAlertas | None = None


def iniciar_planificador() -> None:
    """Arranca (una sola vez) el hilo de alertas programadas."""
    global _planificador
    if _planificador is None or not _planificador.is_alive():
        _planificador = PlanificadorAlertas()
        _planificador.start()
