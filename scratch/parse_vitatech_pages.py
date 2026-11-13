import pypdf

reader = pypdf.PdfReader("Documentacion/ListadoProductos2.pdf")

for pno in range(44, 47): # 45 to 47 (0-indexed 44 to 46)
    text = reader.pages[pno].extract_text()
    print(f"=== Page {pno+1} ===")
    lines = text.split("\n")
    for l in lines:
        print(l)
