/// Modelos para multi-ubicación por zonas, lotes FEFO y reservas de stock (Fase 4).
class ProductLocation {
  final int id;
  final String productCode;
  final String ubicacion;
  final String tipoZona;
  final int stock;
  final int capacidadMax;
  final bool esPrincipal;

  const ProductLocation({
    required this.id,
    required this.productCode,
    required this.ubicacion,
    required this.tipoZona,
    required this.stock,
    this.capacidadMax = 0,
    this.esPrincipal = false,
  });

  factory ProductLocation.fromJson(Map<String, dynamic> json) {
    return ProductLocation(
      id: (json['id'] as num?)?.toInt() ?? 0,
      productCode: json['product_code']?.toString() ?? '',
      ubicacion: json['ubicacion']?.toString() ?? '',
      tipoZona: json['tipo_zona']?.toString() ?? 'picking',
      stock: (json['stock'] as num?)?.toInt() ?? 0,
      capacidadMax: (json['capacidad_max'] as num?)?.toInt() ?? 0,
      esPrincipal: json['es_principal'] as bool? ?? false,
    );
  }
}

class ProductLocationsSummary {
  final String productCode;
  final String productName;
  final int stockFisico;
  final int stockReservado;
  final int stockDisponible;
  final List<ProductLocation> ubicaciones;

  const ProductLocationsSummary({
    required this.productCode,
    required this.productName,
    required this.stockFisico,
    required this.stockReservado,
    required this.stockDisponible,
    required this.ubicaciones,
  });

  factory ProductLocationsSummary.fromJson(Map<String, dynamic> json) {
    final rawUbics = json['ubicaciones'] as List<dynamic>? ?? [];
    return ProductLocationsSummary(
      productCode: json['product_code']?.toString() ?? '',
      productName: json['product_name']?.toString() ?? '',
      stockFisico: (json['stock_fisico'] as num?)?.toInt() ?? 0,
      stockReservado: (json['stock_reservado'] as num?)?.toInt() ?? 0,
      stockDisponible: (json['stock_disponible'] as num?)?.toInt() ?? 0,
      ubicaciones: rawUbics
          .whereType<Map<String, dynamic>>()
          .map(ProductLocation.fromJson)
          .toList(),
    );
  }
}

class StockLot {
  final int id;
  final String productCode;
  final String productName;
  final String lote;
  final String ubicacion;
  final String fechaVencimiento;
  final int stock;
  final String estado;
  final int? diasParaVencer;
  final bool vencido;
  final String nivelAlerta;

  const StockLot({
    required this.id,
    required this.productCode,
    this.productName = '',
    required this.lote,
    this.ubicacion = '',
    this.fechaVencimiento = '',
    required this.stock,
    this.estado = 'disponible',
    this.diasParaVencer,
    this.vencido = false,
    this.nivelAlerta = '',
  });

  factory StockLot.fromJson(Map<String, dynamic> json) {
    return StockLot(
      id: (json['id'] as num?)?.toInt() ?? 0,
      productCode: json['product_code']?.toString() ?? '',
      productName: json['product_name']?.toString() ?? '',
      lote: json['lote']?.toString() ?? '',
      ubicacion: json['ubicacion']?.toString() ?? '',
      fechaVencimiento: json['fecha_vencimiento']?.toString() ?? '',
      stock: (json['stock'] as num?)?.toInt() ?? 0,
      estado: json['estado']?.toString() ?? 'disponible',
      diasParaVencer: (json['dias_para_vencer'] as num?)?.toInt(),
      vencido: json['vencido'] as bool? ?? false,
      nivelAlerta: json['nivel_alerta']?.toString() ?? '',
    );
  }
}

class StockReservation {
  final int id;
  final String referenciaTipo;
  final String referenciaId;
  final String productCode;
  final String productName;
  final int cantidad;
  final String estado;
  final String ubicacion;
  final String usuario;
  final String nota;

  const StockReservation({
    required this.id,
    required this.referenciaTipo,
    required this.referenciaId,
    required this.productCode,
    this.productName = '',
    required this.cantidad,
    required this.estado,
    this.ubicacion = '',
    this.usuario = 'sistema',
    this.nota = '',
  });

  factory StockReservation.fromJson(Map<String, dynamic> json) {
    return StockReservation(
      id: (json['id'] as num?)?.toInt() ?? 0,
      referenciaTipo: json['referencia_tipo']?.toString() ?? 'ola_picking',
      referenciaId: json['referencia_id']?.toString() ?? '',
      productCode: json['product_code']?.toString() ?? '',
      productName: json['product_name']?.toString() ?? '',
      cantidad: (json['cantidad'] as num?)?.toInt() ?? 0,
      estado: json['estado']?.toString() ?? 'activa',
      ubicacion: json['ubicacion']?.toString() ?? '',
      usuario: json['usuario']?.toString() ?? 'sistema',
      nota: json['nota']?.toString() ?? '',
    );
  }
}
