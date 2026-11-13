import openpyxl

wb = openpyxl.load_workbook("Descuentos/Productos.xlsx", data_only=True)
ws = wb["Hoja1"]

print(f"Max row: {ws.max_row}, Max col: {ws.max_column}")

# Print rows that have headers or section titles (column A is None or not int/code, or col B is bold/title)
for r in range(1, ws.max_row + 1):
    val_a = ws.cell(r, 1).value
    val_b = ws.cell(r, 2).value
    val_c = ws.cell(r, 3).value
    val_d = ws.cell(r, 4).value
    val_e = ws.cell(r, 5).value
    # Section header check: val_a is None or val_b has title
    if val_a is None and val_b is not None:
        print(f"Row {r}: Section Header -> B='{val_b}', C='{val_c}', D='{val_d}', E='{val_e}'")
    elif r <= 5:
        print(f"Row {r}: A='{val_a}', B='{val_b}', C='{val_c}', D='{val_d}', E='{val_e}'")

wb.close()
