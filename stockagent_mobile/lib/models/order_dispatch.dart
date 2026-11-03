/// Representa un artículo contenido en un pedido.
class OrderItem {
  final String codigo;
  final String descripcion;
  final int cantidad;

  const OrderItem({
    required this.codigo,
    required this.descripcion,
    required this.cantidad,
  });

  factory OrderItem.fromJson(Map<String, dynamic> json) {
    return OrderItem(
      codigo: json['codigo']?.toString() ?? '',
      descripcion: json['descripcion']?.toString() ?? '',
      cantidad: (json['cantidad'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'codigo': codigo,
      'descripcion': descripcion,
      'cantidad': cantidad,
    };
  }
}

/// Representa un pedido en el flujo logístico de despacho.
class OrderDispatch {
  final int id;
  final String notaPedido;
  final String numeroPedido;
  final String cliente;
  final int bultos;
  final String logistica;
  final String armador;
  final String estadoDespacho;
  final String createdAt;
  final String despachadoAt;
  final String despachadoPor;
  final String entregadoAt;
  final String entregadoPor;
  final List<OrderItem> items;

  const OrderDispatch({
    required this.id,
    required this.notaPedido,
    this.numeroPedido = '',
    required this.cliente,
    required this.bultos,
    this.logistica = '',
    this.armador = '',
    required this.estadoDespacho,
    required this.createdAt,
    this.despachadoAt = '',
    this.despachadoPor = '',
    this.entregadoAt = '',
    this.entregadoPor = '',
    this.items = const [],
  });

  bool get isArmado => estadoDespacho.toLowerCase() == 'armado';
  bool get isDespachado => estadoDespacho.toLowerCase() == 'despachado';
  bool get isEntregado => estadoDespacho.toLowerCase() == 'entregado';

  factory OrderDispatch.fromJson(Map<String, dynamic> json) {
    final rawItems = json['items'] as List<dynamic>? ?? [];
    return OrderDispatch(
      id: json['id'] as int? ?? 0,
      notaPedido: json['nota_pedido']?.toString() ?? '',
      numeroPedido: json['numero_pedido']?.toString() ?? '',
      cliente: json['cliente']?.toString() ?? '',
      bultos: (json['bultos'] as num?)?.toInt() ?? 0,
      logistica: json['logistica']?.toString() ?? '',
      armador: json['armador']?.toString() ?? '',
      estadoDespacho: json['estado_despacho']?.toString() ?? 'armado',
      createdAt: json['created_at']?.toString() ?? '',
      despachadoAt: json['despachado_at']?.toString() ?? '',
      despachadoPor: json['despachado_por']?.toString() ?? '',
      entregadoAt: json['entregado_at']?.toString() ?? '',
      entregadoPor: json['entregado_por']?.toString() ?? '',
      items: rawItems
          .whereType<Map<String, dynamic>>()
          .map((i) => OrderItem.fromJson(i))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'nota_pedido': notaPedido,
      'numero_pedido': numeroPedido,
      'cliente': cliente,
      'bultos': bultos,
      'logistica': logistica,
      'armador': armador,
      'estado_despacho': estadoDespacho,
      'created_at': createdAt,
      'despachado_at': despachadoAt,
      'despachado_por': despachadoPor,
      'entregado_at': entregadoAt,
      'entregado_por': entregadoPor,
      'items': items.map((i) => i.toJson()).toList(),
    };
  }
}
