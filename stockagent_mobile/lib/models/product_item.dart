/// Representa un producto del catálogo con su stock, saldo disponible y ubicación física.
class ProductItem {
  final String code;
  final String name;
  final int stock;
  final int stockFisico;
  final int stockReservado;
  final int? stockDisponible;
  final int stockMinimo;
  final int stockMaximo;
  final String codBarras;
  final String ubicacion;
  final bool active;

  const ProductItem({
    required this.code,
    required this.name,
    required this.stock,
    this.stockFisico = 0,
    this.stockReservado = 0,
    this.stockDisponible,
    this.stockMinimo = 0,
    this.stockMaximo = 0,
    this.codBarras = '',
    this.ubicacion = '',
    this.active = true,
  });

  int get disponibleNeto =>
      stockDisponible ??
      ((stock - stockReservado) < 0 ? 0 : stock - stockReservado);

  bool get hasBarcode => codBarras.trim().isNotEmpty;
  bool get hasLocation => ubicacion.trim().isNotEmpty;
  bool get hasReservas => stockReservado > 0;
  bool get isCritical => disponibleNeto <= stockMinimo;

  factory ProductItem.fromJson(Map<String, dynamic> json) {
    final parsedStock = (json['stock'] as num?)?.toInt() ?? 0;
    final parsedReservado = (json['stock_reservado'] as num?)?.toInt() ?? 0;
    final rawDisp = json['stock_disponible'];
    final parsedDisp = rawDisp is num
        ? rawDisp.toInt()
        : ((parsedStock - parsedReservado) < 0
            ? 0
            : parsedStock - parsedReservado);

    return ProductItem(
      code: json['code']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      stock: parsedStock,
      stockFisico: (json['stock_fisico'] as num?)?.toInt() ?? 0,
      stockReservado: parsedReservado,
      stockDisponible: parsedDisp,
      stockMinimo: (json['stock_minimo'] as num?)?.toInt() ?? 0,
      stockMaximo: (json['stock_maximo'] as num?)?.toInt() ?? 0,
      codBarras: json['cod_barras']?.toString() ?? '',
      ubicacion: json['ubicacion']?.toString() ?? '',
      active: json['active'] as bool? ?? true,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'code': code,
      'name': name,
      'stock': stock,
      'stock_fisico': stockFisico,
      'stock_reservado': stockReservado,
      'stock_disponible': disponibleNeto,
      'stock_minimo': stockMinimo,
      'stock_maximo': stockMaximo,
      'cod_barras': codBarras,
      'ubicacion': ubicacion,
      'active': active,
    };
  }

  ProductItem copyWith({
    String? code,
    String? name,
    int? stock,
    int? stockFisico,
    int? stockReservado,
    int? stockDisponible,
    int? stockMinimo,
    int? stockMaximo,
    String? codBarras,
    String? ubicacion,
    bool? active,
  }) {
    return ProductItem(
      code: code ?? this.code,
      name: name ?? this.name,
      stock: stock ?? this.stock,
      stockFisico: stockFisico ?? this.stockFisico,
      stockReservado: stockReservado ?? this.stockReservado,
      stockDisponible: stockDisponible ?? this.stockDisponible,
      stockMinimo: stockMinimo ?? this.stockMinimo,
      stockMaximo: stockMaximo ?? this.stockMaximo,
      codBarras: codBarras ?? this.codBarras,
      ubicacion: ubicacion ?? this.ubicacion,
      active: active ?? this.active,
    );
  }
}
