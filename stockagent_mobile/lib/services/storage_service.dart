import 'package:shared_preferences/shared_preferences.dart';
import '../models/server_config.dart';

/// Servicio de almacenamiento persistente para la configuración del servidor.
class StorageService {
  static const String _keyServerHost = 'stockagent_server_ip';
  static const String _keyServerPort = 'stockagent_server_port';
  static const String _keyProtocol = 'stockagent_protocol';

  final SharedPreferences _prefs;

  StorageService(this._prefs);

  /// Inicializa la instancia asíncrona de SharedPreferences
  static Future<StorageService> init() async {
    final prefs = await SharedPreferences.getInstance();
    return StorageService(prefs);
  }

  /// Carga la configuración actual del servidor
  ServerConfig loadConfig() {
    final host = _prefs.getString(_keyServerHost) ?? ServerConfig.defaultHost;
    final port = _prefs.getString(_keyServerPort) ?? ServerConfig.defaultPort;
    final protocol = _prefs.getString(_keyProtocol) ?? ServerConfig.defaultProtocol;

    return ServerConfig(
      host: host.isEmpty ? ServerConfig.defaultHost : host,
      port: port,
      protocol: protocol,
    );
  }

  /// Guarda una nueva configuración de servidor de forma persistente
  Future<void> saveConfig(ServerConfig config) async {
    await _prefs.setString(_keyServerHost, config.host.trim());
    await _prefs.setString(_keyServerPort, config.normalizedPort);
    await _prefs.setString(_keyProtocol, config.normalizedProtocol);
  }

  /// Verifica si ya existe una configuración válida almacenada
  bool hasValidConfig() {
    return loadConfig().isValid;
  }

  /// Limpia los datos guardados
  Future<void> clearConfig() async {
    await _prefs.remove(_keyServerHost);
    await _prefs.remove(_keyServerPort);
    await _prefs.remove(_keyProtocol);
  }
}
