"""Test unitario para verificar que al imprimir rótulos de un pedido de N bultos
se generen exactamente N etiquetas sin repetir hasta llenar la hoja A4.
"""
from pathlib import Path
import pypdf

from src.labels import generar_etiquetas_bultos_pdf
from src.orders import Pedido


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


def test_etiquetas_agregado_concatena_nombre_cliente(tmp_path: Path):
    """Verifica que si el pedido es un agregado se concatene 'Agregado' al nombre del cliente."""
    from src.labels import generar_etiquetas_termicas_pdf

    # 1. Pedido normal (no agregado)
    p_normal = Pedido(
        id=60,
        nota_pedido="REM-100",
        numero_pedido="55",
        cliente="Distribuidora Norte",
        bultos=1,
        logistica="Expreso",
        armador="Lucas",
        tipo_archivo="pdf",
        nombre_archivo="doc.pdf",
        agregado=False,
        articulos_descontados=5,
        resumen_items="5 un.",
        created_at="2026-10-30 12:00:00",
        estado="descontado",
    )
    pdf_normal_a4 = generar_etiquetas_bultos_pdf(p_normal, tmp_path)
    texto_a4_norm = pypdf.PdfReader(str(pdf_normal_a4)).pages[0].extract_text()
    assert "Distribuidora Norte" in texto_a4_norm
    assert "Agregado" not in texto_a4_norm

    # 2. Pedido agregado (debe concatenar 'Agregado')
    p_agregado = Pedido(
        id=61,
        nota_pedido="REM-101",
        numero_pedido="88",
        cliente="Ferretería San Martín",
        bultos=1,
        logistica="Expreso",
        armador="Lucas",
        tipo_archivo="pdf",
        nombre_archivo="doc.pdf",
        agregado=True,
        articulos_descontados=2,
        resumen_items="2 un.",
        created_at="2026-10-30 12:00:00",
        estado="descontado",
    )
    pdf_a4_agregado = generar_etiquetas_bultos_pdf(p_agregado, tmp_path)
    texto_a4_agr = pypdf.PdfReader(str(pdf_a4_agregado)).pages[0].extract_text()
    texto_a4_agr_unido = " ".join(texto_a4_agr.split())
    assert "Ferretería San Martín Agregado" in texto_a4_agr_unido
    assert "Nro 88" in texto_a4_agr_unido

    # 3. Rótulo térmico también debe concatenar 'Agregado'
    pdf_term_agregado = generar_etiquetas_termicas_pdf(p_agregado, tmp_path)
    texto_term = pypdf.PdfReader(str(pdf_term_agregado)).pages[0].extract_text()
    assert "Ferretería San Martín Agregado" in texto_term

    # 4. No debe duplicar si el cliente ya contiene la palabra 'Agregado'
    p_ya_agregado = Pedido(
        id=62,
        nota_pedido="REM-102",
        numero_pedido="",
        cliente="Ferretería San Martín Agregado",
        bultos=1,
        logistica="Expreso",
        armador="Lucas",
        tipo_archivo="pdf",
        nombre_archivo="doc.pdf",
        agregado=True,
        articulos_descontados=2,
        resumen_items="2 un.",
        created_at="2026-10-30 12:00:00",
        estado="descontado",
    )
    pdf_ya_agr = generar_etiquetas_bultos_pdf(p_ya_agregado, tmp_path)
    texto_ya_agr = pypdf.PdfReader(str(pdf_ya_agr)).pages[0].extract_text()
    texto_ya_agr_unido = " ".join(texto_ya_agr.split())
    assert "Ferretería San Martín Agregado" in texto_ya_agr_unido
    assert "Agregado Agregado" not in texto_ya_agr_unido
