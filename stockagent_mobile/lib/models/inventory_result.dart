/// Línea de comparativa entre stock digital y conteo físico.
class InventoryComparisonItem {
  final String codigo;
  final String nombre;
  final int stockSistema;
  final int stockFisico;
  final int diferencia;
  final String estado;

  const InventoryComparisonItem({
    required this.codigo,
    required this.nombre,
    required this.stockSistema,
    required this.stockFisico,
    required this.diferencia,
    required this.estado,
  });

  bool get isCoincide => diferencia == 0;
  bool get isFaltante => diferencia < 0;
  bool get isSobrante => diferencia > 0;

  factory InventoryComparisonItem.fromJson(Map<String, dynamic> json) {
    return InventoryComparisonItem(
      codigo: json['codigo']?.toString() ?? '',
      nombre: json['nombre']?.toString() ?? '',
      stockSistema: (json['stock_sistema'] as num?)?.toInt() ?? 0,
      stockFisico: (json['stock_fisico'] as num?)?.toInt() ?? 0,
      diferencia: (json['diferencia'] as num?)?.toInt() ?? 0,
      estado: json['estado']?.toString() ?? 'COINCIDE',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'codigo': codigo,
      'nombre': nombre,
      'stock_sistema': stockSistema,
      'stock_fisico': stockFisico,
      'diferencia': diferencia,
      'estado': estado,
    };
  }
}

/// Resumen final del relevamiento de inventario.
class InventorySummary {
  final bool ok;
  final String mensaje;
  final int totalItems;
  final int coinciden;
  final int faltantes;
  final int sobrantes;
  final String? archivoGenerado;
  final List<InventoryComparisonItem> items;

  const InventorySummary({
    required this.ok,
    required this.mensaje,
    required this.totalItems,
    required this.coinciden,
    required this.faltantes,
    required this.sobrantes,
    this.archivoGenerado,
    this.items = const [],
  });

  factory InventorySummary.fromJson(Map<String, dynamic> json) {
    final rawItems = json['comparativa'] as List<dynamic>? ??
        json['items'] as List<dynamic>? ??
        [];
    return InventorySummary(
      ok: json['ok'] as bool? ?? false,
      mensaje: json['mensaje']?.toString() ?? '',
      totalItems: (json['total_items'] as num?)?.toInt() ?? 0,
      coinciden: (json['coinciden'] as num?)?.toInt() ?? 0,
      faltantes: (json['faltantes'] as num?)?.toInt() ?? 0,
      sobrantes: (json['sobrantes'] as num?)?.toInt() ?? 0,
      archivoGenerado: json['archivo_generado']?.toString(),
      items: rawItems
          .whereType<Map<String, dynamic>>()
          .map((i) => InventoryComparisonItem.fromJson(i))
          .toList(),
    );
  }
}
