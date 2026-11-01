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
    return const ServerConfig(
      host: '',
      port: defaultPort,
      protocol: defaultProtocol,
    );
  }

  /// Parser inteligente y sanitizador para entradas de usuario (IP, URL o Host:Port)
  factory ServerConfig.fromUserInput({
    required String rawHost,
    String? rawPort,
    String? rawProtocol,
  }) {
    String cleanHost = rawHost.trim();
    String detectedProtocol = (rawProtocol ?? defaultProtocol).trim().toLowerCase();
    String detectedPort = (rawPort ?? defaultPort).trim();

    // 1. Detectar prefijo de protocolo si fue pegado en el campo de host (ej: http:// o https://)
    if (cleanHost.toLowerCase().startsWith('https://')) {
      detectedProtocol = 'https';
      cleanHost = cleanHost.substring(8);
    } else if (cleanHost.toLowerCase().startsWith('http://')) {
      detectedProtocol = 'http';
      cleanHost = cleanHost.substring(7);
    }

    // 2. Remover rutas o barras finales (ej: 192.168.1.45/ -> 192.168.1.45)
    if (cleanHost.contains('/')) {
      cleanHost = cleanHost.split('/').first;
    }

    // 3. Detectar puerto si está incluido en el host (ej: 192.168.1.45:8550)
    if (cleanHost.contains(':')) {
      final parts = cleanHost.split(':');
      cleanHost = parts[0];
      if (parts.length > 1 && parts[1].isNotEmpty) {
        detectedPort = parts[1];
      }
    }

    return ServerConfig(
      host: cleanHost.trim(),
      port: detectedPort.isEmpty ? defaultPort : detectedPort,
      protocol: detectedProtocol == 'https' ? 'https' : 'http',
    );
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

  /// Alias de conveniencia para la URL base del servidor
  String get baseUrl => fullUrl;

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
