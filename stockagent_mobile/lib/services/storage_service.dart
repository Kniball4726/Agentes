import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/server_config.dart';

/// Servicio de almacenamiento persistente y seguro para configuración,
/// credenciales cifradas (Android Keystore) y colas offline por usuario.
class StorageService {
  static const String _keyServerHost = 'stockagent_server_ip';
  static const String _keyServerPort = 'stockagent_server_port';
  static const String _keyProtocol = 'stockagent_protocol';
  static const String _keyCertPinPrefix = 'stockagent_cert_sha256_';
  static const String _keyAuthToken = 'stockagent_auth_token';
  static const String _keyAuthUser = 'stockagent_auth_user';
  static const String _keyDraftCount = 'stockagent_draft_inventory_count';
  static const String _keyDraftNames = 'stockagent_draft_inventory_names';
  static const String _keyOfflineDispatch = 'stockagent_offline_dispatch_queue';
  static const String _keyLightTheme = 'stockagent_light_theme';
  static const String _keyLaserScannerMode = 'stockagent_laser_scanner_mode';

  static const MethodChannel _secureChannel =
      MethodChannel('com.stockagent.mobile/secure_storage');

  final SharedPreferences _prefs;
  String? _cachedAuthToken;

  StorageService(this._prefs) {
    _cachedAuthToken = _prefs.getString(_keyAuthToken);
  }

  /// Inicializa la instancia asíncrona de SharedPreferences y carga el token
  /// desde el almacén cifrado respaldado por Android Keystore.
  static Future<StorageService> init() async {
    final prefs = await SharedPreferences.getInstance();
    final service = StorageService(prefs);
    await service._hydrateSecureToken();
    return service;
  }

  Future<void> _hydrateSecureToken() async {
    try {
      final secureToken = await _secureChannel.invokeMethod<String>(
        'readSecure',
        {'key': _keyAuthToken},
      );
      if (secureToken != null && secureToken.trim().isNotEmpty) {
        _cachedAuthToken = secureToken.trim();
        if (_prefs.containsKey(_keyAuthToken)) {
          await _prefs.remove(_keyAuthToken);
        }
        return;
      }
      // Migración automática si había un token legado en SharedPreferences
      final legacyToken = _prefs.getString(_keyAuthToken);
      if (legacyToken != null && legacyToken.trim().isNotEmpty) {
        _cachedAuthToken = legacyToken.trim();
        await _secureChannel.invokeMethod<bool>(
          'writeSecure',
          {'key': _keyAuthToken, 'value': _cachedAuthToken},
        );
        await _prefs.remove(_keyAuthToken);
      }
    } on MissingPluginException {
      // Entorno de test o plataforma sin canal nativo
      _cachedAuthToken = _prefs.getString(_keyAuthToken);
    } catch (_) {
      _cachedAuthToken = _prefs.getString(_keyAuthToken);
    }
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
    final cleanHost =
        host != null && host.trim().isNotEmpty ? host.trim() : ServerConfig.defaultHost;
    final pinnedCert = getPinnedCertSha256(cleanHost);

    return ServerConfig(
      host: cleanHost,
      port: port,
      protocol: protocol,
      certSha256: pinnedCert,
    );
  }

  /// Guarda una nueva configuración de servidor de forma persistente
  Future<void> saveConfig(ServerConfig config) async {
    final cleanHost = config.host.trim();
    await _prefs.setString(_keyServerHost, cleanHost);
    await _prefs.setString(_keyServerPort, config.normalizedPort);
    await _prefs.setString(_keyProtocol, config.normalizedProtocol);
    if (config.certSha256 != null && config.certSha256!.trim().isNotEmpty) {
      await savePinnedCertSha256(cleanHost, config.certSha256!.trim());
    }
  }

  /// Limpia los datos de servidor guardados y sus huellas TLS asociadas
  Future<void> clearConfig() async {
    final oldHost = _prefs.getString(_keyServerHost);
    if (oldHost != null && oldHost.isNotEmpty) {
      await clearPinnedCertSha256(oldHost);
    }
    await _prefs.remove(_keyServerHost);
    await _prefs.remove(_keyServerPort);
    await _prefs.remove(_keyProtocol);
  }

  // --- Pinning de Certificados TLS por Host ---

  String _certPinKey(String host) =>
      '$_keyCertPinPrefix${host.trim().toLowerCase()}';

  String? getPinnedCertSha256([String? host]) {
    final targetHost = (host ?? _prefs.getString(_keyServerHost) ?? '').trim();
    if (targetHost.isEmpty) return null;
    final val = _prefs.getString(_certPinKey(targetHost));
    return (val != null && val.trim().isNotEmpty) ? val.trim().toLowerCase() : null;
  }

  Future<void> savePinnedCertSha256(String host, String sha256) async {
    final cleanHost = host.trim();
    final cleanHash = sha256.trim().toLowerCase();
    if (cleanHost.isEmpty || cleanHash.isEmpty) return;
    await _prefs.setString(_certPinKey(cleanHost), cleanHash);
  }

  Future<void> clearPinnedCertSha256([String? host]) async {
    if (host != null && host.trim().isNotEmpty) {
      await _prefs.remove(_certPinKey(host));
      return;
    }
    final keys = _prefs
        .getKeys()
        .where((k) => k.startsWith(_keyCertPinPrefix))
        .toList();
    for (final k in keys) {
      await _prefs.remove(k);
    }
  }

  // --- Gestión Segura de Sesión y Tokens (Android Keystore) ---

  String? getAuthToken() {
    if (_cachedAuthToken != null && _cachedAuthToken!.isNotEmpty) {
      return _cachedAuthToken;
    }
    return _prefs.getString(_keyAuthToken);
  }

  Future<void> saveAuthToken(String token) async {
    final clean = token.trim();
    _cachedAuthToken = clean;
    try {
      await _secureChannel.invokeMethod<bool>(
        'writeSecure',
        {'key': _keyAuthToken, 'value': clean},
      );
      await _prefs.remove(_keyAuthToken);
    } on MissingPluginException {
      await _prefs.setString(_keyAuthToken, clean);
    } catch (_) {
      await _prefs.setString(_keyAuthToken, clean);
    }
  }

  Future<void> clearAuthToken() async {
    _cachedAuthToken = null;
    await _prefs.remove(_keyAuthToken);
    try {
      await _secureChannel.invokeMethod<bool>(
        'deleteSecure',
        {'key': _keyAuthToken},
      );
    } catch (_) {}
  }

  String? getAuthUser() {
    return _prefs.getString(_keyAuthUser);
  }

  /// Obtiene el username activo para aislar borradores y colas offline por operario.
  String _resolveUsername([String? explicitUsername]) {
    if (explicitUsername != null && explicitUsername.trim().isNotEmpty) {
      return explicitUsername.trim().toLowerCase();
    }
    final raw = getAuthUser();
    if (raw != null && raw.trim().isNotEmpty) {
      try {
        final map = jsonDecode(raw) as Map<String, dynamic>;
        final u = (map['username'] ?? '').toString().trim().toLowerCase();
        if (u.isNotEmpty) return u;
      } catch (_) {}
    }
    return 'anon';
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
    await _prefs.remove(_keyDraftCount);
    await _prefs.remove(_keyDraftNames);
  }

  // --- Almacenamiento Offline de Conteo Borrador y Caché de Nombres (Aislado por Usuario) ---

  String _scopedKey(String baseKey, [String? username]) {
    final u = _resolveUsername(username);
    return '${baseKey}_$u';
  }

  String? getDraftCount({String? username}) {
    final scoped = _prefs.getString(_scopedKey(_keyDraftCount, username));
    if (scoped != null) return scoped;
    return _prefs.getString(_keyDraftCount);
  }

  Future<void> saveDraftCount(String countJson, {String? username}) async {
    await _prefs.setString(_scopedKey(_keyDraftCount, username), countJson);
  }

  Future<void> clearDraftCount({String? username}) async {
    await _prefs.remove(_scopedKey(_keyDraftCount, username));
    await _prefs.remove(_keyDraftCount);
  }

  String? getNamesCache({String? username}) {
    return _prefs.getString(_scopedKey(_keyDraftNames, username));
  }

  Future<void> saveNamesCache(String namesJson, {String? username}) async {
    await _prefs.setString(_scopedKey(_keyDraftNames, username), namesJson);
  }

  Future<void> clearNamesCache({String? username}) async {
    await _prefs.remove(_scopedKey(_keyDraftNames, username));
  }

  // --- Persistencia de Cola Offline de Despacho por Usuario ---

  String? getOfflineDispatchQueue({String? username}) {
    return _prefs.getString(_scopedKey(_keyOfflineDispatch, username));
  }

  Future<void> saveOfflineDispatchQueue(String queueJson, {String? username}) async {
    await _prefs.setString(_scopedKey(_keyOfflineDispatch, username), queueJson);
  }

  Future<void> clearOfflineDispatchQueue({String? username}) async {
    await _prefs.remove(_scopedKey(_keyOfflineDispatch, username));
  }

  // --- Preferencias de Ergonomía en Depósito (Tema Claro Alto Contraste y Modo Lector Láser) ---

  bool get isLightTheme => _prefs.getBool(_keyLightTheme) ?? false;

  Future<void> saveLightTheme(bool value) async {
    await _prefs.setBool(_keyLightTheme, value);
  }

  bool get isLaserScannerMode => _prefs.getBool(_keyLaserScannerMode) ?? false;

  Future<void> saveLaserScannerMode(bool value) async {
    await _prefs.setBool(_keyLaserScannerMode, value);
  }
}
