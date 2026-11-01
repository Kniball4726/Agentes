import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;

class AppUpdateInfo {
  final int versionCode;
  final String versionName;
  final String apkUrl;
  final String releaseNotes;
  final int fileSize;
  final String updatedAt;

  AppUpdateInfo({
    required this.versionCode,
    required this.versionName,
    required this.apkUrl,
    required this.releaseNotes,
    required this.fileSize,
    required this.updatedAt,
  });

  factory AppUpdateInfo.fromJson(Map<String, dynamic> json) {
    return AppUpdateInfo(
      versionCode: (json['version_code'] as num?)?.toInt() ?? 1,
      versionName: json['version_name']?.toString() ?? '1.0.0',
      apkUrl: json['apk_url']?.toString() ?? '/actualizaciones/StockAgent.apk',
      releaseNotes: json['release_notes']?.toString() ?? 'Actualización disponible para StockAgent.',
      fileSize: (json['file_size'] as num?)?.toInt() ?? 0,
      updatedAt: json['updated_at']?.toString() ?? '',
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

  /// Descarga el APK desde el servidor y activa el instalador de Android
  Future<void> downloadAndInstall({
    required String downloadUrl,
    required void Function(double progress) onProgress,
    required void Function(String error) onError,
  }) async {
    http.Client? client;
    IOSink? sink;
    try {
      final cacheDirStr = await _channel.invokeMethod<String>('getCacheDirectory');
      if (cacheDirStr == null || cacheDirStr.isEmpty) {
        onError('No se pudo acceder a la carpeta temporal del dispositivo.');
        return;
      }

      final targetFile = File('$cacheDirStr/StockAgent_update.apk');
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

      // Disparar instalación nativa
      final installed = await _channel.invokeMethod<bool>('installApk', <String, dynamic>{
        'filePath': targetFile.path,
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
