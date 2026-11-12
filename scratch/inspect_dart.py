with open(r'C:\Users\user\Desktop\Software\DescuentoAgentico\Agentes\.venv\Lib\site-packages\flet_web\web\main.dart.js', encoding='utf-8', errors='ignore') as f:
    text = f.read()

# Let's search where FilePicker or "file_picker" is in main.dart.js
import re
matches = [m.start() for m in re.finditer(r'FilePicker|file_picker', text, re.IGNORECASE)]
print("Total matches:", len(matches))
for m in matches[:10]:
    start = max(0, m - 100)
    end = min(len(text), m + 150)
    print("--- MATCH ---")
    print(text[start:end])
