/**
 * Controlador de escaneo de códigos de barra para cámara web y móvil.
 * Utiliza WebRTC (getUserMedia) y la BarcodeDetector API nativa.
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

function playBeep() {
  if (!audioCtx) return;
  try {
    if (audioCtx.state === "suspended") {
      audioCtx.resume();
    }
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(1200, audioCtx.currentTime);
    gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.12);
  } catch (e) {
    console.warn("AudioContext error:", e);
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
        // Error temporal de decodificación en cuadro
      }
    }
    requestAnimationFrame(detectLoop);
  };
  requestAnimationFrame(detectLoop);
}

/**
 * Procesa un código detectado emitiendo feedback y transmitiéndolo a la sesión.
 */
function onCodeDetected(code) {
  playBeep();
  if (navigator.vibrate) {
    navigator.vibrate(100);
  }

  const lastCodeEl = document.getElementById("lastCode");
  const detectionInfo = document.getElementById("detectionInfo");
  if (lastCodeEl) lastCodeEl.textContent = code;
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

window.addEventListener("DOMContentLoaded", initCamera);
