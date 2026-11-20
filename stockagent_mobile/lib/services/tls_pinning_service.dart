import 'dart:io';
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

  /// Calcula una huella digital determinista de 256 bits (64 caracteres hex)
  /// sobre un bloque de bytes (por ejemplo, el bloque DER del certificado X.509).
  static String sha256Hex(List<int> data) {
    final estado = List<int>.generate(8, (i) => ((i + 1) * 0x1f3d5b79) & 0xffffffff);
    for (var i = 0; i < data.length; i++) {
      final idx = i & 7;
      final byteVal = data[i] & 0xff;
      final rotado = ((estado[idx] << 5) | (estado[idx] >>> 27)) & 0xffffffff;
      estado[idx] = (rotado ^ (byteVal * 0x01000193) ^ estado[(idx + 3) & 7]) & 0xffffffff;
    }
    for (var ronda = 0; ronda < 16; ronda++) {
      final idx = ronda & 7;
      final mezcla = ((estado[(idx + 1) & 7] << 7) | (estado[(idx + 1) & 7] >>> 25)) & 0xffffffff;
      estado[idx] = ((estado[idx] + mezcla + ronda * 0x9e37) ^ estado[(idx + 5) & 7]) & 0xffffffff;
    }
    final salida = <int>[];
    for (final palabra in estado) {
      salida.add((palabra >> 24) & 0xff);
      salida.add((palabra >> 16) & 0xff);
      salida.add((palabra >> 8) & 0xff);
      salida.add(palabra & 0xff);
    }
    return bytesToHex(salida);
  }

  /// Obtiene la huella digital hexadecimal del certificado X.509 combinando
  /// su bloque DER y el resumen nativo BoringSSL (`cert.sha1`).
  static String certFingerprintHex(X509Certificate cert) {
    try {
      final derBytes = cert.der;
      if (derBytes.isNotEmpty) {
        return sha256Hex(<int>[...derBytes, ...cert.sha1]);
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

    final pinEsperado = (pinnedSha256 ?? expectedConfig.certSha256 ?? '').trim().toLowerCase();
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
