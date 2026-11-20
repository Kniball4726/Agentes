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

  DispatchController({
    required this.apiService,
    required this.currentUser,
  }) {
    _cargarColaOfflinePersistida();
    cargarPedidos();
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
    notifyListeners();
  }

  void alternarVista() {
    verListaPendientes = !verListaPendientes;
    if (verListaPendientes) {
      cargarPedidos();
    }
    notifyListeners();
  }

  Future<void> cargarPedidos() async {
    cargandoPedidos = true;
    errorCargaPedidos = null;
    notifyListeners();
    try {
      final pedidos = await apiService.listOrders(limit: 60);
      pedidosActivos = pedidos;
    } on ApiException catch (e) {
      errorCargaPedidos = e.message;
    } catch (e) {
      errorCargaPedidos = 'No se pudo cargar la lista de pedidos: $e';
    } finally {
      cargandoPedidos = false;
      notifyListeners();
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
        await _procesarUnEscaneo(item.key, item.value);
      }
    } finally {
      isProcessing = false;
      notifyListeners();
    }
  }

  Future<void> _procesarUnEscaneo(String codigo, String? estadoDestino) async {
    try {
      final resultado = await apiService.scanDispatch(
        codigo,
        targetState: estadoDestino,
      );

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
      notifyListeners();
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
      notifyListeners();
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
      notifyListeners();
    }
  }

  Future<int> sincronizarColaOffline() async {
    if (colaOffline.isEmpty || sincronizandoOffline) return 0;
    sincronizandoOffline = true;
    notifyListeners();

    int sincronizados = 0;
    try {
      final itemsAEnviar = List<Map<String, dynamic>>.from(colaOffline);
      final resultados = await apiService.scanDispatchBatch(itemsAEnviar);

      for (int i = 0; i < resultados.length; i++) {
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

      final procesados = resultados.length.clamp(0, colaOffline.length);
      if (procesados > 0) {
        colaOffline.removeRange(0, procesados);
      }
      await _guardarColaOffline();

      HapticFeedback.lightImpact();
      await cargarPedidos();
    } catch (_) {
      HapticFeedback.heavyImpact();
    } finally {
      sincronizandoOffline = false;
      notifyListeners();
    }
    return sincronizados;
  }
}
