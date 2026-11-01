import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// Estados posibles de la conexión con el servidor StockAgent.
enum ServerLinkState { connecting, connected, disconnected }

/// Icono compacto que muestra si la app está conectada al servidor móvil.
///
/// - Verde (wifi): conectado.
/// - Ámbar (sincronizando): conectando / verificando.
/// - Rojo (wifi tachado): sin conexión.
///
/// Al tocarlo se ejecuta [onTap] (por ejemplo, para forzar una nueva verificación).
class ConnectionStatusIndicator extends StatelessWidget {
  final ServerLinkState state;
  final String? detail;
  final VoidCallback? onTap;

  const ConnectionStatusIndicator({
    super.key,
    required this.state,
    this.detail,
    this.onTap,
  });

  static const Color _amber = Color(0xFFFFB300);

  Color get _color {
    switch (state) {
      case ServerLinkState.connected:
        return AppTheme.successGreen;
      case ServerLinkState.connecting:
        return _amber;
      case ServerLinkState.disconnected:
        return AppTheme.primaryRed;
    }
  }

  IconData get _icon {
    switch (state) {
      case ServerLinkState.connected:
        return Icons.wifi_rounded;
      case ServerLinkState.connecting:
        return Icons.sync_rounded;
      case ServerLinkState.disconnected:
        return Icons.wifi_off_rounded;
    }
  }

  String get _label {
    switch (state) {
      case ServerLinkState.connected:
        return 'Conectado';
      case ServerLinkState.connecting:
        return 'Conectando...';
      case ServerLinkState.disconnected:
        return 'Sin conexión';
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = _color;
    return Tooltip(
      message: detail == null ? _label : '$_label\n$detail',
      child: Material(
        color: AppTheme.surfaceColor.withOpacity(0.9),
        shape: StadiumBorder(side: BorderSide(color: color.withOpacity(0.7))),
        child: InkWell(
          customBorder: const StadiumBorder(),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 250),
                  child: Icon(_icon, key: ValueKey(state), color: color, size: 18),
                ),
                const SizedBox(width: 6),
                Text(
                  _label,
                  style: TextStyle(
                    color: color,
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
