with open('tests/test_flet_gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '        self.assertNotIn("Imprimir Descuento", botones_por_seccion.get("CLIENTES", []))'

new_test = '''
    def test_asegurar_file_picker_overlay_y_parent(self):
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
        self.assertIsNotNone(interfaz.file_picker.page)
'''

if target in content:
    idx = content.find(target) + len(target)
    # Find next newline
    while idx < len(content) and content[idx] in '\r\n':
        idx += 1
    content = content[:idx] + new_test + content[idx:]
    with open('tests/test_flet_gui.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Successfully added test')
else:
    print('Target not found')
