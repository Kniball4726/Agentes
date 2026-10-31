import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class OfflinePlaceholder extends StatelessWidget {
  final String targetUrl;
  final VoidCallback onRetry;
  final VoidCallback onOpenSettings;

  const OfflinePlaceholder({
    super.key,
    required this.targetUrl,
    required this.onRetry,
    required this.onOpenSettings,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                color: AppTheme.primaryRed.withOpacity(0.15),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.wifi_off_rounded,
                size: 42,
                color: AppTheme.primaryRed,
              ),
            ),
            const SizedBox(height: 20),
            const Text(
              'Sin conexión con el servidor',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: AppTheme.textPrimary,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'No pudimos conectar con: $targetUrl\n\n'
              '1. Verifica que la PC tenga ejecutado "iniciar_servidor_movil.bat".\n'
              '2. Comprueba que ambos dispositivos estén en el mismo Wi-Fi.',
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 13,
                color: AppTheme.textSecondary,
                height: 1.4,
              ),
            ),
            const SizedBox(height: 28),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                OutlinedButton.icon(
                  onPressed: onOpenSettings,
                  icon: const Icon(Icons.settings_rounded, color: Colors.white70),
                  label: const Text('Cambiar IP', style: TextStyle(color: Colors.white70)),
                  style: OutlinedButton.styleFrom(
                    side: const BorderSide(color: Colors.white24),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  ),
                ),
                const SizedBox(width: 14),
                ElevatedButton.icon(
                  onPressed: onRetry,
                  icon: const Icon(Icons.refresh_rounded),
                  label: const Text('Reintentar'),
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
