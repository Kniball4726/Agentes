import 'package:flutter/material.dart';
import '../../models/auth_user.dart';
import '../../models/product_item.dart';
import '../../services/api_service.dart';
import '../../theme/app_theme.dart';

class CatalogTab extends StatefulWidget {
  final ApiService apiService;
  final AuthUser currentUser;

  const CatalogTab({
    super.key,
    required this.apiService,
    required this.currentUser,
  });

  @override
  State<CatalogTab> createState() => _CatalogTabState();
}

class _CatalogTabState extends State<CatalogTab> {
  final _searchController = TextEditingController();
  List<ProductItem> _productos = [];
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _buscarProductos('');
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _buscarProductos(String query) async {
    setState(() => _isLoading = true);
    try {
      final items = await widget.apiService.searchProducts(query, limit: 60);
      if (mounted) {
        setState(() {
          _productos = items;
          _isLoading = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _abrirEditorUbicacion(ProductItem producto) {
    final ubicacionCtrl = TextEditingController(text: producto.ubicacion);

    showDialog(
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
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('Ubicación de ${producto.code} actualizada a $nueva')),
                );
                _buscarProductos(_searchController.text);
              } catch (e) {
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
  }

  void _abrirEditorBarcode(ProductItem producto) {
    final barcodeCtrl = TextEditingController(text: producto.codBarras);

    showDialog(
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
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Código EAN / Barras',
                hintText: 'Ej: 7791234567890',
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
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('Código de barras de ${producto.code} actualizado')),
                );
                _buscarProductos(_searchController.text);
              } catch (e) {
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
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            // Barra de Búsqueda
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              color: AppTheme.cardBg,
              child: TextField(
                controller: _searchController,
                decoration: InputDecoration(
                  hintText: 'Buscar por SKU, nombre o código de barras...',
                  prefixIcon: const Icon(Icons.search),
                  suffixIcon: _searchController.text.isNotEmpty
                      ? IconButton(
                          icon: const Icon(Icons.clear),
                          onPressed: () {
                            _searchController.clear();
                            _buscarProductos('');
                          },
                        )
                      : null,
                  contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                ),
                onSubmitted: (val) => _buscarProductos(val),
              ),
            ),

            // Encabezado de Resultados
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              color: AppTheme.darkBg,
              child: Row(
                children: [
                  Text(
                    'Resultados: ${_productos.length} productos',
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                  ),
                  const Spacer(),
                  IconButton(
                    icon: const Icon(Icons.refresh, size: 20, color: Colors.white54),
                    onPressed: () => _buscarProductos(_searchController.text),
                  ),
                ],
              ),
            ),

            // Lista de Productos
            Expanded(
              child: _isLoading
                  ? const Center(child: CircularProgressIndicator())
                  : _productos.isEmpty
                      ? const Center(
                          child: Text(
                            'No se encontraron productos coincidentes.',
                            style: TextStyle(color: AppTheme.textSecondary),
                          ),
                        )
                      : ListView.separated(
                          padding: const EdgeInsets.all(12),
                          itemCount: _productos.length,
                          separatorBuilder: (_, __) => const SizedBox(height: 8),
                          itemBuilder: (ctx, idx) {
                            final p = _productos[idx];
                            return Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: AppTheme.cardBg,
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
                                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                                      ),
                                      const Spacer(),
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                        decoration: BoxDecoration(
                                          color: p.isCritical
                                              ? Colors.red.withValues(alpha: 0.15)
                                              : Colors.green.withValues(alpha: 0.15),
                                          borderRadius: BorderRadius.circular(8),
                                        ),
                                        child: Text(
                                          'Stock: ${p.stock}',
                                          style: TextStyle(
                                            fontWeight: FontWeight.bold,
                                            fontSize: 12,
                                            color: p.isCritical ? Colors.redAccent : Colors.greenAccent,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    p.name,
                                    style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary),
                                  ),
                                  const SizedBox(height: 10),
                                  Row(
                                    children: [
                                      // Ubicación
                                      InkWell(
                                        onTap: () => _abrirEditorUbicacion(p),
                                        borderRadius: BorderRadius.circular(6),
                                        child: Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                          decoration: BoxDecoration(
                                            color: AppTheme.surfaceColor,
                                            borderRadius: BorderRadius.circular(6),
                                          ),
                                          child: Row(
                                            mainAxisSize: MainAxisSize.min,
                                            children: [
                                              const Icon(Icons.shelves, size: 14, color: Colors.blueAccent),
                                              const SizedBox(width: 4),
                                              Text(
                                                p.hasLocation ? p.ubicacion : 'Sin ubicación',
                                                style: const TextStyle(fontSize: 11, color: Colors.white70),
                                              ),
                                            ],
                                          ),
                                        ),
                                      ),
                                      const SizedBox(width: 8),
                                      // Código de barras
                                      InkWell(
                                        onTap: () => _abrirEditorBarcode(p),
                                        borderRadius: BorderRadius.circular(6),
                                        child: Container(
                                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                          decoration: BoxDecoration(
                                            color: AppTheme.surfaceColor,
                                            borderRadius: BorderRadius.circular(6),
                                          ),
                                          child: Row(
                                            mainAxisSize: MainAxisSize.min,
                                            children: [
                                              const Icon(Icons.qr_code, size: 14, color: Colors.amberAccent),
                                              const SizedBox(width: 4),
                                              Text(
                                                p.hasBarcode ? p.codBarras : 'Vincular código',
                                                style: const TextStyle(fontSize: 11, color: Colors.white70),
                                              ),
                                            ],
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
          ],
        ),
      ),
    );
  }
}
