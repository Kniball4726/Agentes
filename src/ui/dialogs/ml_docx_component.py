"""Componente de carga y previsualización de archivos .docx/.pdf de Mercado Libre."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
import sys
from typing import Any, Callable

import flet as ft

from ...agent import AgenteRemitosStock
from ...inventory import StockManager as _DefaultStockManager
from ...orders import calcular_hash_archivo
from ...parsers.mercado_libre_parser import parsear_pedido_mercado_libre
from ...parsers.remito_parser import ResultadoRemito, normalizar_codigo
from ...paths import application_root


def _resolver_sm():
    mod_ml = sys.modules.get("src.ui.dialogs.dlg_mercadolibre_descuento")
    if mod_ml is not None and hasattr(mod_ml, "_get_stock_manager"):
        return mod_ml._get_stock_manager()
    return _DefaultStockManager


class MercadoLibreDocxComponent:
    """Gestiona la carga, previsualización y procesamiento tradicional de archivos .docx de Mercado Libre."""

    def __init__(
        self,
        interfaz: Any,
        carpeta_ml: Path,
        dest_archivado: Path,
        al_cambiar_estado: Callable | None = None,
    ) -> None:
        self.interfaz = interfaz
        self.carpeta_ml = carpeta_ml
        self.dest_archivado = dest_archivado
        self.al_cambiar_estado = al_cambiar_estado

        self.archivo_seleccionado: list[Path | None] = [None]
        self.resultado_parseo: list[ResultadoRemito | None] = [None]
        self.items_a_descontar: dict[str, int] = {}
        self.archivos_pendientes: list[Path] = []

        self.lista_previsualizacion = ft.ListView(expand=True, spacing=4, height=260)
        self.resumen_texto = ft.Text(
            "Selecciona o sube un archivo .docx de Mercado Libre para previsualizar los productos a descontar.",
            size=12,
            color=interfaz.secundario,
        )
        self.banner_no_encontrados = ft.Container(visible=False)

        self._limpiar_archivos_duplicados_disco()

        self.selector_archivo = ft.Dropdown(
            label="Seleccionar pedido de Mercado Libre (.docx)",
            options=[ft.dropdown.Option(arch.name) for arch in self.archivos_pendientes],
            value=self.archivos_pendientes[0].name if self.archivos_pendientes else None,
            expand=True,
            dense=True,
        )
        self.selector_archivo.on_change = self._cambiar_archivo_dropdown
        self.selector_archivo.on_select = self._cambiar_archivo_dropdown
        if self.archivos_pendientes:
            self.archivo_seleccionado[0] = self.archivos_pendientes[0]
            self.cargar_previsualizacion(self.archivos_pendientes[0])

    def _limpiar_archivos_duplicados_disco(self) -> None:
        self.archivos_pendientes.clear()
        for arch_cand in sorted(list(self.carpeta_ml.glob("*.docx"))):
            h = calcular_hash_archivo(arch_cand)
            if h and self.interfaz.order_store.buscar_pedido_por_hash(h):
                try:
                    dest_file = self.dest_archivado / arch_cand.name
                    if not dest_file.exists() or arch_cand.resolve() != dest_file.resolve():
                        shutil.move(str(arch_cand), str(dest_file))
                    else:
                        arch_cand.unlink(missing_ok=True)
                except Exception:
                    pass
            else:
                self.archivos_pendientes.append(arch_cand)

    def _cambiar_archivo_dropdown(self, _e: ft.Event) -> None:
        nombre = self.selector_archivo.value
        if not nombre:
            self.limpiar()
            return
        for arch in self.archivos_pendientes:
            if arch.name == nombre:
                self.archivo_seleccionado[0] = arch
                self.cargar_previsualizacion(arch)
                break

    def limpiar(self, _e: ft.Event | None = None) -> None:
        self.archivo_seleccionado[0] = None
        self.resultado_parseo[0] = None
        self.items_a_descontar.clear()
        self.lista_previsualizacion.controls.clear()
        self.banner_no_encontrados.visible = False
        self.selector_archivo.value = None
        self.resumen_texto.value = (
            "Selecciona o sube un archivo .docx de Mercado Libre para previsualizar los productos a descontar."
        )
        self.resumen_texto.color = self.interfaz.secundario
        if self.al_cambiar_estado:
            self.al_cambiar_estado(habilitado=False)
        self.interfaz.page.update()

    def cargar_previsualizacion(self, arch: Path) -> None:
        self.lista_previsualizacion.controls.clear()
        self.items_a_descontar.clear()
        self.banner_no_encontrados.visible = False
        if self.al_cambiar_estado:
            self.al_cambiar_estado(habilitado=False)

        if not arch or not arch.exists():
            self.resumen_texto.value = "El archivo seleccionado no se encuentra en el disco."
            self.resumen_texto.color = ft.Colors.RED_400
            self.interfaz.page.update()
            return

        sm = _resolver_sm()(self.interfaz.menu.ruta_excel_base)
        productos_catalogo = [(codigo, nombre) for _, codigo, nombre, _ in sm.productos_base]

        try:
            if arch.suffix.lower() == ".pdf":
                from ...parsers.remito_parser import parsear_remito
                res = parsear_remito(arch)
            else:
                res = parsear_pedido_mercado_libre(arch, productos_catalogo)
            self.resultado_parseo[0] = res
        except Exception as e:
            self.resumen_texto.value = f"Error al leer el archivo {arch.name}: {e}"
            self.resumen_texto.color = ft.Colors.RED_400
            self.interfaz.page.update()
            return

        if not res.items:
            self.resumen_texto.value = f"El archivo {arch.name} no contiene líneas de productos reconocidas."
            self.resumen_texto.color = ft.Colors.AMBER_400
            self.interfaz.page.update()
            return

        total_unidades = sum(it.cantidad for it in res.items)
        for it in res.items:
            cod = normalizar_codigo(it.codigo)
            self.items_a_descontar[cod] = self.items_a_descontar.get(cod, 0) + it.cantidad

        self.resumen_texto.value = (
            f"Comprador: {res.cliente or 'No especificado'} | Paquete/Remito: {res.numero_remito or 'Sin número'} | "
            f"{len(self.items_a_descontar)} productos ({total_unidades} unidades a descontar)"
        )
        self.resumen_texto.color = self.interfaz.texto

        if res.descripciones_sin_coincidencia:
            lineas_aviso = [
                ft.Text(
                    f"• {desc} ({motivo})",
                    size=11,
                    color=ft.Colors.AMBER_200 if self.interfaz.modo_oscuro else ft.Colors.AMBER_900,
                )
                for desc, motivo in res.descripciones_sin_coincidencia
            ]
            self.banner_no_encontrados.visible = True
            self.banner_no_encontrados.content = ft.Container(
                bgcolor=ft.Colors.AMBER_900 if self.interfaz.modo_oscuro else ft.Colors.AMBER_100,
                border=ft.Border.all(1, ft.Colors.AMBER_600),
                border_radius=6,
                padding=8,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.WARNING_AMBER, color=ft.Colors.AMBER_400, size=16),
                                ft.Text(
                                    "Líneas que no coincidieron con el catálogo (no se descontarán):",
                                    weight=ft.FontWeight.BOLD,
                                    size=11,
                                    color=ft.Colors.AMBER_200 if self.interfaz.modo_oscuro else ft.Colors.AMBER_900,
                                ),
                            ],
                            spacing=6,
                        ),
                        *lineas_aviso,
                    ],
                    spacing=4,
                ),
            )

        hash_candidato = calcular_hash_archivo(arch)
        duplicado = self.interfaz.order_store.buscar_pedido_por_hash(hash_candidato) if hash_candidato else None
        if duplicado:
            self.banner_no_encontrados.visible = True
            self.banner_no_encontrados.content = ft.Container(
                bgcolor=ft.Colors.RED_900 if self.interfaz.modo_oscuro else ft.Colors.RED_100,
                border=ft.Border.all(1, ft.Colors.RED_400),
                border_radius=6,
                padding=8,
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.BLOCK, color=ft.Colors.RED_400, size=18),
                        ft.Text(
                            f"⛔ ATENCIÓN: Este archivo ya fue descontado el {duplicado.created_at[:16]} "
                            f"(Comprobante: {duplicado.nota_pedido}).",
                            weight=ft.FontWeight.BOLD,
                            size=11,
                            color=ft.Colors.RED_200 if self.interfaz.modo_oscuro else ft.Colors.RED_900,
                            expand=True,
                        ),
                    ],
                    spacing=8,
                ),
            )
            if self.al_cambiar_estado:
                self.al_cambiar_estado(habilitado=False)
        else:
            if self.al_cambiar_estado:
                self.al_cambiar_estado(habilitado=True)

        for cod, cant in self.items_a_descontar.items():
            nom = sm.catalogo.get(cod, ("", "Producto no encontrado", 0))[1]
            stk_actual = sm.catalogo.get(cod, ("", "", 0))[2]
            stk_nuevo = stk_actual - cant
            color_alerta = ft.Colors.RED_400 if stk_nuevo <= 0 else None
            alerta_txt = " (¡AGOTADO!)" if stk_nuevo <= 0 else ""

            self.lista_previsualizacion.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=6,
                    bgcolor=ft.Colors.WHITE_10 if self.interfaz.modo_oscuro else ft.Colors.GREY_100,
                    content=ft.Row(
                        [
                            ft.Text(f"[{cod}]", weight=ft.FontWeight.BOLD, size=11, width=80),
                            ft.Text(nom, size=11, expand=True, no_wrap=True),
                            ft.Text(f"-{cant} un.", weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400, size=11, width=65),
                            ft.Text(f"Stock: {stk_actual} -> {stk_nuevo}{alerta_txt}", size=11, color=color_alerta or self.interfaz.secundario, width=150),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                )
            )
        self.interfaz.page.update()

    def al_subir_docx(self, guardados: list[Path]) -> None:
        if not guardados:
            return
        archivos_disco = sorted(list(self.carpeta_ml.glob("*.docx")) + list(self.carpeta_ml.glob("*.pdf")))
        self.archivos_pendientes.clear()
        self.archivos_pendientes.extend(archivos_disco)
        self.selector_archivo.options = [ft.dropdown.Option(a.name) for a in self.archivos_pendientes]
        arch = guardados[0]
        self.archivo_seleccionado[0] = arch
        self.selector_archivo.value = arch.name
        self.cargar_previsualizacion(arch)
        self.interfaz.page.update()

    async def subir_desde_pc(self, _e: ft.Event) -> None:
        try:
            guardados = await self.interfaz.subir_archivos_desde_pc(
                carpeta_destino=self.carpeta_ml,
                extensiones=["docx", "pdf"],
                titulo="Seleccionar comprobante de Mercado Libre (.docx, .pdf)",
            )
            if guardados:
                self.al_subir_docx(guardados)
        except Exception as err:
            self.interfaz.notificar(f"Error al subir archivo de Mercado Libre: {err}")

    def descartar_archivo_seleccionado(self, _e: ft.Event) -> None:
        arch = self.archivo_seleccionado[0]
        if not arch:
            self.interfaz.notificar("No hay ningún archivo seleccionado para descartar.")
            return
        try:
            carpeta_descartados = self.carpeta_ml / "descartados"
            carpeta_descartados.mkdir(parents=True, exist_ok=True)
            dest = carpeta_descartados / arch.name
            if arch.exists():
                if dest.exists() and arch.resolve() != dest.resolve():
                    dest.unlink()
                if arch.resolve() != dest.resolve():
                    shutil.move(str(arch), str(dest))
        except Exception as err:
            self.interfaz.notificar(f"No se pudo descartar el archivo: {err}")
            return

        if arch in self.archivos_pendientes:
            self.archivos_pendientes.remove(arch)
        self.selector_archivo.options = [ft.dropdown.Option(a.name) for a in self.archivos_pendientes]
        if self.archivos_pendientes:
            siguiente = self.archivos_pendientes[0]
            self.archivo_seleccionado[0] = siguiente
            self.selector_archivo.value = siguiente.name
            self.cargar_previsualizacion(siguiente)
        else:
            self.limpiar()
        self.interfaz.actualizar_estado()
        self.interfaz.page.update()
        self.interfaz.notificar(f"Archivo {arch.name} descartado de pendientes.")

    async def confirmar_descuento_docx(self, _e: ft.Event) -> None:
        if getattr(self, "_en_proceso_docx", False):
            return
        if not self.archivo_seleccionado[0] or not self.items_a_descontar:
            self.interfaz.notificar("Debes seleccionar un archivo .docx válido con productos para descontar.")
            return

        arch = self.archivo_seleccionado[0]
        if not arch.exists():
            self.interfaz.notificar(f"El archivo {arch.name} ya no existe en la carpeta de pendientes.")
            return

        hash_doc = calcular_hash_archivo(arch)
        if hash_doc:
            dup = self.interfaz.order_store.buscar_pedido_por_hash(hash_doc)
            if dup:
                self.interfaz.notificar(
                    f"⛔ Este archivo ya fue procesado el {dup.created_at[:16]} ({dup.nota_pedido}) y no puede volver a descontarse."
                )
                return

        self._en_proceso_docx = True
        res = self.resultado_parseo[0]
        armador_nom = self.interfaz.usuario_actual.nombre_identificador if self.interfaz.usuario_actual else "Operario"
        self.interfaz.page.pop_dialog()

        def ejecutar_descuento_ml() -> None:
            sm = _resolver_sm()(self.interfaz.menu.ruta_excel_base)
            agente = AgenteRemitosStock(stock_manager=sm)
            reporte = agente.ejecutar(
                rutas_mercado_libre=[arch],
                carpeta_descuentos=self.interfaz.menu.carpeta_descuentos,
                simulacion=False,
            )

            nombre_inf = (
                Path(reporte.reporte_stock.archivo_guardado).name
                if reporte.reporte_stock.archivo_guardado
                else f"ML_{arch.stem}"
            )
            sm.actualizar_stock_base(
                descuentos=reporte.reporte_stock.descuentos_aplicados,
                sincronizar_excel=True,
                nombre_archivo=nombre_inf,
                usuario=armador_nom,
            )

            pdf_nom = Path(reporte.reporte_stock.archivo_pdf).name if reporte.reporte_stock.archivo_pdf else ""
            total_desc = sum(d.cantidad_descontada for d in reporte.reporte_stock.descuentos_aplicados)
            resumen_items = f"{len(reporte.reporte_stock.descuentos_aplicados)} productos ({total_desc} un.)"

            nota_ml = (res.numero_remito or arch.stem).strip() if res else arch.stem
            if self.interfaz.order_store.existe_nota_pedido(nota_ml):
                nota_ml = f"{nota_ml}_{datetime.now().strftime('%H%M%S')}"

            cliente_ml = (res.cliente or "Mercado Libre").strip() if res else "Mercado Libre"
            items_descontados = [
                (d.codigo, d.nombre_producto, d.cantidad_descontada)
                for d in reporte.reporte_stock.descuentos_aplicados
            ]

            dest_pedidos = application_root() / "data" / "pedidos_archivos"
            dest_pedidos.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(str(arch), str(dest_pedidos / arch.name))
            except Exception:
                pass

            sin_coincidencia_ml = list(res.descripciones_sin_coincidencia) if res else []
            self.interfaz.order_store.registrar_pedido(
                nota_pedido=nota_ml,
                numero_pedido=nota_ml,
                cliente=cliente_ml,
                bultos=1,
                logistica="Transporte",
                armador=armador_nom,
                tipo_archivo="docx",
                nombre_archivo=arch.name,
                agregado=False,
                articulos_descontados=total_desc,
                resumen_items=resumen_items,
                archivo_descuento=pdf_nom,
                items=items_descontados,
                archivo_hash=hash_doc,
                items_sin_coincidencia=sin_coincidencia_ml,
            )

            dest_final_carpeta = self.dest_archivado
            dest_final_carpeta.mkdir(parents=True, exist_ok=True)
            try:
                dest_final = dest_final_carpeta / arch.name
                if dest_final.exists() and arch.resolve() != dest_final.resolve():
                    dest_final.unlink()
                if arch.exists() and arch.resolve() != dest_final.resolve():
                    shutil.move(str(arch), str(dest_final))
            except Exception:
                pass

            self.interfaz.actualizar_listas()
            self.interfaz.sincronizar_sesiones(aviso_colaborativo=f"📄 {armador_nom} descontó lote ML ({arch.name})")
            print(f"[OK] Mercado Libre descontado: {nota_ml} | Cliente: {cliente_ml} | Items: {resumen_items} | PDF: {pdf_nom}")

        try:
            exito = await self.interfaz.ejecutar_tarea(f"Descuento Mercado Libre ({arch.name})", ejecutar_descuento_ml)
        finally:
            self._en_proceso_docx = False
        if exito:
            self.interfaz.notificar(f"Se descontaron exitosamente los productos de Mercado Libre ({arch.name}).")

    def construir_vista(self) -> ft.Column:
        return ft.Column(
            [
                ft.Text(
                    "Compara los nombres de productos del archivo .docx contra el catálogo y descuenta el stock en tiempo real en la base de datos.",
                    size=12,
                    color=self.interfaz.secundario,
                ),
                ft.Divider(height=8),
                ft.Row(
                    [
                        self.selector_archivo,
                        ft.Button(
                            "Cargar de PC",
                            icon=ft.Icons.UPLOAD_FILE,
                            bgcolor=ft.Colors.BLUE_GREY_800 if self.interfaz.modo_oscuro else ft.Colors.BLUE_GREY_100,
                            color=self.interfaz.texto,
                            on_click=self.subir_desde_pc,
                        ),
                        ft.IconButton(icon=ft.Icons.CLEAR_ALL, tooltip="Limpiar vista previa", on_click=self.limpiar),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            tooltip="Descartar este archivo de pendientes",
                            on_click=self.descartar_archivo_seleccionado,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    wrap=bool(getattr(self.interfaz, "es_pantalla_movil", False)),
                    spacing=6,
                ),
                self.resumen_texto,
                self.banner_no_encontrados,
                ft.Text("Vista previa de productos a descontar:", size=12, weight=ft.FontWeight.BOLD, color=self.interfaz.texto),
                self.lista_previsualizacion,
            ],
            tight=True,
            spacing=8,
        )
