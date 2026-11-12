with open('tests/test_client_code_and_order_fields.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the search logic in test_crear_pedido_adjuntar_comprobante_invoca_subir_archivos
old_code = '''        # Buscar el boton de Adjuntar Comprobante
        col_content = dialogo.content.content
        btn_adjuntar = None
        for c in col_content.controls:
            if isinstance(c, ft.Container) and hasattr(c, "content"):
                if isinstance(c.content, ft.Row):
                    for elem in c.content.controls:
                        if isinstance(elem, ft.Button) and "Adjuntar Comprobante" in (elem.content if isinstance(elem.content, str) else getattr(elem.content, "value", "")):
                            btn_adjuntar = elem
                            break'''

new_code = '''        # Buscar el boton de Adjuntar Comprobante
        col_content = dialogo.content.content
        btn_adjuntar = None
        for c in col_content.controls:
            if isinstance(c, ft.Container) and hasattr(c, "content") and isinstance(c.content, ft.Column):
                for row_elem in c.content.controls:
                    if isinstance(row_elem, ft.Row):
                        for elem in row_elem.controls:
                            if isinstance(elem, ft.Button) and "Adjuntar Comprobante" in (elem.content if isinstance(elem.content, str) else getattr(elem.content, "value", "")):
                                btn_adjuntar = elem
                                break'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open('tests/test_client_code_and_order_fields.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Updated search logic")
else:
    print("Old code not found")
