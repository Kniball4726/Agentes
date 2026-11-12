import flet as ft
from flet.controls.page import Page, ServiceRegistry
import weakref

page = Page.__new__(Page)
sr = ServiceRegistry()
sr._parent = weakref.ref(page)
page._services = sr

fp = ft.FilePicker()
sr.register_service(fp)
print("Registered services count:", len(sr._services))
print("fp in sr._services:", fp in sr._services)
print("sr.parent is page:", sr.parent is page)
