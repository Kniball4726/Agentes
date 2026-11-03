/// Representa un producto del catálogo con su stock y ubicación física.
class ProductItem {
  final String code;
  final String name;
  final int stock;
  final int stockFisico;
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
    this.stockMinimo = 0,
    this.stockMaximo = 0,
    this.codBarras = '',
    this.ubicacion = '',
    this.active = true,
  });

  bool get hasBarcode => codBarras.trim().isNotEmpty;
  bool get hasLocation => ubicacion.trim().isNotEmpty;
  bool get isCritical => stock <= stockMinimo;

  factory ProductItem.fromJson(Map<String, dynamic> json) {
    return ProductItem(
      code: json['code']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      stock: (json['stock'] as num?)?.toInt() ?? 0,
      stockFisico: (json['stock_fisico'] as num?)?.toInt() ?? 0,
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
      stockMinimo: stockMinimo ?? this.stockMinimo,
      stockMaximo: stockMaximo ?? this.stockMaximo,
      codBarras: codBarras ?? this.codBarras,
      ubicacion: ubicacion ?? this.ubicacion,
      active: active ?? this.active,
    );
  }
}
