/**
 * Definiciones de tipos ambientales para los scripts web y PWA de StockAgent.
 * Utilizadas exclusivamente en tiempo de análisis estático (checkJs / tsc --noEmit).
 */

interface OfflineScanItem {
  code: string;
  timestamp: number;
}

interface ScannedBarcodePayload {
  code: string;
  timestamp: number;
  offline?: boolean;
}

interface BarcodeScannedMessage {
  type: "BARCODE_SCANNED";
  code: string;
  offline?: boolean;
}

interface DetectedBarcode {
  rawValue?: string;
  format?: string;
}

interface BarcodeDetectorOptions {
  formats?: string[];
}

interface BarcodeDetector {
  detect(image: ImageBitmapSource): Promise<DetectedBarcode[]>;
}

declare var BarcodeDetector: {
  prototype: BarcodeDetector;
  new (options?: BarcodeDetectorOptions): BarcodeDetector;
};

interface Window {
  BarcodeDetector?: typeof BarcodeDetector;
  webkitAudioContext?: typeof AudioContext;
}

interface MediaTrackCapabilities {
  torch?: boolean;
}

interface MediaTrackConstraintSet {
  torch?: boolean;
}
