import 'package:shared_preferences/shared_preferences.dart';
import '../models/server_config.dart';

/// Servicio de almacenamiento persistente para la configuración y sesión de StockAgent Móvil.
class StorageService {
  static const String _keyServerHost = 'stockagent_server_ip';
  static const String _keyServerPort = 'stockagent_server_port';
  static const String _keyProtocol = 'stockagent_protocol';
  static const String _keyAuthToken = 'stockagent_auth_token';
  static const String _keyAuthUser = 'stockagent_auth_user';
  static const String _keyDraftCount = 'stockagent_draft_inventory_count';

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

  /// Limpia los datos de servidor guardados
  Future<void> clearConfig() async {
    await _prefs.remove(_keyServerHost);
    await _prefs.remove(_keyServerPort);
    await _prefs.remove(_keyProtocol);
  }

  // --- Gestión de Sesión y Tokens ---

  String? getAuthToken() {
    return _prefs.getString(_keyAuthToken);
  }

  Future<void> saveAuthToken(String token) async {
    await _prefs.setString(_keyAuthToken, token.trim());
  }

  Future<void> clearAuthToken() async {
    await _prefs.remove(_keyAuthToken);
  }

  String? getAuthUser() {
    return _prefs.getString(_keyAuthUser);
  }

  Future<void> saveAuthUser(String userJson) async {
    await _prefs.setString(_keyAuthUser, userJson);
  }

  Future<void> clearAuthUser() async {
    await _prefs.remove(_keyAuthUser);
  }

  Future<void> logout() async {
    await clearAuthToken();
    await clearAuthUser();
  }

  // --- Almacenamiento Offline de Conteo Borrador ---

  String? getDraftCount() {
    return _prefs.getString(_keyDraftCount);
  }

  Future<void> saveDraftCount(String countJson) async {
    await _prefs.setString(_keyDraftCount, countJson);
  }

  Future<void> clearDraftCount() async {
    await _prefs.remove(_keyDraftCount);
  }
}
