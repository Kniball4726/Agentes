import csv

def read_csv(path):
    data = {}
    try:
        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row.get("Codigo", "").strip()
                if code:
                    data[code] = row
    except Exception as e:
        print("Error reading", path, e)
    return data

inv_import = read_csv("data/inventario_import.csv")
bar_import = read_csv("data/codigos_barras_import.csv")

print(f"Total in inventario_import.csv: {len(inv_import)}")
print(f"Total in codigos_barras_import.csv: {len(bar_import)}")

# Check for some missing codes
for c in ["330", "366", "113", "2253"]:
    if c in inv_import:
        print(f"Code {c} in inv_import:", inv_import[c])
    if c in bar_import:
        print(f"Code {c} in bar_import:", bar_import[c])
