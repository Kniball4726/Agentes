import flet as ft
from flet.controls.page import Page, ServiceRegistry
import inspect

with open(r'C:\Users\user\Desktop\Software\DescuentoAgentico\Agentes\.venv\Lib\site-packages\flet\controls\page.py', encoding='utf-8') as f:
    text = f.read()

# Let's inspect ServiceRegistry in page.py
idx = text.find('class ServiceRegistry')
print(text[idx:idx+2000])
