"""Test unitario para verificar que al imprimir rótulos de un pedido de N bultos
se generen exactamente N etiquetas sin repetir hasta llenar la hoja A4.
"""
from pathlib import Path
import pypdf

from src.label_generator import generar_etiquetas_bultos_pdf
from src.orders_store import Pedido


def test_etiquetas_exactas_sin_repeticion(tmp_path: Path):
    """Verifica que un pedido de 2 bultos genere exactamente 2 etiquetas (1 de 2 y 2 de 2)."""
    p2 = Pedido(
        id=55,
        nota_pedido="REM-DOS-BULTOS",
        numero_pedido="5",
        cliente="Comercial Dos",
        bultos=2,
        logistica="Domicilio",
        armador="Lucas",
        tipo_archivo="pdf",
        nombre_archivo="doc.pdf",
        agregado=False,
        articulos_descontados=10,
        resumen_items="10 un.",
        created_at="2026-10-30 12:00:00",
        estado="descontado",
    )
    pdf = generar_etiquetas_bultos_pdf(p2, tmp_path)
    reader = pypdf.PdfReader(str(pdf))
    assert len(reader.pages) == 1
    texto = reader.pages[0].extract_text()

    # Debe contener exactamente una vez "BULTO 1 DE 2" y una vez "BULTO 2 DE 2"
    assert texto.count("BULTO 1 DE 2") == 1
    assert texto.count("BULTO 2 DE 2") == 1
