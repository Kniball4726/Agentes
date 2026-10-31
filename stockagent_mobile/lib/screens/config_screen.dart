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
  }

  @override
  void dispose() {
    _hostController.dispose();
    _portController.dispose();
    _networkService.dispose();
    super.dispose();
  }

  ServerConfig _buildConfigFromInputs() {
    return ServerConfig(
      host: _hostController.text.trim(),
      port: _portController.text.trim(),
      protocol: _protocol,
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
                  keyboardType: TextInputType.datetime,
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                  decoration: const InputDecoration(
                    labelText: 'Dirección IP de la PC Servidor',
                    hintText: 'Ejemplo: 192.168.1.45',
                    prefixIcon: Icon(Icons.wifi_rounded, color: AppTheme.primaryRed),
                  ),
                  validator: (value) {
                    if (value == null || value.trim().isEmpty) {
                      return 'Por favor ingresa la dirección IP de la PC';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 16),

                // Selector de Puerto y Protocolo
                Row(
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
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      flex: 2,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12),
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
                    shape: RoundedRectangleManager(),
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
