import openpyxl
from src.inventory import StockManager

sm = StockManager("Descuentos/Productos.xlsx")
wb = openpyxl.load_workbook("Descuentos/Productos.xlsx", data_only=True)
ws = wb["Hoja1"]

print("fila_inicio_datos:", sm._fila_inicio_datos)
print("col_codigo:", sm._col_codigo)
print("col_nombre:", sm._col_nombre)
print("col_stock:", sm._col_stock)

# Check some codes
for cod in ["2156", "28", "2768"]:
    filas = sm._filas_por_codigo.get(cod)
    cat = sm.catalogo.get(cod)
    print(f"Code {cod}: in sm._filas_por_codigo = {filas}, in sm.catalogo = {cat}")
    for f in filas or []:
        val_a = ws.cell(f, sm._col_codigo).value
        val_b = ws.cell(f, sm._col_nombre).value
        print(f"  Excel row {f}: A='{val_a}', B='{val_b}'")

# Check if there are discrepancies between sm._filas_por_codigo and actual row in Excel
discrepancies = 0
for cod, filas in sm._filas_por_codigo.items():
    for f in filas:
        cell_val = str(ws.cell(f, sm._col_codigo).value or "").strip()
        if cell_val.endswith(".0"):
            cell_val = cell_val[:-2]
        if cell_val != cod:
            discrepancies += 1
            if discrepancies <= 5:
                print(f"Discrepancy for code {cod}: Excel row {f} has '{cell_val}'")

print(f"Total discrepancies: {discrepancies}")
wb.close()
