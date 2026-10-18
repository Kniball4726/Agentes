# Agente de control de stock y remitos

Aplicación de escritorio en Python que procesa remitos mayoristas en PDF y solicitudes de canje en Excel, consolida las cantidades por código de producto y genera un informe de descuentos. En la operación normal utiliza un catálogo local (`Productos.xlsx`) como fuente de stock.

## Funcionalidades

- Extrae productos de remitos PDF y planillas de canje `.xlsx`.
- Suma los productos repetidos entre documentos según su código.
- Compara el total de unidades extraídas de un remito con el total declarado y muestra el resultado de la verificación.
- Genera una planilla con stock inicial, descuento y stock final, además de un resumen de los pedidos procesados.
- Señala en el informe los productos que no aparecen en el catálogo.
- En ejecuciones reales, actualiza el stock del catálogo y archiva los documentos procesados.
- Incluye ejecución interactiva y modo de simulación.
- Protege con credenciales administrativas la opción para agregar productos al catálogo.

## Requisitos

- Python 3.10 o posterior.
- `pip`.
- Microsoft Excel o una aplicación compatible para revisar los archivos `.xlsx`.
- El catálogo `Descuentos/Productos.xlsx`.

Las dependencias de Python están listadas en [`requirements.txt`](requirements.txt). `gspread` y `google-auth` están incluidas para la integración de Google Sheets; el flujo normal del menú usa el catálogo local de Excel.

## Instalación y configuración

Desde la carpeta del proyecto, en Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

La cuenta de administrador se configura en un archivo `.env` en la raíz del proyecto:

```dotenv
_ADMIN_USUARIO=tu_usuario
_ADMIN_CLAVE=tu_contraseña
```

Estas variables se utilizan para la opción **Agregar producto al catálogo**. Si no están definidas, esa opción deniega el acceso y muestra un aviso. El archivo `.env` está excluido de Git; no agregues credenciales reales al repositorio ni las compartas.

## Preparar los archivos de trabajo

El menú crea las carpetas de entrada y salida necesarias si no existen. Coloca los documentos pendientes en:

| Carpeta | Archivos admitidos |
| --- | --- |
| `Descuentos/Mayoristas/` | Remitos `.pdf` |
| `Descuentos/Canjes/` | Canjes `.xlsx` |

El catálogo se encuentra en `Descuentos/Productos.xlsx`. El gestor busca los productos desde la fila 3, leyendo el código de la columna A, la descripción de la B y el stock de la C. Usa la hoja llamada `Stock` cuando existe; si no, utiliza la hoja activa.

Para los canjes, el lector busca encabezados `PEDIDO` y `CODIGO` en las primeras 14 filas y espera la descripción en la columna siguiente a `CODIGO`. Para los remitos, el PDF debe contener texto extraíble con el formato que reconoce el parser; los PDF escaneados como imagen pueden requerir OCR, que no está implementado.

## Ejecución

### Menú interactivo

```powershell
python main.py
```

Opciones disponibles:

1. Procesar remitos y canjes pendientes.
2. Simular el procesamiento sin guardar cambios ni mover documentos.
3. Procesar solo remitos mayoristas.
4. Procesar solo canjes.
5. Consultar el historial de planillas generadas.
6. Copiar archivos archivados de vuelta a las carpetas de entrada para pruebas.
7. Agregar un producto al catálogo (requiere las credenciales del `.env`).
0. Salir.

También puedes iniciar el menú con `ejecutar.bat`.

### Ejecución automática

Procesa todos los archivos pendientes de ambas carpetas sin abrir el menú:

```powershell
python main.py --auto
```

`--all` es un alias de `--auto`.

### Simulación desde la línea de comandos

```powershell
python main.py --dry-run
```

`--simulacion` es un alias de `--dry-run`. La simulación calcula y muestra el informe, pero no guarda la planilla, no actualiza `Productos.xlsx` y no mueve los documentos.

## Flujo y archivos generados

En una ejecución real, el agente:

1. Lee los documentos seleccionados de las carpetas de entrada.
2. Extrae sus metadatos e ítems y muestra el resultado de las verificaciones.
3. Consolida las cantidades por código de producto.
4. Genera `Descuentos/descuentos/DescuentoDD-MM-AAAA.xlsx`, con las columnas `CÓDIGO`, `PRODUCTOS`, `STOCK INICIAL`, `DESCUENTO` y `STOCK FINAL`.
5. Actualiza la columna C del catálogo con el stock final de los productos existentes que tuvieron descuentos y actualiza `Productos_backup.xlsx`.
6. Mueve los PDF procesados a `Descuentos/descontados/Mayoristas/` y los Excel a `Descuentos/descontados/Canjes/`.

En el informe, el descuento aparece como un número negativo. Los productos que no están en el catálogo se agregan al final de la planilla generada con una indicación; no se incorporan automáticamente a `Productos.xlsx`.

La planilla de salida usa la fecha del día en su nombre. Si se vuelve a ejecutar un procesamiento el mismo día, se genera el mismo nombre de archivo; conserva o respalda el informe anterior antes de repetir una corrida si necesitas mantener ambas versiones.

## Consideraciones operativas

- La simulación es la opción recomendada para revisar los cálculos antes de una ejecución real.
- Una discrepancia entre artículos declarados y extraídos se informa en consola, pero no detiene por sí sola el procesamiento. Revisa el documento y el informe antes de continuar con una corrida real.
- La ejecución real modifica el catálogo y mueve los documentos; mantén copias de seguridad antes de procesar datos importantes.
- El modo de restauración copia los documentos archivados a las carpetas pendientes; no los elimina del archivo.
- La autenticación administrativa usa las variables locales de `.env`; este mecanismo no debe considerarse una solución de autenticación para una aplicación expuesta a usuarios remotos.

## Módulos principales

| Archivo | Responsabilidad |
| --- | --- |
| [`main.py`](main.py) | Punto de entrada y selección del modo de ejecución. |
| [`menu.py`](menu.py) | Menú interactivo, rutas de trabajo, autenticación y archivado. |
| [`agent.py`](agent.py) | Orquesta la lectura, consolidación y aplicación de descuentos. |
| [`remito_parser.py`](remito_parser.py) | Extracción de ítems y metadatos de PDF. |
| [`canjes_parser.py`](canjes_parser.py) | Extracción de ítems y metadatos de canjes Excel. |
| [`consolidator.py`](consolidator.py) | Agrupación y suma de ítems por código. |
| [`stock_manager.py`](stock_manager.py) | Lectura y actualización del catálogo Excel y creación del informe. |
| [`sheets_manager.py`](sheets_manager.py) | Módulo de gestión de stock con Google Sheets, separado del flujo local del menú. |
