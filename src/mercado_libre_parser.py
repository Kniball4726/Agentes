"""Lee pedidos de Mercado Libre en DOCX y busca coincidencias exactas en el catálogo."""

import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Tuple

from docx import Document

from .remito_parser import ItemRemito, ResultadoRemito


def _normalizar_descripcion(descripcion: str) -> str:
    texto = unicodedata.normalize("NFKD", descripcion.casefold())
    texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
    return " ".join(re.sub(r"[^\w]+", " ", texto).split())


def _buscar_codigo(
    descripcion: str,
    descripciones_catalogo: Dict[str, List[str]]
) -> Tuple[str | None, str]:
    codigos = descripciones_catalogo.get(_normalizar_descripcion(descripcion), [])
    if len(codigos) == 1:
        return codigos[0], ""
    if codigos:
        return None, "Descripción coincidente con más de un código del catálogo"
    return None, "No se encontró una coincidencia exacta en el catálogo"


def parsear_pedido_mercado_libre(
    ruta_docx: str | Path,
    productos_catalogo: List[Tuple[str, str]]
) -> ResultadoRemito:
    """Cada párrafo no vacío y cada fila de tabla representan una unidad."""
    path = Path(ruta_docx)
    documento = Document(str(path))
    descripciones_catalogo: Dict[str, List[str]] = {}
    for codigo, nombre in productos_catalogo:
        clave = _normalizar_descripcion(nombre)
        if clave:
            codigos = descripciones_catalogo.setdefault(clave, [])
            if codigo not in codigos:
                codigos.append(codigo)

    registros: List[Tuple[str, List[str]]] = [
        (parrafo.text.strip(), [])
        for parrafo in documento.paragraphs
        if parrafo.text.strip()
    ]
    for tabla in documento.tables:
        for fila in tabla.rows:
            celdas = [celda.text.strip() for celda in fila.cells if celda.text.strip()]
            if celdas:
                registros.append((" ".join(celdas), celdas))

    items: List[ItemRemito] = []
    sin_coincidencia: List[Tuple[str, str]] = []
    for descripcion, celdas in registros:
        resultados_celdas = [
            _buscar_codigo(celda, descripciones_catalogo)
            for celda in celdas
        ]
        codigos_en_fila = {codigo for codigo, _ in resultados_celdas if codigo is not None}
        ambiguas_en_fila = [
            motivo
            for codigo, motivo in resultados_celdas
            if codigo is None and "más de un código" in motivo
        ]

        if len(codigos_en_fila) > 1 or ambiguas_en_fila:
            codigo = None
            motivo = (
                "La fila contiene descripciones ambiguas"
                if ambiguas_en_fila
                else "La fila contiene descripciones coincidentes con varios productos"
            )
        elif len(codigos_en_fila) == 1:
            codigo = next(iter(codigos_en_fila))
            motivo = ""
        else:
            codigo, motivo = _buscar_codigo(descripcion, descripciones_catalogo)

        if codigo is None:
            sin_coincidencia.append((descripcion, motivo))
            continue

        items.append(ItemRemito(
            codigo=codigo,
            descripcion=descripcion,
            cantidad=1,
            origen_remito=f"ML-{path.stem}"
        ))

    total_registros = len(registros)
    return ResultadoRemito(
        archivo=path.name,
        numero_remito=f"ML-{path.stem}",
        fecha="Mercado Libre",
        cliente="Mercado Libre",
        articulos_declarados=total_registros,
        articulos_extraidos=len(items),
        verificacion_ok=not sin_coincidencia,
        items=items,
        descripciones_sin_coincidencia=sin_coincidencia
    )
