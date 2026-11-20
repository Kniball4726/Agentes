"""Flujos CLI administrativos protegidos y gestión de fábrica, Full y relevamiento físico."""

from __future__ import annotations

import getpass
import hmac
import os
import shutil
from typing import Callable

from ..inventory import StockManager
from ..parsers.factory_parser import parsear_archivo_fabrica
from ..parsers.mercado_full_parser import parsear_archivo_mercado_full
from ..parsers.physical_stock_parser import parsear_excel_stock_fisico
from ..parsers.remito_parser import normalizar_codigo
from .protocols import InteractiveFlowsHostProtocol


def autenticar_admin_cli() -> bool:
    """Solicita credenciales de administrador configuradas en entorno (`_ADMIN_USUARIO`/`_ADMIN_CLAVE`)."""
    from .. import menu as menu_mod

    admin_usuario = getattr(menu_mod, "_ADMIN_USUARIO", None) or os.getenv("_ADMIN_USUARIO")
    admin_clave = getattr(menu_mod, "_ADMIN_CLAVE", None) or os.getenv("_ADMIN_CLAVE")
    if not admin_usuario or not admin_clave:
        print(
            "\n[ERROR] Credenciales de administrador no configuradas. "
            "Defina _ADMIN_USUARIO y _ADMIN_CLAVE en el archivo .env."
        )
        return False

    print("\n" + "-" * 72)
    print("  ACCESO RESTRINGIDO - Se requieren credenciales de administrador")
    print("-" * 72)

    for intento in range(1, 4):
        try:
            usuario = input(f"  Usuario [{intento}/3]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  [CANCELADO] Autenticacion cancelada por el usuario.")
            return False

        try:
            clave = getpass.getpass("  Contraseña: ")
        except (KeyboardInterrupt, EOFError):
            print("\n  [CANCELADO] Autenticacion cancelada por el usuario.")
            return False
        except Exception:
            try:
                clave = input("  Contraseña (visible): ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n  [CANCELADO] Autenticacion cancelada por el usuario.")
                return False

        usuario_ok = hmac.compare_digest(usuario.encode("utf-8"), str(admin_usuario).encode("utf-8"))
        clave_ok = hmac.compare_digest(clave.encode("utf-8"), str(admin_clave).encode("utf-8"))
        if usuario_ok and clave_ok:
            print("  [OK] Acceso autorizado.\n")
            return True

        restantes = 3 - intento
        print(
            f"  [ERROR] Credenciales incorrectas. Intentos restantes: {restantes}"
            if restantes > 0
            else "  [BLOQUEADO] Se superó el número máximo de intentos."
        )
    return False


def agregar_producto_admin_cli(
    host: InteractiveFlowsHostProtocol,
    autenticar_fn: Callable[[], bool] = autenticar_admin_cli,
) -> None:
    """Flujo protegido para dar de alta un nuevo producto en una posición específica del catálogo."""
    if not autenticar_fn():
        print("\n[ACCESO DENEGADO] No se realizaron cambios en el catálogo.")
        return

    print("=" * 72)
    print("  AGREGAR NUEVO PRODUCTO AL CATALOGO")
    print("=" * 72)
    print("  (Deje el stock inicial en blanco para no asignar valor)")
    print("  (Ctrl+C en cualquier momento para cancelar)")
    print("-" * 72)

    try:
        codigo_nuevo = input("  Código del NUEVO producto    : ").strip()
        if not codigo_nuevo:
            print("\n[CANCELADO] El código no puede estar vacío.")
            return
        nombre_nuevo = input("  Nombre del NUEVO producto    : ").strip()
        if not nombre_nuevo:
            print("\n[CANCELADO] El nombre no puede estar vacío.")
            return
        codigo_arriba = input("  Código del producto ANTERIOR (se insertará debajo de él): ").strip()
        if not codigo_arriba:
            print("\n[CANCELADO] Debe indicar un producto de referencia.")
            return
        stock_str = input("  Stock inicial (Enter = sin valor): ").strip()
        stock_inicial = None
        if stock_str:
            try:
                stock_inicial = int(stock_str)
            except ValueError:
                print("\n[AVISO] El stock debe ser un número entero. Se asignará sin valor.")

        print("\n" + "-" * 72)
        print("  Confirmar alta de producto:")
        print(f"    Código   : {codigo_nuevo}")
        print(f"    Nombre   : {nombre_nuevo}")
        print(f"    Debajo de: {codigo_arriba}")
        print(f"    Stock    : {stock_inicial if stock_inicial is not None else '(sin valor)'}")
        print("-" * 72)
        if input("  ¿Confirmar? [s/N]: ").strip().lower() != "s":
            print("\n[CANCELADO] No se realizaron cambios.")
            return
    except (KeyboardInterrupt, EOFError):
        print("\n\n[CANCELADO] Alta de producto cancelada por el usuario. No se realizaron cambios.")
        return

    try:
        stock_mgr = StockManager(ruta_excel_base=host.ruta_excel_base)
        exito, mensaje, _ = stock_mgr.agregar_producto_en_posicion(
            codigo_nuevo=codigo_nuevo,
            nombre_nuevo=nombre_nuevo,
            codigo_arriba=codigo_arriba,
            stock_inicial=stock_inicial,
        )
        print(f"\n[OK] {mensaje}\n     Archivo actualizado: {host.ruta_excel_base}" if exito else f"\n[ERROR] {mensaje}")
    except KeyboardInterrupt:
        print(f"\n[INTERRUMPIDO] El proceso fue interrumpido. Verifique manualmente: {host.ruta_excel_base}")
    except Exception as e:
        print(f"\n[ERROR] Ocurrió un problema al acceder al catálogo: {e}")


def cargar_pedido_fabrica_cli(
    autenticar_fn: Callable[[], bool],
    on_archivos: Callable[[], None],
    on_manual: Callable[[], None],
) -> None:
    """Flujo CLI para procesar ingresos desde fábrica por archivo o carga manual."""
    if not autenticar_fn():
        print("\n[ACCESO DENEGADO] No se realizaron cambios.")
        return

    print("\n" + "=" * 72)
    print("  CARGA DE PEDIDO DE FÁBRICA / REESTABLECIMIENTO DE STOCK")
    print("=" * 72)
    print("  [1] Procesar archivos en carpeta Descuentos/Fabrica")
    print("  [2] Cargar stock manualmente por código")
    print("  [0] Volver al menú principal")
    print("-" * 72)

    try:
        subopcion = input("  Seleccione una opción [0-2]: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n  [CANCELADO] Operación cancelada por el usuario.")
        return

    if subopcion == "0":
        return
    if subopcion == "1":
        on_archivos()
    elif subopcion == "2":
        on_manual()


def cargar_fabrica_archivos_cli(host: InteractiveFlowsHostProtocol) -> None:
    """Procesa archivos pendientes de ingreso de fábrica y los archiva en Descontados/Fabrica."""
    archivos = host._obtener_pendientes_fabrica()
    if not archivos:
        print(f"\n[AVISO] No hay archivos en la carpeta: {host.carpeta_fabrica}")
        return
    print(f"\nSe encontraron {len(archivos)} archivo(s) de fábrica:")
    for idx, a in enumerate(archivos, 1):
        print(f"  {idx}. {a.name}")
    print("\nTipo de operación:\n  [1] Sumar al stock actual (Reabastecimiento)\n  [2] Sobrescribir stock (Ajuste directo)")
    try:
        sobrescribir = input("  Seleccione modo [1]: ").strip() == "2"
    except (KeyboardInterrupt, EOFError):
        print("\n  [CANCELADO] Operación cancelada.")
        return

    stock_mgr = StockManager(ruta_excel_base=host.ruta_excel_base)
    total_procesados = 0
    for a in archivos:
        print(f"\nProcesando {a.name}...")
        try:
            totales, _ = parsear_archivo_fabrica(a)
            if not totales:
                print("  [AVISO] No se extrajeron productos con cantidad válida de este archivo.")
                continue
            resumen = stock_mgr.registrar_ingreso_fabrica(totales, sobrescribir=sobrescribir)
            print(f"  [OK] Se actualizaron {len(resumen)} productos en la base y Productos.xlsx.")
            for c, (s_ant, s_nvo) in resumen.items():
                print(f"       Cod {c} ({stock_mgr.catalogo[c][1][:30]}): {s_ant} -> {s_nvo}")
            dest_fab = host.carpeta_descontados / "Fabrica"
            dest_fab.mkdir(parents=True, exist_ok=True)
            shutil.move(str(a), str(dest_fab / a.name))
            print(f"       Archivo archivado en: {dest_fab}")
            total_procesados += 1
        except Exception as e:
            print(f"  [ERROR] Falló el procesamiento de {a.name}: {e}")
    print(f"\n[FIN] {total_procesados} archivo(s) procesados exitosamente.")


def cargar_fabrica_manual_cli(host: InteractiveFlowsHostProtocol) -> None:
    """Permite cargar o ajustar stock manualmente código por código desde terminal."""
    stock_mgr = StockManager(ruta_excel_base=host.ruta_excel_base)
    print("\nModo de carga manual (escriba 'fin' o deje código vacío para terminar):")
    print("  [1] Sumar al stock actual (Reabastecimiento)\n  [2] Sobrescribir stock (Ajuste directo)")
    try:
        sobrescribir = input("  Seleccione modo [1]: ").strip() == "2"
    except (KeyboardInterrupt, EOFError):
        print("\n  [CANCELADO] Operación cancelada.")
        return

    cargas: dict[str, int] = {}
    while True:
        try:
            cod = input("\n  Código de producto (o 'fin'): ").strip()
            if not cod or cod.lower() == "fin":
                break
            cod_norm = normalizar_codigo(cod)
            if cod_norm not in stock_mgr.catalogo:
                print(f"  [ERROR] El código '{cod_norm}' no existe en el catálogo.")
                continue
            _, nom, st_actual = stock_mgr.catalogo[cod_norm]
            print(f"  Producto: {nom} | Stock actual: {st_actual}")
            cant_str = input(f"  Cantidad a {'fijar' if sobrescribir else 'sumar'}: ").strip()
            if not cant_str:
                continue
            cant = int(cant_str)
            if cant < 0:
                print("  [ERROR] La cantidad no puede ser negativa.")
                continue
            cargas[cod_norm] = cant
        except ValueError:
            print("  [ERROR] La cantidad debe ser un número entero.")
        except (KeyboardInterrupt, EOFError):
            print("\n  [CANCELADO] Entrada interrumpida.")
            return

    if not cargas:
        print("\n[AVISO] No se ingresaron productos para actualizar.")
        return
    try:
        if input(f"\nSe actualizarán {len(cargas)} producto(s). ¿Confirmar actualización? [s/N]: ").strip().lower() != "s":
            print("\n[CANCELADO] No se realizaron cambios.")
            return
        resumen = stock_mgr.registrar_ingreso_fabrica(cargas, sobrescribir=sobrescribir)
        print(f"\n[OK] Se actualizaron {len(resumen)} productos exitosamente:")
        for c, (s_ant, s_nvo) in resumen.items():
            print(f"     Cod {c} ({stock_mgr.catalogo[c][1][:30]}): {s_ant} -> {s_nvo}")
    except Exception as e:
        print(f"\n[ERROR] Ocurrió un error al actualizar el stock: {e}")


def generar_pedido_fabrica_sugerido_cli(
    host: InteractiveFlowsHostProtocol,
    autenticar_fn: Callable[[], bool] = autenticar_admin_cli,
) -> None:
    """Genera el Excel con los pedidos sugeridos a fábrica según máximos y mínimos."""
    if not autenticar_fn():
        print("\n[ACCESO DENEGADO] Requiere permisos de administrador.")
        return
    stock_mgr = StockManager(host.ruta_excel_base)
    print("\n--- Generando Pedido Sugerido a Fábrica (Excel) ---")
    try:
        ruta = stock_mgr.generar_pedido_sugerido_fabrica(solo_criticos=True)
        print(f"   [OK] Archivo generado exitosamente en:\n        {ruta}")
    except Exception as e:
        print(f"   [ERROR] No se pudo generar el pedido: {e}")


def descontar_mercado_full_terminal_cli(
    host: InteractiveFlowsHostProtocol,
    autenticar_fn: Callable[[], bool] = autenticar_admin_cli,
) -> None:
    """Procesa y descuenta planillas Excel de Mercado Envíos Full desde consola."""
    if not autenticar_fn():
        print("\n[ACCESO DENEGADO] Requiere permisos de administrador.")
        return
    archivos = host._obtener_pendientes_mercado_full()
    if not archivos:
        print(f"\n[AVISO] No hay archivos pendientes en {host.carpeta_mercado_full}.")
        return
    print(f"\n--- Procesar Envíos Mercado Full ({len(archivos)} archivo(s)) ---")
    stock_mgr = StockManager(host.ruta_excel_base)

    for arch in archivos:
        print(f"\nLeyendo: {arch.name}")
        try:
            totales, _ = parsear_archivo_mercado_full(arch)
        except Exception as e:
            print(f"  [ERROR] No se pudo leer {arch.name}: {e}")
            continue
        if not totales:
            print("  [AVISO] No se encontraron productos válidos en el archivo.")
            continue
        print(f"  Se detectaron {len(totales)} productos a descontar (Total unidades: {sum(totales.values())}).")
        for cod, cant in list(totales.items())[:5]:
            _, nom, stk = stock_mgr.catalogo.get(cod, ("", "No encontrado", 0))
            print(f"   • [{cod}] {nom[:30]} | Descontar: {cant} | Stock act: {stk} -> {stk - cant}")
        try:
            conf = input(f"¿Confirmar descuento de {arch.name}? [s/N]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\n  [CANCELADO] Operación interrumpida.")
            return
        if conf != "s":
            print("  [SALTADO] No se aplicaron descuentos para este archivo.")
            continue
        try:
            stock_mgr.descontar_mercado_full(totales, nombre_archivo=arch.name)
            dest = host.carpeta_descontados / "MercadoFull"
            dest.mkdir(parents=True, exist_ok=True)
            shutil.move(str(arch), str(dest / arch.name))
            print(f"  [OK] Descuento aplicado exitosamente. Archivo movido a {dest.name}/.")
        except Exception as e:
            print(f"  [ERROR] Falló al aplicar el descuento: {e}")


def hacer_stock_fisico_terminal_cli(
    host: InteractiveFlowsHostProtocol,
    usuario: str = "operario",
) -> None:
    """Lee planillas Excel en StockFisico, compara con el digital y archiva resultados."""
    archivos = host._obtener_pendientes_stock_fisico()
    if not archivos:
        print(f"\n[AVISO] No hay planillas pendientes en {host.carpeta_stock_fisico}.")
        return
    print(f"\n--- Relevamiento de Stock Físico ({len(archivos)} archivo(s)) ---")
    stock_mgr = StockManager(host.ruta_excel_base)

    for arch in archivos:
        print(f"\nLeyendo: {arch.name}")
        try:
            totales, _ = parsear_excel_stock_fisico(arch)
        except Exception as e:
            print(f"  [ERROR] No se pudo leer {arch.name}: {e}")
            continue
        if not totales:
            print("  [AVISO] No se encontraron productos válidos en el archivo.")
            continue
        ruta_doc, comparativa = stock_mgr.procesar_stock_fisico(totales, usuario=usuario, nombre_archivo=arch.name)
        con_dif = [i for i in comparativa if i["diferencia"] != 0]
        print(f"  [OK] Relevados: {len(comparativa)} | Con diferencias: {len(con_dif)}")
        for item in comparativa[:10]:
            dif = item["diferencia"]
            dif_str = f"+{dif}" if dif > 0 else str(dif)
            print(f"   • [{item['code']}] {item['name'][:30]} | Digital: {item['stock_digital']} | Físico: {item['stock_fisico']} | Dif: {dif_str} ({item['estado']})")
        print(f"  [REPORTE UNIFICADO ADMIN] {ruta_doc}")
        dest = host.carpeta_descontados / "StockFisico"
        dest.mkdir(parents=True, exist_ok=True)
        shutil.move(str(arch), str(dest / arch.name))
