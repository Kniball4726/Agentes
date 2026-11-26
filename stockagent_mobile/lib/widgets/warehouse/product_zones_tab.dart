import 'package:flutter/material.dart';

import '../../models/warehouse_fefo.dart';
import '../../theme/app_theme.dart';

const List<String> kWarehouseZoneTypes = [
  'picking',
  'pulmon',
  'pallet',
  'recepcion',
  'cuarentena',
];

/// Pestaña de multi-ubicación por zona, traslados entre bins y alta de ubicaciones.
class ProductZonesTab extends StatelessWidget {
  final ScrollController scrollController;
  final List<ProductLocation> ubicaciones;
  final bool puedeOperar;
  final bool puedeEditar;
  final bool submitting;

  final String? origenSeleccionado;
  final ValueChanged<String?> onOrigenChanged;
  final TextEditingController destinoCtrl;
  final TextEditingController cantTransfCtrl;
  final String destinoZona;
  final ValueChanged<String> onDestinoZonaChanged;
  final VoidCallback onTransferir;

  final TextEditingController nuevaUbicCtrl;
  final TextEditingController nuevaUbicStockCtrl;
  final String nuevaZona;
  final ValueChanged<String> onNuevaZonaChanged;
  final bool marcarPrincipal;
  final ValueChanged<bool> onMarcarPrincipalChanged;
  final VoidCallback onAsignarUbicacion;

  const ProductZonesTab({
    super.key,
    required this.scrollController,
    required this.ubicaciones,
    required this.puedeOperar,
    required this.puedeEditar,
    required this.submitting,
    required this.origenSeleccionado,
    required this.onOrigenChanged,
    required this.destinoCtrl,
    required this.cantTransfCtrl,
    required this.destinoZona,
    required this.onDestinoZonaChanged,
    required this.onTransferir,
    required this.nuevaUbicCtrl,
    required this.nuevaUbicStockCtrl,
    required this.nuevaZona,
    required this.onNuevaZonaChanged,
    required this.marcarPrincipal,
    required this.onMarcarPrincipalChanged,
    required this.onAsignarUbicacion,
  });

  Widget _buildLocationCard(ProductLocation u) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: AppTheme.surfaceColor,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.borderColor),
      ),
      child: Row(
        children: [
          Icon(
            u.esPrincipal ? Icons.star_rounded : Icons.shelves,
            size: 20,
            color: u.esPrincipal ? Colors.amberAccent : Colors.tealAccent,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  u.ubicacion,
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                ),
                Text(
                  'Zona: ${u.tipoZona.toUpperCase()}${u.esPrincipal ? ' · Principal' : ''}',
                  style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                ),
              ],
            ),
          ),
          Text(
            '${u.stock} u.',
            style: const TextStyle(
              fontWeight: FontWeight.bold,
              fontSize: 14,
              color: Colors.cyanAccent,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildZoneDropdown({
    required String label,
    required String value,
    required ValueChanged<String> onChanged,
  }) {
    return InputDecorator(
      decoration: InputDecoration(
        labelText: label,
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          isExpanded: true,
          value: value,
          dropdownColor: AppTheme.cardBg,
          items: kWarehouseZoneTypes
              .map((z) => DropdownMenuItem(value: z, child: Text(z.toUpperCase())))
              .toList(),
          onChanged: submitting
              ? null
              : (v) {
                  if (v != null) onChanged(v);
                },
        ),
      ),
    );
  }

  List<Widget> _buildTransferSection() {
    return [
      const Divider(height: 24),
      const Text(
        'Transferir entre ubicaciones',
        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
      ),
      const SizedBox(height: 8),
      InputDecorator(
        decoration: const InputDecoration(
          labelText: 'Origen',
          contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        ),
        child: DropdownButtonHideUnderline(
          child: DropdownButton<String>(
            isExpanded: true,
            value: origenSeleccionado,
            dropdownColor: AppTheme.cardBg,
            items: ubicaciones
                .map(
                  (u) => DropdownMenuItem<String>(
                    value: u.ubicacion,
                    child: Text('${u.ubicacion} (${u.tipoZona}: ${u.stock} u.)'),
                  ),
                )
                .toList(),
            onChanged: submitting ? null : onOrigenChanged,
          ),
        ),
      ),
      const SizedBox(height: 8),
      Row(
        children: [
          Expanded(
            flex: 2,
            child: TextField(
              controller: destinoCtrl,
              textCapitalization: TextCapitalization.characters,
              decoration: const InputDecoration(labelText: 'Destino (ej: A-01-1)'),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: TextField(
              controller: cantTransfCtrl,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Cant.'),
            ),
          ),
        ],
      ),
      const SizedBox(height: 8),
      _buildZoneDropdown(
        label: 'Zona destino',
        value: destinoZona,
        onChanged: onDestinoZonaChanged,
      ),
      const SizedBox(height: 10),
      SizedBox(
        height: 48,
        child: ElevatedButton.icon(
          onPressed: submitting ? null : onTransferir,
          icon: const Icon(Icons.swap_horiz),
          label: const Text('TRANSFERIR STOCK'),
        ),
      ),
    ];
  }

  List<Widget> _buildAssignSection() {
    return [
      const Divider(height: 24),
      const Text(
        'Asignar / actualizar ubicación',
        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
      ),
      const SizedBox(height: 8),
      Row(
        children: [
          Expanded(
            flex: 2,
            child: TextField(
              controller: nuevaUbicCtrl,
              textCapitalization: TextCapitalization.characters,
              decoration: const InputDecoration(labelText: 'Ubicación'),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: TextField(
              controller: nuevaUbicStockCtrl,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Saldo'),
            ),
          ),
        ],
      ),
      const SizedBox(height: 8),
      Row(
        children: [
          Expanded(
            child: _buildZoneDropdown(
              label: 'Zona',
              value: nuevaZona,
              onChanged: onNuevaZonaChanged,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              value: marcarPrincipal,
              title: const Text('Principal', style: TextStyle(fontSize: 12)),
              onChanged: submitting
                  ? null
                  : (v) => onMarcarPrincipalChanged(v ?? false),
            ),
          ),
        ],
      ),
      const SizedBox(height: 8),
      SizedBox(
        height: 48,
        child: OutlinedButton.icon(
          onPressed: submitting ? null : onAsignarUbicacion,
          icon: const Icon(Icons.add_location_alt_outlined),
          label: const Text('GUARDAR UBICACIÓN'),
        ),
      ),
    ];
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      controller: scrollController,
      padding: const EdgeInsets.all(14),
      children: [
        if (ubicaciones.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 12),
            child: Text(
              'Sin ubicaciones multi-zona asignadas.',
              style: TextStyle(color: AppTheme.textSecondary),
            ),
          )
        else
          ...ubicaciones.map(_buildLocationCard),
        if (puedeOperar && ubicaciones.isNotEmpty) ..._buildTransferSection(),
        if (puedeEditar) ..._buildAssignSection(),
      ],
    );
  }
}
