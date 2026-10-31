import 'package:flutter/material.dart';
import '../services/network_service.dart';
import '../theme/app_theme.dart';

class StatusBanner extends StatelessWidget {
  final ConnectionResult? result;

  const StatusBanner({super.key, required this.result});

  @override
  Widget build(BuildContext context) {
    if (result == null) return const SizedBox.shrink();

    final isSuccess = result!.isSuccess;
    final color = isSuccess ? AppTheme.successGreen : AppTheme.primaryRed;

    return Container(
      margin: const EdgeInsets.only(bottom: 20),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            isSuccess ? Icons.check_circle_rounded : Icons.error_outline_rounded,
            color: color,
            size: 20,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              result!.message,
              style: TextStyle(
                fontSize: 13,
                color: isSuccess ? Colors.white : const Color(0xFFFF8A80),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
