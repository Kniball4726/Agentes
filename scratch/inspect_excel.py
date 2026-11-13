import openpyxl

wb = openpyxl.load_workbook("Descuentos/Productos.xlsx", data_only=True)
print("Sheet names:", wb.sheetnames)
ws = wb.active
print("Title:", ws.title)
print("Max row:", ws.max_row, "Max col:", ws.max_column)

print("\nFirst 10 rows:")
for r in range(1, 12):
    row_vals = [ws.cell(r, c).value for c in range(1, ws.max_column + 1)]
    print(f"Row {r}: {row_vals}")

wb.close()
