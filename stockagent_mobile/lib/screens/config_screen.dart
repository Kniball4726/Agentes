import 'package:flutter/material.dart';
import '../models/server_config.dart';
import '../services/network_service.dart';
import '../services/storage_service.dart';
import '../theme/app_theme.dart';
import '../widgets/connection_guide_card.dart';
import '../widgets/server_brand_header.dart';
import '../widgets/status_banner.dart';
import 'app_screen.dart';

class ConfigScreen extends StatefulWidget {
  final StorageService storageService;
  final bool isModal;

  const ConfigScreen({
    super.key,
    required this.storageService,
    this.isModal = false,
  });

  @override
  State<ConfigScreen> createState() => _ConfigScreenState();
}

class _ConfigScreenState extends State<ConfigScreen> {
  final _formKey = GlobalKey<FormState>();
  final _networkService = NetworkService();

  late TextEditingController _hostController;
  late TextEditingController _portController;
  late String _protocol;

  bool _isTesting = false;
  ConnectionResult? _testResult;

  @override
  void initState() {
    super.initState();
    final currentConfig = widget.storageService.loadConfig();
    _hostController = TextEditingController(text: currentConfig.host);
    _portController = TextEditingController(text: currentConfig.port);
    _protocol = currentConfig.protocol;

    _hostController.addListener(_onHostChanged);
  }

  void _onHostChanged() {
    final text = _hostController.text.trim();
    // Si el usuario pegó una URL completa (ej: http://192.168.1.50:8550/)
    if (text.startsWith('http://') || text.startsWith('https://') || text.contains(':') || text.contains('/')) {
      final parsed = ServerConfig.fromUserInput(
        rawHost: text,
        rawPort: _portController.text,
        rawProtocol: _protocol,
      );

      if (parsed.host != text) {
        _hostController.value = TextEditingValue(
          text: parsed.host,
          selection: TextSelection.collapsed(offset: parsed.host.length),
        );
        _portController.text = parsed.normalizedPort;
        if (mounted) {
          setState(() {
            _protocol = parsed.normalizedProtocol;
          });
        }
      }
    }
  }

  @override
  void dispose() {
    _hostController.removeListener(_onHostChanged);
    _hostController.dispose();
    _portController.dispose();
    _networkService.dispose();
    super.dispose();
  }

  ServerConfig _buildConfigFromInputs() {
    return ServerConfig.fromUserInput(
      rawHost: _hostController.text,
      rawPort: _portController.text,
      rawProtocol: _protocol,
    );
  }

  Future<void> _probarConexion() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isTesting = true;
      _testResult = null;
    });

    final config = _buildConfigFromInputs();
    final result = await _networkService.testConnection(config);

    if (!mounted) return;
    setState(() {
      _isTesting = false;
      _testResult = result;
      // Si el servidor respondió con el otro protocolo, ajustarlo automáticamente
      if (result.isSuccess && result.resolvedConfig != null) {
        _protocol = result.resolvedConfig!.normalizedProtocol;
      }
    });
  }

  Future<void> _guardarYConectar() async {
    if (!_formKey.currentState!.validate()) return;

    final config = _buildConfigFromInputs();
    await widget.storageService.saveConfig(config);

    if (!mounted) return;

    if (widget.isModal) {
      Navigator.of(context).pop(true);
    } else {
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => AppScreen(storageService: widget.storageService),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Conexión con Servidor PC'),
        leading: widget.isModal
            ? IconButton(
                icon: const Icon(Icons.close),
                onPressed: () => Navigator.of(context).pop(false),
              )
            : null,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const ServerBrandHeader(),
                const SizedBox(height: 28),

                // Campo IP / Host
                TextFormField(
                  controller: _hostController,
                  keyboardType: TextInputType.url,
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                  decoration: const InputDecoration(
                    labelText: 'Dirección IP de la PC Servidor',
                    hintText: 'Ej: 192.168.100.19',
                    prefixIcon: Icon(Icons.wifi_rounded, color: AppTheme.primaryRed),
                    helperText: 'Puedes escribir solo la IP o pegar la URL completa',
                  ),
                  validator: (value) {
                    if (value == null || value.trim().isEmpty) {
                      return 'Por favor ingresa la dirección IP de la PC';
                    }
                    final cfg = ServerConfig.fromUserInput(rawHost: value);
                    if (!cfg.isValid) {
                      return 'Formato de IP o host no válido';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 16),

                // Selector de Puerto y Protocolo
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      flex: 3,
                      child: TextFormField(
                        controller: _portController,
                        keyboardType: TextInputType.number,
                        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                        decoration: const InputDecoration(
                          labelText: 'Puerto',
                          hintText: '8550',
                          prefixIcon: Icon(Icons.settings_ethernet_rounded, color: AppTheme.primaryRed),
                        ),
                        validator: (val) {
                          if (val != null && val.trim().isNotEmpty) {
                            final p = int.tryParse(val.trim());
                            if (p == null || p < 1 || p > 65535) {
                              return 'Puerto inválido (1-65535)';
                            }
                          }
                          return null;
                        },
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      flex: 2,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                        decoration: BoxDecoration(
                          color: AppTheme.surfaceColor,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: DropdownButtonHideUnderline(
                          child: DropdownButton<String>(
                            value: _protocol,
                            dropdownColor: AppTheme.surfaceColor,
                            items: const [
                              DropdownMenuItem(value: 'http', child: Text('HTTP')),
                              DropdownMenuItem(value: 'https', child: Text('HTTPS')),
                            ],
                            onChanged: (val) {
                              if (val != null) setState(() => _protocol = val);
                            },
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),

                // Banner de estado de la prueba
                StatusBanner(result: _testResult),

                // Botón Probar Conexión
                OutlinedButton.icon(
                  onPressed: _isTesting ? null : _probarConexion,
                  style: OutlinedButton.styleFrom(
                    side: const BorderSide(color: AppTheme.primaryRed),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                  icon: _isTesting
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2, color: AppTheme.primaryRed),
                        )
                      : const Icon(Icons.network_check_rounded, color: AppTheme.primaryRed),
                  label: Text(
                    _isTesting ? 'Probando...' : 'Probar Conexión',
                    style: const TextStyle(color: AppTheme.textPrimary, fontWeight: FontWeight.bold),
                  ),
                ),
                const SizedBox(height: 12),

                // Botón Guardar y Conectar
                ElevatedButton.icon(
                  onPressed: _guardarYConectar,
                  icon: const Icon(Icons.login_rounded),
                  label: const Text('Conectar a StockAgent'),
                ),
                const SizedBox(height: 24),

                // Tarjeta de Ayuda
                const ConnectionGuideCard(),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
