# Agente de Control de Stock y Remitos

Sistema automatizado para gestionar descuentos de stock a partir de remitos mayoristas en PDF y canjes en Excel, consolidar ventas duplicadas, validar inconsistencias y actualizar la planilla base de inventario.

## Descripción general

Este proyecto está pensado para operar como un agente de negocio orientado a operaciones comerciales y de stock. Su objetivo es:

- Leer remitos mayoristas en formato PDF.
- Leer planillas de canjes en formato Excel (.xlsx).
- Validar la consistencia de los datos extraídos.
- Consolidar productos repetidos entre distintos documentos.
- Descontar cantidades del stock disponible en la planilla base.
- Generar una nueva planilla de descuentos con un resumen de movimientos.
- Actualizar el catálogo base para la próxima corrida.
- Permitir ejecución interactiva o automática desde línea de comandos.

El flujo de trabajo está diseñado para reducir errores manuales, mantener trazabilidad y generar salidas listas para uso operativo.

## Características principales

- Procesamiento de remitos PDF con extracción de datos clave.
- Procesamiento de canjes desde archivos Excel.
- Consolidación de ítems repetidos por código.
- Detección de discrepancias entre artículos declarados y extraídos.
- Generación automática de planillas de descuento.
- Actualización del stock base en `Productos.xlsx`.
- Modo simulación para revisar cálculos sin afectar archivos.
- Menú interactivo con administración de catálogo.
- Archivación de documentos procesados en carpetas específicas.

## Stack tecnológico

- Python 3.x
- OpenPyXL para manipulación de Excel
- PyPDF para lectura de archivos PDF
- gspread / google-auth para posibles integraciones con Google Sheets

## Estructura del proyecto

```text
Agentes/
├── agent.py                  # Orquestador principal del agente
├── canjes_parser.py          # Extracción de datos desde archivos Excel de canje
├── consolidator.py           # Consolidación y suma de productos repetidos
├── ejecutar.bat              # Acceso rápido para ejecutar la app en Windows
├── main.py                   # Punto de entrada del sistema
├── menu.py                   # Menú interactivo y flujo de usuario
├── remito_parser.py          # Extracción y validación de remitos PDF
├── requirements.txt          # Dependencias del proyecto
├── sheets_manager.py         # Gestión de integración con Google Sheets
├── stock_manager.py          # Manejo del catálogo, descuentos y actualización de stock
├── Descuentos/
│   ├── Productos.xlsx        # Base de stock principal
│   ├── Mayoristas/           # Remitos pendientes por procesar
│   ├── Canjes/               # Canjes pendientes por procesar
│   ├── descuentos/           # Planillas generadas de descuento
│   └── descontados/          # Documentos ya procesados
└── README.md                 # Documentación del proyecto
```

## Requisitos

- Python 3.10 o superior recomendado
- Pip instalado
- Microsoft Excel o compatible para abrir archivos `.xlsx`
- Acceso local a la carpeta `Descuentos/`

## Instalación

1. Clonar el repositorio:

```bash
git clone <url-del-repositorio>
cd Agentes
```

2. Crear un entorno virtual (opcional pero recomendado):

```bash
python -m venv .venv
.venv\Scripts\activate
```

3. Instalar dependencias:

```bash
pip install -r requirements.txt
```

## Uso

### Modo interactivo

Ejecuta el programa normalmente:

```bash
python main.py
```

Se abrirá un menú con opciones como:

- Ejecutar descuento completo
- Modo simulación
- Procesar solo remitos
- Procesar solo canjes
- Ver historial
- Restaurar archivos de prueba
- Agregar producto al catálogo (acceso restringido)

### Modo automático

Se puede ejecutar sin abrir el menú:

```bash
python main.py --auto
```

Esto procesa automáticamente remitos y canjes pendientes.

### Modo simulación

Para revisar cálculos sin escribir ni mover archivos:

```bash
python main.py --dry-run
```

o:

```bash
python main.py --simulacion
```

## Flujo de operación

El sistema ejecuta los siguientes pasos:

1. Localiza archivos pendientes en `Descuentos/Mayoristas` y `Descuentos/Canjes`.
2. Extrae información de cada remito PDF o planilla Excel.
3. Valida artículos declarados contra los extraídos.
4. Consolida productos duplicados por código.
5. Revisa si el producto existe en el catálogo base.
6. Calcula el nuevo stock final.
7. Genera una planilla de descuentos en `Descuentos/descuentos/`.
8. Actualiza `Productos.xlsx` con los valores finales para la próxima corrida.
9. Mueve los documentos procesados a la carpeta `Descuentos/descontados/`.

## Salidas esperadas

Durante la ejecución se generan:

- una planilla con columnas: `Código`, `Productos`, `Stock Inicial`, `Descuento`, `Stock Final`;
- un resumen de pedidos descontados;
- registros para productos no encontrados en el catálogo original;
- actualización del stock base para el ciclo siguiente.

## Consideraciones importantes

- El proyecto está orientado a uso local y operativo, no como una API REST.
- El catálogo base debe mantenerse actualizado en `Descuentos/Productos.xlsx`.
- Los archivos en `Mayoristas` y `Canjes` se procesan por lotes según el estado del sistema.
- La función de administración está protegida por credenciales configuradas en `menu.py`.
- En modo simulación no se guardan cambios ni se mueven documentos.

## Recomendaciones

- Mantener un backup del archivo `Productos.xlsx` antes de corridas importantes.
- Revisar el historial de planillas generadas para auditoría.
- Validar con la carpeta `descuentos/` antes de confirmar cambios operativos.
- Usar el modo `--dry-run` cuando se quiera validar la lógica antes de aplicar descuentos reales.

## Licencia

Este proyecto se entrega con fines operativos internos y de gestión de inventario. Ajustar la licencia según la política de la organización o cliente donde se implemente.

## Contacto

Si es necesario mantener, ampliar o adaptar este sistema, se recomienda documentar cualquier cambio en el flujo de stock, validaciones o estructura de archivos antes de utilizarlo en producción.
