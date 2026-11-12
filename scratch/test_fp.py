import sys
sys.path.insert(0, ".")
import flet as ft
from src.flet_gui import InterfazFlet
import weakref

page_real = ft.Page.__new__(ft.Page)
from flet.controls.base_page import Overlay
from flet.controls.core.view import View
page_real.views = [View()]
page_real._overlay = Overlay()
page_real._overlay._parent = weakref.ref(page_real)

fp = ft.FilePicker()
# Fake interfaz with page_real
class Dummy:
    pass
d = Dummy()
d.page = page_real
d.file_picker = fp
InterfazFlet._asegurar_file_picker(d)

print("In overlay:", fp in page_real.overlay)
print("fp.page is page_real:", fp.page is page_real)
