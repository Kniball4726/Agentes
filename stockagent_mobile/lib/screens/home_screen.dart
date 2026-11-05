import 'dart:async';
import 'package:flutter/material.dart';

import '../models/auth_user.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';
import '../theme/app_theme.dart';
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

  bool _serverOnline = true;
  Timer? _heartbeatTimer;

  @override
  void initState() {
    super.initState();
    _apiService = ApiService(storageService: widget.storageService);
    _heartbeatTimer = Timer.periodic(const Duration(seconds: 15), (_) => _verificarServidor());
    _verificarServidor();
  }

  @override
  void dispose() {
    _heartbeatTimer?.cancel();
    super.dispose();
  }

  Future<void> _verificarServidor() async {
    final bool previa = _serverOnline;
    final online = await _apiService.ping();
    if (mounted && !previa && online) {
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

    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => LoginScreen(storageService: widget.storageService),
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

    final List<Widget> tabs = [
      InventoryTab(apiService: _apiService, currentUser: widget.currentUser),
      DispatchTab(apiService: _apiService, currentUser: widget.currentUser),
      CatalogTab(apiService: _apiService, currentUser: widget.currentUser),
    ];

    final List<String> titulos = [
      'Inventario en Vivo',
      'Despacho y Entregas',
      'Consulta de Catálogo',
    ];

    return Scaffold(
      appBar: AppBar(
        title: Text(titulos[_currentIndex]),
        leading: Padding(
          padding: const EdgeInsets.only(left: 12),
          child: Center(
            child: Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _serverOnline ? Colors.greenAccent : Colors.redAccent,
              ),
            ),
          ),
        ),
        actions: [
          PopupMenuButton<String>(
            icon: const Icon(Icons.more_vert),
            color: AppTheme.cardBg,
            onSelected: (val) {
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
                      widget.currentUser.nombre,
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    Text(
                      'Rol: ${widget.currentUser.role.toUpperCase()}',
                      style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                    ),
                    Text(
                      'PC: ${cfg.host}:${cfg.port}',
                      style: const TextStyle(fontSize: 10, color: Colors.white38),
                    ),
                  ],
                ),
              ),
              const PopupMenuDivider(),
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
        backgroundColor: AppTheme.cardBg,
        indicatorColor: AppTheme.primaryRed.withValues(alpha: 0.2),
        onDestinationSelected: (idx) {
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
