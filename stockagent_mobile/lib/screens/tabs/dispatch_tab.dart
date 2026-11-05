import 'package:flutter/material.dart';

import '../../controllers/dispatch_controller.dart';
import '../../models/auth_user.dart';
import '../../models/order_dispatch.dart';
import '../../services/api_service.dart';
import '../../theme/app_theme.dart';
import '../../widgets/barcode_scan_field.dart';
import '../../widgets/order_status_badge.dart';

class DispatchTab extends StatefulWidget {
  final ApiService apiService;
  final AuthUser currentUser;

  const DispatchTab({
    super.key,
    required this.apiService,
    required this.currentUser,
  });

  @override
  State<DispatchTab> createState() => _DispatchTabState();
}

class _DispatchTabState extends State<DispatchTab> {
  late final DispatchController _controller;
  final _qrController = TextEditingController();
  final _qrFocusNode = FocusNode();

  @override
  void initState() {
    super.initState();
    _controller = DispatchController(
      apiService: widget.apiService,
      currentUser: widget.currentUser,
    );
  }

  @override
  void dispose() {
    _qrController.dispose();
    _qrFocusNode.dispose();
    _controller.dispose();
    super.dispose();
  }

  void _enviarCodigo(String codigo) {
    if (codigo.trim().isEmpty) return;
    _controller.procesarEscaneo(codigo);
    _qrController.clear();
    _qrFocusNode.requestFocus();
  }

  void _verDetallePedido(OrderDispatch pedido) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppTheme.cardBg,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => DraggableScrollableSheet(
        initialChildSize: 0.6,
        maxChildSize: 0.9,
        minChildSize: 0.4,
        expand: false,
        builder: (_, scrollCtrl) => Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Colors.white24,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Text(
                    'Remito #${pedido.notaPedido}',
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  const Spacer(),
                  OrderStatusBadge(estado: pedido.estadoDespacho),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                'Cliente: ${pedido.cliente}',
                style: const TextStyle(fontSize: 14, color: AppTheme.textPrimary),
              ),
              Text(
                'Bultos: ${pedido.bultos} · Transporte: ${pedido.logistica.isEmpty ? "No especificado" : pedido.logistica}',
                style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
              ),
              const Divider(height: 20),
              const Text(
                'Artículos incluidos:',
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Colors.white70),
              ),
              const SizedBox(height: 6),
              Expanded(
                child: ListView.separated(
                  controller: scrollCtrl,
                  itemCount: pedido.items.length,
                  separatorBuilder: (_, __) => const Divider(height: 1),
                  itemBuilder: (_, idx) {
                    final item = pedido.items[idx];
                    return ListTile(
                      dense: true,
                      contentPadding: EdgeInsets.zero,
                      title: Text(item.descripcion, style: const TextStyle(fontSize: 13)),
                      subtitle: Text('SKU: ${item.codigo}'),
                      trailing: Text(
                        'x${item.cantidad}',
                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
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
                // Cabecera de Escaneo y Selector de Acción
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  color: AppTheme.cardBg,
                  child: Column(
                    children: [
                      // Selector de Acción
                      Container(
                        decoration: BoxDecoration(
                          color: AppTheme.surfaceColor,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        padding: const EdgeInsets.symmetric(horizontal: 10),
                        child: DropdownButtonHideUnderline(
                          child: DropdownButton<String>(
                            isExpanded: true,
                            value: _controller.modoSeleccionado,
                            dropdownColor: AppTheme.cardBg,
                            icon: const Icon(Icons.arrow_drop_down, color: AppTheme.textSecondary),
                            items: const [
                              DropdownMenuItem(
                                value: 'auto',
                                child: Text('Acción: Avanzar Automático (Armado → Despachado → Entregado)', style: TextStyle(fontSize: 12)),
                              ),
                              DropdownMenuItem(
                                value: 'despachado',
                                child: Text('Acción: Marcar siempre como DESPACHADO', style: TextStyle(fontSize: 12)),
                              ),
                              DropdownMenuItem(
                                value: 'entregado',
                                child: Text('Acción: Marcar siempre como ENTREGADO', style: TextStyle(fontSize: 12)),
                              ),
                              DropdownMenuItem(
                                value: 'armado',
                                child: Text('Acción: Volver a ARMADO', style: TextStyle(fontSize: 12)),
                              ),
                            ],
                            onChanged: (val) {
                              if (val != null) _controller.setModo(val);
                            },
                          ),
                        ),
                      ),
                      const SizedBox(height: 8),

                      // Input de Escáner QR / Remito
                      BarcodeScanField(
                        controller: _qrController,
                        focusNode: _qrFocusNode,
                        hintText: 'Escanear QR de rótulo o N° de remito...',
                        onSubmitted: _enviarCodigo,
                      ),
                    ],
                  ),
                ),

                if (_controller.colaOffline.isNotEmpty)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                    color: Colors.amber.shade900.withValues(alpha: 0.9),
                    child: Row(
                      children: [
                        const Icon(Icons.cloud_off, size: 18, color: Colors.white),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            '⚡ ${_controller.colaOffline.length} escaneo(s) en buffer offline',
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                              fontSize: 12,
                            ),
                          ),
                        ),
                        TextButton.icon(
                          onPressed: _controller.sincronizandoOffline
                              ? null
                              : () => _controller.sincronizarColaOffline(),
                          icon: _controller.sincronizandoOffline
                              ? const SizedBox(
                                  width: 14,
                                  height: 14,
                                  child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                                )
                              : const Icon(Icons.sync, size: 16, color: Colors.white),
                          label: Text(
                            _controller.sincronizandoOffline ? 'ENVIANDO...' : 'SINCRONIZAR',
                            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 11),
                          ),
                        ),
                      ],
                    ),
                  ),

                // Barra de pestañas o vistas (Historial vs Pedidos Activos)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  color: AppTheme.darkBg,
                  child: Row(
                    children: [
                      Text(
                        _controller.verListaPendientes
                            ? 'Pedidos en Sistema (${_controller.pedidosActivos.length})'
                            : 'Historial de Escaneos (${_controller.historial.length})',
                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                      ),
                      const Spacer(),
                      IconButton(
                        icon: Icon(
                          _controller.verListaPendientes ? Icons.history : Icons.format_list_bulleted,
                          size: 20,
                          color: AppTheme.primaryRed,
                        ),
                        tooltip: _controller.verListaPendientes ? 'Ver Historial' : 'Ver Pedidos',
                        onPressed: _controller.alternarVista,
                      ),
                      IconButton(
                        icon: const Icon(Icons.refresh, size: 20, color: Colors.white54),
                        tooltip: 'Recargar',
                        onPressed: _controller.cargarPedidos,
                      ),
                    ],
                  ),
                ),

                // Contenido dinámico
                Expanded(
                  child: _controller.verListaPendientes
                      ? _controller.cargandoPedidos
                          ? const Center(child: CircularProgressIndicator())
                          : _controller.pedidosActivos.isEmpty
                              ? const Center(
                                  child: Text(
                                    'No hay pedidos registrados.',
                                    style: TextStyle(color: AppTheme.textSecondary),
                                  ),
                                )
                              : ListView.separated(
                                  padding: const EdgeInsets.all(12),
                                  itemCount: _controller.pedidosActivos.length,
                                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                                  itemBuilder: (ctx, idx) {
                                    final p = _controller.pedidosActivos[idx];
                                    return InkWell(
                                      onTap: () => _verDetallePedido(p),
                                      borderRadius: BorderRadius.circular(10),
                                      child: Container(
                                        padding: const EdgeInsets.all(12),
                                        decoration: BoxDecoration(
                                          color: AppTheme.cardBg,
                                          borderRadius: BorderRadius.circular(10),
                                          border: Border.all(color: AppTheme.borderColor),
                                        ),
                                        child: Row(
                                          children: [
                                            Expanded(
                                              child: Column(
                                                crossAxisAlignment: CrossAxisAlignment.start,
                                                children: [
                                                  Text(
                                                    'Remito #${p.notaPedido}',
                                                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                                                  ),
                                                  const SizedBox(height: 2),
                                                  Text(
                                                    p.cliente,
                                                    style: const TextStyle(fontSize: 12, color: AppTheme.textPrimary),
                                                  ),
                                                  Text(
                                                    '${p.bultos} bultos · ${p.logistica}',
                                                    style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                                                  ),
                                                ],
                                              ),
                                            ),
                                            OrderStatusBadge(estado: p.estadoDespacho),
                                          ],
                                        ),
                                      ),
                                    );
                                  },
                                )
                      : _controller.historial.isEmpty
                          ? Center(
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: const [
                                  Icon(Icons.qr_code_2_rounded, size: 64, color: Colors.white24),
                                  SizedBox(height: 12),
                                  Text(
                                    'Apunta el lector al rótulo QR o remito',
                                    style: TextStyle(color: AppTheme.textSecondary, fontSize: 15),
                                  ),
                                  SizedBox(height: 4),
                                  Text(
                                    'Actualización de estado en tiempo real',
                                    style: TextStyle(color: Colors.white24, fontSize: 12),
                                  ),
                                ],
                              ),
                            )
                          : ListView.separated(
                              padding: const EdgeInsets.all(12),
                              itemCount: _controller.historial.length,
                              separatorBuilder: (_, __) => const SizedBox(height: 8),
                              itemBuilder: (ctx, idx) {
                                final h = _controller.historial[idx];
                                final color = h.exito ? Colors.green : Colors.redAccent;

                                return Container(
                                  padding: const EdgeInsets.all(12),
                                  decoration: BoxDecoration(
                                    color: color.withValues(alpha: 0.1),
                                    borderRadius: BorderRadius.circular(10),
                                    border: Border.all(color: color.withValues(alpha: 0.3)),
                                  ),
                                  child: Row(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Icon(
                                        h.exito ? Icons.check_circle : Icons.error_outline,
                                        color: color,
                                        size: 20,
                                      ),
                                      const SizedBox(width: 10),
                                      Expanded(
                                        child: Column(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                          children: [
                                            Row(
                                              children: [
                                                Text(
                                                  '[${h.hora}]',
                                                  style: TextStyle(
                                                    fontSize: 11,
                                                    color: color,
                                                    fontWeight: FontWeight.bold,
                                                  ),
                                                ),
                                                const Spacer(),
                                                if (h.pedido != null)
                                                  OrderStatusBadge(estado: h.pedido!.estadoDespacho),
                                              ],
                                            ),
                                            const SizedBox(height: 4),
                                            Text(
                                              h.mensaje,
                                              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                                            ),
                                          ],
                                        ),
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
      },
    );
  }
}
