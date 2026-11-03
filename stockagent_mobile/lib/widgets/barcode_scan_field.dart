import 'package:flutter/material.dart';

/// Campo de texto optimizado para lectores de códigos de barra (Wedge / Teclado).
class BarcodeScanField extends StatelessWidget {
  final TextEditingController controller;
  final FocusNode? focusNode;
  final String hintText;
  final ValueChanged<String> onSubmitted;
  final VoidCallback? onClear;
  final bool autofocus;

  const BarcodeScanField({
    super.key,
    required this.controller,
    this.focusNode,
    this.hintText = 'Escanear o escribir código...',
    required this.onSubmitted,
    this.onClear,
    this.autofocus = true,
  });

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      focusNode: focusNode,
      autofocus: autofocus,
      decoration: InputDecoration(
        hintText: hintText,
        prefixIcon: const Icon(Icons.qr_code_scanner, size: 20),
        suffixIcon: controller.text.isNotEmpty
            ? IconButton(
                icon: const Icon(Icons.arrow_forward),
                onPressed: () => onSubmitted(controller.text),
              )
            : null,
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      ),
      onSubmitted: onSubmitted,
    );
  }
}
