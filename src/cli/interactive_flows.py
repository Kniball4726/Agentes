"""Flujos interactivos de consola CLI para procesamiento, fábrica, Full, inventario y menú."""

from __future__ import annotations

import shutil
from pathlib import Path

from ..agent import AgenteRemitosStock
from ..inventory import StockManager
from .admin_flows import (
    agregar_producto_admin_cli,
    autenticar_admin_cli,
    cargar_fabrica_archivos_cli,
    cargar_fabrica_manual_cli,
    cargar_pedido_fabrica_cli,
    descontar_mercado_full_terminal_cli,
    generar_pedido_fabrica_sugerido_cli,
    hacer_stock_fisico_terminal_cli,
)
from .protocols import InteractiveFlowsHostProtocol


class InteractiveFlowsService:
    """Servicio que implementa los comandos interactivos del menú de terminal."""

    def __init__(self, host: InteractiveFlowsHostProtocol) -> None:
        self._host = host

    def mostrar_banner(self) -> None:
        """Imprime el encabezado y resumen de carpetas pendientes por consola."""
        may, can, ml = self._host._obtener_pendientes()
        fab = self._host._obtener_pendientes_fabrica()
        full = self._host._obtener_pendientes_mercado_full()
        arch_m, arch_c, arch_ml = self._host._obtener_archivados()
        generados = self._host._obtener_generados()

        print("\n" + "=" * 72)
        print("         AGENTE INTELIGENTE DE CONTROL DE STOCK Y REMITOS")
        print("                   Panel de Control Interactivo")
        print("=" * 72)
        print(" [ESTADO DEL SISTEMA]")
        print(f"  * Pendientes Mayoristas (PDF) : {len(may)} archivo(s)")
        print(f"  * Pendientes Canjes (Excel)   : {len(can)} archivo(s)")
        print(f"  * Pendientes Mercado Libre    : {len(ml)} archivo(s)")
        print(f"  * Pedidos de Fábrica (Ingreso): {len(fab)} archivo(s)")
        print(f"  * Envíos Mercado Full (Excel) : {len(full)} archivo(s)")
        print(f"  * Archivos en Descontados     : {len(arch_m) + len(arch_c) + len(arch_ml)} archivo(s)")
        print(f"  * Informes de Descuento       : {len(generados)} archivo(s)")
        print("-" * 72)

    def procesar(
        self,
        incluir_mayoristas: bool = True,
        incluir_canjes: bool = True,
        simulacion: bool = False,
        incluir_mercado_libre: bool = True,
        usuario: str = "sistema",
    ) -> None:
        """Ejecuta el descuento por lotes desde consola para las fuentes seleccionadas."""
        may_pend, can_pend, ml_pend = self._host._obtener_pendientes()
        remitos_pdf = may_pend if incluir_mayoristas else []
        canjes_excel = can_pend if incluir_canjes else []
        pedidos_mercado_libre = ml_pend if incluir_mercado_libre else []

        if not remitos_pdf and not canjes_excel and not pedidos_mercado_libre:
            print("\n[AVISO] No se encontraron archivos para la seleccion indicada.")
            return

        stock_mgr = StockManager(ruta_excel_base=self._host.ruta_excel_base)
        reporte = AgenteRemitosStock(stock_manager=stock_mgr).ejecutar(
            rutas_pdf=remitos_pdf,
            rutas_canjes=canjes_excel,
            rutas_mercado_libre=pedidos_mercado_libre,
            carpeta_descuentos=self._host.carpeta_descuentos,
            simulacion=simulacion,
        )

        print("\n" + "=" * 70)
        print("DESCRIPCION DETALLADA DE PEDIDOS DESCONTADOS")
        print("=" * 70)
        for doc in reporte.documentos_verificados:
            tipo = (
                "REMITO MAYORISTA (PDF)"
                if doc.archivo.lower().endswith(".pdf")
                else ("MERCADO LIBRE (DOCX)" if doc.archivo.lower().endswith(".docx") else "CANJE (EXCEL)")
            )
            print(f"\n* [{tipo}] {doc.numero_remito}")
            print(f"  - Archivo      : {doc.archivo}")
            print(f"  - Cliente/DNI  : {doc.cliente}")
            print(f"  - Fecha/Obs    : {doc.fecha}")
            print(f"  - Articulos Tot: {doc.articulos_extraidos} unidades")
            print("  - Detalle de articulos en este pedido:")
            for it in doc.items:
                print(f"     [Cod {it.codigo:<6}] {it.descripcion[:40]:<40} -> Cant: {it.cantidad}")
            for descripcion, motivo in doc.descripciones_sin_coincidencia:
                print(f"     [NO DESCONTADO] {descripcion} -> {motivo}")

        print("\n" + "=" * 70)
        print("REPORTE CONSOLIDADO APLICADO EN LA PLANILLA DE STOCK")
        print("=" * 70)
        existentes = [d for d in reporte.reporte_stock.descuentos_aplicados if not d.es_nuevo_agregado]
        nuevos = [d for d in reporte.reporte_stock.descuentos_aplicados if d.es_nuevo_agregado]

        print(f"\nA. PRODUCTOS DEL CATALOGO ACTUALIZADOS EN COLUMNA C ({len(existentes)}):")
        print(f"   {'CODIGO':<8} | {'FILA':<5} | {'STOCK ANT.':<10} | {'DESCUENTO':<10} | {'STOCK FINAL':<11} | PRODUCTO")
        print("   " + "-" * 75)
        for desc in existentes:
            print(f"   {desc.codigo:<8} | {desc.fila_excel:<5} | {desc.stock_anterior:<10} | -{desc.cantidad_descontada:<9} | {desc.stock_nuevo:<11} | {desc.nombre_producto}")

        if nuevos:
            print(f"\nB. PRODUCTOS NO ENCONTRADOS AGREGADOS AL FINAL DE LA LISTA ({len(nuevos)}):")
            print(f"   {'CODIGO':<8} | {'FILA':<5} | {'CANT. DESCONTADA':<16} | DETALLE Y EXPLICACION")
            print("   " + "-" * 75)
            for desc in nuevos:
                print(f"   {desc.codigo:<8} | {desc.fila_excel:<5} | -{desc.cantidad_descontada:<15} | {desc.nombre_producto}")

        print("\n" + "=" * 70)
        print(f"DESTINO DEL ARCHIVO: {reporte.reporte_stock.archivo_guardado}")
        print("=" * 70)

        if not simulacion:
            print("\n--- Actualizando saldos de stock en la base de datos ---")
            actualizados = stock_mgr.actualizar_stock_base(
                descuentos=reporte.reporte_stock.descuentos_aplicados,
                sincronizar_excel=True,
                nombre_archivo=Path(reporte.reporte_stock.archivo_guardado).name,
                usuario=usuario,
            )
            print(f"   [OK] {actualizados} productos actualizados en la base de datos SQLite.")
            print("\n--- Archivando pedidos procesados en carpeta 'descontados' ---")
            archivos_movidos = 0
            for subcarpeta, lista in (("Mayoristas", remitos_pdf), ("Canjes", canjes_excel), ("MercadoLibre", pedidos_mercado_libre)):
                destino_dir = self._host.carpeta_descontados / subcarpeta
                destino_dir.mkdir(parents=True, exist_ok=True)
                for ruta in lista:
                    shutil.move(str(ruta), str(destino_dir / ruta.name))
                    print(f"   [MOVIDO] {ruta.name} -> {destino_dir}")
                    archivos_movidos += 1
            print(f"\n[OK] Se archivaron {archivos_movidos} archivos en: {self._host.carpeta_descontados}")
        else:
            print("\n[SIMULACION] No se modificaron ni movieron archivos del sistema.")

    def autenticar(self) -> bool:
        """Solicita credenciales de administrador configuradas en entorno (`_ADMIN_USUARIO`/`_ADMIN_CLAVE`)."""
        return autenticar_admin_cli()

    def agregar_producto_admin(self) -> None:
        """Flujo protegido para dar de alta un nuevo producto en una posición específica del catálogo."""
        agregar_producto_admin_cli(self._host, autenticar_fn=self.autenticar)

    def cargar_pedido_fabrica(self) -> None:
        """Flujo CLI para procesar ingresos desde fábrica por archivo o carga manual."""
        cargar_pedido_fabrica_cli(
            autenticar_fn=self.autenticar,
            on_archivos=self.cargar_fabrica_archivos,
            on_manual=self.cargar_fabrica_manual,
        )

    def cargar_fabrica_archivos(self) -> None:
        cargar_fabrica_archivos_cli(self._host)

    def cargar_fabrica_manual(self) -> None:
        cargar_fabrica_manual_cli(self._host)

    def generar_pedido_fabrica_cli(self) -> None:
        """Genera el Excel con los pedidos sugeridos a fábrica según máximos y mínimos."""
        generar_pedido_fabrica_sugerido_cli(self._host, autenticar_fn=self.autenticar)

    def descontar_mercado_full_cli(self) -> None:
        """Procesa y descuenta planillas Excel de Mercado Envíos Full desde consola."""
        descontar_mercado_full_terminal_cli(self._host, autenticar_fn=self.autenticar)

    def hacer_stock_fisico_cli(self, usuario: str = "operario") -> None:
        """Lee planillas Excel en StockFisico, compara con el digital y archiva resultados."""
        hacer_stock_fisico_terminal_cli(self._host, usuario=usuario)

    def iniciar(self) -> None:
        """Bucle principal del menú interactivo en terminal."""
        acciones = {
            "1": lambda: self.procesar(incluir_mayoristas=True, incluir_canjes=True, simulacion=False),
            "2": lambda: self.procesar(incluir_mayoristas=True, incluir_canjes=True, simulacion=True),
            "3": lambda: self.procesar(incluir_canjes=False, incluir_mercado_libre=False),
            "4": lambda: self.procesar(incluir_mayoristas=False, incluir_mercado_libre=False),
            "5": lambda: self.procesar(incluir_mayoristas=False, incluir_canjes=False),
            "6": self.cargar_pedido_fabrica,
            "7": self._host.ver_historial,
            "8": self._host.restaurar_para_pruebas,
            "9": self.agregar_producto_admin,
            "10": self.generar_pedido_fabrica_cli,
            "11": self.descontar_mercado_full_cli,
            "12": self.hacer_stock_fisico_cli,
        }
        try:
            while True:
                self.mostrar_banner()
                print(" Selecciona una accion:")
                print("  [1] Ejecutar Descuento Completo (Mayoristas + Canjes + Mercado Libre)")
                print("  [2] Modo Simulacion (incluye todas las fuentes, sin guardar ni mover)")
                print("  [3] Procesar Solo Remitos Mayoristas (PDF)")
                print("  [4] Procesar Solo Canjes (Excel)")
                print("  [5] Procesar Solo Pedidos de Mercado Libre (DOCX)")
                print("  [6] Cargar Pedido de Fábrica / Ajustar Stock  [ADMIN]")
                print("  [7] Ver Historial de Planillas Generadas")
                print("  [8] Restaurar Archivos de Prueba (Descontados -> Pendientes)")
                print("  [9] Agregar Producto al Catalogo  [ADMIN]")
                print("  [10] Generar Pedido Sugerido a Fabrica (Excel)  [ADMIN]")
                print("  [11] Descontar Envío Mercado Full (Excel)  [ADMIN]")
                print("  [12] Hacer Stock Físico y Comparar con Digital (Excel)")
                print("  [0] Salir")
                print("-" * 72)

                try:
                    opcion = input(" Ingrese una opcion [0-12]: ").strip()
                except (KeyboardInterrupt, EOFError):
                    print("\n\n[INTERRUMPIDO] Saliendo del menu... ¡Hasta luego!\n")
                    break

                if opcion == "0":
                    print("\n[SALIR] Hasta luego. ¡Mision finalizada!\n")
                    break
                accion = acciones.get(opcion)
                if accion:
                    accion()
                else:
                    print("\n[ERROR] Opcion no valida. Intente de nuevo.")

                try:
                    input("\nPresione ENTER para continuar...")
                except (KeyboardInterrupt, EOFError):
                    print("\n\n[INTERRUMPIDO] Saliendo del menu... ¡Hasta luego!\n")
                    break
        except KeyboardInterrupt:
            print("\n\n[INTERRUMPIDO] Ejecución cancelada. ¡Hasta luego!\n")
