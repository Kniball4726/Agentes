import io
import json
import unittest
from urllib.error import HTTPError

from src.gemini_chat import GeminiChatClient


class GeminiChatTests(unittest.TestCase):
    def test_sends_bounded_conversation_without_server_storage(self):
        respuesta = io.BytesIO(
            json.dumps(
                {
                    "status": "completed",
                    "steps": [
                        {
                            "type": "model_output",
                            "content": [{"type": "text", "text": "Hola."}],
                        }
                    ],
                }
            ).encode("utf-8")
        )
        llamadas = []

        def abrir(solicitud, timeout):
            llamadas.append((solicitud, timeout))
            return respuesta

        cliente = GeminiChatClient(
            api_key="clave-de-prueba", urlopen_fn=abrir, timeout=9
        )
        historial = [
            {"role": "user", "content": "¿Qué puedes hacer?"},
            {"role": "assistant", "content": "Puedo responder consultas."},
            {"role": "user", "content": "¿Puedes ver mi catálogo?"},
        ]

        self.assertEqual(cliente.responder(historial), "Hola.")
        solicitud, timeout = llamadas[0]
        cuerpo = json.loads(solicitud.data.decode("utf-8"))
        self.assertEqual(timeout, 9)
        self.assertEqual(solicitud.get_header("X-goog-api-key"), "clave-de-prueba")
        self.assertFalse(cuerpo["store"])
        self.assertIn("Usuario: ¿Qué puedes hacer?", cuerpo["input"])
        self.assertIn("Asistente: Puedo responder consultas.", cuerpo["input"])
        self.assertIn("No tienes acceso al catálogo", cuerpo["system_instruction"])

    def test_reports_missing_api_key(self):
        cliente = GeminiChatClient(api_key="")

        with self.assertRaisesRegex(RuntimeError, "GEMINI_API_KEY"):
            cliente.responder([{"role": "user", "content": "Hola"}])

    def test_reports_gemini_api_errors(self):
        contenido = json.dumps(
            {"error": {"message": "La clave no es válida."}}
        ).encode("utf-8")

        def rechazar(_solicitud, timeout):
            raise HTTPError(
                "https://generativelanguage.googleapis.com",
                400,
                "Bad Request",
                {},
                io.BytesIO(contenido),
            )

        cliente = GeminiChatClient(api_key="clave-de-prueba", urlopen_fn=rechazar)

        with self.assertRaisesRegex(RuntimeError, "HTTP 400: La clave no es válida"):
            cliente.responder([{"role": "user", "content": "Hola"}])


if __name__ == "__main__":
    unittest.main()
