"""Cliente mínimo para conversar con Gemini sin persistir el historial en el servidor."""

import json
import os
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
_MODELO = "gemini-3.8-flash"
_INSTRUCCIONES = (
    "Eres el asistente conversacional en español de una aplicación local de "
    "control de stock y remitos. Responde consultas y explica cómo usar la "
    "aplicación. No tienes acceso al catálogo, documentos ni archivos locales. "
    "No afirmes haber ejecutado operaciones. El chat solo permite consultas "
    "y simulaciones; nunca puede actualizar el stock, generar informes reales, "
    "archivar, mover ni restaurar documentos."
)


class GeminiChatClient:
    def __init__(
        self,
        api_key: str | None = None,
        urlopen_fn: Callable = urlopen,
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY")
        self.urlopen_fn = urlopen_fn
        self.timeout = timeout

    def responder(self, historial: list[dict[str, str]]) -> str:
        if not self.api_key:
            raise RuntimeError(
                "No se configuró GEMINI_API_KEY. Agrégala al archivo .env "
                "de la carpeta raíz del proyecto."
            )
        if not historial:
            raise ValueError("El mensaje para Gemini no puede estar vacío.")

        entrada = "\n".join(
            f"{'Usuario' if mensaje['role'] == 'user' else 'Asistente'}: "
            f"{mensaje['content']}"
            for mensaje in historial
        )
        cuerpo = json.dumps(
            {
                "model": _MODELO,
                "system_instruction": _INSTRUCCIONES,
                "input": entrada,
                "store": False,
            }
        ).encode("utf-8")
        solicitud = Request(
            _ENDPOINT,
            data=cuerpo,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )

        try:
            with self.urlopen_fn(solicitud, timeout=self.timeout) as respuesta:
                datos = json.loads(respuesta.read().decode("utf-8"))
        except HTTPError as error:
            detalle = self._detalle_error(error.read())
            raise RuntimeError(
                f"Gemini respondió con HTTP {error.code}: "
                f"{detalle or error.reason}"
            ) from error
        except URLError as error:
            raise RuntimeError(
                f"No se pudo conectar con Gemini: {error.reason}"
            ) from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RuntimeError("Gemini devolvió una respuesta inválida.") from error

        if datos.get("status") not in (None, "completed"):
            raise RuntimeError(
                f"Gemini no completó la respuesta (estado: {datos['status']})."
            )

        textos = [
            bloque["text"]
            for paso in datos.get("steps", [])
            if paso.get("type") == "model_output"
            for bloque in paso.get("content", [])
            if bloque.get("type") == "text" and bloque.get("text")
        ]
        if not textos:
            raise RuntimeError("Gemini no devolvió texto en su respuesta.")
        return "\n".join(textos)

    @staticmethod
    def _detalle_error(contenido: bytes) -> str:
        try:
            datos = json.loads(contenido.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return ""
        return datos.get("error", {}).get("message", "")
