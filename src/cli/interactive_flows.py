"""Flujos interactivos de consola CLI para procesamiento, fábrica, Full, inventario y menú."""

from __future__ import annotations

import getpass
import os
import shutil
from pathlib import Path

from ..agent import AgenteRemitosStock
from ..factory_parser import parsear_archivo_fabrica
from ..mercado_full_parser import parsear_archivo_mercado_full
from ..physical_stock_parser import parsear_excel_stock_fisico
from ..remito_parser import normalizar_codigo
from ..stock_manager import StockManager


class InteractiveFlowsMixin:
    """Mixin que implementa los comandos interactivos del menú de terminal."""

    ruta_excel_base: Path
    carpeta_fabrica: Path
    carpeta_mercado_full: Path
    carpeta_stock_fisico: Path
    carpeta_descuentos: Path
    carpeta_descontados: Path

    def mostrar_banner(self) -> None:
        """Imprime el encabezado y resumen de carpetas pendientes por consola."""
        may, can, ml = self._obtener_pendientes()
        fab = self._obtener_pendientes_fabrica()
        full = self._obtener_pendientes_mercado_full()
        arch_m, arch_c, arch_ml = self._obtener_archivados()
        generados = self._obtener_generados()

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
        may_pend, can_pend, ml_pend = self._obtener_pendientes()
        remitos_pdf = may_pend if incluir_mayoristas else []
        canjes_excel = can_pend if incluir_canjes else []
        pedidos_mercado_libre = ml_pend if incluir_mercado_libre else []

        if not remitos_pdf and not canjes_excel and not pedidos_mercado_libre:
            print("\n[AVISO] No se encontraron archivos para la seleccion indicada.")
            return

        stock_mgr = StockManager(ruta_excel_base=self.ruta_excel_base)
        reporte = AgenteRemitosStock(stock_manager=stock_mgr).ejecutar(
            rutas_pdf=remitos_pdf,
            rutas_canjes=canjes_excel,
            rutas_mercado_libre=pedidos_mercado_libre,
            carpeta_descuentos=self.carpeta_descuentos,
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
                destino_dir = self.carpeta_descontados / subcarpeta
                destino_dir.mkdir(parents=True, exist_ok=True)
                for ruta in lista:
                    shutil.move(str(ruta), str(destino_dir / ruta.name))
                    print(f"   [MOVIDO] {ruta.name} -> {destino_dir}")
                    archivos_movidos += 1
            print(f"\n[OK] Se archivaron {archivos_movidos} archivos en: {self.carpeta_descontados}")
        else:
            print("\n[SIMULACION] No se modificaron ni movieron archivos del sistema.")

    def _autenticar(self) -> bool:
        """Solicita credenciales de administrador configuradas en entorno (`_ADMIN_USUARIO`/`_ADMIN_CLAVE`)."""
        from .. import menu as menu_mod

        admin_usuario = getattr(menu_mod, "_ADMIN_USUARIO", None) or os.getenv("_ADMIN_USUARIO")
        admin_clave = getattr(menu_mod, "_ADMIN_CLAVE", None) or os.getenv("_ADMIN_CLAVE")
        if not admin_usuario or not admin_clave:
            print(
                "\n[ERROR] Credenciales de administrador no configuradas. "
                "Defina _ADMIN_USUARIO y _ADMIN_CLAVE en el archivo .env."
            )
            return False

        print("\n" + "-" * 72)
        print("  ACCESO RESTRINGIDO - Se requieren credenciales de administrador")
        print("-" * 72)

        for intento in range(1, 4):
            try:
                usuario = input(f"  Usuario [{intento}/3]: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n  [CANCELADO] Autenticacion cancelada por el usuario.")
                return False

            try:
                clave = getpass.getpass("  Contraseña: ")
            except (KeyboardInterrupt, EOFError):
                print("\n  [CANCELADO] Autenticacion cancelada por el usuario.")
                return False
            except Exception:
                try:
                    clave = input("  Contraseña (visible): ").strip()
                except (KeyboardInterrupt, EOFError):
                    print("\n  [CANCELADO] Autenticacion cancelada por el usuario.")
                    return False

            if usuario == admin_usuario and clave == admin_clave:
                print("  [OK] Acceso autorizado.\n")
                return True

            restantes = 3 - intento
            print(f"  [ERROR] Credenciales incorrectas. Intentos restantes: {restantes}" if restantes > 0 else "  [BLOQUEADO] Se superó el número máximo de intentos.")
        return False

    def agregar_producto_admin(self) -> None:
        """Flujo protegido para dar de alta un nuevo producto en una posición específica del catálogo."""
        if not self._autenticar():
            print("\n[ACCESO DENEGADO] No se realizaron cambios en el catálogo.")
            return

        print("=" * 72)
        print("  AGREGAR NUEVO PRODUCTO AL CATALOGO")
        print("=" * 72)
        print("  (Deje el stock inicial en blanco para no asignar valor)")
        print("  (Ctrl+C en cualquier momento para cancelar)")
        print("-" * 72)

        try:
            codigo_nuevo = input("  Código del NUEVO producto    : ").strip()
            if not codigo_nuevo:
                print("\n[CANCELADO] El código no puede estar vacío.")
                return
            nombre_nuevo = input("  Nombre del NUEVO producto    : ").strip()
            if not nombre_nuevo:
                print("\n[CANCELADO] El nombre no puede estar vacío.")
                return
            codigo_arriba = input("  Código del producto ANTERIOR (se insertará debajo de él): ").strip()
            if not codigo_arriba:
                print("\n[CANCELADO] Debe indicar un producto de referencia.")
                return
            stock_str = input("  Stock inicial (Enter = sin valor): ").strip()
            stock_inicial = None
            if stock_str:
                try:
                    stock_inicial = int(stock_str)
                except ValueError:
                    print("\n[AVISO] El stock debe ser un número entero. Se asignará sin valor.")

            print("\n" + "-" * 72)
            print("  Confirmar alta de producto:")
            print(f"    Código   : {codigo_nuevo}")
            print(f"    Nombre   : {nombre_nuevo}")
            print(f"    Debajo de: {codigo_arriba}")
            print(f"    Stock    : {stock_inicial if stock_inicial is not None else '(sin valor)'}")
            print("-" * 72)
            if input("  ¿Confirmar? [s/N]: ").strip().lower() != "s":
                print("\n[CANCELADO] No se realizaron cambios.")
                return
        except (KeyboardInterrupt, EOFError):
            print("\n\n[CANCELADO] Alta de producto cancelada por el usuario. No se realizaron cambios.")
            return

        try:
            stock_mgr = StockManager(ruta_excel_base=self.ruta_excel_base)
            exito, mensaje, _ = stock_mgr.agregar_producto_en_posicion(
                codigo_nuevo=codigo_nuevo,
                nombre_nuevo=nombre_nuevo,
                codigo_arriba=codigo_arriba,
                stock_inicial=stock_inicial,
            )
            print(f"\n[OK] {mensaje}\n     Archivo actualizado: {self.ruta_excel_base}" if exito else f"\n[ERROR] {mensaje}")
        except KeyboardInterrupt:
            print(f"\n[INTERRUMPIDO] El proceso fue interrumpido. Verifique manualmente: {self.ruta_excel_base}")
        except Exception as e:
            print(f"\n[ERROR] Ocurrió un problema al acceder al catálogo: {e}")

    def cargar_pedido_fabrica(self) -> None:
        """Flujo CLI para procesar ingresos desde fábrica por archivo o carga manual."""
        if not self._autenticar():
            print("\n[ACCESO DENEGADO] No se realizaron cambios.")
            return

        print("\n" + "=" * 72)
        print("  CARGA DE PEDIDO DE FÁBRICA / REESTABLECIMIENTO DE STOCK")
        print("=" * 72)
        print("  [1] Procesar archivos en carpeta Descuentos/Fabrica")
        print("  [2] Cargar stock manualmente por código")
        print("  [0] Volver al menú principal")
        print("-" * 72)

        try:
            subopcion = input("  Seleccione una opción [0-2]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  [CANCELADO] Operación cancelada por el usuario.")
            return

        if subopcion == "0":
            return
        if subopcion == "1":
            self._cargar_fabrica_archivos()
        elif subopcion == "2":
            self._cargar_fabrica_manual()

    def _cargar_fabrica_archivos(self) -> None:
        archivos = self._obtener_pendientes_fabrica()
        if not archivos:
            print(f"\n[AVISO] No hay archivos en la carpeta: {self.carpeta_fabrica}")
            return
        print(f"\nSe encontraron {len(archivos)} archivo(s) de fábrica:")
        for idx, a in enumerate(archivos, 1):
            print(f"  {idx}. {a.name}")
        print("\nTipo de operación:\n  [1] Sumar al stock actual (Reabastecimiento)\n  [2] Sobrescribir stock (Ajuste directo)")
        try:
            sobrescribir = input("  Seleccione modo [1]: ").strip() == "2"
        except (KeyboardInterrupt, EOFError):
            print("\n  [CANCELADO] Operación cancelada.")
            return

        stock_mgr = StockManager(ruta_excel_base=self.ruta_excel_base)
        total_procesados = 0
        for a in archivos:
            print(f"\nProcesando {a.name}...")
            try:
                totales, _ = parsear_archivo_fabrica(a)
                if not totales:
                    print("  [AVISO] No se extrajeron productos con cantidad válida de este archivo.")
                    continue
                resumen = stock_mgr.registrar_ingreso_fabrica(totales, sobrescribir=sobrescribir)
                print(f"  [OK] Se actualizaron {len(resumen)} productos en la base y Productos.xlsx.")
                for c, (s_ant, s_nvo) in resumen.items():
                    print(f"       Cod {c} ({stock_mgr.catalogo[c][1][:30]}): {s_ant} -> {s_nvo}")
                dest_fab = self.carpeta_descontados / "Fabrica"
                dest_fab.mkdir(parents=True, exist_ok=True)
                shutil.move(str(a), str(dest_fab / a.name))
                print(f"       Archivo archivado en: {dest_fab}")
                total_procesados += 1
            except Exception as e:
                print(f"  [ERROR] Falló el procesamiento de {a.name}: {e}")
        print(f"\n[FIN] {total_procesados} archivo(s) procesados exitosamente.")

    def _cargar_fabrica_manual(self) -> None:
        stock_mgr = StockManager(ruta_excel_base=self.ruta_excel_base)
        print("\nModo de carga manual (escriba 'fin' o deje código vacío para terminar):")
        print("  [1] Sumar al stock actual (Reabastecimiento)\n  [2] Sobrescribir stock (Ajuste directo)")
        try:
            sobrescribir = input("  Seleccione modo [1]: ").strip() == "2"
        except (KeyboardInterrupt, EOFError):
            print("\n  [CANCELADO] Operación cancelada.")
            return

        cargas: dict[str, int] = {}
        while True:
            try:
                cod = input("\n  Código de producto (o 'fin'): ").strip()
                if not cod or cod.lower() == "fin":
                    break
                cod_norm = normalizar_codigo(cod)
                if cod_norm not in stock_mgr.catalogo:
                    print(f"  [ERROR] El código '{cod_norm}' no existe en el catálogo.")
                    continue
                _, nom, st_actual = stock_mgr.catalogo[cod_norm]
                print(f"  Producto: {nom} | Stock actual: {st_actual}")
                cant_str = input(f"  Cantidad a {'fijar' if sobrescribir else 'sumar'}: ").strip()
                if not cant_str:
                    continue
                cant = int(cant_str)
                if cant < 0:
                    print("  [ERROR] La cantidad no puede ser negativa.")
                    continue
                cargas[cod_norm] = cant
            except ValueError:
                print("  [ERROR] La cantidad debe ser un número entero.")
            except (KeyboardInterrupt, EOFError):
                print("\n  [CANCELADO] Entrada interrumpida.")
                return

        if not cargas:
            print("\n[AVISO] No se ingresaron productos para actualizar.")
            return
        try:
            if input(f"\nSe actualizarán {len(cargas)} producto(s). ¿Confirmar actualización? [s/N]: ").strip().lower() != "s":
                print("\n[CANCELADO] No se realizaron cambios.")
                return
            resumen = stock_mgr.registrar_ingreso_fabrica(cargas, sobrescribir=sobrescribir)
            print(f"\n[OK] Se actualizaron {len(resumen)} productos exitosamente:")
            for c, (s_ant, s_nvo) in resumen.items():
                print(f"     Cod {c} ({stock_mgr.catalogo[c][1][:30]}): {s_ant} -> {s_nvo}")
        except Exception as e:
            print(f"\n[ERROR] Ocurrió un error al actualizar el stock: {e}")

    def generar_pedido_fabrica_cli(self) -> None:
        """Genera el Excel con los pedidos sugeridos a fábrica según máximos y mínimos."""
        if not self._autenticar():
            print("\n[ACCESO DENEGADO] Requiere permisos de administrador.")
            return
        stock_mgr = StockManager(self.ruta_excel_base)
        print("\n--- Generando Pedido Sugerido a Fábrica (Excel) ---")
        try:
            ruta = stock_mgr.generar_pedido_sugerido_fabrica(solo_criticos=True)
            print(f"   [OK] Archivo generado exitosamente en:\n        {ruta}")
        except Exception as e:
            print(f"   [ERROR] No se pudo generar el pedido: {e}")

    def descontar_mercado_full_cli(self) -> None:
        """Procesa y descuenta planillas Excel de Mercado Envíos Full desde consola."""
        if not self._autenticar():
            print("\n[ACCESO DENEGADO] Requiere permisos de administrador.")
            return
        archivos = self._obtener_pendientes_mercado_full()
        if not archivos:
            print(f"\n[AVISO] No hay archivos pendientes en {self.carpeta_mercado_full}.")
            return
        print(f"\n--- Procesar Envíos Mercado Full ({len(archivos)} archivo(s)) ---")
        stock_mgr = StockManager(self.ruta_excel_base)

        for arch in archivos:
            print(f"\nLeyendo: {arch.name}")
            try:
                totales, _ = parsear_archivo_mercado_full(arch)
            except Exception as e:
                print(f"  [ERROR] No se pudo leer {arch.name}: {e}")
                continue
            if not totales:
                print("  [AVISO] No se encontraron productos válidos en el archivo.")
                continue
            print(f"  Se detectaron {len(totales)} productos a descontar (Total unidades: {sum(totales.values())}).")
            for cod, cant in list(totales.items())[:5]:
                _, nom, stk = stock_mgr.catalogo.get(cod, ("", "No encontrado", 0))
                print(f"   • [{cod}] {nom[:30]} | Descontar: {cant} | Stock act: {stk} -> {stk - cant}")
            try:
                conf = input(f"¿Confirmar descuento de {arch.name}? [s/N]: ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                print("\n  [CANCELADO] Operación interrumpida.")
                return
            if conf != "s":
                print("  [SALTADO] No se aplicaron descuentos para este archivo.")
                continue
            try:
                stock_mgr.descontar_mercado_full(totales, nombre_archivo=arch.name)
                dest = self.carpeta_descontados / "MercadoFull"
                dest.mkdir(parents=True, exist_ok=True)
                shutil.move(str(arch), str(dest / arch.name))
                print(f"  [OK] Descuento aplicado exitosamente. Archivo movido a {dest.name}/.")
            except Exception as e:
                print(f"  [ERROR] Falló al aplicar el descuento: {e}")

    def hacer_stock_fisico_cli(self, usuario: str = "operario") -> None:
        """Lee planillas Excel en StockFisico, compara con el digital y archiva resultados."""
        archivos = self._obtener_pendientes_stock_fisico()
        if not archivos:
            print(f"\n[AVISO] No hay planillas pendientes en {self.carpeta_stock_fisico}.")
            return
        print(f"\n--- Relevamiento de Stock Físico ({len(archivos)} archivo(s)) ---")
        stock_mgr = StockManager(self.ruta_excel_base)

        for arch in archivos:
            print(f"\nLeyendo: {arch.name}")
            try:
                totales, _ = parsear_excel_stock_fisico(arch)
            except Exception as e:
                print(f"  [ERROR] No se pudo leer {arch.name}: {e}")
                continue
            if not totales:
                print("  [AVISO] No se encontraron productos válidos en el archivo.")
                continue
            ruta_doc, comparativa = stock_mgr.procesar_stock_fisico(totales, usuario=usuario, nombre_archivo=arch.name)
            con_dif = [i for i in comparativa if i["diferencia"] != 0]
            print(f"  [OK] Relevados: {len(comparativa)} | Con diferencias: {len(con_dif)}")
            for item in comparativa[:10]:
                dif = item["diferencia"]
                dif_str = f"+{dif}" if dif > 0 else str(dif)
                print(f"   • [{item['code']}] {item['name'][:30]} | Digital: {item['stock_digital']} | Físico: {item['stock_fisico']} | Dif: {dif_str} ({item['estado']})")
            print(f"  [REPORTE UNIFICADO ADMIN] {ruta_doc}")
            dest = self.carpeta_descontados / "StockFisico"
            dest.mkdir(parents=True, exist_ok=True)
            shutil.move(str(arch), str(dest / arch.name))

    def iniciar(self) -> None:
        """Bucle principal del menú interactivo en terminal."""
        acciones = {
            "1": lambda: self.procesar(incluir_mayoristas=True, incluir_canjes=True, simulacion=False),
            "2": lambda: self.procesar(incluir_mayoristas=True, incluir_canjes=True, simulacion=True),
            "3": lambda: self.procesar(incluir_canjes=False, incluir_mercado_libre=False),
            "4": lambda: self.procesar(incluir_mayoristas=False, incluir_mercado_libre=False),
            "5": lambda: self.procesar(incluir_mayoristas=False, incluir_canjes=False),
            "6": self.cargar_pedido_fabrica,
            "7": self.ver_historial,
            "8": self.restaurar_para_pruebas,
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
