import 'dart:convert';

/// Representa el usuario autenticado en la sesión de la app móvil.
class AuthUser {
  final int id;
  final String username;
  final String role;
  final String nombre;
  final String? email;
  final String? token;

  const AuthUser({
    required this.id,
    required this.username,
    required this.role,
    required this.nombre,
    this.email,
    this.token,
  });

  bool get isMaster => role.toLowerCase() == 'master';
  bool get isAdmin => role.toLowerCase() == 'administrador' || isMaster;
  bool get isOperator => role.toLowerCase() == 'operador' || isAdmin;

  factory AuthUser.fromJson(Map<String, dynamic> json, {String? token}) {
    return AuthUser(
      id: json['id'] as int? ?? 0,
      username: json['username'] as String? ?? '',
      role: json['role'] as String? ?? 'operador',
      nombre: json['nombre'] as String? ?? json['username'] as String? ?? '',
      email: json['email'] as String?,
      token: token ?? json['token'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'username': username,
      'role': role,
      'nombre': nombre,
      if (email != null) 'email': email,
      if (token != null) 'token': token,
    };
  }

  String serialize() => jsonEncode(toJson());

  static AuthUser? deserialize(String? raw) {
    if (raw == null || raw.trim().isEmpty) return null;
    try {
      final decoded = jsonDecode(raw) as Map<String, dynamic>;
      return AuthUser.fromJson(decoded);
    } catch (_) {
      return null;
    }
  }
}
