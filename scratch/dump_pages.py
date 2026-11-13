import pypdf

reader = pypdf.PdfReader("Documentacion/ListadoProductos2.pdf")

print("--- PAGE 1 DUMP ---")
print(reader.pages[0].extract_text())

print("\n--- PAGE 37 DUMP ---")
print(reader.pages[36].extract_text()[:1500])

print("\n--- PAGE 45 DUMP ---")
print(reader.pages[44].extract_text()[:1500])
