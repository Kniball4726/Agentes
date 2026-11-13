import pypdf

reader = pypdf.PdfReader("Documentacion/ListadoProductos2.pdf")

for i, page in enumerate(reader.pages):
    text = page.extract_text() or ""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    # On page 1 there is header info, then brand name. On later pages, the top line is often the brand name.
    header = lines[0] if lines else ""
    print(f"Page {i+1}: First line = '{header}' | Second line = '{lines[1] if len(lines)>1 else ''}'")
