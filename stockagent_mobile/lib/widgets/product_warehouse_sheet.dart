import 'package:flutter/material.dart';

import '../models/auth_user.dart';
import '../models/product_item.dart';
import '../models/warehouse_fefo.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import 'warehouse/product_fefo_tab.dart';
import 'warehouse/product_zones_tab.dart';

Future<bool?> showProductWarehouseSheet(
  BuildContext context, {
  required ApiService apiService,
  required AuthUser currentUser,
  required ProductItem producto,
  VoidCallback? onChanged,
}) {
  return showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    backgroundColor: AppTheme.cardBg,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (ctx) => _ProductWarehouseSheetBody(
      apiService: apiService,
      currentUser: currentUser,
      producto: producto,
      onChanged: onChanged,
    ),
  );
}

class _ProductWarehouseSheetBody extends StatefulWidget {
  final ApiService apiService;
  final AuthUser currentUser;
  final ProductItem producto;
  final VoidCallback? onChanged;

  const _ProductWarehouseSheetBody({
    required this.apiService,
    required this.currentUser,
    required this.producto,
    this.onChanged,
  });

  @override
  State<_ProductWarehouseSheetBody> createState() =>
      _ProductWarehouseSheetBodyState();
}

class _ProductWarehouseSheetBodyState extends State<_ProductWarehouseSheetBody>
    with SingleTickerProviderStateMixin {
  late final TabController _tabCtrl;

  final _destinoCtrl = TextEditingController();
  final _cantTransfCtrl = TextEditingController(text: '1');
  final _nuevaUbicCtrl = TextEditingController();
  final _nuevaUbicStockCtrl = TextEditingController(text: '0');

  final _cantConsumoCtrl = TextEditingController(text: '1');
  final _loteNomCtrl = TextEditingController();
  final _loteCantCtrl = TextEditingController(text: '1');
  final _loteFvCtrl = TextEditingController();
  final _loteUbicCtrl = TextEditingController();

  ProductLocationsSummary? _summary;
  List<StockLot> _lotes = [];
  bool _loading = true;
  bool _submitting = false;
  bool _changed = false;
  String? _error;

  String? _origenSeleccionado;
  String _destinoZona = 'picking';
  String _nuevaZona = 'pulmon';
  bool _marcarPrincipal = false;
  bool _descontarStockAlConsumir = true;

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 2, vsync: this);
    _loteUbicCtrl.text = widget.producto.ubicacion;
    _cargarDatos();
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    _destinoCtrl.dispose();
    _cantTransfCtrl.dispose();
    _nuevaUbicCtrl.dispose();
    _nuevaUbicStockCtrl.dispose();
    _cantConsumoCtrl.dispose();
    _loteNomCtrl.dispose();
    _loteCantCtrl.dispose();
    _loteFvCtrl.dispose();
    _loteUbicCtrl.dispose();
    super.dispose();
  }

  Future<void> _cargarDatos() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait<dynamic>([
        widget.apiService.getProductLocations(widget.producto.code),
        widget.apiService.getProductLots(widget.producto.code),
      ]);
      if (!mounted) return;
      final sum = results[0] as ProductLocationsSummary;
      final lots = results[1] as List<StockLot>;
      setState(() {
        _summary = sum;
        _lotes = lots;
        _loading = false;
        if (sum.ubicaciones.isNotEmpty) {
          final keys = sum.ubicaciones.map((u) => u.ubicacion).toList();
          if (_origenSeleccionado == null ||
              !keys.contains(_origenSeleccionado)) {
            _origenSeleccionado = keys.first;
          }
        } else {
          _origenSeleccionado = null;
        }
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = '$e';
      });
    }
  }

  void _mostrarFeedback(String msg, {bool error = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: error ? Colors.redAccent : Colors.green.shade700,
      ),
    );
  }

  Future<void> _ejecutarAccionConFeedback(
    Future<String> Function() accion, {
    required String errorPrefix,
  }) async {
    setState(() => _submitting = true);
    try {
      final msg = await accion();
      if (!mounted) return;
      _changed = true;
      widget.onChanged?.call();
      _mostrarFeedback(msg);
      await _cargarDatos();
    } catch (e) {
      _mostrarFeedback('$errorPrefix: $e', error: true);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _transferir() async {
    final origen = _origenSeleccionado?.trim() ?? '';
    final destino = _destinoCtrl.text.trim();
    final cant = int.tryParse(_cantTransfCtrl.text.trim()) ?? 0;
    if (origen.isEmpty || destino.isEmpty || cant <= 0) {
      _mostrarFeedback('Completá origen, destino y cantidad > 0.', error: true);
      return;
    }
    await _ejecutarAccionConFeedback(
      () async {
        await widget.apiService.transferBetweenLocations(
          widget.producto.code,
          origen: origen,
          destino: destino,
          cantidad: cant,
          destinoZona: _destinoZona,
        );
        _destinoCtrl.clear();
        return 'Trasladadas $cant u. de $origen a ${destino.toUpperCase()}.';
      },
      errorPrefix: 'Error al transferir',
    );
  }

  Future<void> _asignarUbicacion() async {
    final ubic = _nuevaUbicCtrl.text.trim();
    final stk = int.tryParse(_nuevaUbicStockCtrl.text.trim()) ?? 0;
    if (ubic.isEmpty || stk < 0) {
      _mostrarFeedback(
        'Ingresá ubicación válida y stock >= 0.',
        error: true,
      );
      return;
    }
    await _ejecutarAccionConFeedback(
      () async {
        await widget.apiService.assignProductLocation(
          widget.producto.code,
          ubicacion: ubic,
          tipoZona: _nuevaZona,
          stock: stk,
          esPrincipal: _marcarPrincipal,
        );
        _nuevaUbicCtrl.clear();
        return 'Ubicación ${ubic.toUpperCase()} guardada.';
      },
      errorPrefix: 'Error al guardar ubicación',
    );
  }

  Future<void> _consumirFefo() async {
    final cant = int.tryParse(_cantConsumoCtrl.text.trim()) ?? 0;
    if (cant <= 0) {
      _mostrarFeedback('Indicá una cantidad mayor a 0.', error: true);
      return;
    }
    await _ejecutarAccionConFeedback(
      () async {
        final res = await widget.apiService.consumeLotsFefo(
          widget.producto.code,
          cantidad: cant,
          descontarStockProducto: _descontarStockAlConsumir,
        );
        final consumido = res['consumido'] ?? 0;
        return 'Consumidas $consumido u. siguiendo orden FEFO.';
      },
      errorPrefix: 'Error en consumo FEFO',
    );
  }

  Future<void> _registrarLote() async {
    final lote = _loteNomCtrl.text.trim();
    final cant = int.tryParse(_loteCantCtrl.text.trim()) ?? -1;
    if (lote.isEmpty || cant < 0) {
      _mostrarFeedback(
        'Ingresá código de lote y cantidad >= 0.',
        error: true,
      );
      return;
    }
    await _ejecutarAccionConFeedback(
      () async {
        await widget.apiService.registerProductLot(
          widget.producto.code,
          lote: lote,
          cantidad: cant,
          fechaVencimiento: _loteFvCtrl.text.trim(),
          ubicacion: _loteUbicCtrl.text.trim(),
        );
        _loteNomCtrl.clear();
        _loteFvCtrl.clear();
        return 'Lote ${lote.toUpperCase()} registrado.';
      },
      errorPrefix: 'Error al registrar lote',
    );
  }

  Widget _badgeSaldo(String label, int valor, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 6),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.14),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: color.withValues(alpha: 0.35)),
        ),
        child: Column(
          children: [
            Text(
              '$valor',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
            Text(
              label,
              style: TextStyle(
                fontSize: 10,
                color: color,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.of(context).viewInsets.bottom;
    final puedeOperar =
        widget.currentUser.isPicker || widget.currentUser.isOperator;
    final puedeEditar = widget.currentUser.canEditCatalog;
    final fis = _summary?.stockFisico ?? widget.producto.stock;
    final res = _summary?.stockReservado ?? widget.producto.stockReservado;
    final disp = _summary?.stockDisponible ?? widget.producto.disponibleNeto;

    return Padding(
      padding: EdgeInsets.only(bottom: bottomInset),
      child: DraggableScrollableSheet(
        initialChildSize: 0.82,
        minChildSize: 0.5,
        maxChildSize: 0.95,
        expand: false,
        builder: (_, scrollCtrl) => Column(
          children: [
            Container(
              margin: const EdgeInsets.symmetric(vertical: 8),
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: Colors.white24,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                children: [
                  const Icon(
                    Icons.warehouse_outlined,
                    color: Colors.tealAccent,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          widget.producto.code,
                          style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        Text(
                          widget.producto.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppTheme.textSecondary,
                          ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    constraints: const BoxConstraints(
                      minWidth: 48,
                      minHeight: 48,
                    ),
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.of(context).pop(_changed),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
              child: Row(
                children: [
                  _badgeSaldo('FÍSICO', fis, Colors.blueAccent),
                  const SizedBox(width: 8),
                  _badgeSaldo('RESERVADO', res, Colors.amberAccent),
                  const SizedBox(width: 8),
                  _badgeSaldo('DISPONIBLE', disp, Colors.greenAccent),
                ],
              ),
            ),
            TabBar(
              controller: _tabCtrl,
              tabs: const [
                Tab(text: 'Zonas y Traslados'),
                Tab(text: 'Lotes FEFO'),
              ],
            ),
            Expanded(
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _error != null
                      ? Center(
                          child: Padding(
                            padding: const EdgeInsets.all(20),
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text(
                                  _error!,
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(color: Colors.redAccent),
                                ),
                                const SizedBox(height: 12),
                                ElevatedButton.icon(
                                  onPressed: _cargarDatos,
                                  icon: const Icon(Icons.refresh),
                                  label: const Text('Reintentar'),
                                ),
                              ],
                            ),
                          ),
                        )
                      : TabBarView(
                          controller: _tabCtrl,
                          children: [
                            ProductZonesTab(
                              scrollController: scrollCtrl,
                              ubicaciones: _summary?.ubicaciones ?? [],
                              puedeOperar: puedeOperar,
                              puedeEditar: puedeEditar,
                              submitting: _submitting,
                              origenSeleccionado: _origenSeleccionado,
                              onOrigenChanged: (v) =>
                                  setState(() => _origenSeleccionado = v),
                              destinoCtrl: _destinoCtrl,
                              cantTransfCtrl: _cantTransfCtrl,
                              destinoZona: _destinoZona,
                              onDestinoZonaChanged: (v) =>
                                  setState(() => _destinoZona = v),
                              onTransferir: _transferir,
                              nuevaUbicCtrl: _nuevaUbicCtrl,
                              nuevaUbicStockCtrl: _nuevaUbicStockCtrl,
                              nuevaZona: _nuevaZona,
                              onNuevaZonaChanged: (v) =>
                                  setState(() => _nuevaZona = v),
                              marcarPrincipal: _marcarPrincipal,
                              onMarcarPrincipalChanged: (v) =>
                                  setState(() => _marcarPrincipal = v),
                              onAsignarUbicacion: _asignarUbicacion,
                            ),
                            ProductFefoTab(
                              scrollController: scrollCtrl,
                              lotes: _lotes,
                              puedeOperar: puedeOperar,
                              puedeEditar: puedeEditar,
                              submitting: _submitting,
                              cantConsumoCtrl: _cantConsumoCtrl,
                              descontarStockAlConsumir: _descontarStockAlConsumir,
                              onDescontarStockChanged: (v) =>
                                  setState(() => _descontarStockAlConsumir = v),
                              onConsumirFefo: _consumirFefo,
                              loteNomCtrl: _loteNomCtrl,
                              loteCantCtrl: _loteCantCtrl,
                              loteFvCtrl: _loteFvCtrl,
                              loteUbicCtrl: _loteUbicCtrl,
                              onRegistrarLote: _registrarLote,
                            ),
                          ],
                        ),
            ),
          ],
        ),
      ),
    );
  }
}
