"""Módulo para la síntesis de audio y feedback auditivo mediante Web Audio API y fallback nativo."""

from __future__ import annotations

from functools import lru_cache
import io
import itertools
import math
import struct
import sys
from typing import Any
import wave
import weakref

import flet as ft

_AUDIO_SEQ = itertools.count(1)
_SP_AUDIO_KEY = "__sa_audio_event"

TONOS_FRECUENCIAS: dict[str, list[tuple[float, float, float, float, str]]] = {
    "exito": [(880.0, 0.0, 0.14, 0.12, "sine")],
    "notificacion": [(587.33, 0.0, 0.10, 0.08, "sine"), (880.0, 0.08, 0.15, 0.09, "sine")],
    "colaborativo": [(587.33, 0.0, 0.10, 0.08, "sine"), (880.0, 0.08, 0.15, 0.09, "sine")],
    "cierre": [
        (523.25, 0.0, 0.12, 0.10, "triangle"),
        (659.25, 0.09, 0.12, 0.10, "triangle"),
        (783.99, 0.18, 0.22, 0.11, "triangle"),
    ],
    "campana": [
        (783.99, 0.0, 0.09, 0.14, "triangle"),
        (1046.50, 0.08, 0.20, 0.15, "sine"),
    ],
    "quiebre": [
        (440.0, 0.0, 0.15, 0.12, "sawtooth"),
        (330.0, 0.14, 0.20, 0.12, "sawtooth"),
    ],
    "error": [
        (280.0, 0.0, 0.15, 0.18, "triangle"),
        (200.0, 0.17, 0.18, 0.18, "triangle"),
    ],
}


@lru_cache(maxsize=16)
def _sintetizar_wav_tono(tipo: str) -> bytes:
    """Genera un WAV PCM mono en memoria para reproducción asíncrona en escritorio."""
    secuencia = TONOS_FRECUENCIAS.get(tipo, TONOS_FRECUENCIAS["notificacion"])
    sample_rate = 22050
    duracion_total = max(d + dur for _, d, dur, _, _ in secuencia) + 0.04
    total_muestras = max(1, int(sample_rate * duracion_total))
    muestras = [0.0] * total_muestras

    for freq, delay, dur, vol, onda in secuencia:
        inicio = max(0, int(delay * sample_rate))
        n_nota = max(1, int(dur * sample_rate))
        ataque = max(1, int(0.008 * sample_rate))
        for i in range(n_nota):
            idx = inicio + i
            if idx >= total_muestras:
                break
            t = i / sample_rate
            fase = freq * t
            if onda == "triangle":
                val = 4.0 * abs((fase % 1.0) - 0.5) - 1.0
            elif onda == "sawtooth":
                val = 2.0 * (fase % 1.0) - 1.0
            else:
                val = math.sin(2.0 * math.pi * fase)
            env_atk = min(1.0, i / ataque)
            env_dec = math.exp(-5.5 * (i / max(1, n_nota)))
            muestras[idx] += val * vol * env_atk * env_dec

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for m in muestras:
            clamped = max(-0.95, min(0.95, m))
            frames.extend(struct.pack("<h", int(clamped * 32767)))
        wf.writeframes(bytes(frames))
    return buf.getvalue()


def _obtener_shared_prefs(interfaz: Any, page: Any) -> Any:
    """Obtiene o registra el servicio ft.SharedPreferences en la página actual."""
    sp = getattr(interfaz, "shared_prefs", None)
    if sp is None and hasattr(page, "services") and isinstance(page.services, list):
        for s in page.services:
            if isinstance(s, ft.SharedPreferences):
                sp = s
                break
    if sp is None and hasattr(page, "services") and isinstance(page.services, list):
        try:
            sp = ft.SharedPreferences()
        except Exception:
            sp = None

    if sp is not None:
        if hasattr(page, "services") and isinstance(page.services, list):
            if not any(s is sp for s in page.services):
                page.services.append(sp)
        reg = getattr(page, "_services", None)
        if type(reg).__name__ == "ServiceRegistry":
            if getattr(reg, "parent", None) is None and isinstance(page, ft.Page):
                try:
                    reg._parent = weakref.ref(page)
                except Exception:
                    pass
            if hasattr(reg, "_services") and not any(s is sp for s in reg._services):
                try:
                    reg.register_service(sp)
                except Exception:
                    pass
        if getattr(sp, "parent", None) is None:
            if isinstance(page, ft.Page):
                try:
                    sp._parent = weakref.ref(page)
                except Exception:
                    pass
            try:
                page.update()
            except Exception:
                pass
        if interfaz is not None:
            try:
                interfaz.shared_prefs = sp
            except Exception:
                pass
    return sp


def registrar_servicio_audio_web(interfaz: Any) -> None:
    """Pre-registra SharedPreferences al abrir sesión web para emitir sonidos sin latencia."""
    page = getattr(interfaz, "page", None)
    if page is not None and getattr(page, "web", False) is True:
        _obtener_shared_prefs(interfaz, page)


def reproducir_sonido_web(interfaz: Any, tipo: str = "exito") -> None:
    """Emite un feedback sonoro breve en cliente Web (Web Audio API) o escritorio Windows."""
    try:
        page = getattr(interfaz, "page", None)
        if not page:
            return

        tipo_limpio = tipo if tipo in TONOS_FRECUENCIAS else "notificacion"

        run_js = getattr(page, "run_js", None)
        if callable(run_js):
            secuencia = TONOS_FRECUENCIAS[tipo_limpio]
            pasos_js = "\n".join(
                f"playTone({f}, {d}, {dur}, {v}, '{w}');"
                for f, d, dur, v, w in secuencia
            )
            js = f"""
            (() => {{
                try {{
                    const AudioCtx = window.AudioContext || window.webkitAudioContext;
                    if (!AudioCtx) return;
                    const ctx = window.__saAudioCtx || (window.__saAudioCtx = new AudioCtx());
                    const playAll = () => {{
                        const playTone = (freq, delay, dur, vol, wave) => {{
                            const osc = ctx.createOscillator();
                            const gain = ctx.createGain();
                            osc.connect(gain);
                            gain.connect(ctx.destination);
                            osc.type = wave || 'sine';
                            osc.frequency.setValueAtTime(freq, ctx.currentTime + delay);
                            gain.gain.setValueAtTime(vol || 0.12, ctx.currentTime + delay);
                            gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + delay + dur);
                            osc.start(ctx.currentTime + delay);
                            osc.stop(ctx.currentTime + delay + dur);
                        }};
                        {pasos_js}
                    }};
                    if (ctx.state === 'suspended') {{
                        ctx.resume().then(playAll).catch(playAll);
                    }} else {{
                        playAll();
                    }}
                }} catch(e) {{}}
            }})()
            """
            run_js(js)
            return

        es_flet_real = type(page).__module__.startswith("flet.")
        if getattr(page, "web", False) is True:
            sp = _obtener_shared_prefs(interfaz, page)
            run_task = getattr(page, "run_task", None)
            if sp is not None and callable(run_task):
                payload = f"{tipo_limpio}:{next(_AUDIO_SEQ)}"

                async def _emitir_web() -> None:
                    try:
                        await sp.set(_SP_AUDIO_KEY, payload)
                    except Exception:
                        pass

                run_task(_emitir_web)
            return

        if es_flet_real and getattr(page, "web", True) is False and sys.platform == "win32":
            import winsound

            wav_bytes = _sintetizar_wav_tono(tipo_limpio)
            winsound.PlaySound(wav_bytes, winsound.SND_MEMORY | winsound.SND_ASYNC)
    except Exception:
        pass
