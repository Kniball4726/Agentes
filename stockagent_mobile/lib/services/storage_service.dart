import 'package:shared_preferences/shared_preferences.dart';
import '../models/server_config.dart';

/// Servicio de almacenamiento persistente para la configuración del servidor StockAgent.
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

  /// Comprueba si el usuario ya configuró explícitamente la conexión al servidor
  bool get isConfigured {
    final host = _prefs.getString(_keyServerHost);
    return host != null && host.trim().isNotEmpty;
  }

  /// Verifica si existe una configuración guardada y válida
  bool hasValidConfig() {
    return isConfigured && loadConfig().isValid;
  }

  /// Carga la configuración actual del servidor o una por defecto
  ServerConfig loadConfig() {
    final host = _prefs.getString(_keyServerHost);
    final port = _prefs.getString(_keyServerPort) ?? ServerConfig.defaultPort;
    final protocol = _prefs.getString(_keyProtocol) ?? ServerConfig.defaultProtocol;

    return ServerConfig(
      host: host != null && host.trim().isNotEmpty ? host.trim() : ServerConfig.defaultHost,
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

  /// Limpia los datos guardados
  Future<void> clearConfig() async {
    await _prefs.remove(_keyServerHost);
    await _prefs.remove(_keyServerPort);
    await _prefs.remove(_keyProtocol);
  }
}
