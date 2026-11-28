import 'dart:async';
import 'package:flutter/material.dart';
import '../../models/auth_user.dart';
import '../../models/product_item.dart';
import '../../services/api_service.dart';
import '../../theme/app_theme.dart';
import '../../widgets/product_warehouse_sheet.dart';
import '../../widgets/warehouse_alerts_sheet.dart';

class CatalogTab extends StatefulWidget {
  final ApiService apiService;
  final AuthUser currentUser;
  final bool isActive;

  const CatalogTab({
    super.key,
    required this.apiService,
    required this.currentUser,
    this.isActive = false,
  });

  @override
  State<CatalogTab> createState() => _CatalogTabState();
}

class _CatalogTabState extends State<CatalogTab> {
  final _searchController = TextEditingController();
  final _searchFocusNode = FocusNode();
  Timer? _debounceTimer;
  int _searchGeneration = 0;
  List<ProductItem> _productos = [];
  bool _isLoading = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _buscarProductos('');
  }

  @override
  void didUpdateWidget(covariant CatalogTab oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!widget.isActive && oldWidget.isActive) {
      _searchFocusNode.unfocus();
    }
  }

  @override
  void dispose() {
    _debounceTimer?.cancel();
    _searchController.dispose();
    _searchFocusNode.dispose();
    super.dispose();
  }

  void _onSearchChanged(String query) {
    _debounceTimer?.cancel();
    _debounceTimer = Timer(const Duration(milliseconds: 350), () {
      _buscarProductos(query);
    });
  }

  Future<void> _buscarProductos(String query) async {
    final requestId = ++_searchGeneration;
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final items = await widget.apiService.searchProducts(query, limit: 60);
      if (mounted && requestId == _searchGeneration) {
        setState(() {
          _productos = items;
          _isLoading = false;
        });
      }
    } on ApiException catch (e) {
      if (mounted && requestId == _searchGeneration) {
        setState(() {
          _isLoading = false;
          _errorMessage = e.message;
        });
      }
    } catch (e) {
      if (mounted && requestId == _searchGeneration) {
        setState(() {
          _isLoading = false;
          _errorMessage = 'No se pudo consultar el catálogo: $e';
        });
      }
    }
  }

  Future<void> _abrirEditorUbicacion(ProductItem producto) async {
    if (!widget.currentUser.canEditCatalog) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Tu rol no tiene permisos para editar ubicaciones.')),
      );
      return;
    }

    final ubicacionCtrl = TextEditingController(text: producto.ubicacion);
    try {
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text('Ubicación: ${producto.code}'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(producto.name, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              const SizedBox(height: 14),
              TextField(
                controller: ubicacionCtrl,
                autofocus: true,
                textCapitalization: TextCapitalization.characters,
                decoration: const InputDecoration(
                  labelText: 'Estantería / Posición',
                  hintText: 'Ej: A-02-3',
                  prefixIcon: Icon(Icons.shelves),
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: const Text('CANCELAR'),
            ),
            ElevatedButton(
              onPressed: () async {
                final nueva = ubicacionCtrl.text.trim();
                Navigator.of(ctx).pop();
                try {
                  await widget.apiService.updateLocation(producto.code, nueva);
                  if (!mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Ubicación de ${producto.code} actualizada a $nueva')),
                  );
                  _buscarProductos(_searchController.text);
                } catch (e) {
                  if (!mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Error: $e')),
                  );
                }
              },
              child: const Text('GUARDAR'),
            ),
          ],
        ),
      );
    } finally {
      ubicacionCtrl.dispose();
    }
  }

  Future<void> _abrirEditorBarcode(ProductItem producto) async {
    if (!widget.currentUser.canEditCatalog) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Tu rol no tiene permisos para vincular códigos de barras.')),
      );
      return;
    }

    final barcodeCtrl = TextEditingController(text: producto.codBarras);
    try {
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text('Código de Barras: ${producto.code}'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(producto.name, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
              const SizedBox(height: 14),
              TextField(
                controller: barcodeCtrl,
                autofocus: true,
                // Soporta EAN-13 numéricos y códigos industriales alfanuméricos (Code-128 / Code-39)
                keyboardType: TextInputType.text,
                textCapitalization: TextCapitalization.characters,
                decoration: const InputDecoration(
                  labelText: 'Código EAN / Code-128 / Barras',
                  hintText: 'Ej: 7791234567890 o SKU-A12',
                  prefixIcon: Icon(Icons.qr_code),
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: const Text('CANCELAR'),
            ),
            ElevatedButton(
              onPressed: () async {
                final nuevo = barcodeCtrl.text.trim();
                Navigator.of(ctx).pop();
                try {
                  await widget.apiService.associateBarcode(producto.code, nuevo);
                  if (!mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Código de barras de ${producto.code} actualizado')),
                  );
                  _buscarProductos(_searchController.text);
                } catch (e) {
                  if (!mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Error: $e')),
                  );
                }
              },
              child: const Text('GUARDAR'),
            ),
          ],
        ),
      );
    } finally {
      barcodeCtrl.dispose();
    }
  }

  Future<void> _abrirDetalleWarehouse(ProductItem producto) async {
    var cambiadoEnSheet = false;
    final res = await showProductWarehouseSheet(
      context,
      apiService: widget.apiService,
      currentUser: widget.currentUser,
      producto: producto,
      onChanged: () => cambiadoEnSheet = true,
    );
    if ((res == true || cambiadoEnSheet) && mounted) {
      _buscarProductos(_searchController.text);
    }
  }

  Future<void> _abrirAlertasWarehouse({int initialTab = 0}) async {
    var cambiadoEnSheet = false;
    final res = await showWarehouseAlertsSheet(
      context,
      apiService: widget.apiService,
      currentUser: widget.currentUser,
      initialTab: initialTab,
      onChanged: () => cambiadoEnSheet = true,
    );
    if ((res == true || cambiadoEnSheet) && mounted) {
      _buscarProductos(_searchController.text);
    }
  }

  @override
  Widget build(BuildContext context) {
    final puedeEditar = widget.currentUser.canEditCatalog;

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            // Barra de Búsqueda con ValueListenableBuilder y Debounce
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              color: Theme.of(context).colorScheme.surface,
              child: ValueListenableBuilder<TextEditingValue>(
                valueListenable: _searchController,
                builder: (context, value, _) {
                  return TextField(
                    controller: _searchController,
                    focusNode: _searchFocusNode,
                    onChanged: _onSearchChanged,
                    decoration: InputDecoration(
                      hintText: 'Buscar por SKU, nombre o código de barras...',
                      prefixIcon: const Icon(Icons.search),
                      suffixIcon: value.text.isNotEmpty
                          ? IconButton(
                              constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
                              icon: const Icon(Icons.clear),
                              onPressed: () {
                                _debounceTimer?.cancel();
                                _searchController.clear();
                                _buscarProductos('');
                              },
                            )
                          : null,
                      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                    ),
                    onSubmitted: (val) {
                      _debounceTimer?.cancel();
                      _buscarProductos(val);
                    },
                  );
                },
              ),
            ),

            // Encabezado de Resultados
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              color: Theme.of(context).scaffoldBackgroundColor,
              child: Row(
                children: [
                  Text(
                    'Resultados: ${_productos.length} productos',
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                  ),
                  const Spacer(),
                  IconButton(
                    constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
                    tooltip: 'Alertas vencimiento FEFO',
                    icon: const Icon(Icons.event_available_outlined, size: 22, color: Colors.amberAccent),
                    onPressed: () => _abrirAlertasWarehouse(initialTab: 0),
                  ),
                  IconButton(
                    constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
                    tooltip: 'Reservas activas',
                    icon: const Icon(Icons.bookmark_border, size: 22, color: Colors.cyanAccent),
                    onPressed: () => _abrirAlertasWarehouse(initialTab: 1),
                  ),
                  IconButton(
                    constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
                    icon: const Icon(Icons.refresh, size: 22, color: Colors.white54),
                    onPressed: () => _buscarProductos(_searchController.text),
                  ),
                ],
              ),
            ),

            // Lista de Productos
            Expanded(
              child: _isLoading
                  ? const Center(child: CircularProgressIndicator())
                  : _errorMessage != null
                      ? Center(
                          child: Padding(
                            padding: const EdgeInsets.all(24),
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Icon(Icons.wifi_off_rounded, size: 48, color: Colors.redAccent),
                                const SizedBox(height: 12),
                                Text(
                                  _errorMessage!,
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(color: Colors.redAccent, fontSize: 13),
                                ),
                                const SizedBox(height: 16),
                                ElevatedButton.icon(
                                  onPressed: () => _buscarProductos(_searchController.text),
                                  icon: const Icon(Icons.refresh),
                                  label: const Text('Reintentar'),
                                ),
                              ],
                            ),
                          ),
                        )
                      : _productos.isEmpty
                          ? const Center(
                              child: Text(
                                'No se encontraron productos coincidentes.',
                                style: TextStyle(color: AppTheme.textSecondary),
                              ),
                            )
                          : RefreshIndicator(
                              onRefresh: () => _buscarProductos(_searchController.text),
                              child: ListView.separated(
                                padding: const EdgeInsets.all(12),
                                itemCount: _productos.length,
                                separatorBuilder: (_, __) => const SizedBox(height: 8),
                                itemBuilder: (ctx, idx) {
                                  final p = _productos[idx];
                                  return Container(
                                    padding: const EdgeInsets.all(12),
                                    decoration: BoxDecoration(
                                      color: Theme.of(context).colorScheme.surface,
                                      borderRadius: BorderRadius.circular(10),
                                      border: Border.all(
                                        color: p.isCritical
                                            ? Colors.redAccent.withValues(alpha: 0.4)
                                            : AppTheme.borderColor,
                                      ),
                                    ),
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Row(
                                          children: [
                                            Text(
                                              p.code,
                                              style: const TextStyle(
                                                fontWeight: FontWeight.bold,
                                                fontSize: 15,
                                              ),
                                            ),
                                            const Spacer(),
                                            Container(
                                              padding: const EdgeInsets.symmetric(
                                                horizontal: 10,
                                                vertical: 4,
                                              ),
                                              decoration: BoxDecoration(
                                                color: p.isCritical
                                                    ? Colors.red.withValues(alpha: 0.15)
                                                    : Colors.green.withValues(alpha: 0.15),
                                                borderRadius: BorderRadius.circular(8),
                                              ),
                                              child: Text(
                                                p.hasReservas
                                                    ? 'Disp: ${p.disponibleNeto} (Res: ${p.stockReservado})'
                                                    : 'Disp: ${p.disponibleNeto}',
                                                style: TextStyle(
                                                  fontWeight: FontWeight.bold,
                                                  fontSize: 12,
                                                  color: p.isCritical
                                                      ? Colors.redAccent
                                                      : Colors.greenAccent,
                                                ),
                                              ),
                                            ),
                                          ],
                                        ),
                                        const SizedBox(height: 4),
                                        Text(
                                          p.name,
                                          style: const TextStyle(
                                            fontSize: 13,
                                            color: AppTheme.textPrimary,
                                          ),
                                        ),
                                        if (p.hasReservas)
                                          Padding(
                                            padding: const EdgeInsets.only(top: 4),
                                            child: Text(
                                              'Stock físico: ${p.stock} · Comprometido en reservas: ${p.stockReservado}',
                                              style: const TextStyle(
                                                fontSize: 11,
                                                color: Colors.amberAccent,
                                              ),
                                            ),
                                          ),
                                        const SizedBox(height: 10),
                                        Wrap(
                                          spacing: 8,
                                          runSpacing: 8,
                                          children: [
                                            // Chip de Ubicación con altura >= 48dp apta para guantes
                                            InkWell(
                                              onTap: puedeEditar ? () => _abrirEditorUbicacion(p) : null,
                                              borderRadius: BorderRadius.circular(8),
                                              child: ConstrainedBox(
                                                constraints: const BoxConstraints(minHeight: 48),
                                                child: Container(
                                                  padding: const EdgeInsets.symmetric(
                                                    horizontal: 12,
                                                    vertical: 8,
                                                  ),
                                                  decoration: BoxDecoration(
                                                    color: AppTheme.surfaceColor,
                                                    borderRadius: BorderRadius.circular(8),
                                                  ),
                                                  child: Row(
                                                    mainAxisSize: MainAxisSize.min,
                                                    children: [
                                                      const Icon(
                                                        Icons.shelves,
                                                        size: 16,
                                                        color: Colors.blueAccent,
                                                      ),
                                                      const SizedBox(width: 6),
                                                      Text(
                                                        p.hasLocation ? p.ubicacion : 'Sin ubicación',
                                                        style: const TextStyle(
                                                          fontSize: 12,
                                                          color: Colors.white70,
                                                          fontWeight: FontWeight.w500,
                                                        ),
                                                      ),
                                                    ],
                                                  ),
                                                ),
                                              ),
                                            ),
                                            // Chip de Código de barras con altura >= 48dp apta para guantes
                                            InkWell(
                                              onTap: puedeEditar ? () => _abrirEditorBarcode(p) : null,
                                              borderRadius: BorderRadius.circular(8),
                                              child: ConstrainedBox(
                                                constraints: const BoxConstraints(minHeight: 48),
                                                child: Container(
                                                  padding: const EdgeInsets.symmetric(
                                                    horizontal: 12,
                                                    vertical: 8,
                                                  ),
                                                  decoration: BoxDecoration(
                                                    color: AppTheme.surfaceColor,
                                                    borderRadius: BorderRadius.circular(8),
                                                  ),
                                                  child: Row(
                                                    mainAxisSize: MainAxisSize.min,
                                                    children: [
                                                      const Icon(
                                                        Icons.qr_code,
                                                        size: 16,
                                                        color: Colors.amberAccent,
                                                      ),
                                                      const SizedBox(width: 6),
                                                      Text(
                                                        p.hasBarcode ? p.codBarras : 'Vincular código',
                                                        style: const TextStyle(
                                                          fontSize: 12,
                                                          color: Colors.white70,
                                                          fontWeight: FontWeight.w500,
                                                        ),
                                                      ),
                                                    ],
                                                  ),
                                                ),
                                              ),
                                            ),
                                            // Acceso a Zonas multi-ubicación y Lotes FEFO
                                            InkWell(
                                              onTap: () => _abrirDetalleWarehouse(p),
                                              borderRadius: BorderRadius.circular(8),
                                              child: ConstrainedBox(
                                                constraints: const BoxConstraints(minHeight: 48),
                                                child: Container(
                                                  padding: const EdgeInsets.symmetric(
                                                    horizontal: 12,
                                                    vertical: 8,
                                                  ),
                                                  decoration: BoxDecoration(
                                                    color: AppTheme.surfaceColor,
                                                    borderRadius: BorderRadius.circular(8),
                                                  ),
                                                  child: const Row(
                                                    mainAxisSize: MainAxisSize.min,
                                                    children: [
                                                      Icon(
                                                        Icons.warehouse_outlined,
                                                        size: 16,
                                                        color: Colors.tealAccent,
                                                      ),
                                                      SizedBox(width: 6),
                                                      Text(
                                                        'Zonas / FEFO',
                                                        style: TextStyle(
                                                          fontSize: 12,
                                                          color: Colors.white70,
                                                          fontWeight: FontWeight.w500,
                                                        ),
                                                      ),
                                                    ],
                                                  ),
                                                ),
                                              ),
                                            ),
                                          ],
                                        ),
                                      ],
                                    ),
                                  );
                                },
                              ),
                            ),
            ),
          ],
        ),
      ),
    );
  }
}
