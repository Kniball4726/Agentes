import pypdf
import re

pdf_path = "Documentacion/ListadoProductos2.pdf"
reader = pypdf.PdfReader(pdf_path)
print(f"Total pages: {len(reader.pages)}")

# Print sample text from first page
first_page_text = reader.pages[0].extract_text()
print("--- First Page Sample ---")
print(first_page_text[:1000])

# Search for Ultra Tech / Vitatech across pages
matches = []
for idx, page in enumerate(reader.pages):
    text = page.extract_text() or ""
    lines = text.split("\n")
    for line in lines:
        if re.search(r"ultra\s*tech|vitatech", line, re.IGNORECASE):
            matches.append((idx + 1, line))

print(f"\nTotal matches found: {len(matches)}")
for page_num, line in matches[:30]:
    print(f"P.{page_num}: {line}")

if len(matches) > 30:
    print(f"... and {len(matches) - 30} more")
