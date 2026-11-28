import 'dart:io';

import 'package:crypto/crypto.dart';

import '../models/server_config.dart';
import 'storage_service.dart';

/// Servicio de validación TLS y fijación de certificado (Certificate Pinning / TOFU)
/// para conexiones HTTPS hacia el servidor StockAgent en red local.
class TlsPinningService {
  const TlsPinningService._();

  /// Convierte una lista de bytes en representación hexadecimal en minúsculas.
  static String bytesToHex(List<int> bytes) {
    final buffer = StringBuffer();
    for (final b in bytes) {
      buffer.write((b & 0xff).toRadixString(16).padLeft(2, '0'));
    }
    return buffer.toString();
  }

  /// Calcula el digest criptográfico SHA-256 estándar (64 caracteres hex en minúsculas).
  static String sha256Hex(List<int> data) {
    return sha256.convert(data).toString();
  }

  /// Obtiene la huella digital SHA-256 estándar del certificado X.509 (DER).
  static String certFingerprintHex(X509Certificate cert) {
    try {
      final derBytes = cert.der;
      if (derBytes.isNotEmpty) {
        return sha256Hex(derBytes);
      }
    } catch (_) {}
    return bytesToHex(cert.sha1);
  }

  /// Verifica que el certificado presentado por el servidor cumpla:
  /// 1. Vigencia temporal (`startValidity` <= ahora <= `endValidity`).
  /// 2. Coincidencia estricta del host con el configurado por el usuario.
  /// 3. Coincidencia con la huella fijada (`pinnedSha256`) o registro TOFU explícito.
  static bool verifyServerCertificate({
    required X509Certificate cert,
    required String host,
    required int port,
    required ServerConfig expectedConfig,
    String? pinnedSha256,
    void Function(String fingerprint)? onPinFirstUse,
  }) {
    final cleanHost = host.trim().toLowerCase();
    final expectedHost = expectedConfig.host.trim().toLowerCase();
    if (cleanHost.isEmpty || expectedHost.isEmpty || cleanHost != expectedHost) {
      return false;
    }

    final ahora = DateTime.now().toUtc();
    if (ahora.isBefore(cert.startValidity.toUtc()) ||
        ahora.isAfter(cert.endValidity.toUtc())) {
      return false;
    }

    final actualFp = certFingerprintHex(cert).toLowerCase();
    if (actualFp.isEmpty) {
      return false;
    }

    final pinEsperado =
        (pinnedSha256 ?? expectedConfig.certSha256 ?? '').trim().toLowerCase();
    if (pinEsperado.isNotEmpty) {
      return actualFp == pinEsperado;
    }

    if (onPinFirstUse != null) {
      onPinFirstUse(actualFp);
      return true;
    }

    return false;
  }

  /// Construye un [HttpClient] que aplica verificación de certificado fijado (TOFU / Pinning)
  /// en lugar de aceptar ciegamente cualquier certificado autofirmado.
  static HttpClient createPinnedHttpClient(
    StorageService storage, {
    bool allowTofu = true,
    Duration connectionTimeout = const Duration(seconds: 6),
  }) {
    final client = HttpClient()..connectionTimeout = connectionTimeout;
    client.badCertificateCallback = (X509Certificate cert, String host, int port) {
      final cfg = storage.loadConfig();
      final pinned = storage.getPinnedCertSha256(host) ?? cfg.certSha256;
      return verifyServerCertificate(
        cert: cert,
        host: host,
        port: port,
        expectedConfig: cfg,
        pinnedSha256: pinned,
        onPinFirstUse: allowTofu
            ? (fp) {
                storage.savePinnedCertSha256(host, fp);
              }
            : null,
      );
    };
    return client;
  }
}
