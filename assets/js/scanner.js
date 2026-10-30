/**
 * Controlador de escaneo de códigos de barra para cámara web y móvil.
 * Utiliza WebRTC (getUserMedia), la BarcodeDetector API nativa
 * e incorpora cola resiliente Offline-First ante microcortes de red.
 */

let currentStream = null;
let currentFacingMode = "environment";
let torchActive = false;
let track = null;
let barcodeDetector = null;
let scanning = true;
let lastScannedText = "";
let lastScanTime = 0;

// Sintetizador de audio para confirmación de escaneo
const AudioContextClass = window.AudioContext || window.webkitAudioContext;
const audioCtx = AudioContextClass ? new AudioContextClass() : null;

function playBeep(frequency = 1200, duration = 0.12) {
  if (!audioCtx) return;
  try {
    if (audioCtx.state === "suspended") {
      audioCtx.resume();
    }
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(frequency, audioCtx.currentTime);
    gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + duration);
  } catch (e) {
    console.warn("AudioContext error:", e);
  }
}

/**
 * Gestión de la Cola Resiliente Local (Offline Scan Queue)
 */
function obtenerColaOffline() {
  try {
    const q = localStorage.getItem("stockagent_offline_scan_queue");
    return q ? JSON.parse(q) : [];
  } catch (e) {
    return [];
  }
}

function guardarEnColaOffline(code) {
  const q = obtenerColaOffline();
  q.push({ code: code, timestamp: Date.now() });
  try {
    localStorage.setItem("stockagent_offline_scan_queue", JSON.stringify(q));
  } catch (e) {}
  actualizarIndicadorRed();
}

function sincronizarColaOffline() {
  const q = obtenerColaOffline();
  if (!q || q.length === 0) return;
  console.log(`[PWA] Sincronizando ${q.length} escaneos acumulados en offline...`);

  for (const item of q) {
    localStorage.setItem(
      "stockagent_scanned_barcode",
      JSON.stringify({ code: item.code, timestamp: item.timestamp, offline: true })
    );
    if (window.opener && !window.opener.closed) {
      window.opener.postMessage({ type: "BARCODE_SCANNED", code: item.code, offline: true }, "*");
    }
  }

  localStorage.removeItem("stockagent_offline_scan_queue");
  const detectionInfo = document.getElementById("detectionInfo");
  if (detectionInfo) {
    detectionInfo.textContent = `✅ Red restablecida: ¡${q.length} código(s) sincronizados con el servidor!`;
    detectionInfo.style.color = "#22c55e";
  }
  actualizarIndicadorRed();
}

function actualizarIndicadorRed() {
  const q = obtenerColaOffline();
  const isOffline = !navigator.onLine;
  let badge = document.getElementById("netStatusBadge");

  if (!badge) {
    badge = document.createElement("div");
    badge.id = "netStatusBadge";
    badge.style.cssText =
      "font-size: 11px; padding: 4px 8px; border-radius: 12px; margin-top: 6px; font-weight: 600; text-align: center; display: inline-block;";
    const statusCard = document.querySelector(".status-card");
    if (statusCard) statusCard.appendChild(badge);
  }

  if (isOffline) {
    badge.textContent = `⚠️ Sin WiFi · ${q.length} escaneo(s) guardados en cola local`;
    badge.style.background = "#78350f";
    badge.style.color = "#fef3c7";
  } else if (q.length > 0) {
    badge.textContent = `🔄 Sincronizando ${q.length} escaneo(s)...`;
    badge.style.background = "#1e3a8a";
    badge.style.color = "#dbeafe";
    sincronizarColaOffline();
  } else {
    badge.textContent = "🟢 En línea · Conexión activa";
    badge.style.background = "#14532d";
    badge.style.color = "#dcfce7";
  }
}

/**
 * Inicializa el flujo de video de la cámara trasera o frontal.
 */
async function initCamera() {
  if (currentStream) {
    currentStream.getTracks().forEach((t) => t.stop());
  }
  const detectionInfo = document.getElementById("detectionInfo");
  try {
    const constraints = {
      video: {
        facingMode: { ideal: currentFacingMode },
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
    };
    currentStream = await navigator.mediaDevices.getUserMedia(constraints);
    const video = document.getElementById("video");
    video.srcObject = currentStream;
    track = currentStream.getVideoTracks()[0];
    await video.play();
    startDetection();
    actualizarIndicadorRed();
  } catch (err) {
    if (detectionInfo) {
      detectionInfo.textContent = "Permiso de cámara denegado o no disponible: " + err.message;
      detectionInfo.style.color = "#ef4444";
    }
  }
}

/**
 * Inicia el bucle de detección de códigos de barra.
 */
async function startDetection() {
  if ("BarcodeDetector" in window) {
    try {
      barcodeDetector = new window.BarcodeDetector({
        formats: ["code_128", "code_39", "ean_13", "ean_8", "qr_code", "upc_a", "upc_e"],
      });
    } catch (e) {
      console.warn("Formatos de BarcodeDetector no soportados:", e);
    }
  }

  const video = document.getElementById("video");
  const detectLoop = async () => {
    if (!scanning) return;
    if (barcodeDetector && video.readyState === video.HAVE_ENOUGH_DATA) {
      try {
        const barcodes = await barcodeDetector.detect(video);
        if (barcodes.length > 0) {
          const code = barcodes[0].rawValue.trim();
          const now = Date.now();
          if (code && (code !== lastScannedText || now - lastScanTime > 1800)) {
            onCodeDetected(code);
            lastScannedText = code;
            lastScanTime = now;
          }
        }
      } catch (e) {
        // Error temporal de cuadro
      }
    }
    requestAnimationFrame(detectLoop);
  };
  requestAnimationFrame(detectLoop);
}

/**
 * Procesa un código detectado emitiendo feedback y transmitiéndolo a la sesión.
 * Si no hay red, lo resguarda en la cola offline local.
 */
function onCodeDetected(code) {
  playBeep();
  if (navigator.vibrate) {
    navigator.vibrate(100);
  }

  const lastCodeEl = document.getElementById("lastCode");
  const detectionInfo = document.getElementById("detectionInfo");
  if (lastCodeEl) lastCodeEl.textContent = code;

  const isOffline = !navigator.onLine;

  if (isOffline) {
    guardarEnColaOffline(code);
    if (detectionInfo) {
      detectionInfo.textContent = "⚠️ Guardado en cola local (sin WiFi). Se sincronizará al reconectar.";
      detectionInfo.style.color = "#f59e0b";
    }
    return;
  }

  if (detectionInfo) {
    detectionInfo.textContent = "¡Código leído y transmitido!";
    detectionInfo.style.color = "#22c55e";
  }

  // 1. Notificar a través de LocalStorage para sincronizar con la ventana de StockAgent
  localStorage.setItem(
    "stockagent_scanned_barcode",
    JSON.stringify({
      code: code,
      timestamp: Date.now(),
    })
  );

  // 2. Si se abrió como ventana secundaria / popup, emitir postMessage directo
  if (window.opener && !window.opener.closed) {
    window.opener.postMessage({ type: "BARCODE_SCANNED", code: code }, "*");
  }

  actualizarIndicadorRed();
}

/**
 * Envío manual de código ingresado por teclado.
 */
function enviarManual() {
  const inp = document.getElementById("inputManual");
  if (!inp) return;
  const val = inp.value.trim();
  if (val) {
    onCodeDetected(val);
    inp.value = "";
  }
}

/**
 * Alterna la linterna del dispositivo móvil si el hardware lo soporta.
 */
async function toggleFlash() {
  if (track && track.getCapabilities && track.getCapabilities().torch) {
    torchActive = !torchActive;
    try {
      await track.applyConstraints({ advanced: [{ torch: torchActive }] });
    } catch (e) {
      console.warn("No se pudo alternar la linterna:", e);
    }
  } else {
    alert("La linterna no está disponible en este dispositivo o cámara.");
  }
}

/**
 * Cambia entre la cámara frontal y trasera.
 */
function switchCamera() {
  currentFacingMode = currentFacingMode === "environment" ? "user" : "environment";
  initCamera();
}

// Event Listeners de Conectividad y PWA
window.addEventListener("online", () => {
  console.log("[PWA] Conexión WiFi reanudada");
  actualizarIndicadorRed();
  sincronizarColaOffline();
});

window.addEventListener("offline", () => {
  console.log("[PWA] Conexión WiFi perdida");
  actualizarIndicadorRed();
});

// Registro de Service Worker PWA
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js", { scope: "/" })
      .then((reg) => console.log("[PWA] Service Worker activo:", reg.scope))
      .catch((err) => console.warn("[PWA] Aviso registro Service Worker:", err));
  });
}

window.addEventListener("DOMContentLoaded", initCamera);
