import openpyxl

wb = openpyxl.load_workbook("Descuentos/Productos.xlsx", data_only=True)
ws = wb["Hoja1"]

for r in range(355, ws.max_row + 1):
    vals = [ws.cell(r, c).value for c in range(1, 6)]
    if any(v is not None for v in vals):
        print(f"Row {r}: {vals}")

wb.close()
