# Agente de control de stock y remitos

Aplicación de escritorio para procesar remitos mayoristas en PDF y solicitudes de canje en Excel, consolidar cantidades por código de producto y generar informes de descuentos. El flujo operativo utiliza un catálogo local de Excel como fuente de stock.

> **Plataforma principal:** Windows · **Lenguaje:** Python 3.10+

## Contenido

- [Funciones](#funciones)
- [Requisitos e instaladores](#requisitos-e-instaladores)
- [Instalación](#instalación)
- [Configuración](#configuración)
- [Preparar los archivos](#preparar-los-archivos)
- [Uso](#uso)
- [Flujo de procesamiento](#flujo-de-procesamiento)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Notas operativas](#notas-operativas)

## Funciones

- Lee remitos mayoristas en PDF, planillas de canje `.xlsx` y pedidos de Mercado Libre en `.docx`.
- Consolida productos repetidos por código y suma sus cantidades.
- Compara el total de unidades extraídas de un remito con el total declarado y muestra discrepancias.
- Genera una planilla con stock inicial, descuento, stock final y resumen de pedidos.
- Señala en el informe los productos que no están en el catálogo.
- Compara cada descripción de Mercado Libre con el catálogo; aplica una unidad por registro solo si encuentra una coincidencia inequívoca.
- En una ejecución real, actualiza el stock del catálogo y archiva los documentos procesados.
- Ofrece menú interactivo, ejecución automática y simulación.
- Protege con credenciales administrativas la opción para agregar productos al catálogo.

## Requisitos e instaladores

| Herramienta                                  | Uso                                                  | Descarga                                                                                                                            |
| -------------------------------------------- | ---------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Python 3.10 o posterior                      | Ejecutar la aplicación                              | [Descargas oficiales de Python para Windows](https://www.python.org/downloads/windows/)                                              |
| Git for Windows *(opcional)*               | Clonar y actualizar el repositorio desde la terminal | [Descarga oficial de Git](https://git-scm.com/download/win)                                                                          |
| Visual Studio Code *(opcional)*            | Editar el código y abrir la terminal integrada      | [Descarga oficial de VS Code](https://code.visualstudio.com/Download)                                                                |
| Microsoft Excel o LibreOffice *(opcional)* | Revisar los archivos `.xlsx`                       | [Microsoft 365](https://www.microsoft.com/microsoft-365) · [LibreOffice](https://www.libreoffice.org/download/download-libreoffice/) |

La instalación de Python incluye `pip`, que se usa para instalar las dependencias del proyecto. Al instalar Python en Windows, activa la opción **Add python.exe to PATH** si aparece en el instalador.

Las dependencias de la aplicación están enumeradas en [`requirements.txt`](requirements.txt). `gspread` y `google-auth` se usan para la integración con Google Sheets; el menú estándar opera con el catálogo local de Excel.

## Instalación

### 1. Obtener el proyecto

Si tienes Git instalado:

```powershell
git clone https://github.com/Kniball4726/Agentes.git
cd Agentes
```

También puedes descargar el repositorio como ZIP desde [GitHub](https://github.com/Kniball4726/Agentes) y extraerlo en una carpeta local.

### 2. Comprobar Python

Abre PowerShell en la carpeta del proyecto y ejecuta:

```powershell
py --version
```

Debe mostrar Python 3.10 o posterior. Si `py` no está disponible, instala Python desde [python.org](https://www.python.org/downloads/windows/) y vuelve a abrir PowerShell.

### 3. Crear el entorno e instalar dependencias

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Si PowerShell impide activar el entorno por la política de ejecución, puedes ejecutar la aplicación con el Python del entorno sin activarlo:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Configuración

Crea un archivo llamado `.env` en la carpeta raíz del proyecto —junto a `main.py`— con las credenciales que quieras asignar a la función administrativa:

```dotenv
_ADMIN_USUARIO=tu_usuario
_ADMIN_CLAVE=tu_contraseña
```

Estas credenciales se solicitan al elegir **Agregar producto al catálogo** en el menú. Si falta cualquiera de las dos variables, la opción deniega el acceso y muestra un aviso.

El archivo `.env` está excluido de Git. No publiques credenciales reales ni las incluyas en capturas o archivos compartidos.

## Preparar los archivos

Al iniciar, el agente crea `Descuentos/` y sus carpetas de entrada, salida y archivado si no existen. Si faltan, inicializa `Productos.xlsx` y `Productos_backup.xlsx` desde las plantillas incluidas en `plantillas/`. No reemplaza archivos existentes. Coloca los archivos pendientes en:

| Carpeta                      | Contenido                                                           |
| ---------------------------- | ------------------------------------------------------------------- |
| `Descuentos/Mayoristas/`   | Remitos mayoristas `.pdf`                                         |
| `Descuentos/Canjes/`       | Planillas de canje `.xlsx`                                        |
| `Descuentos/MercadoLibre/` | Documentos Word `.docx`, con una descripción por párrafo o fila |

El catálogo de productos debe estar en `Descuentos/Productos.xlsx`. El gestor busca los productos desde la fila 3: código en la columna A, descripción en la B y stock en la C. Usa la hoja `Stock` cuando existe; si no, usa la hoja activa.

Para leer un canje, el programa busca los encabezados `PEDIDO` y `CODIGO` en las primeras 14 filas y espera la descripción en la columna siguiente a `CODIGO`. Los PDF deben contener texto extraíble y respetar el formato reconocido por el parser. No se incluye OCR para documentos escaneados como imagen.

En los documentos de Mercado Libre, cada párrafo no vacío o fila de tabla con contenido representa un producto y descuenta **una unidad**. El agente compara la descripción completa con la columna de productos del catálogo, ignorando diferencias de mayúsculas, acentos, puntuación y espacios. No hace búsqueda aproximada: si no encuentra una coincidencia única, no descuenta ese registro y lo informa en consola y en la planilla generada. Si una descripción aparece asociada a más de un código del catálogo, también se considera ambigua y no se descuenta.

## Uso

### Menú interactivo

```powershell
python main.py
```

También puedes iniciar la aplicación haciendo doble clic en `ejecutar.bat`.

El menú permite:

1. Procesar remitos, canjes y documentos de Mercado Libre pendientes.
2. Simular todas las fuentes sin guardar cambios ni mover documentos.
3. Procesar solo remitos mayoristas.
4. Procesar solo canjes.
5. Procesar solo documentos de Mercado Libre.
6. Consultar las planillas generadas.
7. Copiar documentos archivados de vuelta a las carpetas de entrada para pruebas.
8. Agregar un producto al catálogo (requiere credenciales de `.env`).
9. Salir.

### Ejecución automática

Procesa todos los documentos pendientes, incluidos los pedidos de Mercado Libre, sin mostrar el menú:

```powershell
python main.py --auto
```

`--all` es un alias de `--auto`.

### Simulación

```powershell
python main.py --dry-run
```

`--simulacion` es un alias de `--dry-run`. La simulación calcula y muestra el informe, pero no guarda la planilla, no actualiza `Productos.xlsx` y no mueve los documentos.

## Flujo de procesamiento

En una ejecución real, el agente:

1. Lee los documentos seleccionados de las carpetas de entrada.
2. Extrae metadatos e ítems y muestra los resultados de las verificaciones.
3. Consolida las cantidades por código de producto.
4. Genera `Descuentos/descuentos/DescuentoDD-MM-AAAA.xlsx`, con las columnas `CÓDIGO`, `PRODUCTOS`, `STOCK INICIAL`, `DESCUENTO` y `STOCK FINAL`.
5. Actualiza en `Productos.xlsx` el stock final de productos existentes que tuvieron descuentos, y guarda también `Productos_backup.xlsx`.
6. Mueve los remitos PDF a `Descuentos/descontados/Mayoristas/`, los canjes Excel a `Descuentos/descontados/Canjes/` y los documentos Word a `Descuentos/descontados/MercadoLibre/`.

Los descuentos aparecen como valores negativos. Los códigos que no están en el catálogo se incluyen al final del informe, pero no se agregan automáticamente a `Productos.xlsx`. Las descripciones de Mercado Libre que no se pudieron asociar se registran como pendientes de revisión en una sección aparte del informe.

El archivo de salida usa la fecha del día. Si ejecutas más de un procesamiento en la misma fecha, se reutiliza el mismo nombre; respalda el informe anterior si necesitas conservarlo.

## Estructura del proyecto

```text
Agentes/
├── ejecutar.bat              # Lanzador para Windows
├── main.py                   # Punto de entrada y modos de ejecución
├── requirements.txt          # Dependencias de Python
├── plantillas/               # Catálogo inicial y su respaldo
│   ├── Productos.xlsx
│   └── Productos_backup.xlsx
├── src/                       # Código fuente y módulos internos
│   ├── __init__.py
│   ├── agent.py               # Orquestación de lectura, consolidación y descuentos
│   ├── canjes_parser.py       # Lectura de planillas de canje
│   ├── consolidator.py        # Agrupación de productos por código
│   ├── mercado_libre_parser.py # Lectura y asociación de pedidos DOCX al catálogo
│   ├── menu.py                # Menú, autenticación y archivado
│   ├── remito_parser.py       # Lectura y verificación de remitos PDF
│   ├── sheets_manager.py      # Integración de stock con Google Sheets
│   └── stock_manager.py       # Catálogo Excel e informes de descuentos
└── Descuentos/
    ├── Productos.xlsx        # Catálogo y stock base
    ├── Mayoristas/           # Remitos PDF pendientes
    ├── Canjes/               # Canjes Excel pendientes
    ├── MercadoLibre/         # Pedidos Word pendientes de asociación
    ├── descuentos/           # Informes de descuentos generados
    └── descontados/          # Documentos procesados
        ├── Mayoristas/
        ├── Canjes/
        └── MercadoLibre/
```

`main.py`, `ejecutar.bat`, `requirements.txt`, `.env`, `plantillas/` y `Descuentos/` permanecen en la raíz del proyecto. El resto de los módulos Python se encuentra dentro de `src/`.

## Notas operativas

- Ejecuta primero una simulación para revisar los cálculos antes de procesar documentos reales.
- Una discrepancia entre las unidades declaradas y extraídas se informa, pero no detiene por sí sola el procesamiento. Revisa el documento antes de una ejecución real.
- La ejecución real modifica el catálogo y mueve los documentos. Mantén copias de seguridad antes de procesar información importante.
- La opción de restauración **copia** los documentos archivados a las carpetas pendientes; no elimina los originales archivados.
- La autenticación mediante `.env` está pensada para uso local; no es un sistema de autenticación para una aplicación expuesta a usuarios remotos.
