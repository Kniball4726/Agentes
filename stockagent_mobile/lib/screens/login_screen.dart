import 'package:flutter/material.dart';
import '../models/auth_user.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';
import '../theme/app_theme.dart';
import 'config_screen.dart';
import 'home_screen.dart';

class LoginScreen extends StatefulWidget {
  final StorageService storageService;

  const LoginScreen({super.key, required this.storageService});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _userController = TextEditingController();
  final _passwordController = TextEditingController();

  late final ApiService _apiService;
  bool _isLoading = false;
  bool _obscurePassword = true;
  String? _errorMessage;
  bool? _serverOnline;

  @override
  void initState() {
    super.initState();
    _apiService = ApiService(storageService: widget.storageService);
    _verificarServidor();
  }

  @override
  void dispose() {
    _userController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _verificarServidor() async {
    final online = await _apiService.ping();
    if (mounted) {
      setState(() => _serverOnline = online);
    }
  }

  Future<void> _iniciarSesion() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final user = await _apiService.login(
        _userController.text,
        _passwordController.text,
      );

      if (!mounted) return;
      _navegarAHome(user);
    } on ApiException catch (e) {
      setState(() {
        _errorMessage = e.message;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = 'Error inesperado: $e';
        _isLoading = false;
      });
    }
  }

  void _navegarAHome(AuthUser user) {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => HomeScreen(
          storageService: widget.storageService,
          currentUser: user,
        ),
      ),
    );
  }

  Future<void> _abrirConfiguracion() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ConfigScreen(storageService: widget.storageService),
      ),
    );
    _verificarServidor();
  }

  @override
  Widget build(BuildContext context) {
    final cfg = widget.storageService.loadConfig();

    return Scaffold(
      appBar: AppBar(
        title: const Text('StockAgent'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            tooltip: 'Configurar Servidor',
            onPressed: _abrirConfiguracion,
          ),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Form(
                key: _formKey,
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // Indicador de estado del servidor
                    GestureDetector(
                      onTap: _verificarServidor,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                        decoration: BoxDecoration(
                          color: (_serverOnline == true)
                              ? Colors.green.withValues(alpha: 0.15)
                              : (_serverOnline == false)
                                  ? Colors.red.withValues(alpha: 0.15)
                                  : AppTheme.surfaceColor,
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(
                            color: (_serverOnline == true)
                                ? Colors.green.withValues(alpha: 0.4)
                                : (_serverOnline == false)
                                    ? Colors.red.withValues(alpha: 0.4)
                                    : AppTheme.borderColor,
                          ),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Container(
                              width: 8,
                              height: 8,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: (_serverOnline == true)
                                    ? Colors.greenAccent
                                    : (_serverOnline == false)
                                        ? Colors.redAccent
                                        : Colors.amber,
                              ),
                            ),
                            const SizedBox(width: 8),
                            Flexible(
                              child: Text(
                                (_serverOnline == true)
                                    ? 'Servidor activo en ${cfg.host}:${cfg.port}'
                                    : (_serverOnline == false)
                                        ? 'Sin respuesta en ${cfg.host}:${cfg.port} (Toca para reintentar)'
                                        : 'Verificando enlace...',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: (_serverOnline == true)
                                      ? Colors.greenAccent
                                      : (_serverOnline == false)
                                          ? Colors.redAccent
                                          : AppTheme.textSecondary,
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 32),

                    // Icono de la App
                    Center(
                      child: Container(
                        width: 80,
                        height: 80,
                        decoration: BoxDecoration(
                          color: AppTheme.primaryRed.withValues(alpha: 0.15),
                          shape: BoxShape.circle,
                          border: Border.all(color: AppTheme.primaryRed, width: 2),
                        ),
                        child: const Icon(
                          Icons.inventory_2_rounded,
                          size: 42,
                          color: AppTheme.primaryRed,
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    const Text(
                      'Terminal Móvil',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.textPrimary,
                        letterSpacing: 0.5,
                      ),
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      'Ingresa tus credenciales del depósito',
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 14, color: AppTheme.textSecondary),
                    ),
                    const SizedBox(height: 28),

                    // Mensaje de Error
                    if (_errorMessage != null) ...[
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.red.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: Colors.red.withValues(alpha: 0.4)),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.error_outline, color: Colors.redAccent, size: 20),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Text(
                                _errorMessage!,
                                style: const TextStyle(color: Colors.redAccent, fontSize: 13),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 18),
                    ],

                    // Campo Usuario
                    TextFormField(
                      controller: _userController,
                      decoration: const InputDecoration(
                        labelText: 'Usuario o Correo',
                        prefixIcon: Icon(Icons.person_outline),
                      ),
                      textInputAction: TextInputAction.next,
                      validator: (val) {
                        if (val == null || val.trim().isEmpty) {
                          return 'Ingresa tu usuario';
                        }
                        return null;
                      },
                    ),
                    const SizedBox(height: 16),

                    // Campo Contraseña
                    TextFormField(
                      controller: _passwordController,
                      obscureText: _obscurePassword,
                      decoration: InputDecoration(
                        labelText: 'Contraseña',
                        prefixIcon: const Icon(Icons.lock_outline),
                        suffixIcon: IconButton(
                          icon: Icon(
                            _obscurePassword ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                            color: AppTheme.textSecondary,
                          ),
                          onPressed: () {
                            setState(() => _obscurePassword = !_obscurePassword);
                          },
                        ),
                      ),
                      textInputAction: TextInputAction.done,
                      onFieldSubmitted: (_) => _iniciarSesion(),
                      validator: (val) {
                        if (val == null || val.isEmpty) {
                          return 'Ingresa tu contraseña';
                        }
                        return null;
                      },
                    ),
                    const SizedBox(height: 24),

                    // Botón Iniciar Sesión
                    SizedBox(
                      height: 52,
                      child: ElevatedButton(
                        onPressed: _isLoading ? null : _iniciarSesion,
                        child: _isLoading
                            ? const SizedBox(
                                width: 22,
                                height: 22,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2.5,
                                  color: Colors.white,
                                ),
                              )
                            : const Text(
                                'INGRESAR',
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                  letterSpacing: 1,
                                ),
                              ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
