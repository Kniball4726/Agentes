import 'package:flutter/material.dart';

import '../models/auth_user.dart';
import '../models/warehouse_fefo.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';

Future<bool?> showWarehouseAlertsSheet(
  BuildContext context, {
  required ApiService apiService,
  required AuthUser currentUser,
  int initialTab = 0,
  VoidCallback? onChanged,
}) {
  return showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    backgroundColor: AppTheme.cardBg,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (ctx) => _WarehouseAlertsSheetBody(
      apiService: apiService,
      currentUser: currentUser,
      initialTab: initialTab,
      onChanged: onChanged,
    ),
  );
}

class _WarehouseAlertsSheetBody extends StatefulWidget {
  final ApiService apiService;
  final AuthUser currentUser;
  final int initialTab;
  final VoidCallback? onChanged;

  const _WarehouseAlertsSheetBody({
    required this.apiService,
    required this.currentUser,
    this.initialTab = 0,
    this.onChanged,
  });

  @override
  State<_WarehouseAlertsSheetBody> createState() =>
      _WarehouseAlertsSheetBodyState();
}

class _WarehouseAlertsSheetBodyState extends State<_WarehouseAlertsSheetBody>
    with SingleTickerProviderStateMixin {
  late final TabController _tabCtrl;

  List<StockLot> _alertasFefo = [];
  List<StockReservation> _reservasActivas = [];
  String _filtroNivel = 'TODOS';
  bool _loading = true;
  bool _submitting = false;
  bool _changed = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(
      length: 2,
      vsync: this,
      initialIndex: widget.initialTab.clamp(0, 1),
    );
    _cargarTodo();
  }

  @override
  void dispose() {
    _tabCtrl.dispose();
    super.dispose();
  }

  Future<void> _cargarTodo() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final res = await Future.wait<dynamic>([
        widget.apiService.getExpiringLots(dias: 30, incluirVencidos: true),
        widget.apiService.listReservations(estado: 'activa'),
      ]);
      if (!mounted) return;
      setState(() {
        _alertasFefo = res[0] as List<StockLot>;
        _reservasActivas = res[1] as List<StockReservation>;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = '$e';
      });
    }
  }

  Future<void> _accionarReserva(
    String referenciaTipo,
    String referenciaId, {
    required bool consolidar,
  }) async {
    setState(() => _submitting = true);
    try {
      if (consolidar) {
        await widget.apiService.consolidateReservation(
          referenciaId: referenciaId,
          referenciaTipo: referenciaTipo,
          descontarStock: true,
        );
      } else {
        await widget.apiService.releaseReservation(
          referenciaId: referenciaId,
          referenciaTipo: referenciaTipo,
        );
      }
      if (!mounted) return;
      _changed = true;
      widget.onChanged?.call();
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            consolidar
                ? 'Reserva $referenciaId consolidada y descontada.'
                : 'Reserva $referenciaId liberada al disponible.',
          ),
          backgroundColor: Colors.green.shade700,
        ),
      );
      await _cargarTodo();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Error al actualizar reserva: $e'),
          backgroundColor: Colors.redAccent,
        ),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final puedeOperar = widget.currentUser.isPicker || widget.currentUser.isOperator;

    return DraggableScrollableSheet(
        initialChildSize: 0.78,
        minChildSize: 0.45,
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
                  const Icon(Icons.notifications_active_outlined, color: Colors.amberAccent),
                  const SizedBox(width: 10),
                  const Expanded(
                    child: Text(
                      'Alertas FEFO y Reservas Activas',
                      style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                    ),
                  ),
                  IconButton(
                    constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
                    icon: const Icon(Icons.refresh),
                    onPressed: _loading ? null : _cargarTodo,
                  ),
                  IconButton(
                    constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.of(context).pop(_changed),
                  ),
                ],
              ),
            ),
            TabBar(
              controller: _tabCtrl,
              tabs: [
                Tab(text: 'Vtos FEFO (${_alertasFefo.length})'),
                Tab(text: 'Reservas (${_reservasActivas.length})'),
              ],
            ),
            Expanded(
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _error != null
                      ? Center(
                          child: Padding(
                            padding: const EdgeInsets.all(20),
                            child: Text(
                              _error!,
                              textAlign: TextAlign.center,
                              style: const TextStyle(color: Colors.redAccent),
                            ),
                          ),
                        )
                      : TabBarView(
                          controller: _tabCtrl,
                          children: [
                            _construirListaFefo(scrollCtrl),
                            _construirListaReservas(scrollCtrl, puedeOperar),
                          ],
                        ),
            ),
          ],
        ),
      );
  }

  Widget _construirListaFefo(ScrollController scrollCtrl) {
    final filtrados = _alertasFefo.where((l) {
      if (_filtroNivel == 'TODOS') return true;
      return l.nivelAlerta.toUpperCase() == _filtroNivel;
    }).toList();

    return Column(
      children: [
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: Row(
            children: ['TODOS', 'VENCIDO', 'CRITICO', 'PROXIMO'].map((niv) {
              final selected = _filtroNivel == niv;
              return Padding(
                padding: const EdgeInsets.only(right: 6),
                child: ChoiceChip(
                  label: Text(niv),
                  selected: selected,
                  onSelected: (_) => setState(() => _filtroNivel = niv),
                ),
              );
            }).toList(),
          ),
        ),
        Expanded(
          child: filtrados.isEmpty
              ? const Center(
                  child: Text(
                    'Sin alertas de vencimiento para este filtro.',
                    style: TextStyle(color: AppTheme.textSecondary),
                  ),
                )
              : ListView.separated(
                  controller: scrollCtrl,
                  padding: const EdgeInsets.all(12),
                  itemCount: filtrados.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                  itemBuilder: (_, idx) {
                    final lt = filtrados[idx];
                    final Color c = lt.nivelAlerta == 'VENCIDO'
                        ? Colors.redAccent
                        : (lt.nivelAlerta == 'CRITICO'
                            ? Colors.orangeAccent
                            : Colors.amberAccent);
                    return Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: AppTheme.surfaceColor,
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: c.withValues(alpha: 0.4)),
                      ),
                      child: Row(
                        children: [
                          Icon(Icons.schedule, color: c, size: 22),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  '[${lt.productCode}] ${lt.productName}',
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                                ),
                                Text(
                                  'Lote ${lt.lote} · Vto ${lt.fechaVencimiento} · Ubic ${lt.ubicacion}',
                                  style: TextStyle(fontSize: 11, color: c),
                                ),
                              ],
                            ),
                          ),
                          Text(
                            '${lt.stock} u.',
                            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                          ),
                        ],
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }

  Widget _construirListaReservas(
    ScrollController scrollCtrl,
    bool puedeOperar,
  ) {
    if (_reservasActivas.isEmpty) {
      return const Center(
        child: Text(
          'No hay reservas activas en preparación.',
          style: TextStyle(color: AppTheme.textSecondary),
        ),
      );
    }

    final Map<String, List<StockReservation>> porRef = {};
    for (final r in _reservasActivas) {
      final clave = '${r.referenciaTipo}::${r.referenciaId}';
      porRef.putIfAbsent(clave, () => []).add(r);
    }
    final grupos = porRef.entries.toList();

    return ListView.separated(
      controller: scrollCtrl,
      padding: const EdgeInsets.all(12),
      itemCount: grupos.length,
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (_, idx) {
        final items = grupos[idx].value;
        final refTipo = items.first.referenciaTipo;
        final refId = items.first.referenciaId;
        final totalUn = items.fold<int>(0, (acc, r) => acc + r.cantidad);

        return Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppTheme.surfaceColor,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: AppTheme.borderColor),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      '$refTipo: $refId',
                      style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                    ),
                  ),
                  Text(
                    '$totalUn u.',
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      color: Colors.amberAccent,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              ...items.map(
                (it) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Text(
                    '• [${it.productCode}] ${it.productName} · ${it.cantidad} u. ${it.ubicacion.isNotEmpty ? '(${it.ubicacion})' : ''}',
                    style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                  ),
                ),
              ),
              if (puedeOperar) ...[
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(
                      child: SizedBox(
                        height: 48,
                        child: OutlinedButton.icon(
                          onPressed: _submitting
                              ? null
                              : () => _accionarReserva(refTipo, refId, consolidar: false),
                          icon: const Icon(Icons.lock_open_outlined, size: 18),
                          label: const Text('Liberar'),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: SizedBox(
                        height: 48,
                        child: ElevatedButton.icon(
                          onPressed: _submitting
                              ? null
                              : () => _accionarReserva(refTipo, refId, consolidar: true),
                          icon: const Icon(Icons.check_circle_outline, size: 18),
                          label: const Text('Consolidar'),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ],
          ),
        );
      },
    );
  }
}
