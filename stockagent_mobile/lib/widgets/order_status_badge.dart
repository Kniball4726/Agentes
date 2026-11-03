import 'package:flutter/material.dart';

/// Badge visual reutilizable que muestra el estado de un pedido (ARMADO, DESPACHADO, ENTREGADO).
class OrderStatusBadge extends StatelessWidget {
  final String estado;

  const OrderStatusBadge({super.key, required this.estado});

  @override
  Widget build(BuildContext context) {
    final est = estado.toLowerCase().trim();
    final Color color;
    final String label;

    switch (est) {
      case 'entregado':
        color = Colors.green;
        label = 'ENTREGADO';
        break;
      case 'despachado':
        color = Colors.blue;
        label = 'DESPACHADO';
        break;
      default:
        color = Colors.amber;
        label = 'ARMADO';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.bold,
          letterSpacing: 0.5,
        ),
      ),
    );
  }
}
