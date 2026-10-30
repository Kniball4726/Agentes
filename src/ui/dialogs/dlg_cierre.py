"""Diálogo modal para el Cierre de Jornada de Pedidos y generación de hojas de ruta."""
from pathlib import Path
import sys
from typing import Any
import flet as ft

from ...backup_manager import crear_backup_sistema
from ...canjes_parser import parsear_canje_excel
from ...consolidator import ItemConsolidado
from ...dispatch_manifest import generar_hoja_ruta_pdf
from ...paths import application_root
from ...remito_parser import ItemRemito, ResultadoRemito, normalizar_codigo, parsear_remito
from ...stock_manager import StockManager as _DefaultStockManager
from ..theme import ROJO


def _get_stock_manager_cls():
    mod = sys.modules.get("src.flet_gui")
    if mod and hasattr(mod, "StockManager"):
        return getattr(mod, "StockManager")
    return _DefaultStockManager


def mostrar_dialogo_cierre_jornada(interfaz: Any) -> None:
    """Abre el panel para cerrar la jornada operativa, descontar stock en bloque y generar la Hoja de Ruta."""
    if interfaz.usuario_actual is None or interfaz.usuario_actual.role != "operador":
        interfaz.notificar("El cierre de jornada es una función exclusiva del rol operador.")
        return

    # Usar las funciones auxiliares de flet_gui
    mod_gui = sys.modules.get("src.flet_gui")
    obtener_correo_fn = getattr(mod_gui, "obtener_correo_cierre_guardado", lambda: "")
    guardar_correo_fn = getattr(mod_gui, "guardar_correo_cierre", lambda _c: None)

    pedidos_pendientes = interfaz.order_store.listar_pedidos_pendientes_cierre()
    cierres_anteriores = interfaz.order_store.listar_cierres(limit=25)

    items_pendientes = ft.ListView(expand=True, spacing=6)
    total_articulos_pendientes = sum(p.articulos_descontados for p in pedidos_pendientes)

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
    else:
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
                                        [
                                            ft.Text(num_ped_txt, weight=ft.FontWeight.BOLD, size=12, color=interfaz.texto),
                                            ft.Text(f"Cliente: {p.cliente}", size=11, color=interfaz.texto),
                                        ],
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

    lista_cierres = ft.ListView(expand=True, spacing=6)
    if not cierres_anteriores:
        lista_cierres.controls.append(
            ft.Text("Aún no se han ejecutado cierres de jornada.", size=12, color=interfaz.secundario)
        )
    else:
        for c in cierres_anteriores:
            pdf_ruta = interfaz.menu.carpeta_descuentos / c.archivo_pdf if c.archivo_pdf else None
            xls_ruta = interfaz.menu.carpeta_descuentos / c.archivo_excel if c.archivo_excel else None
            hoja_ruta = interfaz.menu.carpeta_descuentos / c.archivo_hoja_ruta if c.archivo_hoja_ruta else None

            def abrir_o_generar_hoja_ruta(cierre_obj=c, hr_path=hoja_ruta) -> None:
                if hr_path and hr_path.exists():
                    interfaz.abrir_informe(ruta_especifica=hr_path)
                else:
                    peds = interfaz.order_store.obtener_pedidos_por_cierre(cierre_obj.id)
                    if not peds:
                        interfaz.notificar("No se encontraron registros de pedidos para generar la hoja de ruta de este cierre.")
                        return
                    nueva_hr = generar_hoja_ruta_pdf(
                        cierre_id=cierre_obj.id,
                        pedidos=peds,
                        usuario=cierre_obj.usuario,
                        carpeta_destino=interfaz.menu.carpeta_descuentos,
                    )
                    interfaz.order_store.actualizar_hoja_ruta_cierre(cierre_obj.id, nueva_hr.name)
                    interfaz.abrir_informe(ruta_especifica=nueva_hr)

            boton_hoja_ruta_cierre = ft.IconButton(
                icon=ft.Icons.LOCAL_SHIPPING,
                tooltip="Ver / Imprimir Hoja de Ruta de Despacho",
                icon_color=ft.Colors.TEAL_400 if interfaz.modo_oscuro else ft.Colors.TEAL_700,
                on_click=lambda _e, cierre_obj=c, hr_path=hoja_ruta: abrir_o_generar_hoja_ruta(cierre_obj, hr_path),
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

    correo_cierre_input = ft.TextField(
        label="Enviar copia de cierre por correo a (opcional)",
        value=obtener_correo_fn(),
        hint_text="ej: gerencia@empresa.com, administracion@empresa.com",
        prefix_icon=ft.Icons.EMAIL,
        dense=True,
        content_padding=ft.Padding.symmetric(horizontal=10, vertical=8),
    )

    async def ejecutar_cierre(_e: ft.Event) -> None:
        if not pedidos_pendientes:
            interfaz.notificar("No hay pedidos pendientes para cerrar.")
            return

        correo_destino = (correo_cierre_input.value or "").strip()
        if correo_destino:
            guardar_correo_fn(correo_destino)

        interfaz.page.pop_dialog()

        resultado_cierre: dict[str, Any] = {}

        def tarea_cierre() -> None:
            items_pendientes_data = interfaz.order_store.obtener_items_pendientes_cierre()
            items_consolidados: dict[str, ItemConsolidado] = {}

            for cod, desc, cant, remitos in items_pendientes_data:
                items_consolidados[cod] = ItemConsolidado(
                    codigo=cod,
                    descripcion=desc,
                    cantidad_total=cant,
                    remitos_origen=remitos,
                )

            if not items_consolidados:
                for ped in pedidos_pendientes:
                    arch_path = application_root() / "data" / "pedidos_archivos" / ped.nombre_archivo
                    if arch_path.exists():
                        if ped.tipo_archivo == "pdf":
                            res = parsear_remito(arch_path)
                        else:
                            res = parsear_canje_excel(arch_path)
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

            pedidos_doc = []
            for p in pedidos_pendientes:
                items_p = [
                    ItemRemito(
                        codigo=cod,
                        descripcion=desc,
                        cantidad=cant,
                        origen_remito=p.nota_pedido,
                    )
                    for cod, desc, cant in interfaz.order_store.obtener_items_pedido(p.id)
                ]
                pedidos_doc.append(
                    ResultadoRemito(
                        archivo=p.nombre_archivo,
                        numero_remito=p.nota_pedido,
                        fecha=p.created_at[:10],
                        cliente=p.cliente,
                        articulos_declarados=p.articulos_descontados,
                        articulos_extraidos=p.articulos_descontados,
                        items=items_p,
                        verificacion_ok=True,
                    )
                )

            sm_cls = _get_stock_manager_cls()
            stock_mgr = sm_cls(ruta_excel_base=interfaz.menu.ruta_excel_base)
            rep = stock_mgr.aplicar_descuentos(
                items_consolidados=items_consolidados,
                carpeta_destino=interfaz.menu.carpeta_descuentos,
                pedidos_procesados=pedidos_doc,
                guardar_archivo=True,
                prefijo_archivo="Cierre_Descuento",
            )

            pdf_path = Path(rep.archivo_pdf) if rep.archivo_pdf else None
            xls_path = Path(rep.archivo_guardado) if rep.archivo_guardado else None

            total_arts = sum(it.cantidad_total for it in items_consolidados.values())
            resumen_p = f"{len(pedidos_pendientes)} pedidos ({total_arts} un.)"

            cierre_id = interfaz.order_store.registrar_cierre(
                usuario=interfaz.usuario_actual.username if interfaz.usuario_actual else "Operario",
                pedidos_ids=[p.id for p in pedidos_pendientes],
                articulos_totales=total_arts,
                resumen_pedidos=resumen_p,
                archivo_pdf=pdf_path.name if pdf_path else "",
                archivo_excel=xls_path.name if xls_path else "",
            )

            try:
                from ...telegram_notifier import notificar_cierre_jornada_telegram
                notificar_cierre_jornada_telegram(
                    responsable=interfaz.usuario_actual.username if interfaz.usuario_actual else "Operario",
                    pedidos=len(pedidos_pendientes),
                    bultos=total_bultos,
                    articulos=total_arts,
                )
            except Exception:
                pass

            try:
                sm_cierre = _get_stock_manager()(interfaz.menu.ruta_excel_base)
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
                    usuario=interfaz.usuario_actual.username if interfaz.usuario_actual else "Operario",
                    accion="ALERTA_STOCK",
                    detalle=f"Cierre #{cierre_id}: {len(art_quiebre)} quiebres, {len(art_criticos)} críticos",
                )

            hoja_ruta_pdf: Path | None = None
            try:
                hoja_ruta_pdf = generar_hoja_ruta_pdf(
                    cierre_id=cierre_id,
                    pedidos=pedidos_pendientes,
                    usuario=interfaz.usuario_actual.username if interfaz.usuario_actual else "Operario",
                    carpeta_destino=interfaz.menu.carpeta_descuentos,
                )
                if hoja_ruta_pdf:
                    interfaz.order_store.actualizar_hoja_ruta_cierre(cierre_id, hoja_ruta_pdf.name)
            except Exception as ex_hr:
                print(f"Error generando hoja de ruta de despacho: {ex_hr}")

            try:
                bk_zip = crear_backup_sistema(
                    ruta_excel_base=interfaz.menu.ruta_excel_base,
                    usuario=interfaz.usuario_actual.username if interfaz.usuario_actual else "Operario",
                )
                interfaz.order_store.registrar_auditoria(
                    usuario=interfaz.usuario_actual.username if interfaz.usuario_actual else "Operario",
                    accion="BACKUP_AUTOMATICO",
                    detalle=f"Respaldo automático en cierre #{cierre_id}: {bk_zip.name}",
                )
            except Exception as ex_bk:
                print(f"Error en backup automático: {ex_bk}")

            resultado_cierre["cierre_id"] = cierre_id
            resultado_cierre["pdf_path"] = pdf_path
            resultado_cierre["xls_path"] = xls_path
            resultado_cierre["hoja_ruta_pdf"] = hoja_ruta_pdf
            resultado_cierre["resumen_p"] = resumen_p
            resultado_cierre["alerta_resumen_notif"] = alerta_resumen_notif
            resultado_cierre["alerta_texto_correo"] = alerta_texto_correo

        exito = await interfaz.ejecutar_tarea("Cierre de Jornada", tarea_cierre)
        if not exito:
            return

        interfaz.actualizar_listas()

        pdf_path = resultado_cierre.get("pdf_path")
        hoja_ruta_pdf = resultado_cierre.get("hoja_ruta_pdf")
        cierre_id = resultado_cierre.get("cierre_id", 0)
        resumen_p = resultado_cierre.get("resumen_p", "")
        alerta_resumen_notif = resultado_cierre.get("alerta_resumen_notif", "")
        alerta_texto_correo = resultado_cierre.get("alerta_texto_correo", "")

        if pdf_path and pdf_path.exists():
            interfaz.abrir_informe(ruta_especifica=pdf_path)
        if hoja_ruta_pdf and hoja_ruta_pdf.exists():
            interfaz.abrir_informe(ruta_especifica=hoja_ruta_pdf)

        if correo_destino:
            interfaz.enviar_correo_cierre(
                destinatarios=correo_destino,
                cierre_id=cierre_id,
                archivo_pdf=pdf_path,
                archivo_excel=resultado_cierre.get("xls_path"),
                resumen_pedidos=resumen_p,
                usuario=interfaz.usuario_actual.username if interfaz.usuario_actual else "Operario",
                archivo_hoja_ruta=hoja_ruta_pdf,
                alerta_stock=alerta_texto_correo,
            )

        mensaje_exito = (
            f"Cierre de jornada #{cierre_id} realizado con éxito ({resumen_p}). "
            "Se generó el informe, la Hoja de Ruta y el Respaldo de seguridad."
        )
        if alerta_resumen_notif:
            mensaje_exito += f"\n⚠️ {alerta_resumen_notif}"
        interfaz.notificar(mensaje_exito)

    vista_pendientes = ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    bgcolor=ROJO if pedidos_pendientes else (ft.Colors.BLUE_GREY_900 if interfaz.modo_oscuro else ft.Colors.BLUE_GREY_100),
                    border_radius=8,
                    padding=10,
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(
                                        f"{len(pedidos_pendientes)} Pedidos Acumulados" if pedidos_pendientes else "Sin pedidos acumulados",
                                        weight=ft.FontWeight.BOLD,
                                        size=13,
                                        color=ft.Colors.WHITE,
                                    ),
                                    ft.Text(
                                        f"Total de {total_articulos_pendientes} unidades descontadas listas para cerrar jornada."
                                        if pedidos_pendientes
                                        else "Todos los pedidos anteriores están cerrados.",
                                        size=11,
                                        color=ft.Colors.WHITE_70,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Button(
                                "Cerrar Jornada e Imprimir",
                                icon=ft.Icons.LOCK,
                                bgcolor=ft.Colors.WHITE,
                                color=ROJO,
                                disabled=not bool(pedidos_pendientes),
                                on_click=ejecutar_cierre,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ),
                correo_cierre_input,
                ft.Text("Pedidos incluidos en este cierre:", size=12, weight=ft.FontWeight.BOLD, color=interfaz.texto),
                ft.Container(content=items_pendientes, expand=True),
            ],
            spacing=10,
            expand=True,
        ),
        expand=True,
        visible=True,
    )

    vista_historial = ft.Container(
        content=ft.Column(
            [
                ft.Text("Cierres de jornada anteriores (puedes reimprimir cualquier cierre):", size=12, color=interfaz.secundario),
                ft.Container(content=lista_cierres, expand=True),
            ],
            spacing=8,
            expand=True,
        ),
        expand=True,
        visible=False,
    )

    boton_tab_pendientes = ft.Button(
        f"Pendientes ({len(pedidos_pendientes)})",
        icon=ft.Icons.PENDING_ACTIONS,
        bgcolor=ROJO,
        color=ft.Colors.WHITE,
    )
    boton_tab_historial = ft.Button(
        f"Historial de Cierres ({len(cierres_anteriores)})",
        icon=ft.Icons.HISTORY,
        bgcolor=ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.BLUE_GREY_100,
        color=interfaz.texto,
    )

    def switch_tab(tab_idx: int) -> None:
        if tab_idx == 0:
            vista_pendientes.visible = True
            vista_historial.visible = False
            boton_tab_pendientes.bgcolor = ROJO
            boton_tab_pendientes.color = ft.Colors.WHITE
            boton_tab_historial.bgcolor = ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.BLUE_GREY_100
            boton_tab_historial.color = interfaz.texto
        else:
            vista_pendientes.visible = False
            vista_historial.visible = True
            boton_tab_pendientes.bgcolor = ft.Colors.BLUE_GREY_800 if interfaz.modo_oscuro else ft.Colors.BLUE_GREY_100
            boton_tab_pendientes.color = interfaz.texto
            boton_tab_historial.bgcolor = ROJO
            boton_tab_historial.color = ft.Colors.WHITE
        interfaz.page.update()

    boton_tab_pendientes.on_click = lambda _e: switch_tab(0)
    boton_tab_historial.on_click = lambda _e: switch_tab(1)

    cuerpo_cierre = ft.Column(
        [
            ft.Row([boton_tab_pendientes, boton_tab_historial], spacing=10),
            vista_pendientes,
            vista_historial,
        ],
        spacing=12,
        expand=True,
    )

    dialogo = ft.AlertDialog(
        title=ft.Row(
            [
                ft.Icon(ft.Icons.TASK_ALT, color=ROJO),
                ft.Text("Cierre de Jornada de Pedidos", weight=ft.FontWeight.BOLD),
            ],
            spacing=8,
        ),
        content=ft.Container(
            width=720,
            height=520,
            content=cuerpo_cierre,
        ),
        actions=[
            interfaz.boton_dialogo("Cerrar", lambda _e: interfaz.page.pop_dialog())
        ],
    )
    interfaz.page.show_dialog(dialogo)
