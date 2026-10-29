"""
Módulo de Extracción y Verificación de Remitos en PDF.
Lee documentos de remito / nota de pedido, extrae los ítems (código, descripción, cantidad)
y verifica la consistencia matemática contra el campo 'Cant. Articulos'.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple
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
    descripciones_sin_coincidencia: List[Tuple[str, str]] = field(default_factory=list)
    discrepancia: bool = False
    codigo_cliente: str = ""
    direccion: str = ""
    fecha_despacho: str = ""


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

    # Fecha de Despacho (prioritaria para fecha de retiro)
    fd_match = re.search(r'fecha\s*despacho[:\s]*(\d{2}/\d{2}/\d{4})', full_text, re.IGNORECASE)
    if not fd_match:
        fd_match = re.search(r'(\d{2}/\d{2}/\d{4})\s*fecha\s*despacho', full_text, re.IGNORECASE)
    fecha_despacho = fd_match.group(1) if fd_match else ""

    # Separación de Código de Cliente y Nombre Limpio
    codigo_cliente = ""
    cliente = "Cliente no identificado"
    c_match = re.search(r'(\d{4,6})\s+-\s+([A-Z0-9\s\-/]+)', full_text)
    if c_match:
        codigo_cliente = c_match.group(1).strip()
        cliente = c_match.group(2).split('\n')[0].strip()
    else:
        c_label = re.search(r'Cliente:\s*([^\n\r]+)', full_text)
        if c_label:
            val = c_label.group(1).strip()
            m_sep = re.match(r'^(\d{4,6})\s+-\s+(.+)$', val)
            if m_sep:
                codigo_cliente = m_sep.group(1).strip()
                cliente = m_sep.group(2).strip()
            else:
                cliente = val

    # Extracción de Dirección para futuras integraciones (ej: Google Maps API)
    lines = [l.strip() for l in full_text.split('\n')]
    loc = ""
    prov = ""
    for l in lines:
        if 'localidad:' in l.lower():
            m_loc = re.search(r'(.*?)\s*Localidad:\s*(.*)', l, re.IGNORECASE)
            if m_loc:
                prov = m_loc.group(1).strip()
                loc = m_loc.group(2).strip()
            break

    calle = ""
    idx_centro = -1
    for i, l in enumerate(lines):
        if l in ('CENTRO DE DISTRIBUCION', 'SUPPLEMENTS SRL'):
            idx_centro = i
            break

    if idx_centro > 0:
        candidata = lines[idx_centro - 1]
        if candidata not in ('Marca', 'Operacion:', 'Operacion: 1-VENTAS A PREPARAR') and not re.match(r'^\d{4,6}\s*-', candidata):
            calle = candidata

    if not calle:
        m_dir = re.search(r'(?:Domicilio|Direcci[oó]n):\s*([^\n\r]+)', full_text, re.IGNORECASE)
        if m_dir and not any(k in m_dir.group(1).lower() for k in ['transporte', 'condici']):
            calle = m_dir.group(1).strip()

    direccion = ""
    if calle:
        if any(k in calle.lower() for k in ['loc.', 'localidad', 'prov.']):
            direccion = calle
        else:
            partes = [calle]
            if loc and loc.lower() not in calle.lower():
                partes.append(loc)
            if prov and prov.lower() not in calle.lower() and 'buenos aires' not in [p.lower() for p in partes]:
                partes.append(prov)
            direccion = ', '.join(partes)

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

        if recording and re.fullmatch(
            r'P.gina\s+\d+\s+de\s+\d+', clean, re.IGNORECASE
        ):
            if buffer:
                items_raw.append(buffer)
                buffer = ""
            recording = False
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
        items=parsed_items,
        codigo_cliente=codigo_cliente,
        direccion=direccion,
        fecha_despacho=fecha_despacho,
    )
