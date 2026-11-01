import socket
import unittest
from unittest.mock import MagicMock, patch

from src.tray_icon import (
    ESTADO_CLIENTE,
    ESTADO_DETENIDO,
    ESTADO_ERROR,
    ESTADO_INICIANDO,
    ESTADO_ONLINE,
    TrayIconServidor,
    _buscar_icono_base,
    _copiar_al_portapapeles,
    _obtener_ip_local,
    iniciar_icono_bandeja,
)


class TestTrayIcon(unittest.TestCase):
    def test_obtener_ip_local(self):
        ip = _obtener_ip_local()
        self.assertIsInstance(ip, str)
        self.assertTrue(len(ip) > 0)

    def test_buscar_icono_base(self):
        ruta = _buscar_icono_base()
        # En el entorno de desarrollo debería encontrar src/img/ultratech.png o assets/favicon.png
        if ruta is not None:
            self.assertTrue(ruta.exists())

    def test_generar_imagen_todos_los_estados(self):
        tray = TrayIconServidor(port=8550, https=True)
        for estado in (ESTADO_INICIANDO, ESTADO_ONLINE, ESTADO_ERROR, ESTADO_DETENIDO):
            img = tray._generar_imagen(estado)
            self.assertIsNotNone(img)
            self.assertEqual(img.size, (64, 64))

    def test_crear_menu(self):
        tray = TrayIconServidor(port=8550, https=True)
        menu = tray._crear_menu()
        self.assertIsNotNone(menu)

    def test_actualizar_estado(self):
        tray = TrayIconServidor(port=8550, https=True)
        mock_icon = MagicMock()
        tray._icon = mock_icon

        tray.actualizar_estado(ESTADO_ONLINE)
        self.assertEqual(tray.estado, ESTADO_ONLINE)
        self.assertIn("En línea", mock_icon.title)

        tray.actualizar_estado(ESTADO_ERROR)
        self.assertEqual(tray.estado, ESTADO_ERROR)
        self.assertIn("Servidor caído", mock_icon.title)

    @patch("src.tray_icon.subprocess.run")
    def test_copiar_al_portapapeles(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        res = _copiar_al_portapapeles("test")
        self.assertTrue(res)

    @patch("src.tray_icon.socket.create_connection")
    def test_verificar_servidor_activo(self, mock_conn):
        tray = TrayIconServidor(port=8550)
        mock_conn.return_value = MagicMock()
        self.assertTrue(tray._verificar_servidor_activo())

        mock_conn.side_effect = OSError("Conexión rechazada")
        self.assertFalse(tray._verificar_servidor_activo())

    @patch("src.tray_icon.TrayIconServidor.iniciar")
    def test_iniciar_icono_bandeja_helper(self, mock_iniciar):
        mock_iniciar.return_value = True
        tray = iniciar_icono_bandeja(port=8550, https=True)
        self.assertIsNotNone(tray)
        self.assertEqual(tray.port, 8550)

    def test_notificar_conexion_cliente(self):
        tray = TrayIconServidor(port=8550, https=False)
        tray.mostrar_notificacion = MagicMock()
        ua = "Mozilla/5.0 (Linux; Android 14) Chrome"

        # Conexiones locales no notifican
        self.assertFalse(tray.notificar_conexion_cliente("127.0.0.1", ua))
        tray.mostrar_notificacion.assert_not_called()

        # Primera conexión remota notifica con el tipo de dispositivo
        self.assertTrue(tray.notificar_conexion_cliente("192.168.1.50", ua))
        titulo, mensaje = tray.mostrar_notificacion.call_args[0]
        self.assertIn("conexión", titulo)
        self.assertIn("Android", mensaje)
        self.assertIn("192.168.1.50", mensaje)

        # Misma IP dentro del intervalo no repite el aviso
        self.assertFalse(tray.notificar_conexion_cliente("192.168.1.50", ua))
        self.assertEqual(tray.mostrar_notificacion.call_count, 1)

        # Otra IP sí notifica
        self.assertTrue(tray.notificar_conexion_cliente("192.168.1.51", ""))
        self.assertEqual(tray.mostrar_notificacion.call_count, 2)


    def test_clientes_conectados_http_y_ws(self):
        tray = TrayIconServidor(port=8550, https=False)
        self.assertEqual(tray.clientes_conectados(), [])

        # Local no cuenta
        tray.registrar_actividad_cliente("127.0.0.1")
        tray.cliente_ws_abierto("::1")
        self.assertEqual(tray.clientes_conectados(), [])

        # Actividad HTTP remota reciente cuenta
        tray.registrar_actividad_cliente("192.168.1.50")
        self.assertEqual(tray.clientes_conectados(), ["192.168.1.50"])

        # WebSocket abierto cuenta aunque expire la ventana HTTP
        tray.cliente_ws_abierto("192.168.1.51")
        tray._clientes_http["192.168.1.50"] -= 1000
        self.assertEqual(tray.clientes_conectados(), ["192.168.1.51"])

        # Al cerrar el WebSocket sigue visible hasta que expire la ventana
        tray.cliente_ws_cerrado("192.168.1.51")
        self.assertEqual(tray.clientes_conectados(), ["192.168.1.51"])
        tray._clientes_http["192.168.1.51"] -= 1000
        self.assertEqual(tray.clientes_conectados(), [])

    def test_estado_cliente_conectado(self):
        tray = TrayIconServidor(port=8550, https=False)
        img = tray._generar_imagen(ESTADO_CLIENTE)
        self.assertEqual(img.size, (64, 64))

        mock_icon = MagicMock()
        tray._icon = mock_icon
        tray.cliente_ws_abierto("192.168.1.50")
        tray.actualizar_estado(ESTADO_CLIENTE)
        self.assertEqual(tray.estado, ESTADO_CLIENTE)
        self.assertIn("1 dispositivo", mock_icon.title)
        self.assertIsNotNone(tray._crear_menu())


if __name__ == "__main__":
    unittest.main()
