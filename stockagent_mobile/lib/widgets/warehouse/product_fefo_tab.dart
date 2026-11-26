import 'package:flutter/material.dart';

import '../../models/warehouse_fefo.dart';
import '../../theme/app_theme.dart';

/// Pestaña de trazabilidad de lotes, consumo ordenado por FEFO y alta/edición de lotes.
class ProductFefoTab extends StatelessWidget {
  final ScrollController scrollController;
  final List<StockLot> lotes;
  final bool puedeOperar;
  final bool puedeEditar;
  final bool submitting;

  final TextEditingController cantConsumoCtrl;
  final bool descontarStockAlConsumir;
  final ValueChanged<bool> onDescontarStockChanged;
  final VoidCallback onConsumirFefo;

  final TextEditingController loteNomCtrl;
  final TextEditingController loteCantCtrl;
  final TextEditingController loteFvCtrl;
  final TextEditingController loteUbicCtrl;
  final VoidCallback onRegistrarLote;

  const ProductFefoTab({
    super.key,
    required this.scrollController,
    required this.lotes,
    required this.puedeOperar,
    required this.puedeEditar,
    required this.submitting,
    required this.cantConsumoCtrl,
    required this.descontarStockAlConsumir,
    required this.onDescontarStockChanged,
    required this.onConsumirFefo,
    required this.loteNomCtrl,
    required this.loteCantCtrl,
    required this.loteFvCtrl,
    required this.loteUbicCtrl,
    required this.onRegistrarLote,
  });

  Widget _buildLotCard(StockLot lt) {
    final Color vColor = lt.vencido
        ? Colors.redAccent
        : (lt.diasParaVencer != null && lt.diasParaVencer! <= 7)
            ? Colors.orangeAccent
            : Colors.greenAccent;
    final fvText =
        lt.fechaVencimiento.isEmpty ? 'Sin vencimiento' : lt.fechaVencimiento;
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppTheme.surfaceColor,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: lt.vencido
              ? Colors.redAccent.withValues(alpha: 0.45)
              : AppTheme.borderColor,
        ),
      ),
      child: Row(
        children: [
          Icon(
            lt.vencido ? Icons.event_busy : Icons.inventory_2_outlined,
            size: 20,
            color: vColor,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${lt.lote} (${lt.estado.toUpperCase()})',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                ),
                Text(
                  'Vto: $fvText · Ubic: ${lt.ubicacion.isEmpty ? '-' : lt.ubicacion}',
                  style: TextStyle(fontSize: 11, color: vColor),
                ),
              ],
            ),
          ),
          Text(
            '${lt.stock} u.',
            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
          ),
        ],
      ),
    );
  }

  List<Widget> _buildConsumeSection() {
    return [
      const Divider(height: 24),
      const Text(
        'Consumir siguiendo regla FEFO',
        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
      ),
      const SizedBox(height: 8),
      TextField(
        controller: cantConsumoCtrl,
        keyboardType: TextInputType.number,
        decoration: const InputDecoration(labelText: 'Cantidad a consumir'),
      ),
      CheckboxListTile(
        contentPadding: EdgeInsets.zero,
        value: descontarStockAlConsumir,
        title: const Text(
          'Descontar también stock físico general',
          style: TextStyle(fontSize: 12),
        ),
        onChanged: submitting
            ? null
            : (v) => onDescontarStockChanged(v ?? true),
      ),
      SizedBox(
        height: 48,
        child: ElevatedButton.icon(
          onPressed: submitting ? null : onConsumirFefo,
          icon: const Icon(Icons.playlist_remove_outlined),
          label: const Text('CONSUMIR FEFO'),
        ),
      ),
    ];
  }

  List<Widget> _buildRegisterLotSection() {
    return [
      const Divider(height: 24),
      const Text(
        'Registrar / actualizar lote',
        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
      ),
      const SizedBox(height: 8),
      Row(
        children: [
          Expanded(
            flex: 2,
            child: TextField(
              controller: loteNomCtrl,
              textCapitalization: TextCapitalization.characters,
              decoration: const InputDecoration(labelText: 'Código Lote *'),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: TextField(
              controller: loteCantCtrl,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Cant.'),
            ),
          ),
        ],
      ),
      const SizedBox(height: 8),
      Row(
        children: [
          Expanded(
            child: TextField(
              controller: loteFvCtrl,
              decoration: const InputDecoration(
                labelText: 'Vto (YYYY-MM-DD)',
                hintText: 'Opcional',
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: TextField(
              controller: loteUbicCtrl,
              textCapitalization: TextCapitalization.characters,
              decoration: const InputDecoration(labelText: 'Ubicación'),
            ),
          ),
        ],
      ),
      const SizedBox(height: 10),
      SizedBox(
        height: 48,
        child: OutlinedButton.icon(
          onPressed: submitting ? null : onRegistrarLote,
          icon: const Icon(Icons.add_box_outlined),
          label: const Text('GUARDAR LOTE'),
        ),
      ),
    ];
  }

  @override
  Widget build(BuildContext context) {
    final tieneDisponibles =
        lotes.any((l) => l.stock > 0 && l.estado == 'disponible');
    return ListView(
      controller: scrollController,
      padding: const EdgeInsets.all(14),
      children: [
        if (lotes.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 12),
            child: Text(
              'Sin lotes FEFO registrados para este SKU.',
              style: TextStyle(color: AppTheme.textSecondary),
            ),
          )
        else
          ...lotes.map(_buildLotCard),
        if (puedeOperar && tieneDisponibles) ..._buildConsumeSection(),
        if (puedeEditar) ..._buildRegisterLotSection(),
      ],
    );
  }
}
