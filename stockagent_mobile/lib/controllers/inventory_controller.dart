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

  int multiplicador = 1;
  bool isProcessing = false;
  String? statusBanner;
  bool statusBannerOk = true;

  InventoryController({
    required this.apiService,
    required this.currentUser,
  }) {
    _cargarBorradorGuardado();
  }

  int get totalProductos => conteo.length;
  int get totalUnidades => conteo.values.fold<int>(0, (a, b) => a + b);
  bool get isEmpty => conteo.isEmpty;
  bool get isNotEmpty => conteo.isNotEmpty;

  void setMultiplicador(int m) {
    multiplicador = m;
    notifyListeners();
  }

  void _cargarBorradorGuardado() {
    final raw = apiService.storageService.getDraftCount();
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
    apiService.storageService.saveDraftCount(jsonEncode(conteo));
  }

  Future<void> procesarCodigo(String rawCode) async {
    final codigo = rawCode.trim();
    if (codigo.isEmpty || isProcessing) return;

    isProcessing = true;
    statusBanner = null;
    notifyListeners();

    try {
      final ProductItem? prod = await apiService.getProduct(codigo);

      final String skuFinal = prod != null ? prod.code : codigo.toUpperCase();
      final String nombreFinal = prod != null ? prod.name : 'Producto no catalogado';

      final actual = conteo[skuFinal] ?? 0;
      conteo[skuFinal] = actual + multiplicador;
      nombresCache[skuFinal] = nombreFinal;
      _guardarBorrador();

      HapticFeedback.lightImpact();
      SystemSound.play(SystemSoundType.click);

      statusBanner = '+$multiplicador · $skuFinal ($nombreFinal)';
      statusBannerOk = true;
    } catch (e) {
      HapticFeedback.heavyImpact();
      statusBanner = 'Error al registrar: $e';
      statusBannerOk = false;
    } finally {
      isProcessing = false;
      notifyListeners();
    }
  }

  void modificarCantidad(String sku, int delta) {
    final actual = conteo[sku] ?? 0;
    final nueva = actual + delta;
    if (nueva <= 0) {
      conteo.remove(sku);
    } else {
      conteo[sku] = nueva;
    }
    _guardarBorrador();
    HapticFeedback.selectionClick();
    notifyListeners();
  }

  void eliminarItem(String sku) {
    conteo.remove(sku);
    _guardarBorrador();
    notifyListeners();
  }

  void limpiarTodo() {
    conteo.clear();
    statusBanner = null;
    apiService.storageService.clearDraftCount();
    notifyListeners();
  }

  Future<InventorySummary> compararPreliminar() async {
    return await apiService.comparePreliminary(conteo);
  }

  Future<InventorySummary> finalizarInventario() async {
    final res = await apiService.finalizeInventory(conteo);
    conteo.clear();
    statusBanner = null;
    notifyListeners();
    return res;
  }
}
