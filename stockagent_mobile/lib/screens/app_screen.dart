import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_android/webview_flutter_android.dart';
import '../models/server_config.dart';
import '../services/network_service.dart';
import '../services/storage_service.dart';
import '../theme/app_theme.dart';
import '../services/update_service.dart';
import '../widgets/connection_status_indicator.dart';
import '../widgets/offline_placeholder.dart';
import '../widgets/update_dialog.dart';
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
  String? _errorMessage;
  bool _pageLoadedSuccessfully = false;
  late ServerConfig _config;
  final NetworkService _networkService = NetworkService();

  // Estado del icono de conexión con el servidor móvil
  static const Duration _heartbeatInterval = Duration(seconds: 10);
  static const MethodChannel _filePickerChannel = MethodChannel('com.stockagent.mobile/file_picker');
  ServerLinkState _linkState = ServerLinkState.connecting;
  String? _linkDetail;
  Timer? _heartbeatTimer;
  bool _heartbeatRunning = false;

  // Repositorio y verificación de actualizaciones OTA
  final UpdateService _updateService = UpdateService();
  AppUpdateInfo? _availableUpdate;
  String _currentVersionName = '1.0.0';
  int _currentVersionCode = 1;
  bool _checkingUpdate = false;

  @override
  void dispose() {
    _heartbeatTimer?.cancel();
    _networkService.dispose();
    super.dispose();
  }

  @override
  void initState() {
    super.initState();
    _config = widget.storageService.loadConfig();
    _initController();
    _heartbeatTimer = Timer.periodic(_heartbeatInterval, (_) => _verificarEnlace());
    _verificarActualizaciones();
  }

  /// Verifica si hay actualizaciones del APK en el repositorio local de la PC
  Future<void> _verificarActualizaciones() async {
    if (_checkingUpdate || !mounted) return;
    _checkingUpdate = true;
    try {
      final info = await _updateService.getCurrentAppInfo();
      _currentVersionCode = (info['versionCode'] as num?)?.toInt() ?? 1;
      _currentVersionName = info['versionName']?.toString() ?? '1.0.0';

      final update = await _updateService.checkUpdate(_config.baseUrl);
      if (mounted) {
        setState(() {
          _availableUpdate = update;
        });
      }
    } catch (_) {
    } finally {
      _checkingUpdate = false;
    }
  }

  /// Abre el diálogo para descargar e instalar el nuevo APK
  void _abrirDialogoActualizacion() {
    if (_availableUpdate == null) return;
    final downloadUrl = _availableUpdate!.apkUrl.startsWith('http')
        ? _availableUpdate!.apkUrl
        : '${_config.baseUrl}${_availableUpdate!.apkUrl}';

    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => UpdateDialog(
        updateInfo: _availableUpdate!,
        currentVersionName: _currentVersionName,
        currentVersionCode: _currentVersionCode,
        downloadFullUrl: downloadUrl,
        updateService: _updateService,
      ),
    );
  }

  /// Verifica en segundo plano que el servidor siga respondiendo y actualiza el icono.
  Future<void> _verificarEnlace({bool mostrarConectando = false}) async {
    if (_heartbeatRunning || !mounted) return;
    _heartbeatRunning = true;
    try {
      if (mostrarConectando) {
        setState(() => _linkState = ServerLinkState.connecting);
      }
      final result = await _networkService.testConnection(
        _config,
        timeout: const Duration(seconds: 4),
      );
      if (!mounted) return;
      setState(() {
        _linkState = result.isSuccess
            ? ServerLinkState.connected
            : ServerLinkState.disconnected;
        _linkDetail = result.isSuccess ? _config.fullUrl : result.message;
      });
      if (result.isSuccess) {
        _verificarActualizaciones();
      }
    } finally {
      _heartbeatRunning = false;
    }
  }

  void _initController() {
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..enableZoom(false)
      ..setBackgroundColor(AppTheme.darkBg)
      ..setNavigationDelegate(
        NavigationDelegate(
          onProgress: (int progress) {
            if (mounted) {
              setState(() {
                _progress = progress / 100.0;
              });
            }
          },
          onPageStarted: (String url) {
            if (mounted) {
              setState(() {
                _isLoading = true;
                _hasError = false;
              });
            }
          },
          onPageFinished: (String url) {
            if (mounted) {
              setState(() {
                _isLoading = false;
                _pageLoadedSuccessfully = true;
              });
            }
          },
          // El servidor en modo HTTPS usa un certificado autofirmado: aceptarlo
          onSslAuthError: (SslAuthError error) {
            error.proceed();
          },
          onWebResourceError: (WebResourceError error) {
            // Solo marcar error crítico si es el marco principal y no se pudo cargar la página
            if (error.isForMainFrame == true) {
              final isFatalError = !_pageLoadedSuccessfully ||
                  error.errorCode == -2 || // ERR_NAME_NOT_RESOLVED
                  error.errorCode == -6 || // ERR_CONNECTION_REFUSED
                  error.errorCode == -8 || // ERR_CONNECTION_TIMED_OUT
                  error.errorCode == -10 || // ERR_CLEARTEXT_NOT_PERMITTED
                  error.errorCode == -14; // ERR_ADDRESS_UNREACHABLE

              if (isFatalError && mounted) {
                setState(() {
                  _isLoading = false;
                  _hasError = true;
                  _errorMessage = error.description;
                });
              }
            }
          },
        ),
      );

    // Habilitar permisos de cámara/micrófono, selector de archivos y ajustar viewport móvil en Android
    if (_controller.platform is AndroidWebViewController) {
      final androidController = _controller.platform as AndroidWebViewController;
      androidController.setOnPlatformPermissionRequest((PlatformWebViewPermissionRequest request) {
        request.grant();
      });
      androidController.setAllowFileAccess(true);
      androidController.setAllowContentAccess(true);
      androidController.setOnShowFileSelector((FileSelectorParams params) async {
        try {
          final allowMultiple = params.mode == FileSelectorMode.openMultiple;
          final result = await _filePickerChannel.invokeMethod<List<dynamic>>(
            'pickFiles',
            <String, dynamic>{
              'allowMultiple': allowMultiple,
              'acceptTypes': params.acceptTypes,
            },
          );
          if (result == null) {
            return <String>[];
          }
          return result.map((dynamic e) => e.toString()).where((String s) => s.isNotEmpty).toList();
        } catch (_) {
          return <String>[];
        }
      });
      androidController.setMediaPlaybackRequiresUserGesture(false);
      androidController.setUseWideViewPort(true);
      androidController.setTextZoom(100);
    }

    _cargarServidor();
  }

  /// Sondea el servidor (probando HTTP y HTTPS si hace falta) antes de cargar
  /// la página, y muestra un error claro si no se logra alcanzar la PC.
  Future<void> _cargarServidor() async {
    if (mounted) {
      setState(() {
        _hasError = false;
        _isLoading = true;
        _pageLoadedSuccessfully = false;
        _linkState = ServerLinkState.connecting;
      });
    }

    final result = await _networkService.testConnection(_config, timeout: const Duration(seconds: 6));
    if (!mounted) return;

    if (!result.isSuccess) {
      setState(() {
        _isLoading = false;
        _hasError = true;
        _errorMessage = result.message;
        _linkState = ServerLinkState.disconnected;
        _linkDetail = result.message;
      });
      return;
    }

    setState(() {
      _linkState = ServerLinkState.connected;
      _linkDetail = result.resolvedConfig?.fullUrl ?? _config.fullUrl;
    });

    final resuelta = result.resolvedConfig;
    if (resuelta != null && resuelta != _config) {
      _config = resuelta;
      await widget.storageService.saveConfig(resuelta);
      if (!mounted) return;
    }

    try {
      await _controller.clearCache();
      await _controller.clearLocalStorage();
    } catch (_) {}

    await _controller.loadRequest(Uri.parse(_config.fullUrl));
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
        _pageLoadedSuccessfully = false;
      });
      _cargarServidor();
    }
  }

  void _reintentar() {
    _cargarServidor();
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
                Positioned.fill(
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
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.4),
                          blurRadius: 16,
                          offset: const Offset(0, 4),
                        ),
                      ],
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
                  errorMessage: _errorMessage,
                  onRetry: _reintentar,
                  onOpenSettings: _abrirAjustes,
                ),

              // Icono de estado de conexión con el servidor móvil
              Positioned(
                top: 10,
                right: 12,
                child: ConnectionStatusIndicator(
                  state: _linkState,
                  detail: _linkDetail,
                  onTap: () => _verificarEnlace(mostrarConectando: true),
                ),
              ),

              // Botón flotante cuando hay una nueva versión compilada en la PC
              if (_availableUpdate != null)
                Positioned(
                  bottom: 16,
                  left: 16,
                  child: ElevatedButton.icon(
                    onPressed: _abrirDialogoActualizacion,
                    icon: const Icon(Icons.system_update_rounded, size: 18, color: Colors.white),
                    label: Text(
                      'Actualizar APK (v${_availableUpdate!.versionName})',
                      style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.white, fontSize: 12),
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.primaryRed,
                      foregroundColor: Colors.white,
                      elevation: 6,
                      shadowColor: Colors.black54,
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(20),
                        side: const BorderSide(color: Colors.white24, width: 1),
                      ),
                    ),
                  ),
                ),

              // Botones de acción flotantes (Recargar y Ajustes)
              Positioned(
                bottom: 16,
                right: 16,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (!_hasError) ...[
                      Opacity(
                        opacity: 0.85,
                        child: FloatingActionButton.small(
                          heroTag: 'btnReload',
                          backgroundColor: AppTheme.surfaceColor,
                          foregroundColor: AppTheme.textPrimary,
                          onPressed: () => _controller.reload(),
                          tooltip: 'Recargar página',
                          child: const Icon(Icons.refresh_rounded, size: 20),
                        ),
                      ),
                      const SizedBox(width: 10),
                    ],
                    Opacity(
                      opacity: 0.85,
                      child: FloatingActionButton.small(
                        heroTag: 'btnSettings',
                        backgroundColor: AppTheme.surfaceColor,
                        foregroundColor: AppTheme.textPrimary,
                        onPressed: _abrirAjustes,
                        tooltip: 'Ajustes del Servidor',
                        child: const Icon(Icons.settings_rounded, size: 20),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
