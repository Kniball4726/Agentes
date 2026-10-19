import unittest

from src.internal_chat import detectar_intencion


class InternalChatTests(unittest.TestCase):
    def test_detects_simulation_requests_in_natural_language(self):
        for mensaje in (
            "/simular",
            "Simula los documentos pendientes",
            "Quiero hacer una simulación",
        ):
            with self.subTest(mensaje=mensaje):
                self.assertEqual(detectar_intencion(mensaje), "simular")

    def test_detects_local_status_and_report_questions(self):
        self.assertEqual(detectar_intencion("¿Qué archivos están pendientes?"), "estado")
        self.assertEqual(detectar_intencion("Muéstrame los informes"), "informes")
        self.assertEqual(detectar_intencion("/estado"), "estado")
        self.assertEqual(detectar_intencion("/informes"), "informes")

    def test_detects_help_and_greetings(self):
        self.assertEqual(detectar_intencion("Hola"), "saludo")
        self.assertEqual(detectar_intencion("¿Qué puedes hacer?"), "ayuda")
        self.assertEqual(detectar_intencion("AYUDA"), "ayuda")

    def test_returns_unknown_for_unsupported_messages(self):
        self.assertEqual(detectar_intencion("¿Qué tiempo hace mañana?"), "desconocido")
        self.assertEqual(detectar_intencion("   "), "desconocido")


if __name__ == "__main__":
    unittest.main()
