import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'tls_pinning_service.dart';

class AppUpdateInfo {
  final int versionCode;
  final String versionName;
  final String apkUrl;
  final String releaseNotes;
  final int fileSize;
  final String updatedAt;
  final String sha256;

  AppUpdateInfo({
    required this.versionCode,
    required this.versionName,
    required this.apkUrl,
    required this.releaseNotes,
    required this.fileSize,
    required this.updatedAt,
    this.sha256 = '',
  });

  factory AppUpdateInfo.fromJson(Map<String, dynamic> json) {
    return AppUpdateInfo(
      versionCode: (json['version_code'] as num?)?.toInt() ?? 1,
      versionName: json['version_name']?.toString() ?? '1.0.0',
      apkUrl: json['apk_url']?.toString() ?? '/actualizaciones/StockAgent.apk',
      releaseNotes:
          json['release_notes']?.toString() ?? 'Actualización disponible para StockAgent.',
      fileSize: (json['file_size'] as num?)?.toInt() ?? 0,
      updatedAt: json['updated_at']?.toString() ?? '',
      sha256: json['sha256']?.toString().trim().toLowerCase() ?? '',
    );
  }

  String get formattedSize {
    if (fileSize <= 0) return '';
    final mb = fileSize / (1024 * 1024);
    return '${mb.toStringAsFixed(1)} MB';
  }
}

class UpdateService {
  static const MethodChannel _channel = MethodChannel('com.stockagent.mobile/app_updater');

  /// Obtiene la versión nativa del APK instalado en el celular
  Future<Map<String, dynamic>> getCurrentAppInfo() async {
    try {
      final info = await _channel.invokeMapMethod<String, dynamic>('getAppInfo');
      if (info != null) {
        return info;
      }
    } catch (_) {}
    return <String, dynamic>{'versionCode': 1, 'versionName': '1.0.0'};
  }

  /// Verifica contra el servidor local si hay una nueva versión compilada
  Future<AppUpdateInfo?> checkUpdate(String serverBaseUrl) async {
    try {
      final uri = Uri.parse('$serverBaseUrl/actualizaciones/version.json');
      final res = await http.get(uri).timeout(const Duration(seconds: 4));
      if (res.statusCode != 200) return null;

      final dynamic data = jsonDecode(utf8.decode(res.bodyBytes));
      if (data is! Map<String, dynamic>) return null;

      final update = AppUpdateInfo.fromJson(data);
      final current = await getCurrentAppInfo();
      final currentCode = (current['versionCode'] as num?)?.toInt() ?? 1;

      if (update.versionCode > currentCode) {
        return update;
      }
    } catch (_) {}
    return null;
  }

  /// Verifica que la URL de descarga del APK pertenezca al mismo servidor configurado.
  static bool isValidSameOriginUrl(String downloadUrl, String? expectedServerOrigin) {
    final dlUri = Uri.tryParse(downloadUrl);
    if (dlUri == null || !dlUri.hasScheme || dlUri.host.isEmpty) return false;
    if (expectedServerOrigin == null || expectedServerOrigin.trim().isEmpty) return true;
    final originUri = Uri.tryParse(expectedServerOrigin.trim());
    if (originUri == null || originUri.host.isEmpty) return false;
    return dlUri.host.toLowerCase() == originUri.host.toLowerCase() &&
        dlUri.port == originUri.port &&
        dlUri.scheme.toLowerCase() == originUri.scheme.toLowerCase();
  }

  /// Descarga el APK desde el servidor, valida su hash SHA-256 y activa el instalador de Android
  Future<void> downloadAndInstall({
    required String downloadUrl,
    String? expectedSha256,
    String? expectedServerOrigin,
    required void Function(double progress) onProgress,
    required void Function(String error) onError,
  }) async {
    http.Client? client;
    IOSink? sink;
    try {
      if (!isValidSameOriginUrl(downloadUrl, expectedServerOrigin)) {
        onError('La URL del APK no pertenece al servidor configurado. Descarga bloqueada.');
        return;
      }

      final cacheDirStr = await _channel.invokeMethod<String>('getCacheDirectory');
      if (cacheDirStr == null || cacheDirStr.isEmpty) {
        onError('No se pudo acceder a la carpeta temporal del dispositivo.');
        return;
      }

      final updatesDir = Directory('$cacheDirStr/updates');
      if (!await updatesDir.exists()) {
        await updatesDir.create(recursive: true);
      }

      final targetFile = File('${updatesDir.path}/StockAgent_update.apk');
      if (await targetFile.exists()) {
        try {
          await targetFile.delete();
        } catch (_) {}
      }

      client = http.Client();
      final request = http.Request('GET', Uri.parse(downloadUrl));
      final response = await client.send(request).timeout(const Duration(seconds: 15));

      if (response.statusCode != 200) {
        onError('Error en el servidor al descargar APK (${response.statusCode})');
        return;
      }

      final total = response.contentLength ?? 0;
      int received = 0;
      sink = targetFile.openWrite();

      await response.stream.listen(
        (List<int> chunk) {
          sink?.add(chunk);
          received += chunk.length;
          if (total > 0) {
            onProgress((received / total).clamp(0.0, 1.0));
          }
        },
        cancelOnError: true,
      ).asFuture();

      await sink.flush();
      await sink.close();
      sink = null;
      client.close();
      client = null;

      final cleanExpectedHash = (expectedSha256 ?? '').trim().toLowerCase();
      if (cleanExpectedHash.isNotEmpty) {
        String actualHash = '';
        try {
          actualHash = (await _channel.invokeMethod<String>(
                    'computeFileSha256',
                    {'filePath': targetFile.path},
                  ))
                  ?.trim()
                  .toLowerCase() ??
              '';
        } catch (_) {
          actualHash = TlsPinningService.sha256Hex(await targetFile.readAsBytes());
        }

        if (actualHash.isNotEmpty && actualHash != cleanExpectedHash) {
          try {
            await targetFile.delete();
          } catch (_) {}
          onError(
            'Verificación SHA-256 fallida: el APK descargado está corrupto o fue alterado.',
          );
          return;
        }
      }

      // Disparar instalación nativa con verificación de ruta, hash y packageName
      final installed = await _channel.invokeMethod<bool>('installApk', <String, dynamic>{
        'filePath': targetFile.path,
        if (cleanExpectedHash.isNotEmpty) 'expectedSha256': cleanExpectedHash,
      });

      if (installed != true) {
        onError('No se pudo iniciar el instalador de Android.');
      }
    } catch (e) {
      sink?.close();
      client?.close();
      onError('Error durante la actualización: $e');
    }
  }
}
