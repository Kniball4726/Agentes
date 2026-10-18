"""
Panel de Control Interactivo del Agente de Stock y Remitos.
Permite al usuario interactuar fácilmente con el agente, ejecutar simulaciones,
procesar remitos mayoristas, canjes, ver el historial y restaurar archivos de prueba.
"""

import sys
import shutil
import getpass
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
_ADMIN_USUARIO = os.getenv("_ADMIN_USUARIO")
_ADMIN_CLAVE = os.getenv("_ADMIN_CLAVE")

# Configurar salida UTF-8 para consola de Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from .agent import AgenteRemitosStock
from .stock_manager import StockManager


class MenuAgente:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.ruta_excel_base = self.base_dir / "Descuentos" / "Productos.xlsx"
        self.carpeta_mayoristas = self.base_dir / "Descuentos" / "Mayoristas"
        self.carpeta_canjes = self.base_dir / "Descuentos" / "Canjes"
        self.carpeta_mercado_libre = self.base_dir / "Descuentos" / "MercadoLibre"
        self.carpeta_descuentos = self.base_dir / "Descuentos" / "descuentos"
        self.carpeta_descontados = self.base_dir / "Descuentos" / "descontados"

        self.carpeta_mayoristas.mkdir(parents=True, exist_ok=True)
        self.carpeta_canjes.mkdir(parents=True, exist_ok=True)
        self.carpeta_mercado_libre.mkdir(parents=True, exist_ok=True)
        self.carpeta_descuentos.mkdir(parents=True, exist_ok=True)
        self.carpeta_descontados.mkdir(parents=True, exist_ok=True)

    def _obtener_pendientes(self):
        mayoristas = sorted(list(self.carpeta_mayoristas.glob("*.pdf")))
        canjes = sorted(list(self.carpeta_canjes.glob("*.xlsx")))
        mercado_libre = sorted(list(self.carpeta_mercado_libre.glob("*.docx")))
        return mayoristas, canjes, mercado_libre

    def _obtener_archivados(self):
        arch_may = list((self.carpeta_descontados / "Mayoristas").glob("*.pdf")) if (self.carpeta_descontados / "Mayoristas").exists() else []
        arch_can = list((self.carpeta_descontados / "Canjes").glob("*.xlsx")) if (self.carpeta_descontados / "Canjes").exists() else []
        carpeta_ml = self.carpeta_descontados / "MercadoLibre"
        arch_ml = list(carpeta_ml.glob("*.docx")) if carpeta_ml.exists() else []
        return arch_may, arch_can, arch_ml

    def _obtener_generados(self):
        informes = [
            *self.carpeta_descuentos.glob("*.xls"),
            *self.carpeta_descuentos.glob("*.xlsx"),
        ]
        return sorted(informes, key=lambda ruta: ruta.stat().st_mtime_ns)

    def mostrar_banner(self):
        may, can, ml = self._obtener_pendientes()
        arch_m, arch_c, arch_ml = self._obtener_archivados()
        generados = self._obtener_generados()

        print("\n" + "=" * 72)
        print("         AGENTE INTELIGENTE DE CONTROL DE STOCK Y REMITOS")
        print("                   Panel de Control Interactivo")
        print("=" * 72)
        print(f" [ESTADO DEL SISTEMA]")
        print(f"  * Pendientes Mayoristas (PDF) : {len(may)} archivo(s)")
        print(f"  * Pendientes Canjes (Excel)   : {len(can)} archivo(s)")
        print(f"  * Pendientes Mercado Libre    : {len(ml)} archivo(s)")
        print(f"  * Archivos en Descontados     : {len(arch_m) + len(arch_c) + len(arch_ml)} archivo(s)")
        print(f"  * Planillas Descuento Creadas : {len(generados)} archivo(s)")
        print("-" * 72)

    def procesar(
        self,
        incluir_mayoristas=True,
        incluir_canjes=True,
        simulacion=False,
        incluir_mercado_libre=True
    ):
        may_pend, can_pend, ml_pend = self._obtener_pendientes()
        remitos_pdf = may_pend if incluir_mayoristas else []
        canjes_excel = can_pend if incluir_canjes else []
        pedidos_mercado_libre = ml_pend if incluir_mercado_libre else []

        if not remitos_pdf and not canjes_excel and not pedidos_mercado_libre:
            print("\n[AVISO] No se encontraron archivos para la seleccion indicada.")
            return

        stock_mgr = StockManager(ruta_excel_base=self.ruta_excel_base)
        agente = AgenteRemitosStock(stock_manager=stock_mgr)

        reporte = agente.ejecutar(
            rutas_pdf=remitos_pdf,
            rutas_canjes=canjes_excel,
            rutas_mercado_libre=pedidos_mercado_libre,
            carpeta_descuentos=self.carpeta_descuentos,
            simulacion=simulacion
        )

        # 1. DESCRIPCIÓN DETALLADA DE CADA PEDIDO
        print("\n" + "=" * 70)
        print("DESCRIPCION DETALLADA DE PEDIDOS DESCONTADOS")
        print("=" * 70)

        for doc in reporte.documentos_verificados:
            if doc.archivo.lower().endswith(".pdf"):
                tipo = "REMITO MAYORISTA (PDF)"
            elif doc.archivo.lower().endswith(".docx"):
                tipo = "MERCADO LIBRE (DOCX)"
            else:
                tipo = "CANJE (EXCEL)"
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

        # 2. REPORTE DEL DESCUENTO CONSOLIDADO EN LA PLANILLA
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

        # 3. ARCHIVADO (solo si no es simulación)
        if not simulacion:
            print("\n--- Archivando pedidos procesados en carpeta 'descontados' ---")
            dest_mayoristas = self.carpeta_descontados / "Mayoristas"
            dest_canjes = self.carpeta_descontados / "Canjes"
            dest_mercado_libre = self.carpeta_descontados / "MercadoLibre"
            dest_mayoristas.mkdir(parents=True, exist_ok=True)
            dest_canjes.mkdir(parents=True, exist_ok=True)
            dest_mercado_libre.mkdir(parents=True, exist_ok=True)

            archivos_movidos = 0
            for pdf_path in remitos_pdf:
                shutil.move(str(pdf_path), str(dest_mayoristas / pdf_path.name))
                print(f"   [MOVIDO] {pdf_path.name} -> {dest_mayoristas}")
                archivos_movidos += 1

            for excel_path in canjes_excel:
                shutil.move(str(excel_path), str(dest_canjes / excel_path.name))
                print(f"   [MOVIDO] {excel_path.name} -> {dest_canjes}")
                archivos_movidos += 1

            for docx_path in pedidos_mercado_libre:
                shutil.move(str(docx_path), str(dest_mercado_libre / docx_path.name))
                print(f"   [MOVIDO] {docx_path.name} -> {dest_mercado_libre}")
                archivos_movidos += 1

            print(f"\n[OK] Se archivaron {archivos_movidos} archivos en: {self.carpeta_descontados}")
        else:
            print("\n[SIMULACION] No se modificaron ni movieron archivos del sistema.")

    def ver_historial(self):
        generados = self._obtener_generados()
        print("\n" + "=" * 70)
        print("HISTORIAL DE PLANILLAS DE DESCUENTO GENERADAS")
        print("=" * 70)
        if not generados:
            print("  (No hay planillas generadas aun en Descuentos/descuentos/)")
        else:
            for i, arch in enumerate(generados, 1):
                tam_kb = arch.stat().st_size / 1024
                mtime = datetime.fromtimestamp(arch.stat().st_mtime).strftime("%d/%m/%Y %H:%M:%S")
                print(f"  {i}. {arch.name:<30} | {tam_kb:>6.1f} KB | Creado: {mtime}")
        print("=" * 70)

    def restaurar_para_pruebas(self):
        arch_m, arch_c, arch_ml = self._obtener_archivados()
        total = len(arch_m) + len(arch_c) + len(arch_ml)

        if total == 0:
            print("\n[INFO] No hay archivos en 'descontados' para restaurar.")
            return

        print(f"\nRestaurando {total} archivos desde 'descontados' hacia sus carpetas pendientes...")
        for f in arch_m:
            shutil.copy2(str(f), str(self.carpeta_mayoristas / f.name))
            print(f"  * Copiado a Mayoristas: {f.name}")

        for f in arch_c:
            shutil.copy2(str(f), str(self.carpeta_canjes / f.name))
            print(f"  * Copiado a Canjes: {f.name}")

        for f in arch_ml:
            shutil.copy2(str(f), str(self.carpeta_mercado_libre / f.name))
            print(f"  * Copiado a Mercado Libre: {f.name}")

        print("[OK] Archivos restaurados exitosamente para nuevas pruebas.")

    def _autenticar(self) -> bool:
        """
        Solicita usuario y contraseña. Permite hasta 3 intentos.
        Retorna True si las credenciales son válidas, False en caso contrario.
        Ctrl+C durante el login cancela la autenticación limpiamente.
        """
        if not _ADMIN_USUARIO or not _ADMIN_CLAVE:
            print(
                "\n[ERROR] Credenciales de administrador no configuradas. "
                "Defina _ADMIN_USUARIO y _ADMIN_CLAVE en el archivo .env."
            )
            return False

        print("\n" + "-" * 72)
        print("  ACCESO RESTRINGIDO - Se requieren credenciales de administrador")
        print("-" * 72)

        MAX_INTENTOS = 3
        for intento in range(1, MAX_INTENTOS + 1):
            try:
                usuario = input(f"  Usuario [{intento}/{MAX_INTENTOS}]: ").strip()
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

            if usuario == _ADMIN_USUARIO and clave == _ADMIN_CLAVE:
                print("  [OK] Acceso autorizado.\n")
                return True

            restantes = MAX_INTENTOS - intento
            if restantes > 0:
                print(f"  [ERROR] Credenciales incorrectas. Intentos restantes: {restantes}")
            else:
                print("  [BLOQUEADO] Se superó el número máximo de intentos.")

        return False

    def agregar_producto_admin(self):
        """
        Funcionalidad protegida por contraseña para agregar un nuevo producto
        al catálogo (Productos.xlsx) en una posición específica.
        Ctrl+C en cualquier punto del formulario cancela la operación sin modificar archivos.
        """
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
            # --- Recopilar datos del nuevo producto ---
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
                    stock_inicial = None

            # --- Confirmación antes de escribir ---
            print("\n" + "-" * 72)
            print("  Confirmar alta de producto:")
            print(f"    Código   : {codigo_nuevo}")
            print(f"    Nombre   : {nombre_nuevo}")
            print(f"    Debajo de: {codigo_arriba}")
            print(f"    Stock    : {stock_inicial if stock_inicial is not None else '(sin valor)'}")
            print("-" * 72)
            confirmar = input("  ¿Confirmar? [s/N]: ").strip().lower()
            if confirmar != "s":
                print("\n[CANCELADO] No se realizaron cambios.")
                return

        except (KeyboardInterrupt, EOFError):
            print("\n\n[CANCELADO] Alta de producto cancelada por el usuario. No se realizaron cambios.")
            return

        # --- Ejecutar inserción (fuera del bloque de inputs para distinguir errores de I/O) ---
        try:
            stock_mgr = StockManager(ruta_excel_base=self.ruta_excel_base)
            exito, mensaje, fila = stock_mgr.agregar_producto_en_posicion(
                codigo_nuevo=codigo_nuevo,
                nombre_nuevo=nombre_nuevo,
                codigo_arriba=codigo_arriba,
                stock_inicial=stock_inicial
            )
            if exito:
                print(f"\n[OK] {mensaje}")
                print(f"     Archivo actualizado: {self.ruta_excel_base}")
            else:
                print(f"\n[ERROR] {mensaje}")
        except KeyboardInterrupt:
            print("\n[INTERRUMPIDO] El proceso fue interrumpido. El archivo puede haber quedado en estado incompleto.")
            print(f"               Verifique manualmente: {self.ruta_excel_base}")
        except Exception as e:
            print(f"\n[ERROR] Ocurrió un problema al acceder al catálogo: {e}")

    def iniciar(self):
        try:
            while True:
                self.mostrar_banner()
                print(" Selecciona una accion:")
                print("  [1] Ejecutar Descuento Completo (Mayoristas + Canjes + Mercado Libre)")
                print("  [2] Modo Simulacion (incluye todas las fuentes, sin guardar ni mover)")
                print("  [3] Procesar Solo Remitos Mayoristas (PDF)")
                print("  [4] Procesar Solo Canjes (Excel)")
                print("  [5] Procesar Solo Pedidos de Mercado Libre (DOCX)")
                print("  [6] Ver Historial de Planillas Generadas")
                print("  [7] Restaurar Archivos de Prueba (Descontados -> Pendientes)")
                print("  [8] Agregar Producto al Catalogo  [ADMIN]")
                print("  [0] Salir")
                print("-" * 72)

                try:
                    opcion = input(" Ingrese una opcion [0-8]: ").strip()
                except (KeyboardInterrupt, EOFError):
                    print("\n\n[INTERRUMPIDO] Saliendo del menu... ¡Hasta luego!\n")
                    break

                if opcion == "1":
                    self.procesar(incluir_mayoristas=True, incluir_canjes=True, simulacion=False)
                elif opcion == "2":
                    self.procesar(incluir_mayoristas=True, incluir_canjes=True, simulacion=True)
                elif opcion == "3":
                    self.procesar(incluir_canjes=False, incluir_mercado_libre=False)
                elif opcion == "4":
                    self.procesar(incluir_mayoristas=False, incluir_mercado_libre=False)
                elif opcion == "5":
                    self.procesar(incluir_mayoristas=False, incluir_canjes=False)
                elif opcion == "6":
                    self.ver_historial()
                elif opcion == "7":
                    self.restaurar_para_pruebas()
                elif opcion == "8":
                    self.agregar_producto_admin()
                elif opcion == "0":
                    print("\n[SALIR] Hasta luego. ¡Mision finalizada!\n")
                    break
                else:
                    print("\n[ERROR] Opcion no valida. Intente de nuevo.")

                try:
                    input("\nPresione ENTER para continuar...")
                except (KeyboardInterrupt, EOFError):
                    print("\n\n[INTERRUMPIDO] Saliendo del menu... ¡Hasta luego!\n")
                    break

        except KeyboardInterrupt:
            print("\n\n[INTERRUMPIDO] Ejecución cancelada. ¡Hasta luego!\n")


if __name__ == "__main__":
    menu = MenuAgente()
    menu.iniciar()
