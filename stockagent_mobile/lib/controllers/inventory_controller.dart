import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models/auth_user.dart';
import '../models/inventory_result.dart';
import '../models/product_item.dart';
import '../services/api_service.dart';

/// Controlador de lógica de negocio y estado para el relevamiento de inventario físico.
class InventoryController extends ChangeNotifier {
  final ApiService apiService;
  final AuthUser currentUser;

  final Map<String, int> conteo = {};
  final Map<String, String> nombresCache = {};

  /// Cola FIFO para no descartar lecturas de pistolas láser rápidas mientras hay una petición en vuelo.
  final List<MapEntry<String, int>> _colaEscaneos = [];

  int multiplicador = 1;
  bool isProcessing = false;
  String? statusBanner;
  bool statusBannerOk = true;

  String? lastDeletedSku;
  int? lastDeletedCount;
  String? lastDeletedName;

  InventoryController({
    required this.apiService,
    required this.currentUser,
  }) {
    _cargarBorradorGuardado();
  }

  int get totalProductos => conteo.length;
  int get totalUnidades => conteo.values.fold<int>(0, (a, b) => a + b);
  int get escaneosEnCola => _colaEscaneos.length;
  bool get isEmpty => conteo.isEmpty;
  bool get isNotEmpty => conteo.isNotEmpty;

  void setMultiplicador(int m) {
    multiplicador = m;
    notifyListeners();
  }

  void _cargarBorradorGuardado() {
    final storage = apiService.storageService;
    final rawNames = storage.getNamesCache(username: currentUser.username);
    if (rawNames != null && rawNames.isNotEmpty) {
      try {
        final decodedNames = jsonDecode(rawNames) as Map<String, dynamic>;
        for (final entry in decodedNames.entries) {
          final nombre = entry.value?.toString().trim() ?? '';
          if (nombre.isNotEmpty) {
            nombresCache[entry.key] = nombre;
          }
        }
      } catch (_) {}
    }

    final raw = storage.getDraftCount(username: currentUser.username);
    if (raw != null && raw.isNotEmpty) {
      try {
        final decoded = jsonDecode(raw) as Map<String, dynamic>;
        for (final entry in decoded.entries) {
          final cant = (entry.value as num?)?.toInt() ?? 0;
          if (cant > 0) {
            conteo[entry.key] = cant;
          }
        }
        notifyListeners();
      } catch (_) {}
    }
  }

  void _guardarBorrador() {
    final storage = apiService.storageService;
    storage.saveDraftCount(
      jsonEncode(conteo),
      username: currentUser.username,
    );
    storage.saveNamesCache(
      jsonEncode(nombresCache),
      username: currentUser.username,
    );
  }

  /// Encola el código con el multiplicador activo en el instante del disparo
  /// y procesa la cola en estricto orden FIFO sin perder lecturas consecutivas.
  Future<void> procesarCodigo(String rawCode) async {
    final codigo = rawCode.trim();
    if (codigo.isEmpty) return;

    _colaEscaneos.add(MapEntry<String, int>(codigo, multiplicador));
    if (isProcessing) {
      notifyListeners();
      return;
    }

    await _drenarColaEscaneos();
  }

  Future<void> _drenarColaEscaneos() async {
    if (isProcessing) return;
    isProcessing = true;
    notifyListeners();

    try {
      while (_colaEscaneos.isNotEmpty) {
        final item = _colaEscaneos.removeAt(0);
        await _procesarUnCodigo(item.key, item.value);
      }
    } finally {
      isProcessing = false;
      notifyListeners();
    }
  }

  Future<void> _procesarUnCodigo(String codigo, int mult) async {
    try {
      final ProductItem? prod = await apiService.getProduct(codigo);

      final String skuFinal = prod != null ? prod.code : codigo.toUpperCase();
      final String nombreFinal = prod != null
          ? prod.name
          : (nombresCache[skuFinal] ?? 'Producto no catalogado');

      final actual = conteo[skuFinal] ?? 0;
      conteo[skuFinal] = actual + mult;
      nombresCache[skuFinal] = nombreFinal;
      _guardarBorrador();

      HapticFeedback.lightImpact();
      SystemSound.play(SystemSoundType.click);

      statusBanner = '+$mult · $skuFinal ($nombreFinal)';
      statusBannerOk = true;
      notifyListeners();
    } on ApiException catch (e) {
      // Si el error es de conectividad o timeout (Wi-Fi caído en pasillo), guardar conteo offline
      if (e.statusCode == 0 || e.statusCode == 408 || e.statusCode >= 502) {
        final skuOffline = codigo.toUpperCase();
        final nombreOffline =
            nombresCache[skuOffline] ?? 'Guardado offline (pendiente de validar)';
        final actual = conteo[skuOffline] ?? 0;
        conteo[skuOffline] = actual + mult;
        nombresCache[skuOffline] = nombreOffline;
        _guardarBorrador();

        HapticFeedback.mediumImpact();
        statusBanner = '⚡ Guardado offline: +$mult · $skuOffline ($nombreOffline)';
        statusBannerOk = true;
        notifyListeners();
        return;
      }

      HapticFeedback.heavyImpact();
      statusBanner = 'Error al registrar ($codigo): ${e.message}';
      statusBannerOk = false;
      notifyListeners();
    } catch (e) {
      HapticFeedback.heavyImpact();
      statusBanner = 'Error al registrar: $e';
      statusBannerOk = false;
      notifyListeners();
    }
  }

  void modificarCantidad(String sku, int delta) {
    final actual = conteo[sku] ?? 0;
    final nueva = actual + delta;
    if (nueva <= 0) {
      eliminarItem(sku);
      return;
    }
    conteo[sku] = nueva;
    _guardarBorrador();
    HapticFeedback.selectionClick();
    notifyListeners();
  }

  void eliminarItem(String sku) {
    if (!conteo.containsKey(sku)) return;
    lastDeletedSku = sku;
    lastDeletedCount = conteo.remove(sku);
    lastDeletedName = nombresCache[sku];
    _guardarBorrador();
    notifyListeners();
  }

  /// Restaura el último ítem eliminado accidentalmente por el operario.
  bool deshacerEliminacion() {
    final sku = lastDeletedSku;
    final cant = lastDeletedCount;
    if (sku == null || cant == null || cant <= 0) return false;

    conteo[sku] = (conteo[sku] ?? 0) + cant;
    if (lastDeletedName != null && lastDeletedName!.isNotEmpty) {
      nombresCache[sku] = lastDeletedName!;
    }
    lastDeletedSku = null;
    lastDeletedCount = null;
    lastDeletedName = null;
    _guardarBorrador();
    HapticFeedback.lightImpact();
    notifyListeners();
    return true;
  }

  void limpiarTodo() {
    conteo.clear();
    nombresCache.clear();
    statusBanner = null;
    lastDeletedSku = null;
    lastDeletedCount = null;
    lastDeletedName = null;
    apiService.storageService.clearDraftCount(username: currentUser.username);
    apiService.storageService.clearNamesCache(username: currentUser.username);
    notifyListeners();
  }

  Future<InventorySummary> compararPreliminar() async {
    return await apiService.comparePreliminary(conteo);
  }

  Future<InventorySummary> finalizarInventario() async {
    final res = await apiService.finalizeInventory(conteo);
    conteo.clear();
    nombresCache.clear();
    statusBanner = null;
    await apiService.storageService.clearDraftCount(username: currentUser.username);
    await apiService.storageService.clearNamesCache(username: currentUser.username);
    notifyListeners();
    return res;
  }
}
