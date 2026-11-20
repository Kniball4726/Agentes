import 'package:flutter/material.dart';

/// Campo de texto optimizado para lectores de códigos de barra (Wedge / Teclado / Láser)
/// con actualización reactiva de botones de limpieza y envío, y áreas táctiles >= 48dp.
class BarcodeScanField extends StatelessWidget {
  final TextEditingController controller;
  final FocusNode? focusNode;
  final String hintText;
  final ValueChanged<String> onSubmitted;
  final VoidCallback? onClear;
  final bool autofocus;
  final bool laserMode;

  const BarcodeScanField({
    super.key,
    required this.controller,
    this.focusNode,
    this.hintText = 'Escanear o escribir código...',
    required this.onSubmitted,
    this.onClear,
    this.autofocus = true,
    this.laserMode = false,
  });

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<TextEditingValue>(
      valueListenable: controller,
      builder: (context, value, _) {
        final tieneTexto = value.text.trim().isNotEmpty;
        return TextField(
          controller: controller,
          focusNode: focusNode,
          autofocus: autofocus,
          keyboardType: laserMode ? TextInputType.none : TextInputType.text,
          textInputAction: TextInputAction.send,
          decoration: InputDecoration(
            hintText: hintText,
            prefixIcon: Icon(
              laserMode ? Icons.bolt_rounded : Icons.qr_code_scanner,
              size: 22,
            ),
            suffixIcon: tieneTexto
                ? Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      IconButton(
                        constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
                        tooltip: 'Limpiar código',
                        icon: const Icon(Icons.clear, size: 20),
                        onPressed: () {
                          controller.clear();
                          onClear?.call();
                          focusNode?.requestFocus();
                        },
                      ),
                      IconButton(
                        constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
                        tooltip: 'Enviar código',
                        icon: const Icon(Icons.arrow_forward),
                        onPressed: () => onSubmitted(controller.text),
                      ),
                    ],
                  )
                : null,
            contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
          ),
          onSubmitted: onSubmitted,
        );
      },
    );
  }
}
