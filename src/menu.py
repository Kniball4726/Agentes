"""
Panel de Control Interactivo del Agente de Stock y Remitos.
Permite al usuario interactuar fácilmente con el agente, ejecutar simulaciones,
procesar remitos mayoristas, canjes, ver el historial y restaurar archivos de prueba.
"""

import sys
import shutil
import getpass
import os
import re
import unicodedata
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import openpyxl
import xlrd

from .paths import application_root

load_dotenv(application_root() / ".env")
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
        self.base_dir = application_root()
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
            *self.carpeta_descuentos.glob("*.pdf"),
        ]
        return sorted(informes, key=lambda ruta: ruta.stat().st_mtime_ns)

    @staticmethod
    def _leer_referencias_informe(ruta_informe: Path) -> list[tuple[str, str]]:
        if ruta_informe.suffix.lower() == ".xls":
            hoja = xlrd.open_workbook(str(ruta_informe)).sheet_by_index(0)
            filas = [
                [hoja.cell_value(fila, columna) for columna in range(hoja.ncols)]
                for fila in range(hoja.nrows)
            ]
        else:
            libro = openpyxl.load_workbook(
                ruta_informe, read_only=True, data_only=True
            )
            hoja = libro.active
            filas = [list(fila) for fila in hoja.iter_rows(values_only=True)]
            libro.close()

        tipos = {
            "REMITO MAYORISTA": "Mayoristas",
            "CANJE": "Canjes",
            "MERCADO LIBRE": "MercadoLibre",
        }
        encabezados_posibles = (
            "PEDIDOS CON PRODUCTOS DESCONTADOS",
            "PEDIDOS DESCONTADOS EN ESTA PLANILLA",
            "PEDIDOS PROCESADOS",
        )
        for indice, fila in enumerate(filas[:-1]):
            encabezado_pedidos = any(
                any(
                    encabezado in str(valor or "").strip().upper()
                    for encabezado in encabezados_posibles
                )
                for valor in fila
            )
            encabezados_columnas = [
                str(valor or "").strip().upper()
                for valor in filas[indice + 1]
            ]
            if (
                not encabezado_pedidos
                or not encabezados_columnas
                or not encabezados_columnas[0].startswith("TIPO")
                or len(encabezados_columnas) < 3
                or "CLIENTE" not in encabezados_columnas[1]
                or "REMITO" not in encabezados_columnas[2]
            ):
                continue

            referencias = []
            for fila_documento in filas[indice + 2:]:
                tipo = (
                    str(fila_documento[0] or "").strip().upper()
                    if fila_documento
                    else ""
                )
                categoria = tipos.get(tipo)
                if categoria is None:
                    break
                if len(fila_documento) > 2 and fila_documento[2] is not None:
                    referencias.append(
                        (categoria, str(fila_documento[2]).strip())
                    )
            return referencias
        return []

    @staticmethod
    def _normalizar_referencia(texto: str) -> str:
        normalizado = unicodedata.normalize("NFKD", texto)
        return "".join(
            caracter
            for caracter in normalizado
            if not unicodedata.combining(caracter)
        ).strip().casefold()

    def _buscar_archivado(
        self, categoria: str, referencia: str, archivados: list[Path]
    ) -> Path | None:
        if categoria == "Mayoristas":
            numeros = re.findall(r"\d+", referencia)
            if not numeros:
                return None
            numero_remito = numeros[-1].lstrip("0")
            for archivo in archivados:
                coincidencia = re.match(r"(\d+)", archivo.stem)
                if coincidencia and coincidencia.group(1).lstrip("0") == numero_remito:
                    return archivo
            return None

        prefijo = "CANJE-" if categoria == "Canjes" else "ML-"
        referencia_archivo = referencia
        if referencia_archivo.upper().startswith(prefijo):
            referencia_archivo = referencia_archivo[len(prefijo):]
        referencia_normalizada = self._normalizar_referencia(referencia_archivo)
        for archivo in archivados:
            nombre_normalizado = self._normalizar_referencia(archivo.stem)
            if (
                nombre_normalizado == referencia_normalizada
                or nombre_normalizado.startswith(referencia_normalizada)
            ):
                return archivo
        return None

    def _restauraciones_por_fecha(self) -> dict[str, list[tuple[Path, Path]]]:
        carpetas_pendientes = {
            "Mayoristas": self.carpeta_mayoristas,
            "Canjes": self.carpeta_canjes,
            "MercadoLibre": self.carpeta_mercado_libre,
        }
        archivados = self._obtener_archivados()
        archivados_por_categoria = {
            "Mayoristas": archivados[0],
            "Canjes": archivados[1],
            "MercadoLibre": archivados[2],
        }
        restauraciones: dict[str, dict[Path, Path]] = {}
        for informe in self._obtener_generados():
            if informe.suffix.lower() not in {".xls", ".xlsx"}:
                continue
            coincidencia = re.match(
                r"^Descuento(\d{2}-\d{2}-\d{4})_", informe.stem
            )
            if not coincidencia:
                continue
            try:
                fecha = datetime.strptime(
                    coincidencia.group(1), "%d-%m-%Y"
                ).date().isoformat()
            except ValueError:
                continue
            for categoria, referencia in self._leer_referencias_informe(informe):
                archivado = self._buscar_archivado(
                    categoria,
                    referencia,
                    archivados_por_categoria[categoria],
                )
                if archivado is not None:
                    destino = carpetas_pendientes[categoria] / archivado.name
                    restauraciones.setdefault(fecha, {})[archivado] = destino
        return {
            fecha: list(archivos.items())
            for fecha, archivos in restauraciones.items()
        }

    def fechas_descuento_disponibles(self) -> list[str]:
        """Fechas con documentos archivados asociados a un informe de descuento."""
        return sorted(self._restauraciones_por_fecha(), reverse=True)

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
        print(f"  * Informes de Descuento       : {len(generados)} archivo(s)")
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

    def restaurar_para_pruebas(self, fecha_descuento: str | None = None) -> int:
        restauraciones = self._restauraciones_por_fecha()
        fechas = sorted(restauraciones, reverse=True)
        if not fechas:
            print(
                "\n[INFO] No hay documentos archivados asociados a informes "
                "de descuento."
            )
            return 0

        if fecha_descuento is None:
            print("\nFechas de descuento disponibles:")
            for indice, fecha in enumerate(fechas, start=1):
                print(f"  [{indice}] {datetime.fromisoformat(fecha).strftime('%d/%m/%Y')}")
            seleccion = input("Seleccione el número de la fecha a restaurar: ").strip()
            if not seleccion.isdigit() or not 1 <= int(seleccion) <= len(fechas):
                print("\n[ERROR] Selección de fecha no válida.")
                return 0
            fecha_descuento = fechas[int(seleccion) - 1]
        else:
            try:
                fecha_descuento = datetime.strptime(
                    fecha_descuento, "%Y-%m-%d"
                ).date().isoformat()
            except ValueError:
                print("\n[ERROR] La fecha de descuento no tiene un formato válido.")
                return 0

        archivos = restauraciones.get(fecha_descuento)
        if not archivos:
            print("\n[ERROR] No hay documentos archivados para esa fecha.")
            return 0

        fecha_legible = datetime.fromisoformat(fecha_descuento).strftime("%d/%m/%Y")
        print(
            f"\nRestaurando {len(archivos)} documentos descontados el "
            f"{fecha_legible}..."
        )
        for origen, destino in archivos:
            shutil.copy2(str(origen), str(destino))
            print(f"  * Copiado: {origen.name} -> {destino.parent.name}")

        print("[OK] Documentos restaurados exitosamente.")
        return len(archivos)

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
