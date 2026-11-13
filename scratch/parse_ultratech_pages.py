import pypdf
import re

reader = pypdf.PdfReader("Documentacion/ListadoProductos2.pdf")

# Let's inspect how the PDF text flows from page to page.
# Specifically, let's track the current section brand.
brands_pages = {}
current_brand = None

# Regex to match a product line: Code + Name + Stock
# Looking at sample:
# "119 3 EN 1 FAT BURNER SYSTEM 0,000"
# "2735 CHRISTMAS PROTEIN BAR SABOR ... CAJA X 12 UNIDADES87,000" or with spaces before stock
# Stock ends with comma and 3 decimals (e.g. 0,000 or -7,000 or 87,000 or 122,000 or -96,00)
# Notice some might have 2 or 3 decimals, or negative signs.

# Let's see all lines on pages 37 to 42 (Ultra Tech) and 45 to 47 (Vitatech)
for pno in range(36, 42): # 37 to 42 (0-indexed 36 to 41)
    text = reader.pages[pno].extract_text()
    print(f"=== Page {pno+1} ===")
    lines = text.split("\n")
    for l in lines:
        print(l)
