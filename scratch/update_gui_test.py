with open('tests/test_flet_gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

idx_start = content.find('def test_asegurar_file_picker_overlay_y_parent(')
idx_end = content.find('if __name__ == "__main__":')

new_test = '''def test_asegurar_file_picker_overlay_y_parent(self):
        """Verifica que _asegurar_file_picker mantenga el file_picker fuera de overlay (evita 'Unknown control: FilePicker') y con parent valido."""
        interfaz, _, page = self.crear_interfaz()
        # Simular que estaba en overlay por error
        page.overlay.append(interfaz.file_picker)

        interfaz._asegurar_file_picker()

        # No debe estar en overlay porque FilePicker es un Servicio en Flet 1.0 (evita panel rojo de error)
        self.assertNotIn(interfaz.file_picker, page.overlay)

        # Verificar resolucion correcta de file_picker.page y registro en services con Page real de Flet 1.0
        import weakref
        from flet.controls.base_page import Overlay
        from flet.controls.core.view import View
        page_real = ft.Page.__new__(ft.Page)
        page_real.views = [View()]
        page_real._overlay = Overlay()
        page_real._overlay._parent = weakref.ref(page_real)
        interfaz.page = page_real
        interfaz._asegurar_file_picker()
        self.assertNotIn(interfaz.file_picker, page_real.overlay)
        self.assertIn(interfaz.file_picker, page_real.services)
        self.assertIs(interfaz.file_picker.page, page_real)

'''

if idx_start != -1 and idx_end != -1:
    content = content[:idx_start] + new_test + content[idx_end:]
    with open('tests/test_flet_gui.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Updated test_asegurar_file_picker_overlay_y_parent")
else:
    print("Index not found:", idx_start, idx_end)
