import 'package:flutter/material.dart';

import '../services/update_service.dart';
import '../theme/app_theme.dart';

class UpdateDialog extends StatefulWidget {
  final AppUpdateInfo updateInfo;
  final String currentVersionName;
  final int currentVersionCode;
  final String downloadFullUrl;
  final String? expectedServerOrigin;
  final UpdateService updateService;

  const UpdateDialog({
    super.key,
    required this.updateInfo,
    required this.currentVersionName,
    required this.currentVersionCode,
    required this.downloadFullUrl,
    this.expectedServerOrigin,
    required this.updateService,
  });

  @override
  State<UpdateDialog> createState() => _UpdateDialogState();
}

class _UpdateDialogState extends State<UpdateDialog> {
  bool _isDownloading = false;
  double _progress = 0.0;
  String? _errorMessage;

  Future<void> _iniciarActualizacion() async {
    setState(() {
      _isDownloading = true;
      _progress = 0.0;
      _errorMessage = null;
    });

    await widget.updateService.downloadAndInstall(
      downloadUrl: widget.downloadFullUrl,
      expectedSha256: widget.updateInfo.sha256,
      expectedServerOrigin: widget.expectedServerOrigin,
      onProgress: (p) {
        if (mounted) {
          setState(() => _progress = p);
        }
      },
      onError: (err) {
        if (mounted) {
          setState(() {
            _isDownloading = false;
            _errorMessage = err;
          });
        }
      },
      onInstalled: () {
        if (mounted) {
          setState(() => _isDownloading = false);
        }
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final info = widget.updateInfo;
    final porcentaje = (_progress * 100).toInt();
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final cardColor = isDark ? AppTheme.cardBg : AppTheme.lightCardBg;
    final surfaceColor = isDark ? AppTheme.surfaceColor : AppTheme.lightSurface;
    final borderColor = isDark ? Colors.white12 : AppTheme.lightBorder;
    final textPrimary = isDark ? Colors.white : AppTheme.lightTextPrimary;
    final textSecondary = isDark ? AppTheme.textSecondary : AppTheme.lightTextSecondary;

    return PopScope(
      canPop: !_isDownloading,
      child: AlertDialog(
        backgroundColor: cardColor,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: borderColor),
        ),
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppTheme.primaryRed.withAlpha(51),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(
                Icons.system_update_rounded,
                color: AppTheme.primaryRed,
                size: 24,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                'Nueva Versión Lista',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: textPrimary,
                ),
              ),
            ),
          ],
        ),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: isDark ? Colors.black26 : AppTheme.lightSurface,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Actual: v${widget.currentVersionName} (${widget.currentVersionCode})',
                      style: TextStyle(fontSize: 12, color: textSecondary),
                    ),
                    Icon(Icons.arrow_forward_rounded, size: 14, color: textSecondary),
                    Text(
                      'Nueva: v${info.versionName} (${info.versionCode})',
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.successGreen,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              if (info.formattedSize.isNotEmpty) ...[
                Text(
                  'Tamaño: ${info.formattedSize}',
                  style: TextStyle(fontSize: 11, color: textSecondary),
                ),
                const SizedBox(height: 6),
              ],
              Text(
                'Novedades:',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: textPrimary,
                ),
              ),
              const SizedBox(height: 4),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: surfaceColor,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: borderColor),
                ),
                child: Text(
                  info.releaseNotes,
                  style: TextStyle(fontSize: 12, color: textPrimary, height: 1.3),
                ),
              ),
              if (_isDownloading) ...[
                const SizedBox(height: 18),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Descargando archivo APK...',
                      style: TextStyle(fontSize: 12, color: textSecondary),
                    ),
                    Text(
                      '$porcentaje%',
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.primaryRed,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: _progress > 0 ? _progress : null,
                    backgroundColor: borderColor,
                    valueColor: const AlwaysStoppedAnimation<Color>(AppTheme.primaryRed),
                    minHeight: 8,
                  ),
                ),
              ],
              if (_errorMessage != null) ...[
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: Colors.red.withAlpha(38),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.red.withAlpha(76)),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.error_outline, color: Colors.redAccent, size: 16),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          _errorMessage!,
                          style: const TextStyle(fontSize: 11, color: Colors.redAccent),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
        actions: [
          if (!_isDownloading) ...[
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text('Más tarde', style: TextStyle(color: textSecondary)),
            ),
            ElevatedButton.icon(
              onPressed: _iniciarActualizacion,
              icon: const Icon(Icons.download_rounded, size: 18),
              label: Text(_errorMessage != null ? 'Reintentar' : 'Actualizar ahora'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primaryRed,
                foregroundColor: Colors.white,
              ),
            ),
          ] else ...[
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Text(
                'Verificando firma SHA-256 y preparando instalación...',
                style: TextStyle(
                  fontSize: 11,
                  color: textSecondary,
                  fontStyle: FontStyle.italic,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
