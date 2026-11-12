with open('tests/test_flet_gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_test = '''    def test_asegurar_file_picker_overlay_y_parent(self):
        """Verifica que _asegurar_file_picker mantenga el file_picker en overlay y con parent valido para evitar RuntimeError."""
        interfaz, _, page = self.crear_interfaz()
        interfaz._asegurar_file_picker()

        self.assertIn(interfaz.file_picker, page.overlay)
        self.assertIsNotNone(interfaz.file_picker.page)

        # Simular limpieza de overlay al recargar dashboard
        page.overlay.clear()
        self.assertNotIn(interfaz.file_picker, page.overlay)

        # Re-asegurar debe volver a incluirlo en overlay y mantener page funcional
        interfaz._asegurar_file_picker()
        self.assertIn(interfaz.file_picker, page.overlay)
        self.assertIsNotNone(interfaz.file_picker.page)'''

new_test = '''    def test_asegurar_file_picker_overlay_y_parent(self):
        """Verifica que _asegurar_file_picker mantenga el file_picker en overlay y con parent valido para evitar RuntimeError."""
        interfaz, _, page = self.crear_interfaz()
        interfaz._asegurar_file_picker()

        self.assertIn(interfaz.file_picker, page.overlay)

        # Simular limpieza de overlay al recargar dashboard
        page.overlay.clear()
        self.assertNotIn(interfaz.file_picker, page.overlay)

        # Re-asegurar debe volver a incluirlo en overlay
        interfaz._asegurar_file_picker()
        self.assertIn(interfaz.file_picker, page.overlay)

        # Verificar resolucion correcta de file_picker.page con instancia real de Page (Flet 1.0)
        import weakref
        from flet.controls.base_page import Overlay
        from flet.controls.core.view import View
        page_real = ft.Page.__new__(ft.Page)
        page_real.views = [View()]
        page_real._overlay = Overlay()
        page_real._overlay._parent = weakref.ref(page_real)
        interfaz.page = page_real
        interfaz._asegurar_file_picker()
        self.assertIn(interfaz.file_picker, page_real.overlay)
        self.assertIs(interfaz.file_picker.page, page_real)'''

if old_test in content:
    content = content.replace(old_test, new_test)
    with open('tests/test_flet_gui.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced test successfully")
else:
    print("Old test not found")
