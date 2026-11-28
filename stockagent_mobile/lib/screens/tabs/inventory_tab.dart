import 'package:flutter/material.dart';

import '../../controllers/inventory_controller.dart';
import '../../models/auth_user.dart';
import '../../models/inventory_result.dart';
import '../../services/api_service.dart';
import '../../theme/app_theme.dart';
import '../../widgets/barcode_scan_field.dart';
import '../../widgets/warehouse_alerts_sheet.dart';

class InventoryTab extends StatefulWidget {
  final ApiService apiService;
  final AuthUser currentUser;
  final bool isActive;
  final bool laserMode;

  const InventoryTab({
    super.key,
    required this.apiService,
    required this.currentUser,
    this.isActive = true,
    this.laserMode = false,
  });

  @override
  State<InventoryTab> createState() => _InventoryTabState();
}

class _InventoryTabState extends State<InventoryTab> {
  late final InventoryController _controller;
  final _barcodeTextCtrl = TextEditingController();
  final _barcodeFocusNode = FocusNode();

  @override
  void initState() {
    super.initState();
    _controller = InventoryController(
      apiService: widget.apiService,
      currentUser: widget.currentUser,
    );
  }

  @override
  void didUpdateWidget(covariant InventoryTab oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.isActive && !oldWidget.isActive) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _barcodeFocusNode.requestFocus();
      });
    } else if (!widget.isActive && oldWidget.isActive) {
      _barcodeFocusNode.unfocus();
    }
  }

  @override
  void dispose() {
    _barcodeTextCtrl.dispose();
    _barcodeFocusNode.dispose();
    _controller.dispose();
    super.dispose();
  }

  void _enviarCodigo(String codigo) {
    if (codigo.trim().isEmpty) return;
    _controller.procesarCodigo(codigo);
    _barcodeTextCtrl.clear();
    _barcodeFocusNode.requestFocus();
  }

  void _eliminarConDeshacer(String sku) {
    final cantPrevia = _controller.conteo[sku] ?? 0;
    _controller.eliminarItem(sku);
    if (!mounted) return;
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Eliminado $sku ($cantPrevia un.) del conteo'),
        duration: const Duration(seconds: 5),
        action: SnackBarAction(
          label: 'DESHACER',
          textColor: Colors.amberAccent,
          onPressed: () {
            _controller.deshacerEliminacion();
          },
        ),
      ),
    );
  }

  void _confirmarVaciar() {
    if (_controller.isEmpty) return;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('¿Vaciar conteo actual?'),
        content: const Text('Esta acción borrará los productos contados en este lote.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('CANCELAR'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.redAccent),
            onPressed: () {
              Navigator.of(ctx).pop();
              _controller.limpiarTodo();
            },
            child: const Text('VACIAR'),
          ),
        ],
      ),
    );
  }

  Future<void> _verComparativaPreliminar() async {
    if (_controller.isEmpty) return;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const PopScope(
        canPop: false,
        child: Center(child: CircularProgressIndicator()),
      ),
    );

    try {
      final summary = await _controller.compararPreliminar();
      if (!mounted) return;
      Navigator.of(context).pop();
      _mostrarModalComparativa(summary);
    } catch (e) {
      if (!mounted) return;
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error al calcular balance: $e')),
      );
    }
  }

  void _mostrarModalComparativa(InventorySummary summary) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final sheetBg = isDark ? AppTheme.cardBg : AppTheme.lightCardBg;
    final handleColor = isDark ? Colors.white24 : AppTheme.lightBorder;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: sheetBg,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => DraggableScrollableSheet(
        initialChildSize: 0.7,
        maxChildSize: 0.95,
        minChildSize: 0.4,
        expand: false,
        builder: (_, scrollCtrl) => Column(
          children: [
            Container(
              margin: const EdgeInsets.symmetric(vertical: 10),
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: handleColor,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  const Icon(Icons.analytics_outlined, color: Colors.blueAccent),
                  const SizedBox(width: 10),
                  const Text(
                    'Balance Preliminar de Stock',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                  const Spacer(),
                  IconButton(
                    constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.of(ctx).pop(),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                children: [
                  _metricCard('COINCIDEN', summary.coinciden, Colors.green),
                  const SizedBox(width: 8),
                  _metricCard('FALTANTES', summary.faltantes, Colors.redAccent),
                  const SizedBox(width: 8),
                  _metricCard('SOBRANTES', summary.sobrantes, Colors.amber),
                ],
              ),
            ),
            const Divider(),
            Expanded(
              child: ListView.builder(
                controller: scrollCtrl,
                itemCount: summary.items.length,
                itemBuilder: (_, idx) {
                  final item = summary.items[idx];
                  final Color color = item.isCoincide
                      ? Colors.green
                      : item.isFaltante
                          ? Colors.redAccent
                          : Colors.amber;
                  return ListTile(
                    dense: true,
                    leading: CircleAvatar(
                      radius: 14,
                      backgroundColor: color.withValues(alpha: 0.2),
                      child: Text(
                        item.diferencia > 0 ? '+${item.diferencia}' : '${item.diferencia}',
                        style: TextStyle(fontSize: 10, color: color, fontWeight: FontWeight.bold),
                      ),
                    ),
                    title: Text(item.nombre, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                    subtitle: Text('SKU: ${item.codigo} · Sistema: ${item.stockSistema} · Físico: ${item.stockFisico}'),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _metricCard(String label, int value, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: color.withValues(alpha: 0.3)),
        ),
        child: Column(
          children: [
            Text('$value', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: color)),
            const SizedBox(height: 2),
            Text(label, style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: color)),
          ],
        ),
      ),
    );
  }

  Future<void> _finalizarInventario() async {
    if (_controller.isEmpty) return;

    final confirmar = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('¿Cerrar y enviar inventario?'),
        content: Text(
          'Se procesarán ${_controller.totalProductos} artículos contados por ${widget.currentUser.nombre}. '
          'La PC generará el documento Excel de diferencias.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('SEGUIR CONTANDO'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('FINALIZAR Y ENVIAR'),
          ),
        ],
      ),
    );

    if (confirmar != true) return;

    if (!mounted) return;
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const PopScope(
        canPop: false,
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              CircularProgressIndicator(),
              SizedBox(height: 16),
              Text('Enviando a la PC...', style: TextStyle(color: Colors.white70)),
            ],
          ),
        ),
      ),
    );

    try {
      final res = await _controller.finalizarInventario();
      if (!mounted) return;
      Navigator.of(context).pop();

      _mostrarResultadoExitoso(res);
    } catch (e) {
      if (!mounted) return;
      Navigator.of(context).pop();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error al finalizar: $e')),
      );
    }
  }

  void _mostrarResultadoExitoso(InventorySummary res) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.check_circle, color: Colors.green, size: 28),
            SizedBox(width: 10),
            Expanded(child: Text('¡Inventario Procesado!')),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Archivo generado: ${res.archivoGenerado ?? "Excel Guardado"}'),
            const SizedBox(height: 12),
            Text('• Coinciden: ${res.coinciden}'),
            Text('• Faltantes: ${res.faltantes}'),
            Text('• Sobrantes: ${res.sobrantes}'),
          ],
        ),
        actions: [
          ElevatedButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('ENTENDIDO'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: _controller,
      builder: (ctx, _) {
        return Scaffold(
          body: SafeArea(
            child: Column(
              children: [
                // Panel Superior Ergonómico: Multiplicador arriba (>= 48dp) y Escáner de ancho completo abajo
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  color: Theme.of(context).colorScheme.surface,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      // Selector de multiplicador con botones aptos para uso con guantes (>= 48dp)
                      Container(
                        decoration: BoxDecoration(
                          color: AppTheme.surfaceColor,
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Row(
                          children: [1, 5, 10, 50].map((m) {
                            final isSel = _controller.multiplicador == m;
                            return Expanded(
                              child: InkWell(
                                onTap: () => _controller.setMultiplicador(m),
                                borderRadius: BorderRadius.circular(12),
                                child: ConstrainedBox(
                                  constraints: const BoxConstraints(minHeight: 48),
                                  child: Container(
                                    alignment: Alignment.center,
                                    decoration: BoxDecoration(
                                      color: isSel ? AppTheme.primaryRed : Colors.transparent,
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: Text(
                                      '+$m',
                                      style: TextStyle(
                                        fontSize: 14,
                                        fontWeight: isSel ? FontWeight.bold : FontWeight.w600,
                                        color: isSel ? Colors.white : AppTheme.textSecondary,
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                            );
                          }).toList(),
                        ),
                      ),
                      const SizedBox(height: 10),
                      // Campo de Escaneo de Código de Barras / SKU a ancho completo
                      BarcodeScanField(
                        controller: _barcodeTextCtrl,
                        focusNode: _barcodeFocusNode,
                        autofocus: widget.isActive,
                        laserMode: widget.laserMode,
                        hintText: 'Escanear o escribir SKU / EAN...',
                        onSubmitted: _enviarCodigo,
                      ),
                      if (_controller.statusBanner != null) ...[
                        const SizedBox(height: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                          decoration: BoxDecoration(
                            color: _controller.statusBannerOk
                                ? Colors.green.withValues(alpha: 0.15)
                                : Colors.red.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Row(
                            children: [
                              Icon(
                                _controller.statusBannerOk ? Icons.check_circle : Icons.error_outline,
                                size: 18,
                                color: _controller.statusBannerOk ? Colors.greenAccent : Colors.redAccent,
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  _controller.statusBanner!,
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: _controller.statusBannerOk ? Colors.greenAccent : Colors.redAccent,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ],
                  ),
                ),

                // Barra de Resumen del Lote
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                  color: Theme.of(context).scaffoldBackgroundColor,
                  child: Row(
                    children: [
                      Text(
                        '${_controller.totalProductos} productos (${_controller.totalUnidades} un.)',
                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                      ),
                      const Spacer(),
                      IconButton(
                        constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
                        icon: const Icon(Icons.event_available_outlined, color: Colors.amberAccent, size: 22),
                        tooltip: 'Alertas FEFO y Reservas',
                        onPressed: () => showWarehouseAlertsSheet(
                          context,
                          apiService: widget.apiService,
                          currentUser: widget.currentUser,
                        ),
                      ),
                      if (_controller.isNotEmpty) ...[
                        IconButton(
                          constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
                          icon: const Icon(Icons.delete_sweep_outlined, color: Colors.white54, size: 22),
                          tooltip: 'Vaciar lista',
                          onPressed: _confirmarVaciar,
                        ),
                        IconButton(
                          constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
                          icon: const Icon(Icons.analytics_outlined, color: Colors.blueAccent, size: 22),
                          tooltip: 'Ver diferencias',
                          onPressed: _verComparativaPreliminar,
                        ),
                      ],
                    ],
                  ),
                ),

                // Lista de Productos Contados
                Expanded(
                  child: _controller.isEmpty
                      ? const Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.barcode_reader, size: 64, color: Colors.white24),
                              SizedBox(height: 12),
                              Text(
                                'Pasa el lector o escribe el SKU',
                                style: TextStyle(color: AppTheme.textSecondary, fontSize: 15),
                              ),
                              SizedBox(height: 4),
                              Text(
                                'Las lecturas se guardan automáticamente (incluso offline)',
                                style: TextStyle(color: Colors.white24, fontSize: 12),
                              ),
                            ],
                          ),
                        )
                      : ListView.separated(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                          itemCount: _controller.conteo.length,
                          separatorBuilder: (_, __) => const SizedBox(height: 6),
                          itemBuilder: (ctx, idx) {
                            final sku = _controller.conteo.keys.elementAt(idx);
                            final cant = _controller.conteo[sku]!;
                            final nombre = _controller.nombresCache[sku] ?? 'Producto en catálogo';

                            return Container(
                              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                              decoration: BoxDecoration(
                                color: Theme.of(context).colorScheme.surface,
                                borderRadius: BorderRadius.circular(10),
                                border: Border.all(color: AppTheme.borderColor),
                              ),
                              child: Row(
                                children: [
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(sku, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                                        const SizedBox(height: 2),
                                        Text(
                                          nombre,
                                          style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                                          maxLines: 1,
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                      ],
                                    ),
                                  ),
                                  Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      IconButton(
                                        constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
                                        tooltip: 'Restar 1',
                                        icon: const Icon(Icons.remove_circle_outline, size: 24, color: Colors.white70),
                                        onPressed: () => _controller.modificarCantidad(sku, -1),
                                      ),
                                      Padding(
                                        padding: const EdgeInsets.symmetric(horizontal: 4),
                                        child: Text(
                                          '$cant',
                                          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                                        ),
                                      ),
                                      IconButton(
                                        constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
                                        tooltip: 'Sumar 1',
                                        icon: const Icon(Icons.add_circle_outline, size: 24, color: Colors.white70),
                                        onPressed: () => _controller.modificarCantidad(sku, 1),
                                      ),
                                      IconButton(
                                        constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
                                        tooltip: 'Eliminar ítem',
                                        icon: const Icon(Icons.close, size: 20, color: Colors.redAccent),
                                        onPressed: () => _eliminarConDeshacer(sku),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            );
                          },
                        ),
                ),

                // Botón Inferior: Finalizar Inventario
                if (_controller.isNotEmpty)
                  Container(
                    padding: const EdgeInsets.all(12),
                    color: Theme.of(context).colorScheme.surface,
                    child: SizedBox(
                      width: double.infinity,
                      height: 50,
                      child: ElevatedButton.icon(
                        icon: const Icon(Icons.cloud_upload_outlined),
                        label: const Text(
                          'FINALIZAR Y ENVIAR RELEVAMIENTO',
                          style: TextStyle(fontWeight: FontWeight.bold),
                        ),
                        onPressed: _finalizarInventario,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }
}
