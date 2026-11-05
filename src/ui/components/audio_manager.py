"""Módulo para la síntesis de audio y feedback auditivo mediante Web Audio API."""

from __future__ import annotations
from typing import Any

TONOS_FRECUENCIAS = {
    "exito": [(880, 0, 0.14, 0.12, "sine")],
    "notificacion": [(587.33, 0, 0.10, 0.08, "sine"), (880.0, 0.08, 0.15, 0.09, "sine")],
    "colaborativo": [(587.33, 0, 0.10, 0.08, "sine"), (880.0, 0.08, 0.15, 0.09, "sine")],
    "cierre": [
        (523.25, 0, 0.12, 0.10, "triangle"),
        (659.25, 0.09, 0.12, 0.10, "triangle"),
        (783.99, 0.18, 0.22, 0.11, "triangle"),
    ],
    "campana": [
        (523.25, 0, 0.12, 0.10, "triangle"),
        (659.25, 0.09, 0.12, 0.10, "triangle"),
        (783.99, 0.18, 0.22, 0.11, "triangle"),
    ],
    "quiebre": [
        (440, 0, 0.15, 0.12, "sawtooth"),
        (330, 0.14, 0.20, 0.12, "sawtooth"),
    ],
    "error": [
        (280, 0, 0.15, 0.18, "triangle"),
        (200, 0.17, 0.18, 0.18, "triangle"),
    ],
}


def reproducir_sonido_web(interfaz: Any, tipo: str = "exito") -> None:
    """Emite un feedback sonoro breve sintetizado mediante Web Audio API en el navegador o cliente Flet."""
    try:
        page = getattr(interfaz, "page", None)
        if not page or not hasattr(page, "run_js"):
            return

        secuencia = TONOS_FRECUENCIAS.get(tipo, TONOS_FRECUENCIAS["error"])
        pasos_js = "\n".join(
            f"playTone({f}, {d}, {dur}, {v}, '{w}');"
            for f, d, dur, v, w in secuencia
        )
        js = f"""
        (() => {{
            try {{
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
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
            }} catch(e) {{}}
        }})()
        """
        page.run_js(js)
    except Exception:
        pass
