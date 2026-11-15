"""Lógica de renderizado de listas y ejecución transaccional del Cierre de Jornada del operario."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import flet as ft

from ....backup_manager import crear_backup_sistema as _default_crear_backup
from ....consolidator import ItemConsolidado
from ....parsers.canjes_parser import parsear_canje_excel as _default_parsear_canje
from ....parsers.mercado_libre_parser import parsear_pedido_mercado_libre as _default_parsear_ml
from ....parsers.remito_parser import ItemRemito, ResultadoRemito, normalizar_codigo
from ....parsers.remito_parser import parsear_remito as _default_parsear_remito
from ....paths import application_root
from ....stock.manifest_pdf import generar_hoja_ruta_pdf as _default_generar_hoja_ruta
from ...theme import ROJO
from .cierre_reportes_helper import generar_reportes_cierre_jornada
from .hoja_ruta import (
    _get_stock_manager_cls as _default_get_sm_cls,
    gestionar_hoja_ruta_cierre,
    resolver_archivos_cierre,
)


def _resolver_dependencias_cierre():
    """Resuelve funciones potencialmente mockeadas sobre dlg_cierre_operario."""
    mod = sys.modules.get("src.ui.dialogs.cierre.dlg_cierre_operario")
    return {
        "get_sm_cls": getattr(mod, "_get_stock_manager_cls", _default_get_sm_cls) if mod else _default_get_sm_cls,
        "parsear_remito": getattr(mod, "parsear_remito", _default_parsear_remito) if mod else _default_parsear_remito,
        "parsear_canje": getattr(mod, "parsear_canje_excel", _default_parsear_canje) if mod else _default_parsear_canje,
        "parsear_ml": getattr(mod, "parsear_pedido_mercado_libre", _default_parsear_ml) if mod else _default_parsear_ml,
        "generar_hr": getattr(mod, "generar_hoja_ruta_pdf", _default_generar_hoja_ruta) if mod else _default_generar_hoja_ruta,
        "crear_backup": getattr(mod, "crear_backup_sistema", _default_crear_backup) if mod else _default_crear_backup,
        "app_root": getattr(mod, "application_root", application_root) if mod else application_root,
    }


def poblar_items_pendientes(interfaz: Any, items_pendientes: ft.ListView, pedidos_pendientes: list) -> None:
    """Rellena la lista visual de pedidos pendientes incluidos en el cierre."""
    if not pedidos_pendientes:
        items_pendientes.controls.append(
            ft.Container(
                bgcolor=ft.Colors.GREEN_900 if interfaz.modo_oscuro else ft.Colors.GREEN_50,
                border=ft.Border.all(1, ft.Colors.GREEN_700 if interfaz.modo_oscuro else ft.Colors.GREEN_300),
                border_radius=8,
                padding=12,
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_400),
                        ft.Text(
                            "No hay pedidos pendientes de cierre. Todos los pedidos armados ya fueron incluidos en cierres anteriores.",
                            size=12,
                            color=interfaz.texto,
                            expand=True,
                        ),
                    ],
                    spacing=10,
                ),
            )
        )
        return

    for p in pedidos_pendientes:
        if getattr(p, "numero_pedido", ""):
            num_ped_txt = f"Pedido #{p.numero_pedido} · Remito: {p.nota_pedido}"
        else:
            num_ped_txt = f"Remito / Factura: {p.nota_pedido}"
        items_pendientes.controls.append(
            ft.Container(
                bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.GREY_50,
                border=ft.Border.all(1, interfaz.borde),
                border_radius=6,
                padding=8,
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Row(
                                    [ft.Text(num_ped_txt, weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto), ft.Text(f"Cliente: {p.cliente}", size=11, color=interfaz.texto)],
                                    spacing=10,
                                ),
                                ft.Row(
                                    [
                                        ft.Text(f"Bultos: {p.bultos}", size=11, color=interfaz.secundario),
                                        ft.Text(f"Logística: {p.logistica}", size=11, color=interfaz.secundario),
                                        ft.Text(f"Descuento: {p.resumen_items}", size=11, color=ft.Colors.GREEN_400),
                                    ],
                                    spacing=10,
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.Text(p.created_at[11:16], size=11, color=interfaz.secundario),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            )
        )


def poblar_historial_cierres(interfaz: Any, lista_cierres: ft.ListView, cierres_anteriores: list) -> None:
    """Rellena la lista de cierres históricos con acciones de reimpresión, hoja de ruta y correo."""
    if not cierres_anteriores:
        lista_cierres.controls.append(ft.Text("Aún no se han ejecutado cierres de jornada.", size=12, color=interfaz.secundario))
        return

    for c in cierres_anteriores:
        pdf_ruta, xls_ruta, hoja_ruta = resolver_archivos_cierre(interfaz, c)

        boton_hoja_ruta_cierre = ft.IconButton(
            icon=ft.Icons.LOCAL_SHIPPING,
            tooltip="Ver / Imprimir Hoja de Ruta de Despacho",
            icon_color=ft.Colors.TEAL_400 if interfaz.modo_oscuro else ft.Colors.TEAL_700,
            on_click=lambda _e, cierre_obj=c, hr_path=hoja_ruta: gestionar_hoja_ruta_cierre(interfaz, cierre_obj, hr_path),
        )
        boton_imprimir_cierre = (
            ft.IconButton(
                icon=ft.Icons.PRINT,
                tooltip="Imprimir / Abrir PDF de este cierre",
                icon_color=ROJO,
                on_click=(lambda _e, r=pdf_ruta: interfaz.abrir_informe(ruta_especifica=r)) if (pdf_ruta and pdf_ruta.exists()) else None,
            )
            if (pdf_ruta and pdf_ruta.exists())
            else ft.Container()
        )
        boton_correo_cierre = (
            ft.IconButton(
                icon=ft.Icons.EMAIL_OUTLINED,
                tooltip="Enviar este cierre por correo",
                icon_color=ft.Colors.BLUE_400,
                on_click=(
                    lambda _e, cid=c.id, pdf=pdf_ruta, xls=xls_ruta, res=c.resumen_pedidos, usr=c.usuario, hr=hoja_ruta:
                    interfaz.mostrar_dialogo_compartir_cierre(cid, pdf, xls, res, usr, hr)
                ),
            )
            if ((pdf_ruta and pdf_ruta.exists()) or (xls_ruta and xls_ruta.exists()) or (hoja_ruta and hoja_ruta.exists()))
            else ft.Container()
        )
        lista_cierres.controls.append(
            ft.Container(
                bgcolor=interfaz.fondo_acento if interfaz.modo_oscuro else ft.Colors.GREY_50,
                border=ft.Border.all(1, interfaz.borde),
                border_radius=6,
                padding=8,
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(f"Cierre #{c.id}", weight=ft.FontWeight.BOLD, size=13, color=interfaz.texto),
                                        ft.Text(f"{c.cantidad_pedidos} pedidos ({c.articulos_totales} un.)", size=11, weight=ft.FontWeight.W_500, color=ROJO),
                                        ft.Text(f"Armador: {c.usuario}", size=11, color=interfaz.secundario),
                                    ],
                                    spacing=10,
                                ),
                                ft.Text(
                                    f"Fecha: {c.created_at[:16]} · Informe: {c.archivo_pdf or 'N/A'}"
                                    + (f" · Hoja de Ruta: {c.archivo_hoja_ruta}" if c.archivo_hoja_ruta else ""),
                                    size=10,
                                    color=interfaz.secundario,
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.Row([boton_correo_cierre, boton_hoja_ruta_cierre, boton_imprimir_cierre], spacing=2),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            )
        )


def ejecutar_tarea_cierre_operario(interfaz: Any, pedidos_pendientes: list) -> dict[str, Any]:
    """Ejecuta en segundo plano el cálculo consolidado, PDF, cierre DB, Hoja de Ruta, backup y alertas."""
    deps = _resolver_dependencias_cierre()
    items_pendientes_data = interfaz.order_store.obtener_items_pendientes_cierre()
    items_consolidados: dict[str, ItemConsolidado] = {}

    for cod, desc, cant, remitos in items_pendientes_data:
        cod_n = normalizar_codigo(cod)
        if cod_n not in items_consolidados:
            items_consolidados[cod_n] = ItemConsolidado(
                codigo=cod_n,
                descripcion=desc,
                cantidad_total=cant,
                remitos_origen=list(remitos),
            )
        else:
            items_consolidados[cod_n].cantidad_total += cant
            for rem in remitos:
                if rem not in items_consolidados[cod_n].remitos_origen:
                    items_consolidados[cod_n].remitos_origen.append(rem)

    if not items_consolidados:
        for ped in pedidos_pendientes:
            arch_path = deps["app_root"]() / "data" / "pedidos_archivos" / ped.nombre_archivo
            if arch_path.exists():
                res = deps["parsear_remito"](arch_path) if ped.tipo_archivo == "pdf" else deps["parsear_canje"](arch_path)
                for it in res.items:
                    cod_n = normalizar_codigo(it.codigo)
                    if cod_n not in items_consolidados:
                        items_consolidados[cod_n] = ItemConsolidado(
                            codigo=cod_n,
                            descripcion=it.descripcion,
                            cantidad_total=it.cantidad,
                            remitos_origen=[ped.nota_pedido],
                        )
                    else:
                        items_consolidados[cod_n].cantidad_total += it.cantidad
                        if ped.nota_pedido not in items_consolidados[cod_n].remitos_origen:
                            items_consolidados[cod_n].remitos_origen.append(ped.nota_pedido)

    stock_mgr = deps["get_sm_cls"]()(ruta_excel_base=interfaz.menu.ruta_excel_base)
    pedidos_doc = []
    for p in pedidos_pendientes:
        items_db = interfaz.order_store.obtener_items_pedido(p.id)
        items_p = [
            ItemRemito(codigo=normalizar_codigo(cod), descripcion=desc, cantidad=cant, origen_remito=p.nota_pedido)
            for cod, desc, cant in items_db
        ]
        sin_coincidencia_p: list[tuple[str, str]] = []
        if hasattr(interfaz.order_store, "obtener_items_sin_coincidencia"):
            try:
                sin_coincidencia_p = interfaz.order_store.obtener_items_sin_coincidencia(p.id)
            except Exception:
                sin_coincidencia_p = []

        arch_p = deps["app_root"]() / "data" / "pedidos_archivos" / p.nombre_archivo
        if not arch_p.exists():
            carp_desc = getattr(interfaz.menu, "carpeta_descontados", None)
            if carp_desc:
                carp_desc_path = Path(carp_desc)
                candidatos = [
                    carp_desc_path / "MercadoLibre" / p.nombre_archivo,
                    carp_desc_path / "Mayoristas" / p.nombre_archivo,
                    carp_desc_path / "Canjes" / p.nombre_archivo,
                    carp_desc_path / "Fabrica" / p.nombre_archivo,
                    carp_desc_path / p.nombre_archivo,
                ]
                for cand in candidatos:
                    if cand.exists():
                        arch_p = cand
                        break

        if arch_p.exists():
            try:
                sufijo = arch_p.suffix.lower()
                if sufijo == ".pdf" or p.tipo_archivo == "pdf":
                    res_doc = deps["parsear_remito"](arch_p)
                elif sufijo == ".docx" or p.tipo_archivo == "docx":
                    prods_cat = [(c, n) for _, c, n, _ in stock_mgr.productos_base]
                    res_doc = deps["parsear_ml"](arch_p, prods_cat)
                elif sufijo in (".xlsx", ".xls") or p.tipo_archivo == "excel":
                    res_doc = deps["parsear_canje"](arch_p)
                else:
                    res_doc = None
                if res_doc is not None:
                    if not sin_coincidencia_p:
                        sin_coincidencia_p = list(res_doc.descripciones_sin_coincidencia)
                    if not items_p:
                        items_p = res_doc.items
            except Exception as e:
                print(f"[AVISO] Error al re-parsear {arch_p.name} para cierre: {e}")

        if sin_coincidencia_p and hasattr(interfaz.order_store, "guardar_items_sin_coincidencia"):
            try:
                interfaz.order_store.guardar_items_sin_coincidencia(p.id, sin_coincidencia_p)
            except Exception:
                pass

        pedidos_doc.append(
            ResultadoRemito(
                archivo=p.nombre_archivo,
                numero_remito=p.nota_pedido,
                fecha=p.created_at[:10],
                cliente=p.cliente,
                articulos_declarados=p.articulos_descontados,
                articulos_extraidos=p.articulos_descontados,
                items=items_p,
                descripciones_sin_coincidencia=sin_coincidencia_p,
                verificacion_ok=True,
            )
        )

    rep = stock_mgr.aplicar_descuentos(
        items_consolidados=items_consolidados,
        carpeta_destino=interfaz.menu.carpeta_descuentos,
        pedidos_procesados=pedidos_doc,
        guardar_archivo=False,
        prefijo_archivo="Cierre_Descuento",
        descuento_ya_aplicado=True,
    )

    usr_cierre = interfaz.usuario_actual.username if interfaz.usuario_actual else "Operario"
    if hasattr(interfaz.order_store, "obtener_ventana_ultimo_cierre"):
        fecha_desde, fecha_hasta, cierre_ant_id = interfaz.order_store.obtener_ventana_ultimo_cierre()
    else:
        from datetime import datetime
        hoy_str = datetime.now().strftime("%Y-%m-%d")
        fecha_desde, fecha_hasta, cierre_ant_id = f"{hoy_str}T00:00:00", f"{hoy_str}T23:59:59", None

    archivos_rep = generar_reportes_cierre_jornada(
        interfaz=interfaz,
        stock_mgr=stock_mgr,
        pedidos_pendientes=pedidos_pendientes,
        pedidos_doc=pedidos_doc,
        items_consolidados=items_consolidados,
        reporte_simulado=rep,
        usr_cierre=usr_cierre,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        cierre_anterior_id=cierre_ant_id,
    )
    pdf_path = archivos_rep.get("pdf_path")
    xls_path = archivos_rep.get("xls_path")
    admin_pdf_path = archivos_rep.get("admin_pdf_path")
    total_arts = sum(it.cantidad_total for it in items_consolidados.values())
    resumen_p = f"{len(pedidos_pendientes)} pedidos ({total_arts} un.)"

    cierre_id = interfaz.order_store.registrar_cierre(
        usuario=usr_cierre,
        pedidos_ids=[p.id for p in pedidos_pendientes],
        articulos_totales=total_arts,
        resumen_pedidos=resumen_p,
        archivo_pdf=pdf_path.name if pdf_path else "",
        archivo_excel=xls_path.name if xls_path else "",
    )

    total_bultos = sum(p.bultos for p in pedidos_pendientes)
    try:
        from ....integrations.telegram_notifier import notificar_cierre_jornada_telegram
        notificar_cierre_jornada_telegram(
            responsable=usr_cierre,
            pedidos=len(pedidos_pendientes),
            bultos=total_bultos,
            articulos=total_arts,
        )
    except Exception:
        pass

    try:
        ruta_xl = getattr(interfaz.menu, "ruta_excel_base", None)
        if ruta_xl and Path(ruta_xl).exists():
            sm_cierre = deps["get_sm_cls"]()(ruta_excel_base=ruta_xl)
            if hasattr(sm_cierre, "sincronizar_catalogo_completo_excel"):
                sm_cierre.sincronizar_catalogo_completo_excel()
    except Exception:
        pass

    art_quiebre = rep.articulos_quiebre
    art_criticos = rep.articulos_criticos
    alerta_texto_correo = ""
    alerta_resumen_notif = ""
    if art_quiebre or art_criticos:
        lineas_alerta = []
        if art_quiebre:
            lineas_alerta.append(f"🔴 {len(art_quiebre)} producto(s) en QUIEBRE (stock <= 0)")
        if art_criticos:
            lineas_alerta.append(f"🟠 {len(art_criticos)} producto(s) en STOCK CRÍTICO (1 a 5 un.)")
        alerta_resumen_notif = " · ".join(lineas_alerta)
        alerta_texto_correo = alerta_resumen_notif
        for r in art_quiebre:
            alerta_texto_correo += f"\n  - [QUIEBRE] {r.codigo}: {r.nombre_producto} (Stock: {r.stock_nuevo})"
        for r in art_criticos:
            alerta_texto_correo += f"\n  - [CRÍTICO] {r.codigo}: {r.nombre_producto} (Stock: {r.stock_nuevo})"

        interfaz.order_store.registrar_auditoria(
            usuario=usr_cierre,
            accion="ALERTA_STOCK",
            detalle=f"Cierre #{cierre_id}: {len(art_quiebre)} quiebres, {len(art_criticos)} críticos",
        )

    hoja_ruta_pdf: Path | None = None
    try:
        hoja_ruta_pdf = deps["generar_hr"](
            cierre_id=cierre_id,
            pedidos=pedidos_pendientes,
            usuario=usr_cierre,
            carpeta_destino=interfaz.menu.carpeta_descuentos,
        )
        if hoja_ruta_pdf:
            interfaz.order_store.actualizar_hoja_ruta_cierre(cierre_id, hoja_ruta_pdf.name)
    except Exception as ex_hr:
        print(f"Error generando hoja de ruta de despacho: {ex_hr}")

    try:
        bk_zip = deps["crear_backup"](ruta_excel_base=interfaz.menu.ruta_excel_base, usuario=usr_cierre)
        interfaz.order_store.registrar_auditoria(
            usuario=usr_cierre,
            accion="BACKUP_AUTOMATICO",
            detalle=f"Respaldo automático en cierre #{cierre_id}: {bk_zip.name}",
        )
    except Exception as ex_bk:
        print(f"Error en backup automático: {ex_bk}")

    try:
        from ....webhook_manager import despachar_evento_webhook
        despachar_evento_webhook(
            "CIERRE_JORNADA",
            {
                "cierre_id": cierre_id,
                "usuario": usr_cierre,
                "resumen_pedidos": resumen_p,
                "total_quiebres": len(art_quiebre),
                "total_criticos": len(art_criticos),
                "hoja_ruta": hoja_ruta_pdf.name if hoja_ruta_pdf else None,
                "archivo_pdf": pdf_path.name if pdf_path else None,
                "archivo_excel": xls_path.name if xls_path else None,
            },
        )
        for r_q in art_quiebre:
            despachar_evento_webhook(
                "QUIEBRE_STOCK",
                {
                    "codigo": r_q.codigo,
                    "nombre": r_q.nombre_producto,
                    "stock_actual": r_q.stock_nuevo,
                    "origen": f"Cierre #{cierre_id}",
                    "estado": "AGOTADO" if r_q.stock_nuevo <= 0 else "CRITICO",
                },
            )
    except Exception as ex_wh:
        print(f"Error despachando webhook de cierre: {ex_wh}")

    return {
        "cierre_id": cierre_id,
        "pdf_path": pdf_path,
        "xls_path": xls_path,
        "admin_pdf_path": admin_pdf_path,
        "hoja_ruta_pdf": hoja_ruta_pdf,
        "resumen_p": resumen_p,
        "alerta_resumen_notif": alerta_resumen_notif,
        "alerta_texto_correo": alerta_texto_correo,
    }
