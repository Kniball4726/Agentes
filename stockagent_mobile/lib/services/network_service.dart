import 'dart:async';
import 'dart:io';
import '../models/server_config.dart';
import 'storage_service.dart';
import 'tls_pinning_service.dart';

/// Servicio especializado en pruebas de conectividad y sondeo seguro de red local.
class NetworkService {
  final HttpClient _client;
  final StorageService? storageService;
  ServerConfig? _activeProbeConfig;
  String? _lastPinnedFingerprint;

  NetworkService({
    HttpClient? client,
    this.storageService,
  }) : _client = client ?? HttpClient() {
    if (client == null) {
      _client.badCertificateCallback = (X509Certificate cert, String host, int port) {
        final expected = _activeProbeConfig ??
            storageService?.loadConfig() ??
            ServerConfig(host: host, port: port.toString(), protocol: 'https');
        final existingPin = storageService?.getPinnedCertSha256(host) ?? expected.certSha256;
        return TlsPinningService.verifyServerCertificate(
          cert: cert,
          host: host,
          port: port,
          expectedConfig: expected,
          pinnedSha256: existingPin,
          onPinFirstUse: (fp) {
            _lastPinnedFingerprint = fp;
          },
        );
      };
    }
  }

  /// Realiza un GET rápido a `/api/v1/sistema/ping` o raíz de [config] y devuelve el código HTTP.
  Future<int> _probe(ServerConfig config, Duration timeout) async {
    _activeProbeConfig = config;
    _lastPinnedFingerprint = config.certSha256 ?? storageService?.getPinnedCertSha256(config.host);
    final uri = Uri.parse('${config.fullUrl}/api/v1/sistema/ping');
    final request = await _client.getUrl(uri).timeout(timeout);
    final response = await request.close().timeout(timeout);
    await response.drain<void>().timeout(timeout);
    return response.statusCode;
  }

  /// Comprueba la salud del servidor StockAgent aplicando prevención de downgrade TLS:
  /// - Si el usuario seleccionó HTTPS, NUNCA degrada silenciosamente a HTTP en texto plano.
  /// - Si el usuario seleccionó HTTP, intenta primero elevar a HTTPS de forma segura y solo
  ///   usa HTTP si el usuario lo solicitó explícitamente y HTTPS no está activo.
  Future<ConnectionResult> testConnection(
    ServerConfig config, {
    Duration timeout = const Duration(seconds: 4),
  }) async {
    if (!config.isValid) {
      return ConnectionResult.failure('La dirección IP o nombre del servidor no es válida.');
    }

    final List<ServerConfig> candidates = config.normalizedProtocol == 'https'
        ? <ServerConfig>[config]
        : <ServerConfig>[
            config.copyWith(protocol: 'https'),
            config,
          ];

    Object? firstError;
    int? firstStatus;

    for (final candidate in candidates) {
      try {
        final status = await _probe(candidate, timeout);
        if (status >= 200 && status < 500) {
          final resolved = candidate.normalizedProtocol == 'https'
              ? candidate.copyWith(certSha256: _lastPinnedFingerprint ?? candidate.certSha256)
              : candidate;
          if (resolved.normalizedProtocol == 'https' &&
              resolved.certSha256 != null &&
              resolved.certSha256!.isNotEmpty) {
            await storageService?.savePinnedCertSha256(resolved.host, resolved.certSha256!);
          }
          final upgradedToHttps =
              config.normalizedProtocol == 'http' && resolved.normalizedProtocol == 'https';
          return ConnectionResult.success(
            upgradedToHttps
                ? '¡Conexión segura establecida! El servidor soporta HTTPS; se elevó el protocolo automáticamente.'
                : '¡Conexión establecida exitosamente con el servidor (${resolved.normalizedProtocol.toUpperCase()})!',
            resolvedConfig: resolved,
          );
        }
        firstStatus ??= status;
      } catch (e) {
        if (candidate.normalizedProtocol == config.normalizedProtocol) {
          firstError = e;
        } else {
          firstError ??= e;
        }
      }
    }

    if (firstStatus != null) {
      return ConnectionResult.failure('El servidor respondió con código HTTP $firstStatus.');
    }
    return ConnectionResult.failure(_describeError(firstError, config));
  }

  String _describeError(Object? e, ServerConfig config) {
    if (e is TimeoutException) {
      return 'Tiempo de espera agotado al conectar a ${config.fullUrl}.\n'
          '• Verifica que el celular y la PC estén en la misma red Wi-Fi.\n'
          '• Asegúrate de que "iniciar_servidor_movil.bat" esté abierto en la PC.\n'
          '• Si el router tiene "aislamiento de clientes/AP isolation", desactívalo.';
    }
    if (e is HandshakeException || e is TlsException) {
      return 'Error de validación SSL/TLS al conectar a ${config.fullUrl}.\n'
          '• Si el certificado del servidor cambió, vuelve a guardar la configuración o verifica que HTTPS esté activo.';
    }
    if (e is SocketException) {
      return 'No se pudo conectar a ${config.fullUrl}.\n'
          '(${e.message}${e.osError != null ? ' - ${e.osError!.message}' : ''})\n'
          'Comprueba la IP, que el puerto ${config.normalizedPort} esté libre y el Firewall configurado.';
    }
    return 'Error al conectar con ${config.fullUrl}: $e\n'
        'Verifica que "iniciar_servidor_movil.bat" esté en ejecución en tu PC.';
  }

  void dispose() {
    _client.close(force: true);
  }
}

/// Resultado tipado del sondeo de conectividad.
class ConnectionResult {
  final bool isSuccess;
  final String message;

  /// Configuración que realmente respondió (incluyendo huella certSha256 en HTTPS).
  final ServerConfig? resolvedConfig;

  const ConnectionResult._({
    required this.isSuccess,
    required this.message,
    this.resolvedConfig,
  });

  factory ConnectionResult.success(String message, {ServerConfig? resolvedConfig}) =>
      ConnectionResult._(isSuccess: true, message: message, resolvedConfig: resolvedConfig);
  factory ConnectionResult.failure(String message) =>
      ConnectionResult._(isSuccess: false, message: message);
}
