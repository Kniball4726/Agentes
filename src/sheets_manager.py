"""
Módulo de Gestión de Stock en Google Sheets.
Permite conectar el Agente a una hoja de cálculo en la nube (Google Sheets)
utilizando la biblioteca gspread y una cuenta de servicio de Google Cloud.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from .consolidator import ItemConsolidado
from .remito_parser import normalizar_codigo
from .stock_manager import AlertaStock, RegistroDescuento, ReporteStock

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_INSTALADO = True
except ImportError:
    GSPREAD_INSTALADO = False


class GoogleSheetsStockManager:
    """
    Administrador de Stock conectado directamente a Google Sheets.
    Implementa la misma interfaz que StockManager local, permitiendo
    intercambiar Excel por Google Sheets sin modificar la lógica del agente.
    """
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    def __init__(self, spreadsheet_url_o_nombre: str, credenciales_json: str | Path, hoja: str = "Stock"):
        if not GSPREAD_INSTALADO:
            raise ImportError(
                "Para usar Google Sheets debes instalar las dependencias: pip install gspread google-auth"
            )

        self.credenciales_path = Path(credenciales_json)
        if not self.credenciales_path.exists():
            raise FileNotFoundError(
                f"No se encontró el archivo de credenciales de Google: {self.credenciales_path}\n"
                "Asegúrate de colocar tu archivo .json descargado de Google Cloud Console."
            )

        self.spreadsheet_ref = spreadsheet_url_o_nombre
        self.nombre_hoja = hoja
        
        # Conexión con Google Sheets
        self.creds = Credentials.from_service_account_file(str(self.credenciales_path), scopes=self.SCOPES)
        self.client = gspread.authorize(self.creds)

        if spreadsheet_url_o_nombre.startswith("http"):
            self.sheet_doc = self.client.open_by_url(spreadsheet_url_o_nombre)
        else:
            self.sheet_doc = self.client.open(spreadsheet_url_o_nombre)

        self.worksheet = self.sheet_doc.worksheet(self.nombre_hoja)
        self.catalogo: Dict[str, Tuple[int, str, int]] = {}
        self._cargar_catalogo()

    def _cargar_catalogo(self):
        """Descarga los valores de la hoja y construye el mapa de códigos en memoria."""
        # Obtenemos todos los valores como matriz para minimizar llamadas a la API (cuota)
        filas = self.worksheet.get_all_values()
        self.catalogo.clear()

        # Fila 1 son encabezados, fila 2 vacía, fila 3 en adelante son productos (índice 0-based: i >= 2)
        for i, fila in enumerate(filas):
            if i < 2:
                continue
            
            fila_sheet = i + 1  # Google Sheets es 1-based
            val_cod = fila[0] if len(fila) > 0 else ""
            nombre = fila[1] if len(fila) > 1 else ""
            val_stock = fila[2] if len(fila) > 2 else "0"

            if val_cod.strip():
                cod = normalizar_codigo(val_cod)
                try:
                    stock_num = int(round(float(val_stock.replace(",", ".")))) if val_stock.strip() else 0
                except ValueError:
                    stock_num = 0

                self.catalogo[cod] = (fila_sheet, nombre.strip(), stock_num)

    def aplicar_descuentos(self, items_consolidados: Dict[str, ItemConsolidado], **kwargs) -> ReporteStock:
        """
        Aplica los descuentos en Google Sheets usando actualización por lote (batch_update)
        para ser rápido y no superar los límites de cuota de la API.
        """
        descuentos: List[RegistroDescuento] = []
        alertas: List[AlertaStock] = []
        celdas_a_actualizar = []

        for cod, item in items_consolidados.items():
            if cod in self.catalogo:
                fila_idx, nombre, stock_ant = self.catalogo[cod]
                nuevo_stock = int(stock_ant - item.cantidad_total)

                # En Google Sheets la columna C es la columna 3 (guardamos como número entero)
                celdas_a_actualizar.append(gspread.Cell(row=fila_idx, col=3, value=nuevo_stock))
                self.catalogo[cod] = (fila_idx, nombre, nuevo_stock)

                descuentos.append(RegistroDescuento(
                    codigo=cod,
                    nombre_producto=nombre,
                    fila_excel=fila_idx,
                    stock_anterior=int(stock_ant),
                    cantidad_descontada=item.cantidad_total,
                    stock_nuevo=nuevo_stock
                ))
            else:
                alertas.append(AlertaStock(
                    codigo=cod,
                    descripcion=item.descripcion,
                    cantidad=item.cantidad_total,
                    motivo="No encontrado en Google Sheets / Merchandising"
                ))

        # Actualización eficiente en una sola llamada de red
        if celdas_a_actualizar:
            self.worksheet.update_cells(celdas_a_actualizar)

        return ReporteStock(
            descuentos_aplicados=descuentos,
            alertas=alertas,
            archivo_guardado=f"Google Sheets: {self.sheet_doc.title} ({self.worksheet.title})"
        )
