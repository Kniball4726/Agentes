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

  final List<ScanRecord> historial = [];
  List<OrderDispatch> pedidosActivos = [];

  DispatchController({
    required this.apiService,
    required this.currentUser,
  }) {
    cargarPedidos();
  }

  void setModo(String nuevoModo) {
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
    notifyListeners();
    try {
      final pedidos = await apiService.listOrders(limit: 60);
      pedidosActivos = pedidos;
    } catch (_) {
    } finally {
      cargandoPedidos = false;
      notifyListeners();
    }
  }

  Future<void> procesarEscaneo(String rawCode) async {
    final codigo = rawCode.trim();
    if (codigo.isEmpty || isProcessing) return;

    isProcessing = true;
    notifyListeners();

    try {
      final String? estadoDestino =
          modoSeleccionado == 'auto' ? null : modoSeleccionado;

      final resultado = await apiService.scanDispatch(
        codigo,
        targetState: estadoDestino,
      );

      final ahora = DateTime.now();
      final horaStr =
          '${ahora.hour.toString().padLeft(2, '0')}:${ahora.minute.toString().padLeft(2, '0')}:${ahora.second.toString().padLeft(2, '0')}';

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
    } catch (e) {
      HapticFeedback.heavyImpact();
      final ahora = DateTime.now();
      final horaStr =
          '${ahora.hour.toString().padLeft(2, '0')}:${ahora.minute.toString().padLeft(2, '0')}:${ahora.second.toString().padLeft(2, '0')}';

      historial.insert(
        0,
        ScanRecord(
          hora: horaStr,
          exito: false,
          mensaje: e.toString(),
        ),
      );
    } finally {
      isProcessing = false;
      notifyListeners();
    }
  }
}
