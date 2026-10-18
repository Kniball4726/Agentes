"""
Módulo de Extracción y Verificación de Remitos en PDF.
Lee documentos de remito / nota de pedido, extrae los ítems (código, descripción, cantidad)
y verifica la consistencia matemática contra el campo 'Cant. Articulos'.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from pypdf import PdfReader


@dataclass
class ItemRemito:
    codigo: str
    descripcion: str
    cantidad: int
    origen_remito: str


@dataclass
class ResultadoRemito:
    archivo: str
    numero_remito: str
    fecha: str
    cliente: str
    articulos_declarados: Optional[int]
    articulos_extraidos: int
    verificacion_ok: bool
    items: List[ItemRemito] = field(default_factory=list)


def normalizar_codigo(codigo_raw: str) -> str:
    """Limpia el código de producto removiendo espacios y posibles decimales (.0)."""
    cod = str(codigo_raw).strip()
    if cod.endswith('.0'):
        cod = cod[:-2]
    return cod


def parsear_remito(ruta_pdf: str | Path) -> ResultadoRemito:
    """
    Parsea un remito en formato PDF extrayendo sus metadatos y detalle de artículos.
    """
    path = Path(ruta_pdf)
    reader = PdfReader(str(path))
    
    full_text = ""
    for page in reader.pages:
        full_text += (page.extract_text() or "") + "\n"

    # 1. Extracción de Metadatos
    num_match = re.search(r'(\d{4}-\d{8})', full_text)
    numero_remito = num_match.group(1) if num_match else path.stem

    fecha_match = re.search(r'(\d{2}/\d{2}/\d{4})', full_text)
    fecha = fecha_match.group(1) if fecha_match else "Sin fecha"

    cliente_match = re.search(r'(\d{5}\s+-\s+[A-Z0-9\s\-/]+)', full_text)
    if not cliente_match:
        cliente_match = re.search(r'Cliente:\s*([^\n\r]+)', full_text)
    cliente = cliente_match.group(1).split('\n')[0].strip() if cliente_match else "Cliente no identificado"

    cant_articulos_match = re.search(r'Cant\.\s*Articulos:\s*(\d+)', full_text, re.IGNORECASE)
    declarados = int(cant_articulos_match.group(1)) if cant_articulos_match else None

    # 2. Extracción de Ítems
    lines = full_text.split('\n')
    items_raw = []
    recording = False
    buffer = ""

    for line in lines:
        clean = line.strip()
        # La tabla comienza usualmente tras los encabezados de la distribuidora
        if 'SUPPLEMENTS SRL' in clean or 'Operacion:' in clean:
            recording = True
            continue
        
        # La tabla termina antes de las observaciones o datos de logística
        if recording and any(stop_word in clean for stop_word in ['OBSERVACIONES', 'DATOS LOGISTICA', 'Forma de Pago:']):
            if buffer:
                items_raw.append(buffer)
                buffer = ""
            recording = False
            break

        if recording:
            # Si la línea empieza con un número (código), es un nuevo ítem
            if re.match(r'^\d+\s+', clean):
                if buffer:
                    items_raw.append(buffer)
                buffer = clean
            else:
                # Línea de continuación (descripciones largas que ocupan más de una línea)
                if buffer:
                    buffer += " " + clean

    if buffer:
        items_raw.append(buffer)

    parsed_items: List[ItemRemito] = []
    for raw in items_raw:
        # Formato: <código> <descripción...> <cantidad>
        m = re.match(r'^(\d+)\s+(.*?)\s+(\d+)$', raw)
        if m:
            cod = normalizar_codigo(m.group(1))
            desc = m.group(2).strip()
            qty = int(m.group(3))
            parsed_items.append(ItemRemito(
                codigo=cod,
                descripcion=desc,
                cantidad=qty,
                origen_remito=numero_remito
            ))

    suma_extraida = sum(it.cantidad for it in parsed_items)
    verificacion_ok = (declarados is None) or (suma_extraida == declarados)

    return ResultadoRemito(
        archivo=path.name,
        numero_remito=numero_remito,
        fecha=fecha,
        cliente=cliente,
        articulos_declarados=declarados,
        articulos_extraidos=suma_extraida,
        verificacion_ok=verificacion_ok,
        items=parsed_items
    )
