import 'dart:async';
import 'package:http/http.dart' as http;
import '../models/server_config.dart';

/// Servicio especializado en pruebas de conectividad y sondeo de red local.
class NetworkService {
  final http.Client _client;

  NetworkService([http.Client? client]) : _client = client ?? http.Client();

  /// Comprueba la salud del servidor StockAgent realizando un GET rápido.
  Future<ConnectionResult> testConnection(ServerConfig config, {Duration timeout = const Duration(seconds: 4)}) async {
    if (!config.isValid) {
      return ConnectionResult.failure('La dirección IP del servidor no es válida.');
    }

    try {
      final uri = Uri.parse(config.fullUrl);
      final response = await _client.get(uri).timeout(timeout);

      // Si responde cualquier código HTTP menor a 500, el servidor está alcanzable
      if (response.statusCode >= 200 && response.statusCode < 500) {
        return ConnectionResult.success('¡Conexión establecida exitosamente con el servidor!');
      } else {
        return ConnectionResult.failure('El servidor respondió con código de estado HTTP ${response.statusCode}.');
      }
    } on TimeoutException {
      return ConnectionResult.failure('Tiempo de espera agotado. Verifica que ambos dispositivos estén en el mismo Wi-Fi.');
    } catch (e) {
      return ConnectionResult.failure('No se pudo conectar a ${config.fullUrl}. Comprueba que "iniciar_servidor_movil.bat" esté activo.');
    }
  }

  void dispose() {
    _client.close();
  }
}

/// Resultado tipado del sondeo de conectividad.
class ConnectionResult {
  final bool isSuccess;
  final String message;

  const ConnectionResult._({required this.isSuccess, required this.message});

  factory ConnectionResult.success(String message) => ConnectionResult._(isSuccess: true, message: message);
  factory ConnectionResult.failure(String message) => ConnectionResult._(isSuccess: false, message: message);
}
