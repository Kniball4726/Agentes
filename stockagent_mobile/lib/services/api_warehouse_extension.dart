part of 'api_service.dart';

/// Operaciones de multi-ubicación por zona, trazabilidad de lotes FEFO y reservas activas.
extension ApiWarehouseExtension on ApiService {
  Future<ProductLocationsSummary> getProductLocations(String code) async {
    final encoded = Uri.encodeComponent(code.trim());
    final res = await _send('GET', '/api/v1/productos/$encoded/ubicaciones');
    if (res is Map<String, dynamic>) {
      return ProductLocationsSummary.fromJson(res);
    }
    throw ApiException(500, 'Respuesta inesperada al consultar ubicaciones.');
  }

  Future<ProductLocation> assignProductLocation(
    String code, {
    required String ubicacion,
    String tipoZona = 'picking',
    int? stock,
    int capacidadMax = 0,
    bool esPrincipal = false,
  }) async {
    final encoded = Uri.encodeComponent(code.trim());
    final res = await _send(
      'POST',
      '/api/v1/productos/$encoded/ubicaciones',
      body: {
        'ubicacion': ubicacion.trim().toUpperCase(),
        'tipo_zona': tipoZona,
        if (stock != null) 'stock': stock,
        'capacidad_max': capacidadMax,
        'es_principal': esPrincipal,
      },
    );
    if (res is Map<String, dynamic> &&
        res['ubicacion'] is Map<String, dynamic>) {
      return ProductLocation.fromJson(res['ubicacion'] as Map<String, dynamic>);
    }
    throw ApiException(500, 'No se pudo guardar la ubicación.');
  }

  Future<Map<String, dynamic>> transferBetweenLocations(
    String code, {
    required String origen,
    required String destino,
    required int cantidad,
    String destinoZona = 'picking',
  }) async {
    final encoded = Uri.encodeComponent(code.trim());
    final res = await _send(
      'POST',
      '/api/v1/productos/$encoded/ubicaciones/transferir',
      body: {
        'origen': origen.trim().toUpperCase(),
        'destino': destino.trim().toUpperCase(),
        'cantidad': cantidad,
        'destino_zona': destinoZona,
        'crear_destino': true,
      },
    );
    if (res is Map<String, dynamic>) {
      return res;
    }
    throw ApiException(500, 'Respuesta inesperada al transferir ubicaciones.');
  }

  Future<List<StockLot>> getProductLots(
    String code, {
    bool soloDisponibles = false,
  }) async {
    final encoded = Uri.encodeComponent(code.trim());
    final res = await _send(
      'GET',
      '/api/v1/productos/$encoded/lotes',
      queryParams: {'solo_disponibles': soloDisponibles.toString()},
    );
    if (res is Map<String, dynamic> && res['lotes'] is List) {
      return (res['lotes'] as List<dynamic>)
          .whereType<Map<String, dynamic>>()
          .map(StockLot.fromJson)
          .toList();
    }
    return [];
  }

  Future<StockLot> registerProductLot(
    String code, {
    required String lote,
    required int cantidad,
    String fechaVencimiento = '',
    String ubicacion = '',
  }) async {
    final encoded = Uri.encodeComponent(code.trim());
    final res = await _send(
      'POST',
      '/api/v1/productos/$encoded/lotes',
      body: {
        'lote': lote.trim().toUpperCase(),
        'cantidad': cantidad,
        'fecha_vencimiento': fechaVencimiento.trim(),
        'ubicacion': ubicacion.trim().toUpperCase(),
      },
    );
    if (res is Map<String, dynamic> && res['lote'] is Map<String, dynamic>) {
      return StockLot.fromJson(res['lote'] as Map<String, dynamic>);
    }
    throw ApiException(500, 'No se pudo registrar el lote FEFO.');
  }

  Future<Map<String, dynamic>> consumeLotsFefo(
    String code, {
    required int cantidad,
    String? ubicacion,
    bool descontarStockProducto = true,
    String detalle = 'Consumo FEFO móvil',
  }) async {
    final encoded = Uri.encodeComponent(code.trim());
    final res = await _send(
      'POST',
      '/api/v1/productos/$encoded/lotes/consumir-fefo',
      body: {
        'cantidad': cantidad,
        if (ubicacion != null && ubicacion.trim().isNotEmpty)
          'ubicacion': ubicacion.trim().toUpperCase(),
        'descontar_stock_producto': descontarStockProducto,
        'detalle': detalle,
      },
    );
    if (res is Map<String, dynamic>) {
      return res;
    }
    throw ApiException(500, 'Respuesta inesperada al consumir lotes FEFO.');
  }

  Future<List<StockLot>> getExpiringLots({
    int dias = 30,
    bool incluirVencidos = true,
  }) async {
    final res = await _send(
      'GET',
      '/api/v1/productos/lotes/proximos-vencer',
      queryParams: {
        'dias': dias.toString(),
        'incluir_vencidos': incluirVencidos.toString(),
      },
    );
    if (res is Map<String, dynamic> && res['lotes'] is List) {
      return (res['lotes'] as List<dynamic>)
          .whereType<Map<String, dynamic>>()
          .map(StockLot.fromJson)
          .toList();
    }
    return [];
  }

  Future<List<StockReservation>> listReservations({
    String estado = 'activa',
    String? referenciaTipo,
    String? referenciaId,
    String? codigo,
  }) async {
    final qParams = <String, String>{'estado': estado};
    if (referenciaTipo != null && referenciaTipo.isNotEmpty) {
      qParams['referencia_tipo'] = referenciaTipo;
    }
    if (referenciaId != null && referenciaId.isNotEmpty) {
      qParams['referencia_id'] = referenciaId;
    }
    if (codigo != null && codigo.isNotEmpty) {
      qParams['codigo'] = codigo;
    }
    final res = await _send(
      'GET',
      '/api/v1/productos/reservas',
      queryParams: qParams,
    );
    if (res is Map<String, dynamic> && res['reservas'] is List) {
      return (res['reservas'] as List<dynamic>)
          .whereType<Map<String, dynamic>>()
          .map(StockReservation.fromJson)
          .toList();
    }
    return [];
  }

  Future<Map<String, dynamic>> consolidateReservation({
    required String referenciaId,
    String referenciaTipo = 'ola_picking',
    bool descontarStock = true,
    String detalle = 'Consolidación móvil',
  }) async {
    final res = await _send(
      'POST',
      '/api/v1/productos/reservas/consolidar',
      body: {
        'referencia_id': referenciaId,
        'referencia_tipo': referenciaTipo,
        'descontar_stock': descontarStock,
        'detalle': detalle,
      },
    );
    if (res is Map<String, dynamic>) {
      return res;
    }
    throw ApiException(500, 'No se pudo consolidar la reserva.');
  }

  Future<Map<String, dynamic>> releaseReservation({
    required String referenciaId,
    String referenciaTipo = 'ola_picking',
    String motivo = 'Liberado desde app móvil',
  }) async {
    final res = await _send(
      'POST',
      '/api/v1/productos/reservas/liberar',
      body: {
        'referencia_id': referenciaId,
        'referencia_tipo': referenciaTipo,
        'motivo': motivo,
      },
    );
    if (res is Map<String, dynamic>) {
      return res;
    }
    throw ApiException(500, 'No se pudo liberar la reserva.');
  }
}
