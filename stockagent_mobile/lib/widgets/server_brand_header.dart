import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class ServerBrandHeader extends StatelessWidget {
  const ServerBrandHeader({super.key});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        const SizedBox(height: 10),
        Center(
          child: Container(
            width: 90,
            height: 90,
            decoration: BoxDecoration(
              color: AppTheme.surfaceColor,
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: AppTheme.primaryRed.withOpacity(0.3),
                  blurRadius: 20,
                  offset: const Offset(0, 4),
                )
              ],
            ),
            padding: const EdgeInsets.all(16),
            child: Image.asset(
              'assets/icon.png',
              errorBuilder: (_, __, ___) => const Icon(
                Icons.warehouse_rounded,
                size: 48,
                color: AppTheme.primaryRed,
              ),
            ),
          ),
        ),
        const SizedBox(height: 18),
        const Text(
          'StockAgent Móvil',
          textAlign: TextAlign.center,
          style: TextStyle(
            fontSize: 22,
            fontWeight: FontWeight.bold,
            color: AppTheme.textPrimary,
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          'Ingresa la IP de tu PC para conectarte a través de la red local Wi-Fi.',
          textAlign: TextAlign.center,
          style: TextStyle(
            fontSize: 13,
            color: AppTheme.textSecondary,
          ),
        ),
      ],
    );
  }
}
