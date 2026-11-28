import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models/auth_user.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';
import '../services/update_service.dart';
import '../theme/app_theme.dart';
import '../widgets/update_dialog.dart';
import 'config_screen.dart';
import 'login_screen.dart';
import 'tabs/catalog_tab.dart';
import 'tabs/dispatch_tab.dart';
import 'tabs/inventory_tab.dart';

class HomeScreen extends StatefulWidget {
  final StorageService storageService;
  final AuthUser currentUser;

  const HomeScreen({
    super.key,
    required this.storageService,
    required this.currentUser,
  });

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;
  late final ApiService _apiService;
  late final UpdateService _updateService;
  final ValueNotifier<int> _reconnectSyncNotifier = ValueNotifier<int>(0);

  late AuthUser _currentUser;
  bool _serverOnline = true;
  bool _checkingServer = false;
  bool _redirigiendoPor401 = false;
  late bool _isLightTheme;
  late bool _laserMode;
  Timer? _heartbeatTimer;

  @override
  void initState() {
    super.initState();
    _currentUser = widget.currentUser;
    _isLightTheme = widget.storageService.isLightTheme;
    _laserMode = widget.storageService.isLaserScannerMode;
    _updateService = UpdateService(storageService: widget.storageService);
    _apiService = ApiService(
      storageService: widget.storageService,
      onUnauthorized: _manejarSesionExpirada,
    );
    ApiService.globalOnUnauthorized = _manejarSesionExpirada;

    _heartbeatTimer = Timer.periodic(
      const Duration(seconds: 15),
      (_) => _verificarServidor(),
    );
    _verificarServidor();
    _validarSesionInicial();
    _verificarActualizacionesOta();
  }

  @override
  void dispose() {
    _heartbeatTimer?.cancel();
    if (ApiService.globalOnUnauthorized == _manejarSesionExpirada) {
      ApiService.globalOnUnauthorized = null;
    }
    _reconnectSyncNotifier.dispose();
    _apiService.dispose();
    super.dispose();
  }

  void _manejarSesionExpirada() {
    if (!mounted || _redirigiendoPor401) return;
    _redirigiendoPor401 = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('🔒 Tu sesión expiró o fue revocada. Ingresa nuevamente.'),
          backgroundColor: Colors.redAccent,
        ),
      );
      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute(
          builder: (_) => LoginScreen(storageService: widget.storageService),
        ),
        (route) => false,
      );
    });
  }

  Future<void> _validarSesionInicial() async {
    final refreshed = await _apiService.getMe();
    if (refreshed != null && mounted) {
      setState(() => _currentUser = refreshed);
    }
  }

  Future<void> _verificarActualizacionesOta({bool manual = false}) async {
    final cfg = widget.storageService.loadConfig();
    if (!cfg.isValid) return;

    final updateInfo = await _updateService.checkUpdate(cfg.baseUrl);
    if (!mounted) return;

    if (updateInfo == null) {
      if (manual) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('StockAgent Móvil está actualizado a la última versión.')),
        );
      }
      return;
    }

    final currentInfo = await _updateService.getCurrentAppInfo();
    if (!mounted) return;
    final currentCode = (currentInfo['versionCode'] as num?)?.toInt() ?? 1;
    final currentName = currentInfo['versionName']?.toString() ?? '1.0.0';

    final apkPath = updateInfo.apkUrl.startsWith('http')
        ? updateInfo.apkUrl
        : '${cfg.baseUrl}${updateInfo.apkUrl.startsWith('/') ? '' : '/'}${updateInfo.apkUrl}';

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => UpdateDialog(
        updateInfo: updateInfo,
        currentVersionName: currentName,
        currentVersionCode: currentCode,
        downloadFullUrl: apkPath,
        expectedServerOrigin: cfg.baseUrl,
        updateService: _updateService,
      ),
    );
  }

  Future<void> _verificarServidor() async {
    if (_checkingServer) return;
    _checkingServer = true;
    try {
      final bool previa = _serverOnline;
      final online = await _apiService.ping();
      if (mounted && !previa && online) {
        _reconnectSyncNotifier.value++;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('🟢 Conexión reestablecida con el servidor central.'),
            duration: Duration(seconds: 3),
            backgroundColor: Colors.green,
          ),
        );
      }
      if (mounted) {
        setState(() => _serverOnline = online);
      }
    } finally {
      _checkingServer = false;
    }
  }

  Future<void> _toggleThemeMode() async {
    final nuevo = !_isLightTheme;
    setState(() => _isLightTheme = nuevo);
    await widget.storageService.saveLightTheme(nuevo);
    AppTheme.themeModeNotifier.value = nuevo ? ThemeMode.light : ThemeMode.dark;
    SystemChrome.setSystemUIOverlayStyle(
      SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: nuevo ? Brightness.dark : Brightness.light,
        systemNavigationBarColor: nuevo ? AppTheme.lightBg : AppTheme.darkBg,
        systemNavigationBarIconBrightness: nuevo ? Brightness.dark : Brightness.light,
      ),
    );
  }

  Future<void> _toggleLaserMode() async {
    final nuevo = !_laserMode;
    setState(() => _laserMode = nuevo);
    await widget.storageService.saveLaserScannerMode(nuevo);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          nuevo
              ? '⚡ Modo Lector Láser activado (teclado en pantalla oculto)'
              : '⌨️ Modo Teclado Virtual restaurado',
        ),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  Future<void> _cerrarSesion() async {
    final confirmar = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('¿Cerrar Sesión?'),
        content: const Text('Volverás a la pantalla de ingreso.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('CANCELAR'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.primaryRed),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('SALIR'),
          ),
        ],
      ),
    );

    if (confirmar != true) return;

    await _apiService.logout();
    if (!mounted) return;

    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(
        builder: (_) => LoginScreen(storageService: widget.storageService),
      ),
      (route) => false,
    );
  }

  Future<void> _abrirConfiguracion() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ConfigScreen(
          storageService: widget.storageService,
          isModal: true,
        ),
      ),
    );
    _verificarServidor();
  }

  @override
  Widget build(BuildContext context) {
    final cfg = widget.storageService.loadConfig();

    final isDark = Theme.of(context).brightness == Brightness.dark;
    final menuPrimaryColor = isDark ? AppTheme.textPrimary : AppTheme.lightTextPrimary;
    final menuSecondaryColor = isDark ? AppTheme.textSecondary : AppTheme.lightTextSecondary;

    final List<Widget> tabs = [
      InventoryTab(
        apiService: _apiService,
        currentUser: _currentUser,
        isActive: _currentIndex == 0,
        laserMode: _laserMode,
      ),
      DispatchTab(
        apiService: _apiService,
        currentUser: _currentUser,
        isActive: _currentIndex == 1,
        laserMode: _laserMode,
        reconnectSyncTrigger: _reconnectSyncNotifier,
      ),
      CatalogTab(
        apiService: _apiService,
        currentUser: _currentUser,
        isActive: _currentIndex == 2,
      ),
    ];

    final List<String> titulos = [
      'Inventario en Vivo',
      'Despacho y Entregas',
      'Consulta de Catálogo',
    ];

    return Scaffold(
      appBar: AppBar(
        title: Text(titulos[_currentIndex]),
        leadingWidth: 96,
        leading: Padding(
          padding: const EdgeInsets.only(left: 10),
          child: Center(
            child: Semantics(
              label: _serverOnline ? 'Servidor en línea' : 'Servidor sin conexión',
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: _serverOnline
                      ? Colors.green.withValues(alpha: 0.16)
                      : Colors.red.withValues(alpha: 0.16),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: _serverOnline
                        ? Colors.greenAccent.withValues(alpha: 0.5)
                        : Colors.redAccent.withValues(alpha: 0.5),
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      _serverOnline ? Icons.cloud_done_rounded : Icons.cloud_off_rounded,
                      size: 14,
                      color: _serverOnline ? Colors.greenAccent : Colors.redAccent,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      _serverOnline ? 'ONLINE' : 'OFFLINE',
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                        color: _serverOnline ? Colors.greenAccent : Colors.redAccent,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
        actions: [
          PopupMenuButton<String>(
            icon: const Icon(Icons.more_vert),
            onSelected: (val) {
              if (val == 'theme') _toggleThemeMode();
              if (val == 'laser') _toggleLaserMode();
              if (val == 'update') _verificarActualizacionesOta(manual: true);
              if (val == 'config') _abrirConfiguracion();
              if (val == 'logout') _cerrarSesion();
            },
            itemBuilder: (ctx) => [
              PopupMenuItem(
                enabled: false,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _currentUser.nombre,
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: menuPrimaryColor,
                      ),
                    ),
                    Text(
                      'Rol: ${_currentUser.role.toUpperCase()}',
                      style: TextStyle(fontSize: 11, color: menuSecondaryColor),
                    ),
                    Text(
                      'PC: ${cfg.host}:${cfg.port} (${cfg.normalizedProtocol.toUpperCase()})',
                      style: TextStyle(fontSize: 10, color: menuSecondaryColor),
                    ),
                  ],
                ),
              ),
              const PopupMenuDivider(),
              PopupMenuItem(
                value: 'theme',
                child: Row(
                  children: [
                    Icon(
                      _isLightTheme ? Icons.dark_mode_outlined : Icons.wb_sunny_outlined,
                      size: 18,
                    ),
                    const SizedBox(width: 10),
                    Text(_isLightTheme ? 'Modo Oscuro Depósito' : 'Modo Claro Alto Contraste'),
                  ],
                ),
              ),
              PopupMenuItem(
                value: 'laser',
                child: Row(
                  children: [
                    Icon(
                      _laserMode ? Icons.keyboard_outlined : Icons.bolt_rounded,
                      size: 18,
                    ),
                    const SizedBox(width: 10),
                    Text(_laserMode ? 'Activar Teclado Virtual' : 'Modo Lector Láser'),
                  ],
                ),
              ),
              const PopupMenuItem(
                value: 'update',
                child: Row(
                  children: [
                    Icon(Icons.system_update_outlined, size: 18),
                    SizedBox(width: 10),
                    Text('Buscar Actualización APK'),
                  ],
                ),
              ),
              const PopupMenuItem(
                value: 'config',
                child: Row(
                  children: [
                    Icon(Icons.settings_outlined, size: 18),
                    SizedBox(width: 10),
                    Text('Ajustes de Servidor'),
                  ],
                ),
              ),
              const PopupMenuItem(
                value: 'logout',
                child: Row(
                  children: [
                    Icon(Icons.logout, size: 18, color: Colors.redAccent),
                    SizedBox(width: 10),
                    Text('Cerrar Sesión', style: TextStyle(color: Colors.redAccent)),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
      body: IndexedStack(
        index: _currentIndex,
        children: tabs,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        indicatorColor: AppTheme.primaryRed.withValues(alpha: 0.2),
        onDestinationSelected: (idx) {
          FocusScope.of(context).unfocus();
          setState(() => _currentIndex = idx);
        },
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.inventory_2_outlined),
            selectedIcon: Icon(Icons.inventory_2, color: AppTheme.primaryRed),
            label: 'Inventario',
          ),
          NavigationDestination(
            icon: Icon(Icons.local_shipping_outlined),
            selectedIcon: Icon(Icons.local_shipping, color: AppTheme.primaryRed),
            label: 'Despacho',
          ),
          NavigationDestination(
            icon: Icon(Icons.search_outlined),
            selectedIcon: Icon(Icons.search, color: AppTheme.primaryRed),
            label: 'Catálogo',
          ),
        ],
      ),
    );
  }
}
