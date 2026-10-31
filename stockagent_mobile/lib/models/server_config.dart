/// Modelo inmutable de configuración del servidor StockAgent.
class ServerConfig {
  final String host;
  final String port;
  final String protocol;

  static const String defaultHost = '192.168.100.19';
  static const String defaultPort = '8550';
  static const String defaultProtocol = 'http';

  const ServerConfig({
    this.host = defaultHost,
    this.port = defaultPort,
    this.protocol = defaultProtocol,
  });

  /// Crea una configuración inicial por defecto
  factory ServerConfig.empty() {
    return const ServerConfig(host: defaultHost, port: defaultPort, protocol: defaultProtocol);
  }

  /// Verifica si el host no está vacío y tiene formato válido
  bool get isValid {
    final trimmedHost = host.trim();
    if (trimmedHost.isEmpty) return false;
    // Admite nombres de host, IP local o dominios
    return !trimmedHost.contains(' ') && trimmedHost.length >= 3;
  }

  /// Retorna el puerto normalizado
  String get normalizedPort {
    final p = port.trim();
    return p.isEmpty ? defaultPort : p;
  }

  /// Retorna el protocolo normalizado en minúsculas
  String get normalizedProtocol {
    final pr = protocol.trim().toLowerCase();
    return (pr == 'https') ? 'https' : 'http';
  }

  /// URL HTTP/HTTPS completa para acceder a la aplicación
  String get fullUrl {
    if (!isValid) return '';
    return '$normalizedProtocol://${host.trim()}:$normalizedPort';
  }

  /// URL WebSocket para streaming de eventos en vivo
  String get wsUrl {
    if (!isValid) return '';
    final wsScheme = normalizedProtocol == 'https' ? 'wss' : 'ws';
    return '$wsScheme://${host.trim()}:$normalizedPort/ws';
  }

  /// Crea una copia con campos modificados opcionalmente
  ServerConfig copyWith({
    String? host,
    String? port,
    String? protocol,
  }) {
    return ServerConfig(
      host: host ?? this.host,
      port: port ?? this.port,
      protocol: protocol ?? this.protocol,
    );
  }

  /// Serialización a Map para almacenamiento
  Map<String, dynamic> toJson() {
    return {
      'host': host.trim(),
      'port': normalizedPort,
      'protocol': normalizedProtocol,
    };
  }

  /// Deserialización desde Map
  factory ServerConfig.fromJson(Map<String, dynamic> json) {
    return ServerConfig(
      host: json['host'] as String? ?? '',
      port: json['port'] as String? ?? defaultPort,
      protocol: json['protocol'] as String? ?? defaultProtocol,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is ServerConfig &&
          runtimeType == other.runtimeType &&
          host == other.host &&
          port == other.port &&
          protocol == other.protocol;

  @override
  int get hashCode => host.hashCode ^ port.hashCode ^ protocol.hashCode;

  @override
  String toString() => fullUrl;
}
