import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models/auth_user.dart';
import '../models/order_dispatch.dart';
import '../services/api_service.dart';

class ScanRecord {
  final String hora;
  final bool exito;
  final String mensaje;
  final OrderDispatch? pedido;

  ScanRecord({
    required this.hora,
    required this.exito,
    required this.mensaje,
    this.pedido,
  });
}

/// Controlador de lógica de negocio y estado para el despacho y control logístico de pedidos.
class DispatchController extends ChangeNotifier {
  final ApiService apiService;
  final AuthUser currentUser;

  String modoSeleccionado = 'auto'; // 'auto', 'despachado', 'entregado', 'armado'
  bool isProcessing = false;
  bool cargandoPedidos = false;
  bool verListaPendientes = false;
  String? errorCargaPedidos;

  final List<ScanRecord> historial = [];
  List<OrderDispatch> pedidosActivos = [];
  final List<Map<String, dynamic>> colaOffline = [];
  final List<MapEntry<String, String?>> _colaEscaneos = [];
  bool sincronizandoOffline = false;
  bool _disposed = false;

  DispatchController({
    required this.apiService,
    required this.currentUser,
  }) {
    _cargarColaOfflinePersistida();
    cargarPedidos();
  }

  void _safeNotify() {
    if (!_disposed) {
      notifyListeners();
    }
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }

  void _cargarColaOfflinePersistida() {
    final raw = apiService.storageService.getOfflineDispatchQueue(
      username: currentUser.username,
    );
    if (raw == null || raw.trim().isEmpty) return;
    try {
      final list = jsonDecode(raw) as List<dynamic>;
      colaOffline
        ..clear()
        ..addAll(
          list.whereType<Map<String, dynamic>>().map(
                (item) => Map<String, dynamic>.from(item),
              ),
        );
    } catch (_) {}
  }

  Future<void> _guardarColaOffline() async {
    await apiService.storageService.saveOfflineDispatchQueue(
      jsonEncode(colaOffline),
      username: currentUser.username,
    );
  }

  void setModo(String nuevoModo) {
    if (nuevoModo == 'armado' && !currentUser.canRevertDispatchState) {
      return;
    }
    modoSeleccionado = nuevoModo;
    _safeNotify();
  }

  void alternarVista() {
    verListaPendientes = !verListaPendientes;
    if (verListaPendientes) {
      cargarPedidos();
    }
    _safeNotify();
  }

  Future<void> cargarPedidos() async {
    if (_disposed) return;
    cargandoPedidos = true;
    errorCargaPedidos = null;
    _safeNotify();
    try {
      final pedidos = await apiService.listOrders(limit: 60);
      if (_disposed) return;
      pedidosActivos = pedidos;
    } on ApiException catch (e) {
      errorCargaPedidos = e.message;
    } catch (e) {
      errorCargaPedidos = 'No se pudo cargar la lista de pedidos: $e';
    } finally {
      cargandoPedidos = false;
      _safeNotify();
    }
  }

  String _horaActual() {
    final ahora = DateTime.now();
    return '${ahora.hour.toString().padLeft(2, '0')}:'
        '${ahora.minute.toString().padLeft(2, '0')}:'
        '${ahora.second.toString().padLeft(2, '0')}';
  }

  /// Encola el código QR/remito en una cola FIFO para que ráfagas de lectura
  /// no descarten escaneos mientras se aguarda respuesta del servidor.
  Future<void> procesarEscaneo(String rawCode) async {
    final codigo = rawCode.trim();
    if (codigo.isEmpty) return;

    final String? estadoDestino =
        modoSeleccionado == 'auto' ? null : modoSeleccionado;
    _colaEscaneos.add(MapEntry<String, String?>(codigo, estadoDestino));

    if (isProcessing) {
      _safeNotify();
      return;
    }

    await _drenarColaEscaneos();
  }

  Future<void> _drenarColaEscaneos() async {
    if (isProcessing || _disposed) return;
    isProcessing = true;
    _safeNotify();

    try {
      while (_colaEscaneos.isNotEmpty && !_disposed) {
        final item = _colaEscaneos.removeAt(0);
        await _procesarUnEscaneo(item.key, item.value);
      }
    } finally {
      isProcessing = false;
      _safeNotify();
    }
  }

  Future<void> _procesarUnEscaneo(String codigo, String? estadoDestino) async {
    try {
      final resultado = await apiService.scanDispatch(
        codigo,
        targetState: estadoDestino,
      );
      if (_disposed) return;

      final horaStr = _horaActual();
      historial.insert(
        0,
        ScanRecord(
          hora: horaStr,
          exito: resultado.ok,
          mensaje: resultado.mensaje,
          pedido: resultado.pedido,
        ),
      );

      if (resultado.ok) {
        HapticFeedback.lightImpact();
        SystemSound.play(SystemSoundType.click);
        cargarPedidos();
      } else {
        HapticFeedback.heavyImpact();
      }
      _safeNotify();
    } on ApiException catch (e) {
      final horaStr = _horaActual();
      final esFallaDeRed =
          e.statusCode == 0 || e.statusCode == 408 || e.statusCode >= 502;

      if (esFallaDeRed) {
        colaOffline.add({
          'codigo': codigo,
          'targetState': estadoDestino,
          'hora': horaStr,
        });
        await _guardarColaOffline();

        HapticFeedback.mediumImpact();
        historial.insert(
          0,
          ScanRecord(
            hora: horaStr,
            exito: true,
            mensaje:
                '⚡ Red offline: $codigo guardado en cola persistente (${colaOffline.length} en buffer)',
          ),
        );
      } else {
        // Error de negocio o permisos (400, 401, 403, 404, 422): NO encolar como offline
        HapticFeedback.heavyImpact();
        historial.insert(
          0,
          ScanRecord(
            hora: horaStr,
            exito: false,
            mensaje: '❌ [$codigo] ${e.message}',
          ),
        );
      }
      _safeNotify();
    } catch (e) {
      final horaStr = _horaActual();
      HapticFeedback.heavyImpact();
      historial.insert(
        0,
        ScanRecord(
          hora: horaStr,
          exito: false,
          mensaje: '❌ Error al procesar [$codigo]: $e',
        ),
      );
      _safeNotify();
    }
  }

  Future<int> sincronizarColaOffline() async {
    if (colaOffline.isEmpty || sincronizandoOffline || _disposed) return 0;
    sincronizandoOffline = true;
    _safeNotify();

    int sincronizados = 0;
    try {
      final itemsAEnviar = List<Map<String, dynamic>>.from(colaOffline);
      final resultados = await apiService.scanDispatchBatch(itemsAEnviar);
      final totalResultados = resultados.length < itemsAEnviar.length
          ? resultados.length
          : itemsAEnviar.length;

      for (int i = 0; i < totalResultados; i++) {
        final res = resultados[i];
        final it = itemsAEnviar[i];
        final horaStr = _horaActual();

        historial.insert(
          0,
          ScanRecord(
            hora: horaStr,
            exito: res.ok,
            mensaje: '🔄 Sincronizado offline [${it['codigo']}]: ${res.mensaje}',
            pedido: res.pedido,
          ),
        );
        if (res.ok) {
          sincronizados++;
        }
      }

      final procesados = totalResultados.clamp(0, colaOffline.length);
      if (procesados > 0) {
        colaOffline.removeRange(0, procesados);
      }
      await _guardarColaOffline();

      HapticFeedback.lightImpact();
      if (!_disposed) {
        await cargarPedidos();
      }
    } catch (_) {
      HapticFeedback.heavyImpact();
    } finally {
      sincronizandoOffline = false;
      _safeNotify();
    }
    return sincronizados;
  }
}
