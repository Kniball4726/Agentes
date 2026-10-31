import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';
import '../models/server_config.dart';
import '../services/storage_service.dart';
import '../theme/app_theme.dart';
import '../widgets/offline_placeholder.dart';
import 'config_screen.dart';

class AppScreen extends StatefulWidget {
  final StorageService storageService;

  const AppScreen({super.key, required this.storageService});

  @override
  State<AppScreen> createState() => _AppScreenState();
}

class _AppScreenState extends State<AppScreen> {
  late final WebViewController _controller;
  bool _isLoading = true;
  double _progress = 0;
  bool _hasError = false;
  late ServerConfig _config;

  @override
  void initState() {
    super.initState();
    _config = widget.storageService.loadConfig();
    _initController();
  }

  void _initController() {
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(AppTheme.darkBg)
      ..setNavigationDelegate(
        NavigationDelegate(
          onProgress: (int progress) {
            setState(() {
              _progress = progress / 100.0;
            });
          },
          onPageStarted: (String url) {
            setState(() {
              _isLoading = true;
              _hasError = false;
            });
          },
          onPageFinished: (String url) {
            setState(() {
              _isLoading = false;
            });
          },
          onWebResourceError: (WebResourceError error) {
            if (error.isForMainFrame ?? true) {
              setState(() {
                _isLoading = false;
                _hasError = true;
              });
            }
          },
        ),
      )
      ..loadRequest(Uri.parse(_config.fullUrl));
  }

  void _abrirAjustes() async {
    final modificado = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => ConfigScreen(
          storageService: widget.storageService,
          isModal: true,
        ),
      ),
    );

    if (modificado == true && mounted) {
      final nuevaConfig = widget.storageService.loadConfig();
      setState(() {
        _config = nuevaConfig;
        _hasError = false;
        _isLoading = true;
      });
      _controller.loadRequest(Uri.parse(nuevaConfig.fullUrl));
    }
  }

  void _reintentar() {
    setState(() {
      _hasError = false;
      _isLoading = true;
    });
    _controller.loadRequest(Uri.parse(_config.fullUrl));
  }

  Future<bool> _confirmarSalida() async {
    if (await _controller.canGoBack()) {
      _controller.goBack();
      return false;
    }

    if (!mounted) return false;
    final salir = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.cardBg,
        title: const Text('Salir de StockAgent'),
        content: const Text('¿Deseas cerrar la aplicación?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancelar', style: TextStyle(color: AppTheme.textSecondary)),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Salir'),
          ),
        ],
      ),
    );

    return salir ?? false;
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) async {
        if (didPop) return;
        final debeSalir = await _confirmarSalida();
        if (debeSalir && context.mounted) {
          Navigator.of(context).pop();
        }
      },
      child: Scaffold(
        backgroundColor: AppTheme.darkBg,
        body: SafeArea(
          child: Stack(
            children: [
              if (!_hasError)
                RefreshIndicator(
                  color: AppTheme.primaryRed,
                  backgroundColor: AppTheme.cardBg,
                  onRefresh: () => _controller.reload(),
                  child: WebViewWidget(controller: _controller),
                ),

              if (_isLoading && !_hasError)
                Center(
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
                    margin: const EdgeInsets.symmetric(horizontal: 32),
                    decoration: BoxDecoration(
                      color: AppTheme.cardBg,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppTheme.borderColor),
                    ),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const SizedBox(
                          width: 38,
                          height: 38,
                          child: CircularProgressIndicator(
                            strokeWidth: 3,
                            valueColor: AlwaysStoppedAnimation<Color>(AppTheme.primaryRed),
                          ),
                        ),
                        const SizedBox(height: 18),
                        const Text(
                          'Conectando a StockAgent...',
                          style: TextStyle(
                            color: AppTheme.textPrimary,
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          _config.fullUrl,
                          style: const TextStyle(
                            color: AppTheme.textSecondary,
                            fontSize: 13,
                          ),
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
                  ),
                ),

              if (_isLoading && !_hasError)
                Positioned(
                  top: 0,
                  left: 0,
                  right: 0,
                  child: LinearProgressIndicator(
                    value: _progress > 0 ? _progress : null,
                    backgroundColor: Colors.transparent,
                    valueColor: const AlwaysStoppedAnimation<Color>(AppTheme.primaryRed),
                    minHeight: 3,
                  ),
                ),

              if (_hasError)
                OfflinePlaceholder(
                  targetUrl: _config.fullUrl,
                  onRetry: _reintentar,
                  onOpenSettings: _abrirAjustes,
                ),

              Positioned(
                bottom: 16,
                right: 16,
                child: Opacity(
                  opacity: 0.85,
                  child: FloatingActionButton.small(
                    heroTag: 'btnSettings',
                    backgroundColor: AppTheme.surfaceColor,
                    foregroundColor: AppTheme.textPrimary,
                    onPressed: _abrirAjustes,
                    tooltip: 'Cambiar IP del Servidor',
                    child: const Icon(Icons.settings_rounded, size: 20),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
