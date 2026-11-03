import 'dart:async';
import 'dart:convert';
import 'dart:io';

import '../models/auth_user.dart';
import '../models/inventory_result.dart';
import '../models/order_dispatch.dart';
import '../models/product_item.dart';
import '../models/server_config.dart';
import 'storage_service.dart';

class ApiException implements Exception {
  final int statusCode;
  final String message;

  ApiException(this.statusCode, this.message);

  @override
  String toString() => message;
}

class ScanDispatchResult {
  final bool ok;
  final String mensaje;
  final OrderDispatch? pedido;

  const ScanDispatchResult({
    required this.ok,
    required this.mensaje,
    this.pedido,
  });
}

/// Cliente HTTP para consumir los endpoints REST (/api/v1) de StockAgent.
class ApiService {
  final StorageService storageService;
  final HttpClient _client;

  ApiService({
    required this.storageService,
    HttpClient? client,
  }) : _client = client ??
            (HttpClient()
              ..badCertificateCallback = (cert, host, port) => true
              ..connectionTimeout = const Duration(seconds: 6));

  ServerConfig get config => storageService.loadConfig();

  String get baseUrl => config.baseUrl;

  Uri _buildUri(String path, [Map<String, String>? queryParams]) {
    final cleanPath = path.startsWith('/') ? path : '/$path';
    final fullUrl = '$baseUrl$cleanPath';
    final uri = Uri.parse(fullUrl);
    if (queryParams != null && queryParams.isNotEmpty) {
      return uri.replace(queryParameters: queryParams);
    }
    return uri;
  }

  Future<dynamic> _send(
    String method,
    String path, {
    Map<String, dynamic>? body,
    Map<String, String>? queryParams,
    bool requiresAuth = true,
    Duration timeout = const Duration(seconds: 8),
  }) async {
    final uri = _buildUri(path, queryParams);

    try {
      final HttpClientRequest request;
      switch (method.toUpperCase()) {
        case 'GET':
          request = await _client.getUrl(uri).timeout(timeout);
          break;
        case 'POST':
          request = await _client.postUrl(uri).timeout(timeout);
          break;
        case 'PUT':
          request = await _client.putUrl(uri).timeout(timeout);
          break;
        case 'DELETE':
          request = await _client.deleteUrl(uri).timeout(timeout);
          break;
        default:
          throw ApiException(400, 'Método HTTP no soportado: $method');
      }

      request.headers.set('Accept', 'application/json');

      if (requiresAuth) {
        final token = storageService.getAuthToken();
        if (token != null && token.isNotEmpty) {
          request.headers.set('Authorization', 'Bearer $token');
        }
      }

      if (body != null) {
        request.headers.set('Content-Type', 'application/json; charset=utf-8');
        final bytes = utf8.encode(jsonEncode(body));
        request.contentLength = bytes.length;
        request.add(bytes);
      }

      final response = await request.close().timeout(timeout);
      final rawResponse = await response.transform(utf8.decoder).join();

      dynamic jsonBody;
      if (rawResponse.trim().isNotEmpty) {
        try {
          jsonBody = jsonDecode(rawResponse);
        } catch (_) {
          jsonBody = rawResponse;
        }
      }

      if (response.statusCode >= 200 && response.statusCode < 300) {
        return jsonBody;
      }

      String errorMsg = 'Error en el servidor (${response.statusCode})';
      if (jsonBody is Map<String, dynamic>) {
        if (jsonBody.containsKey('detail')) {
          errorMsg = jsonBody['detail'].toString();
        } else if (jsonBody.containsKey('message')) {
          errorMsg = jsonBody['message'].toString();
        }
      }

      throw ApiException(response.statusCode, errorMsg);
    } on SocketException catch (_) {
      throw ApiException(
        0,
        'No se pudo conectar con el servidor en ${config.host}:${config.port}. Verifique la conexión Wi-Fi.',
      );
    } on TimeoutException catch (_) {
      throw ApiException(
        408,
        'Tiempo de espera agotado al comunicar con la PC.',
      );
    }
  }

  // ==========================================
  // Diagnóstico y Heartbeat
  // ==========================================

  Future<bool> ping() async {
    try {
      final res = await _send('GET', '/api/v1/sistema/ping', requiresAuth: false);
      return res is Map && res['status'] == 'pong';
    } catch (_) {
      return false;
    }
  }

  Future<Map<String, dynamic>?> getServerStatus() async {
    try {
      final res = await _send('GET', '/api/v1/sistema/estado', requiresAuth: false);
      if (res is Map<String, dynamic>) {
        return res;
      }
    } catch (_) {}
    return null;
  }

  // ==========================================
  // Autenticación
  // ==========================================

  Future<AuthUser> login(String username, String password) async {
    final res = await _send(
      'POST',
      '/api/v1/auth/login',
      body: {'username': username.trim(), 'password': password},
      requiresAuth: false,
    );

    if (res is Map<String, dynamic> && res['ok'] == true) {
      final token = res['token']?.toString() ?? '';
      final userMap = res['user'] as Map<String, dynamic>? ?? {};
      final user = AuthUser.fromJson(userMap, token: token);

      await storageService.saveAuthToken(token);
      await storageService.saveAuthUser(user.serialize());
      return user;
    }

    throw ApiException(401, 'Credenciales inválidas.');
  }

  Future<AuthUser?> getMe() async {
    try {
      final res = await _send('GET', '/api/v1/auth/me');
      if (res is Map<String, dynamic>) {
        final token = storageService.getAuthToken();
        final user = AuthUser.fromJson(res, token: token);
        await storageService.saveAuthUser(user.serialize());
        return user;
      }
    } catch (e) {
      if (e is ApiException && e.statusCode == 401) {
        await storageService.logout();
      }
    }
    return null;
  }

  Future<void> logout() async {
    try {
      await _send('POST', '/api/v1/auth/logout');
    } catch (_) {}
    await storageService.logout();
  }

  // ==========================================
  // Productos y Stock
  // ==========================================

  Future<List<ProductItem>> searchProducts(String query, {int limit = 50}) async {
    final res = await _send(
      'GET',
      '/api/v1/productos/buscar',
      queryParams: {'q': query.trim(), 'limit': limit.toString()},
    );

    if (res is Map<String, dynamic> && res.containsKey('productos')) {
      final list = res['productos'] as List<dynamic>? ?? [];
      return list
          .whereType<Map<String, dynamic>>()
          .map((p) => ProductItem.fromJson(p))
          .toList();
    }
    return [];
  }

  Future<ProductItem?> getProduct(String codeOrBarcode) async {
    try {
      final encoded = Uri.encodeComponent(codeOrBarcode.trim());
      final res = await _send('GET', '/api/v1/productos/$encoded');
      if (res is Map<String, dynamic>) {
        return ProductItem.fromJson(res);
      }
    } on ApiException catch (e) {
      if (e.statusCode == 404) return null;
      rethrow;
    }
    return null;
  }

  Future<bool> updateLocation(String code, String location) async {
    final encoded = Uri.encodeComponent(code.trim());
    final res = await _send(
      'PUT',
      '/api/v1/productos/$encoded/ubicacion',
      body: {'ubicacion': location.trim().toUpperCase()},
    );
    return res is Map && res['ok'] == true;
  }

  Future<bool> associateBarcode(String code, String barcode) async {
    final encoded = Uri.encodeComponent(code.trim());
    final res = await _send(
      'PUT',
      '/api/v1/productos/$encoded/codigo-barras',
      body: {'cod_barras': barcode.trim()},
    );
    return res is Map && res['ok'] == true;
  }

  // ==========================================
  // Inventario en Vivo
  // ==========================================

  Future<InventorySummary> comparePreliminary(Map<String, int> counts) async {
    final res = await _send(
      'POST',
      '/api/v1/inventario/comparar-preliminar',
      body: {'conteo': counts},
    );
    if (res is Map<String, dynamic>) {
      return InventorySummary.fromJson(res);
    }
    throw ApiException(500, 'Respuesta inesperada al comparar inventario.');
  }

  Future<InventorySummary> finalizeInventory(
    Map<String, int> counts, {
    String? filename,
  }) async {
    final res = await _send(
      'POST',
      '/api/v1/inventario/finalizar',
      body: {
        'conteo': counts,
        if (filename != null) 'nombre_archivo': filename,
      },
      timeout: const Duration(seconds: 30),
    );
    if (res is Map<String, dynamic>) {
      await storageService.clearDraftCount();
      return InventorySummary.fromJson(res);
    }
    throw ApiException(500, 'Error al procesar el cierre de inventario.');
  }

  // ==========================================
  // Despacho y Logística
  // ==========================================

  Future<ScanDispatchResult> scanDispatch(
    String codeOrRemito, {
    String? targetState,
  }) async {
    final res = await _send(
      'POST',
      '/api/v1/despacho/escanear',
      body: {
        'codigo': codeOrRemito.trim(),
        if (targetState != null) 'nuevo_estado': targetState,
      },
    );

    if (res is Map<String, dynamic>) {
      final ok = res['ok'] as bool? ?? false;
      final msg = res['mensaje']?.toString() ?? '';
      OrderDispatch? pedido;
      if (res['pedido'] is Map<String, dynamic>) {
        pedido = OrderDispatch.fromJson(res['pedido'] as Map<String, dynamic>);
      }
      return ScanDispatchResult(ok: ok, mensaje: msg, pedido: pedido);
    }

    throw ApiException(500, 'Respuesta inesperada al procesar el despacho.');
  }

  Future<List<OrderDispatch>> listOrders({
    String? state,
    int limit = 50,
  }) async {
    final qParams = <String, String>{'limit': limit.toString()};
    if (state != null && state.isNotEmpty) {
      qParams['estado_despacho'] = state.toLowerCase();
    }

    final res = await _send(
      'GET',
      '/api/v1/despacho/pedidos',
      queryParams: qParams,
    );

    if (res is Map<String, dynamic> && res.containsKey('pedidos')) {
      final list = res['pedidos'] as List<dynamic>? ?? [];
      return list
          .whereType<Map<String, dynamic>>()
          .map((p) => OrderDispatch.fromJson(p))
          .toList();
    }
    return [];
  }

  Future<OrderDispatch?> getOrderDetail(String remito) async {
    try {
      final encoded = Uri.encodeComponent(remito.trim());
      final res = await _send('GET', '/api/v1/despacho/pedidos/$encoded');
      if (res is Map<String, dynamic>) {
        return OrderDispatch.fromJson(res);
      }
    } on ApiException catch (e) {
      if (e.statusCode == 404) return null;
      rethrow;
    }
    return null;
  }
}
