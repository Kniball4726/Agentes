import pypdf

reader = pypdf.PdfReader("Documentacion/ListadoProductos2.pdf")

for i, page in enumerate(reader.pages):
    text = page.extract_text() or ""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    # Check headers or occurrences of brand names
    for line in lines[:5]: # look at the top lines
        if "TECH" in line.upper():
            print(f"Page {i+1} top: {line}")
    # Also search for standalone ULTRA TECH or VITATECH
    for line in lines:
        if line.strip() in ["ULTRA TECH", "VITATECH"]:
            print(f"Page {i+1} header match: '{line}'")
