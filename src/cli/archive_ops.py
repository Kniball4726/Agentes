"""Operaciones de bandeja de entrada, informes generados y restauración de archivados para CLI."""

from __future__ import annotations

import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Iterable

import openpyxl
import xlrd


def _listar_por_extensiones(carpeta: Path, extensiones: Iterable[str]) -> list[Path]:
    archivos: list[Path] = []
    for ext in extensiones:
        archivos.extend(carpeta.glob(ext))
    return sorted(archivos)


class ArchiveOpsMixin:
    """Mixin que gestiona rutas pendientes, archivadas y restauración por fecha."""

    base_dir: Path
    carpeta_mayoristas: Path
    carpeta_canjes: Path
    carpeta_mercado_libre: Path
    carpeta_fabrica: Path
    carpeta_mercado_full: Path
    carpeta_stock_fisico: Path
    carpeta_descuentos: Path
    carpeta_descontados: Path

    def _obtener_pendientes(self) -> tuple[list[Path], list[Path], list[Path]]:
        return (
            sorted(self.carpeta_mayoristas.glob("*.pdf")),
            sorted(self.carpeta_canjes.glob("*.xlsx")),
            sorted(self.carpeta_mercado_libre.glob("*.docx")),
        )

    def _obtener_pendientes_fabrica(self) -> list[Path]:
        return _listar_por_extensiones(self.carpeta_fabrica, ("*.xlsx", "*.xls", "*.pdf"))

    def _obtener_pendientes_mercado_full(self) -> list[Path]:
        carpeta = getattr(self, "carpeta_mercado_full", self.base_dir / "Descuentos" / "MercadoFull")
        return _listar_por_extensiones(carpeta, ("*.xlsx", "*.xls"))

    def _obtener_pendientes_stock_fisico(self) -> list[Path]:
        carpeta = getattr(self, "carpeta_stock_fisico", self.base_dir / "Descuentos" / "StockFisico")
        return _listar_por_extensiones(carpeta, ("*.xlsx", "*.xls"))

    def _obtener_archivados(self) -> tuple[list[Path], list[Path], list[Path]]:
        carp_may = self.carpeta_descontados / "Mayoristas"
        carp_can = self.carpeta_descontados / "Canjes"
        carp_ml = self.carpeta_descontados / "MercadoLibre"
        return (
            list(carp_may.glob("*.pdf")) if carp_may.exists() else [],
            list(carp_can.glob("*.xlsx")) if carp_can.exists() else [],
            list(carp_ml.glob("*.docx")) if carp_ml.exists() else [],
        )

    def _obtener_generados(self) -> list[Path]:
        carpeta_fab = getattr(self, "carpeta_fabrica", None)
        carpeta_pedidos_fab = carpeta_fab / "Pedidos_Sugeridos" if carpeta_fab else None
        carpeta_sf = getattr(self, "carpeta_stock_fisico", None)
        carpeta_comparativas = carpeta_sf / "Comparativas" if carpeta_sf else None
        informes = _listar_por_extensiones(self.carpeta_descuentos, ("*.xls", "*.xlsx", "*.pdf"))
        if carpeta_pedidos_fab is not None and carpeta_pedidos_fab.exists():
            informes.extend(_listar_por_extensiones(carpeta_pedidos_fab, ("*.xlsx", "*.xls", "*.pdf")))
        if carpeta_comparativas is not None and carpeta_comparativas.exists():
            informes.extend(_listar_por_extensiones(carpeta_comparativas, ("*.xlsx", "*.xls")))
        return sorted(informes, key=lambda ruta: ruta.stat().st_mtime_ns)

    @staticmethod
    def _leer_referencias_informe(ruta_informe: Path) -> list[tuple[str, str]]:
        """Extrae pares `(categoria, referencia)` de los pedidos incluidos en un informe Excel."""
        if ruta_informe.suffix.lower() == ".xls":
            hoja = xlrd.open_workbook(str(ruta_informe)).sheet_by_index(0)
            filas = [
                [hoja.cell_value(fila, columna) for columna in range(hoja.ncols)]
                for fila in range(hoja.nrows)
            ]
        else:
            libro = openpyxl.load_workbook(ruta_informe, read_only=True, data_only=True)
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
                any(enc in str(valor or "").strip().upper() for enc in encabezados_posibles)
                for valor in fila
            )
            encabezados_columnas = [str(valor or "").strip().upper() for valor in filas[indice + 1]]
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
                tipo = str(fila_documento[0] or "").strip().upper() if fila_documento else ""
                categoria = tipos.get(tipo)
                if categoria is None:
                    break
                if len(fila_documento) > 2 and fila_documento[2] is not None:
                    referencias.append((categoria, str(fila_documento[2]).strip()))
            return referencias
        return []

    @staticmethod
    def _normalizar_referencia(texto: str) -> str:
        normalizado = unicodedata.normalize("NFKD", texto)
        return "".join(c for c in normalizado if not unicodedata.combining(c)).strip().casefold()

    def _buscar_archivado(self, categoria: str, referencia: str, archivados: list[Path]) -> Path | None:
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
        referencia_archivo = referencia[len(prefijo):] if referencia.upper().startswith(prefijo) else referencia
        referencia_norm = self._normalizar_referencia(referencia_archivo)
        for archivo in archivados:
            nombre_norm = self._normalizar_referencia(archivo.stem)
            if nombre_norm == referencia_norm or nombre_norm.startswith(referencia_norm):
                return archivo
        return None

    def _restauraciones_por_fecha(self) -> dict[str, list[tuple[Path, Path]]]:
        carpetas_pendientes = {
            "Mayoristas": self.carpeta_mayoristas,
            "Canjes": self.carpeta_canjes,
            "MercadoLibre": self.carpeta_mercado_libre,
        }
        arch_may, arch_can, arch_ml = self._obtener_archivados()
        archivados_por_categoria = {"Mayoristas": arch_may, "Canjes": arch_can, "MercadoLibre": arch_ml}
        restauraciones: dict[str, dict[Path, Path]] = {}

        for informe in self._obtener_generados():
            if informe.suffix.lower() not in {".xls", ".xlsx"}:
                continue
            coincidencia = re.match(r"^Descuento(\d{2}-\d{2}-\d{4})_", informe.stem)
            if not coincidencia:
                continue
            try:
                fecha = datetime.strptime(coincidencia.group(1), "%d-%m-%Y").date().isoformat()
            except ValueError:
                continue
            for categoria, referencia in self._leer_referencias_informe(informe):
                archivado = self._buscar_archivado(categoria, referencia, archivados_por_categoria[categoria])
                if archivado is not None:
                    restauraciones.setdefault(fecha, {})[archivado] = carpetas_pendientes[categoria] / archivado.name

        return {fecha: list(archivos.items()) for fecha, archivos in restauraciones.items()}

    def fechas_descuento_disponibles(self) -> list[str]:
        """Fechas con documentos archivados asociados a un informe de descuento."""
        return sorted(self._restauraciones_por_fecha(), reverse=True)

    def ver_historial(self) -> None:
        """Imprime el listado cronológico de planillas e informes generados."""
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
        """Restaura desde `descontados/` los archivos asociados a una fecha de descuento."""
        restauraciones = self._restauraciones_por_fecha()
        fechas = sorted(restauraciones, reverse=True)
        if not fechas:
            print("\n[INFO] No hay documentos archivados asociados a informes de descuento.")
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
                fecha_descuento = datetime.strptime(fecha_descuento, "%Y-%m-%d").date().isoformat()
            except ValueError:
                print("\n[ERROR] La fecha de descuento no tiene un formato válido.")
                return 0

        archivos = restauraciones.get(fecha_descuento)
        if not archivos:
            print("\n[ERROR] No hay documentos archivados para esa fecha.")
            return 0

        fecha_legible = datetime.fromisoformat(fecha_descuento).strftime("%d/%m/%Y")
        print(f"\nRestaurando {len(archivos)} documentos descontados el {fecha_legible}...")
        for origen, destino in archivos:
            shutil.copy2(str(origen), str(destino))
            print(f"  * Copiado: {origen.name} -> {destino.parent.name}")

        print("[OK] Documentos restaurados exitosamente.")
        return len(archivos)
