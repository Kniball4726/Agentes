import json
import os
import sqlite3
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast
from unittest.mock import patch

import flet as ft

from src.alertas_programadas import PlanificadorAlertas, construir_resumen
from src.backup_manager import (
    crear_backup_sistema,
    guardar_config_backup,
    restaurar_backup_sistema,
)
from src.email_sender import guardar_config_email, obtener_config_email
from src.logger_config import configurar_logging
from src.orders_store import OrderStore
from src.product_store import ProductStore
from src.secretos import PREFIJO as ESTA_CIFRADO_PREFIJO, cifrar as cifrar_secreto, descifrar as descifrar_secreto, esta_cifrado
from src.ssl_manager import asegurar_certificado_ssl
from src.user_store import UserStore
from tests.test_flet_gui import FakeMenu, FakePage, InterfazFlet


class NuevasFuncionalidadesTests(unittest.TestCase):
    def test_secretos_cifrado_y_descifrado_idempotente(self):
        original = "clave_smtp_super_secreta_2026!"
        cifrado = cifrar_secreto(original)
        self.assertTrue(cifrado.startswith(ESTA_CIFRADO_PREFIJO))
        self.assertTrue(esta_cifrado(cifrado))
        # Idempotencia: cifrar algo ya cifrado no vuelve a envolverlo
        self.assertEqual(cifrar_secreto(cifrado), cifrado)
        recuperado = descifrar_secreto(cifrado)
        self.assertEqual(recuperado, original)
        self.assertEqual(cifrar_secreto(""), "")
        self.assertEqual(descifrar_secreto(""), "")

    def test_email_config_cifra_password_en_disco_y_descifra_en_memoria(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with patch("src.email_sender.application_root", return_value=tmp_path), patch.dict(os.environ, {"STOCKAGENT_SMTP_PASSWORD": ""}):
                guardar_config_email(
                    {
                        "smtp_servidor": "smtp.gmail.com",
                        "smtp_puerto": 587,
                        "smtp_usuario": "deposito@empresa.com",
                        "smtp_password": "token_secreto_app_123",
                        "smtp_usar_tls": True,
                        "smtp_usar_ssl": False,
                        "alertas": {
                            "activo": True,
                            "hora": "18:30",
                            "destinatarios": "gerencia@empresa.com",
                        },
                    }
                )
                archivo_json = tmp_path / "data" / "email_config.json"
                self.assertTrue(archivo_json.exists())
                raw_disk = json.loads(archivo_json.read_text(encoding="utf-8"))
                self.assertTrue(str(raw_disk["smtp_password"]).startswith(ESTA_CIFRADO_PREFIJO))
                self.assertNotIn("token_secreto_app_123", archivo_json.read_text(encoding="utf-8"))

                cargado = obtener_config_email()
                self.assertEqual(cargado["smtp_password"], "token_secreto_app_123")
                self.assertTrue(cargado["alertas"]["activo"])
                self.assertEqual(cargado["alertas"]["hora"], "18:30")

    def test_user_store_bloqueo_intentos_cambio_clave_y_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "usuarios.sqlite3"
            store = UserStore(db_path)

            # 1. Usuario Desarrollo inicial tiene must_change_password=True
            res_master = store.authenticate_detailed("Desarrollo", "master1713")
            self.assertIsNotNone(res_master.user)
            self.assertTrue(res_master.user.must_change_password)

            # Cambiar contraseña propia quita must_change_password
            store.change_password(res_master.user.id, "master1713", "NuevaMasterSegura2026!")
            res_master_2 = store.authenticate_detailed("Desarrollo", "NuevaMasterSegura2026!")
            self.assertIsNotNone(res_master_2.user)
            self.assertFalse(res_master_2.user.must_change_password)

            # 2. Crear operario y probar bloqueo tras 5 intentos fallidos
            op = store.create_user("operario1", "OperarioPass123!", "operador", creator_role="master")
            for i in range(4):
                r = store.authenticate_detailed("operario1", "clave_erronea")
                self.assertIsNone(r.user)
                self.assertFalse(r.locked)
                self.assertEqual(r.remaining_attempts, 5 - (i + 1))

            # 5to intento fallido bloquea la cuenta
            r5 = store.authenticate_detailed("operario1", "clave_erronea")
            self.assertIsNone(r5.user)
            self.assertTrue(r5.locked)
            self.assertIn("operario1", store.list_locked_usernames())

            # Incluso con clave correcta sigue bloqueado
            r_bloqueado = store.authenticate_detailed("operario1", "OperarioPass123!")
            self.assertIsNone(r_bloqueado.user)
            self.assertTrue(r_bloqueado.locked)

            # 3. Desbloqueo administrativo
            store.unlock_user("operario1")
            self.assertNotIn("operario1", store.list_locked_usernames())
            r_ok = store.authenticate_detailed("operario1", "OperarioPass123!")
            self.assertIsNotNone(r_ok.user)

            # 4. Reset de contraseña por administrador fuerza cambio de clave
            store.reset_password(op.id, "TemporalReset123!", updater_role="master", must_change=True)
            r_reset = store.authenticate_detailed("operario1", "TemporalReset123!")
            self.assertIsNotNone(r_reset.user)
            self.assertTrue(r_reset.user.must_change_password)

    def test_ssl_manager_genera_certificado_autofirmado(self):
        with tempfile.TemporaryDirectory() as tmp:
            cert_file = Path(tmp) / "certs" / "test_stockagent.crt"
            key_file = Path(tmp) / "certs" / "test_stockagent.key"
            c_out, k_out = asegurar_certificado_ssl(cert_file, key_file)
            self.assertEqual(c_out, cert_file)
            self.assertEqual(k_out, key_file)
            self.assertTrue(cert_file.exists())
            self.assertTrue(key_file.exists())
            self.assertIn("BEGIN CERTIFICATE", cert_file.read_text(encoding="utf-8"))

    def test_product_store_registra_usuario_y_detalle_en_movimientos(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "productos.sqlite3"
            store = ProductStore(db_path)
            store.register_movements(
                [("P100", "Amortiguador Delantero", -4, "descuento")],
                usuario="operario_juan",
                detalle="Remito #0001-00001234",
            )
            store.register_movements(
                [("P100", "Amortiguador Delantero", 10, "ingreso_fabrica")],
                usuario="admin_carlos",
                detalle="Planilla fábrica lote 9",
            )

            movs = store.list_recent_movements(product_code="P100")
            self.assertEqual(len(movs), 2)
            usuarios = {m["usuario"] for m in movs}
            self.assertIn("operario_juan", usuarios)
            self.assertIn("admin_carlos", usuarios)

            solo_desc = store.list_recent_movements(product_code="P100", movement_type="descuento")
            self.assertEqual(len(solo_desc), 1)
            self.assertEqual(solo_desc[0]["detalle"], "Remito #0001-00001234")

    def test_orders_store_estados_despacho_escaner_qr_y_dashboard_filtrado(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "pedidos.sqlite3"
            store = OrderStore(db_path)
            ped = store.registrar_pedido(
                nota_pedido="0001-00099887",
                numero_pedido="99887",
                cliente="Distribuidora Norte",
                bultos=3,
                logistica="Transporte",
                armador="operario1",
                tipo_archivo="pdf",
                nombre_archivo="remito_99887.pdf",
                agregado=False,
                articulos_descontados=12,
                resumen_items="2 productos (12 un.)",
                items=[("COD1", "Producto 1", 12)],
            )
            self.assertEqual(ped.estado_despacho, "armado")

            # Avanzar vía código QR de etiqueta (armado -> despachado)
            qr_payload = "REMITO:0001-00099887|CLIENTE:Distribuidora Norte|BULTOS:1/3|LOGISTICA:Transporte"
            ok1, msg1, ped1 = store.avanzar_estado_por_codigo(qr_payload, usuario="expedicion1")
            self.assertTrue(ok1)
            self.assertIsNotNone(ped1)
            self.assertEqual(ped1.estado_despacho, "despachado")
            self.assertEqual(ped1.despachado_por, "expedicion1")

            # Avanzar nuevamente (despachado -> entregado)
            ok2, msg2, ped2 = store.avanzar_estado_por_codigo("0001-00099887", usuario="chofer1")
            self.assertTrue(ok2)
            self.assertEqual(ped2.estado_despacho, "entregado")
            self.assertEqual(ped2.entregado_por, "chofer1")

            # Resumen enriquecido para chat #remito
            resumen_chat = store.obtener_pedido_resumen_chat("0001-00099887")
            self.assertIsNotNone(resumen_chat)
            self.assertIn("Distribuidora Norte", resumen_chat)
            self.assertIn("ENTREGADO", resumen_chat)

            # Métricas de dashboard con filtro de fechas
            hoy = datetime.now().strftime("%Y-%m-%d")
            metricas = store.obtener_metricas_dashboard(fecha_desde=hoy, fecha_hasta=hoy)
            self.assertEqual(metricas["total_pedidos"], 1)
            self.assertEqual(metricas["total_bultos"], 3)
            self.assertEqual(metricas["estados_despacho"]["entregado"], 1)
            self.assertEqual(len(metricas["pedidos_por_dia"]), 1)

    def test_backup_integral_3_bases_carpeta_secundaria_y_restauracion(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            data_dir = raiz / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            sec_dir = raiz / "copia_externa"

            # Inicializar las 3 bases y Excel maestro
            u_store = UserStore(data_dir / "usuarios.sqlite3")
            o_store = OrderStore(data_dir / "pedidos.sqlite3")
            p_store = ProductStore(data_dir / "productos.sqlite3")
            o_store.crear_cliente("Cliente Backup Test")
            p_store.import_template_once([(2, "BK01", "Producto Backup", 50)])

            excel_base = raiz / "Productos.xlsx"
            excel_base.write_bytes(b"EXCEL_DUMMY_CONTENT")

            with patch("src.backup_manager.application_root", return_value=raiz):
                guardar_config_backup(str(sec_dir))
                zip_creado = crear_backup_sistema(ruta_excel_base=excel_base, usuario="admin")

                self.assertTrue(zip_creado.exists())
                # Verificar réplica en carpeta secundaria
                self.assertTrue((sec_dir / zip_creado.name).exists())

                # Verificar que las 3 bases estén en el ZIP
                with zipfile.ZipFile(zip_creado, "r") as zf:
                    nombres = zf.namelist()
                    self.assertIn("pedidos.sqlite3", nombres)
                    self.assertIn("productos.sqlite3", nombres)
                    self.assertIn("usuarios.sqlite3", nombres)

                # Modificar base actual y luego restaurar desde el ZIP
                o_store.crear_cliente("Cliente Posterior A Borrar")
                self.assertIn("Cliente Posterior A Borrar", o_store.listar_nombres_clientes())

                ok, msg, _ = restaurar_backup_sistema(zip_creado, ruta_excel_base=excel_base)
                self.assertTrue(ok, msg)

                o_store_restaurado = OrderStore(data_dir / "pedidos.sqlite3")
                clientes = o_store_restaurado.listar_nombres_clientes()
                self.assertIn("Cliente Backup Test", clientes)
                self.assertNotIn("Cliente Posterior A Borrar", clientes)

    def test_alertas_programadas_construccion_y_planificador(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            data_dir = raiz / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            p_store = ProductStore(data_dir / "productos.sqlite3")
            o_store = OrderStore(data_dir / "pedidos.sqlite3")
            p_store.import_template_once([(2, "CRIT01", "Filtro Crítico", 0)])

            asunto, cuerpo, cant = construir_resumen(
                ruta_productos_db=data_dir / "productos.sqlite3",
                ruta_pedidos_db=data_dir / "pedidos.sqlite3",
            )
            self.assertEqual(cant, 1)
            self.assertIn("CRIT01", cuerpo)
            self.assertIn("AGOTADOS", cuerpo)

            with patch("src.alertas_programadas.application_root", return_value=raiz), patch(
                "src.email_sender.application_root", return_value=raiz
            ), patch("src.alertas_programadas.enviar_resumen_ahora", return_value=(True, "Enviado OK")) as mock_env:
                guardar_config_email(
                    {
                        "alertas": {
                            "activo": True,
                            "hora": "08:00",
                            "destinatarios": "admin@empresa.com",
                            "ultimo_envio": "",
                        }
                    }
                )
                # Antes de la hora configurada no envía
                self.assertFalse(PlanificadorAlertas.revisar(datetime(2026, 10, 25, 7, 30)))
                # A la hora configurada envía y registra ultimo_envio
                self.assertTrue(PlanificadorAlertas.revisar(datetime(2026, 10, 25, 8, 5)))
                self.assertEqual(mock_env.call_count, 1)
                # Si se vuelve a revisar el mismo día, no duplica el envío
                self.assertFalse(PlanificadorAlertas.revisar(datetime(2026, 10, 25, 9, 0)))

    def test_gui_inactividad_chat_enriquecido_y_nuevos_modales(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "data").mkdir(parents=True, exist_ok=True)
            u_store = UserStore(raiz / "data" / "usuarios.sqlite3")
            o_store = OrderStore(raiz / "data" / "pedidos.sqlite3")
            o_store.registrar_pedido(
                nota_pedido="R-500",
                numero_pedido="500",
                cliente="Taller Central",
                bultos=2,
                logistica="Domicilio",
                armador="operario",
                tipo_archivo="pdf",
                nombre_archivo="r500.pdf",
                agregado=False,
                articulos_descontados=5,
                resumen_items="1 prod (5 un.)",
            )

            page = FakePage()
            menu = FakeMenu()
            with patch("src.flet_gui.MenuAgente", return_value=menu), patch(
                "src.flet_gui.UserStore", return_value=u_store
            ), patch("src.flet_gui.OrderStore", return_value=o_store):
                interfaz = InterfazFlet(cast(ft.Page, page))

            # Iniciar sesión con Desarrollo (debe abrir cambio obligatorio de clave)
            master_usr = u_store.get_user_by_username("Desarrollo")
            interfaz.usuario_actual = master_usr
            interfaz.mostrar_cambio_clave_obligatorio()
            self.assertEqual(len(page.controls), 1)

            # Construir dashboard normal
            u_store.change_password(master_usr.id, "master1713", "ClaveFuerteMaster2026!")
            interfaz.usuario_actual = u_store.get_user(master_usr.id)
            interfaz.construir()

            # Enriquecimiento de #remito en chat de equipo
            interfaz.entrada_chat_equipo.value = "Por favor revisar #R-500 urgente"
            interfaz.enviar_mensaje_equipo()
            mensajes = o_store.listar_mensajes_chat(usuario="Desarrollo")
            self.assertEqual(len(mensajes), 1)
            self.assertIn("Taller Central", mensajes[0].mensaje)

            # Abrir modales nuevos sin errores
            interfaz.mostrar_escaner_qr_despacho()
            self.assertEqual(len(page.dialogos), 1)
            page.pop_dialog()

            interfaz.mostrar_dashboard_metricas()
            self.assertEqual(len(page.dialogos), 1)
            page.pop_dialog()

            interfaz.mostrar_dialogo_backup()
            self.assertEqual(len(page.dialogos), 1)
            page.pop_dialog()

            interfaz.mostrar_configuracion_smtp()
            self.assertEqual(len(page.dialogos), 1)
            page.pop_dialog()

            # Probar expiración por inactividad
            from src.flet_gui import INACTIVIDAD_MAX_MINUTOS
            interfaz.ultima_actividad = datetime.now() - timedelta(minutes=INACTIVIDAD_MAX_MINUTOS + 5)
            permitido = interfaz.exigir_roles("administrador")
            self.assertFalse(permitido)
            self.assertIsNone(interfaz.usuario_actual)
            logs = o_store.listar_auditoria(limit=5, filtro="LOGOUT_INACTIVIDAD")
            self.assertEqual(len(logs), 1)

    def test_logger_rotativo_crea_archivo_log(self):
        logger = configurar_logging()
        logger.info("Prueba unitaria de logger rotativo")
        self.assertTrue(len(logger.handlers) >= 1)

    def test_crud_clientes_order_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "pedidos_test.db"
            store = OrderStore(db_path)

            # 1. Crear cliente
            cli1 = store.crear_cliente("Distribuidora Norte S.A.", usuario="admin")
            self.assertEqual(cli1.nombre, "Distribuidora Norte S.A.")
            self.assertTrue(cli1.activo)

            # No permitir nombres duplicados
            with self.assertRaises(ValueError):
                store.crear_cliente("distribuidora norte s.a.")

            # No permitir nombres vacíos
            with self.assertRaises(ValueError):
                store.crear_cliente("   ")

            # 2. Listar clientes
            clientes = store.listar_clientes()
            self.assertEqual(len(clientes), 1)
            self.assertIn("Distribuidora Norte S.A.", store.listar_nombres_clientes())

            # 3. Actualizar cliente
            actualizado = store.actualizar_cliente(cli1.id, "Distribuidora Norte SRL", usuario="admin")
            self.assertEqual(actualizado.nombre, "Distribuidora Norte SRL")
            self.assertIn("Distribuidora Norte SRL", store.listar_nombres_clientes())

            # 4. Eliminar cliente (soft-delete)
            store.eliminar_cliente(cli1.id, usuario="admin")
            self.assertEqual(len(store.listar_clientes()), 0)

            # 5. Reactivación al crear cliente con mismo nombre
            reactivado = store.crear_cliente("Distribuidora Norte SRL", usuario="admin")
            self.assertEqual(reactivado.id, cli1.id)
            self.assertTrue(reactivado.activo)
            self.assertEqual(len(store.listar_clientes()), 1)

            # 6. Alias registrar_cliente
            cli2 = store.registrar_cliente("Ferretería Central", usuario="operador")
            self.assertEqual(cli2.nombre, "Ferretería Central")
            self.assertEqual(len(store.listar_clientes()), 2)

    def test_modal_gestion_clientes_flet_gui(self):
        from src.user_store import User
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            page = FakePage()
            o_store = OrderStore(tmp_path / "pedidos.sqlite3")
            o_store.crear_cliente("Cliente Inicial")

            interfaz = InterfazFlet(cast(ft.Page, cast(object, page)))
            interfaz.order_store = o_store
            interfaz.usuario_actual = User(1, "operario1", "operador", True)

            interfaz.mostrar_gestion_clientes()
            self.assertEqual(len(page.dialogos), 1)
            dialogo = page.dialogos[0]
            self.assertTrue(dialogo.modal)
            page.pop_dialog()
            self.assertEqual(len(page.dialogos), 0)

    def test_adaptacion_responsive_mobile_deteccion_y_layout(self):
        from src.user_store import User
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            page = FakePage()
            interfaz = InterfazFlet(cast(ft.Page, cast(object, page)))
            interfaz.usuario_actual = User(1, "admin", "administrador", True)

            # Por defecto (sin width numérico o desktop)
            self.assertFalse(interfaz.es_pantalla_movil)
            self.assertEqual(interfaz.ancho_adaptable(600), 600)

            # Simular pantalla de celular (400px ancho, 800px alto)
            page.width = 400
            page.height = 800
            self.assertTrue(interfaz.es_pantalla_movil)
            self.assertEqual(interfaz.ancho_adaptable(600), 376)  # 400 - 24
            self.assertEqual(interfaz.alto_adaptable(900), 740)   # 800 - 60

            # Construir en modo móvil
            interfaz.construir()
            self.assertEqual(len(page.controls), 1)
            # En móvil el root es un ft.Container fluido y no un Row con sidebar rígido
            contenedor_raiz = cast(ft.Container, page.controls[0])
            self.assertIsInstance(contenedor_raiz, ft.Container)
            # Todos los 18 comandos siguen disponibles para el usuario
            # 22 comandos de administración disponibles (Telegram y SMTP reservados a Master)
            self.assertEqual(len(interfaz.controles_tarea), 21)
            # Botón flotante más compacto
            self.assertEqual(interfaz.boton_chat_flotante.width, 110)

            # Verificar que los diálogos adaptan su ancho automáticamente
            dialogo_prueba = ft.AlertDialog(
                content=ft.Container(width=600, height=500, content=ft.Text("Contenido"))
            )
            page.show_dialog(dialogo_prueba)
            self.assertEqual(dialogo_prueba.content.width, 376)
            self.assertEqual(dialogo_prueba.content.height, 500)


if __name__ == "__main__":
    unittest.main()
