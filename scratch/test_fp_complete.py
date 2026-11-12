import flet as ft
from flet.controls.page import Page, ServiceRegistry
from flet.controls.core.view import View
from flet.controls.base_page import Overlay
import weakref

page = Page.__new__(Page)
page.views = [View()]
page._overlay = Overlay()
page._overlay._parent = weakref.ref(page)
page._services = ServiceRegistry()

fp = ft.FilePicker()
# Simulate it was previously in overlay:
page.overlay.append(fp)

# Run new _asegurar_file_picker logic:
if hasattr(page, "overlay") and page.overlay is not None:
    while fp in page.overlay:
        page.overlay.remove(fp)

if hasattr(page, "services") and page.services is not None:
    if fp not in page.services:
        page.services.append(fp)

reg = getattr(page, "_services", None)
if type(reg).__name__ == "ServiceRegistry":
    if getattr(reg, "parent", None) is None:
        try:
            reg._parent = weakref.ref(page)
        except Exception:
            pass
    if hasattr(reg, "_services") and fp not in reg._services:
        try:
            reg.register_service(fp)
        except Exception:
            pass

fp._parent = weakref.ref(page)

print("1. Is fp in overlay?", fp in page.overlay)
print("2. Is fp.page resolving to page?", fp.page is page)
print("3. Is fp in page.services?", fp in page.services)
print("4. Is fp in reg._services?", fp in page._services._services)
print("5. Overlay controls count:", len(page.overlay))
