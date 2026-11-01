import 'dart:async';
import 'dart:io';
import '../models/server_config.dart';

/// Servicio especializado en pruebas de conectividad y sondeo de red local.
class NetworkService {
  /// Cliente HTTP que acepta certificados autofirmados (el servidor StockAgent
  /// genera uno propio cuando se inicia en modo HTTPS).
  final HttpClient _client;

  NetworkService([HttpClient? client])
      : _client = client ?? (HttpClient()..badCertificateCallback = (cert, host, port) => true);

  /// Realiza un GET rápido a [config] y devuelve el código HTTP recibido.
  Future<int> _probe(ServerConfig config, Duration timeout) async {
    final uri = Uri.parse(config.fullUrl);
    final request = await _client.getUrl(uri).timeout(timeout);
    final response = await request.close().timeout(timeout);
    await response.drain<void>().timeout(timeout);
    return response.statusCode;
  }

  /// Comprueba la salud del servidor StockAgent. Si el protocolo configurado
  /// falla, prueba automáticamente con el otro (HTTP <-> HTTPS), porque el
  /// servidor solo atiende uno de los dos según el .bat con el que se inició.
  Future<ConnectionResult> testConnection(
    ServerConfig config, {
    Duration timeout = const Duration(seconds: 4),
  }) async {
    if (!config.isValid) {
      return ConnectionResult.failure('La dirección IP o nombre del servidor no es válida.');
    }

    final alternate = config.copyWith(
      protocol: config.normalizedProtocol == 'https' ? 'http' : 'https',
    );

    Object? firstError;
    int? firstStatus;

    for (final candidate in [config, alternate]) {
      try {
        final status = await _probe(candidate, timeout);
        if (status >= 200 && status < 500) {
          final cambio = candidate.normalizedProtocol != config.normalizedProtocol;
          return ConnectionResult.success(
            cambio
                ? '¡Conexión establecida! El servidor usa ${candidate.normalizedProtocol.toUpperCase()}; '
                    'se ajustó el protocolo automáticamente.'
                : '¡Conexión establecida exitosamente con el servidor!',
            resolvedConfig: candidate,
          );
        }
        firstStatus ??= status;
      } catch (e) {
        firstError ??= e;
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
    if (e is HandshakeException) {
      return 'Error de certificado SSL/TLS al conectar a ${config.fullUrl}.';
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

  /// Configuración que realmente respondió (puede diferir en el protocolo).
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
