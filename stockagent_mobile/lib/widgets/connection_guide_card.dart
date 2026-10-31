import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class ConnectionGuideCard extends StatelessWidget {
  const ConnectionGuideCard({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.cardBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white10),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.lightbulb_outline_rounded, size: 16, color: Colors.amber),
              SizedBox(width: 6),
              Text(
                '¿Cómo obtener la IP de la PC?',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Colors.white),
              ),
            ],
          ),
          SizedBox(height: 8),
          Text(
            '1. Ejecuta "iniciar_servidor_movil.bat" en la PC.\n'
            '2. En la consola verás una línea que dice:\n'
            '   "Acceso Red LAN: http://192.168.X.X:8550".\n'
            '3. Escribe esa misma dirección IP aquí.',
            style: TextStyle(fontSize: 12, color: AppTheme.textSecondary, height: 1.4),
          ),
        ],
      ),
    );
  }
}
