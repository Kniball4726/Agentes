import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:stockagent_mobile/controllers/dispatch_controller.dart';
import 'package:stockagent_mobile/controllers/inventory_controller.dart';
import 'package:stockagent_mobile/models/auth_user.dart';
import 'package:stockagent_mobile/models/order_dispatch.dart';
import 'package:stockagent_mobile/models/product_item.dart';
import 'package:stockagent_mobile/models/server_config.dart';
import 'package:stockagent_mobile/services/api_service.dart';
import 'package:stockagent_mobile/services/storage_service.dart';
import 'package:stockagent_mobile/services/tls_pinning_service.dart';
import 'package:stockagent_mobile/services/update_service.dart';

class _FakeX509Certificate implements X509Certificate {
  @override
  final Uint8List der;

  @override
  final Uint8List sha1;

  @override
  final String pem;

  @override
  final String subject;

  @override
  final String issuer;

  @override
  final DateTime startValidity;

  @override
  final DateTime endValidity;

  _FakeX509Certificate({
    required this.der,
    required this.startValidity,
    required this.endValidity,
    Uint8List? sha1,
    this.pem = '',
    this.subject = 'CN=192.168.100.19',
    this.issuer = 'CN=StockAgent Local CA',
  }) : sha1 = sha1 ?? Uint8List.fromList(List<int>.filled(20, 1));
}

class _StubApiService extends ApiService {
  Future<ProductItem?> Function(String code)? onGetProduct;
  Future<ScanDispatchResult> Function(String code, String? targetState)?
      onScanDispatch;
  Future<List<ScanDispatchResult>> Function(List<Map<String, dynamic>> items)?
      onScanBatch;

  _StubApiService({
    required super.storageService,
    this.onGetProduct,
    this.onScanDispatch,
    this.onScanBatch,
  });

  @override
  Future<List<OrderDispatch>> listOrders({String? state, int limit = 50}) async {
    return <OrderDispatch>[];
  }

  @override
  Future<ProductItem?> getProduct(String codeOrBarcode) async {
    if (onGetProduct != null) {
      return onGetProduct!(codeOrBarcode);
    }
    return ProductItem.fromJson({
      'code': codeOrBarcode.toUpperCase(),
      'name': 'Producto $codeOrBarcode',
      'stock': 10,
      'stock_minimo': 2,
    });
  }

  @override
  Future<ScanDispatchResult> scanDispatch(
    String codeOrRemito, {
    String? targetState,
  }) async {
    if (onScanDispatch != null) {
      return onScanDispatch!(codeOrRemito, targetState);
    }
    return ScanDispatchResult(
      ok: true,
      mensaje: 'Despachado $codeOrRemito',
    );
  }

  @override
  Future<List<ScanDispatchResult>> scanDispatchBatch(
    List<Map<String, dynamic>> items,
  ) async {
    if (onScanBatch != null) {
      return onScanBatch!(items);
    }
    return items
        .map(
          (it) => ScanDispatchResult(
            ok: true,
            mensaje: 'OK ${it['codigo']}',
          ),
        )
        .toList();
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('ServerConfig parsing y validacion', () {
    test('parsea URLs completas con esquema, puerto y ruta', () {
      final cfg = ServerConfig.fromUserInput(
        rawHost: 'https://192.168.1.50:8550/login/',
      );
      expect(cfg.host, '192.168.1.50');
      expect(cfg.normalizedPort, '8550');
      expect(cfg.normalizedProtocol, 'https');
      expect(cfg.fullUrl, 'https://192.168.1.50:8550');
      expect(cfg.wsUrl, 'wss://192.168.1.50:8550/ws');
      expect(cfg.isValid, isTrue);
    });

    test('parsea host:puerto HTTP y valida entradas invalidas', () {
      final httpCfg = ServerConfig.fromUserInput(
        rawHost: 'http://stockagent.local:9000/api',
      );
      expect(httpCfg.host, 'stockagent.local');
      expect(httpCfg.normalizedPort, '9000');
      expect(httpCfg.normalizedProtocol, 'http');
      expect(httpCfg.wsUrl, 'ws://stockagent.local:9000/ws');

      expect(ServerConfig.empty().isValid, isFalse);
      expect(const ServerConfig(host: 'ab').isValid, isFalse);
      expect(const ServerConfig(host: '192.168 1.1').isValid, isFalse);
    });

    test('roundtrip toJson y fromJson preserva certSha256', () {
      const original = ServerConfig(
        host: '10.0.0.5',
        port: '8551',
        protocol: 'https',
        certSha256: 'abc123',
      );
      final restored = ServerConfig.fromJson(original.toJson());
      expect(restored, original);
    });
  });

  group('TlsPinningService SHA-256 y validacion de certificados', () {
    test('sha256Hex coincide con vectores estandar FIPS 180-4', () {
      expect(
        TlsPinningService.sha256Hex(utf8.encode('')),
        'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
      );
      expect(
        TlsPinningService.sha256Hex(utf8.encode('abc')),
        'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
      );
      expect(TlsPinningService.bytesToHex(<int>[0, 15, 255]), '000fff');
    });

    test('verifyServerCertificate valida host, vigencia, TOFU y pin fijado', () {
      final now = DateTime.now().toUtc();
      final cert = _FakeX509Certificate(
        der: Uint8List.fromList(utf8.encode('cert-der-demo')),
        startValidity: now.subtract(const Duration(days: 1)),
        endValidity: now.add(const Duration(days: 30)),
      );
      const expectedCfg = ServerConfig(
        host: '192.168.100.19',
        port: '8550',
        protocol: 'https',
      );

      String? capturedPin;
      final tofuOk = TlsPinningService.verifyServerCertificate(
        cert: cert,
        host: '192.168.100.19',
        port: 8550,
        expectedConfig: expectedCfg,
        onPinFirstUse: (fp) => capturedPin = fp,
      );
      expect(tofuOk, isTrue);
      expect(capturedPin, TlsPinningService.sha256Hex(cert.der));

      // Mismo pin pasa
      expect(
        TlsPinningService.verifyServerCertificate(
          cert: cert,
          host: '192.168.100.19',
          port: 8550,
          expectedConfig: expectedCfg,
          pinnedSha256: capturedPin,
        ),
        isTrue,
      );

      // Pin distinto falla (MITM / rotacion)
      expect(
        TlsPinningService.verifyServerCertificate(
          cert: cert,
          host: '192.168.100.19',
          port: 8550,
          expectedConfig: expectedCfg,
          pinnedSha256: 'deadbeef',
        ),
        isFalse,
      );

      // Host distinto falla
      expect(
        TlsPinningService.verifyServerCertificate(
          cert: cert,
          host: '192.168.100.99',
          port: 8550,
          expectedConfig: expectedCfg,
          onPinFirstUse: (_) {},
        ),
        isFalse,
      );

      // Certificado vencido falla
      final expiredCert = _FakeX509Certificate(
        der: Uint8List.fromList(utf8.encode('cert-expired')),
        startValidity: now.subtract(const Duration(days: 10)),
        endValidity: now.subtract(const Duration(days: 1)),
      );
      expect(
        TlsPinningService.verifyServerCertificate(
          cert: expiredCert,
          host: '192.168.100.19',
          port: 8550,
          expectedConfig: expectedCfg,
          onPinFirstUse: (_) {},
        ),
        isFalse,
      );
    });
  });

  group('UpdateService seguridad same-origin y modelo AppUpdateInfo', () {
    test('isValidSameOriginUrl bloquea origenes distintos y esquemas no HTTP', () {
      const origin = 'https://192.168.100.19:8550';
      expect(
        UpdateService.isValidSameOriginUrl(
          'https://192.168.100.19:8550/actualizaciones/StockAgent.apk',
          origin,
        ),
        isTrue,
      );
      expect(
        UpdateService.isValidSameOriginUrl(
          'http://192.168.100.19:8550/actualizaciones/StockAgent.apk',
          origin,
        ),
        isFalse,
      );
      expect(
        UpdateService.isValidSameOriginUrl(
          'https://evil.example.com:8550/StockAgent.apk',
          origin,
        ),
        isFalse,
      );
      expect(
        UpdateService.isValidSameOriginUrl(
          'file:///sdcard/StockAgent.apk',
          null,
        ),
        isFalse,
      );
    });

    test('AppUpdateInfo formatea tamano y normaliza sha256', () {
      final info = AppUpdateInfo.fromJson({
        'version_code': 7,
        'version_name': '2.0.4',
        'apk_url': '/actualizaciones/StockAgent.apk',
        'release_notes': 'Mejoras de seguridad',
        'file_size': 52428800,
        'updated_at': '2026-11-28',
        'sha256': '  ABCDEF1234  ',
      });
      expect(info.versionCode, 7);
      expect(info.formattedSize, '50.0 MB');
      expect(info.sha256, 'abcdef1234');
    });
  });

  group('StorageService aislamiento por usuario y configuracion', () {
    test('aisla borradores y colas offline entre distintos usuarios', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final prefs = await SharedPreferences.getInstance();
      final storage = StorageService(prefs);

      await storage.saveConfig(
        const ServerConfig(
          host: '192.168.1.20',
          port: '8550',
          protocol: 'https',
          certSha256: 'AA11BB',
        ),
      );
      expect(storage.hasValidConfig(), isTrue);
      expect(storage.getPinnedCertSha256('192.168.1.20'), 'aa11bb');

      await storage.saveDraftCount('{"SKU-1": 5}', username: 'operario_a');
      await storage.saveDraftCount('{"SKU-2": 9}', username: 'operario_b');
      expect(storage.getDraftCount(username: 'operario_a'), '{"SKU-1": 5}');
      expect(storage.getDraftCount(username: 'operario_b'), '{"SKU-2": 9}');

      await storage.saveOfflineDispatchQueue('[{"codigo":"R-1"}]', username: 'operario_a');
      expect(storage.getOfflineDispatchQueue(username: 'operario_b'), isNull);

      await storage.clearConfig();
      expect(storage.isConfigured, isFalse);
      expect(storage.getPinnedCertSha256('192.168.1.20'), isNull);
    });
  });

  group('InventoryController y DispatchController resiliencia', () {
    test('InventoryController procesa escaneos, deshace eliminacion y tolera dispose', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final prefs = await SharedPreferences.getInstance();
      final storage = StorageService(prefs);
      final api = _StubApiService(storageService: storage);
      const user = AuthUser(
        id: 1,
        username: 'picker1',
        role: 'picker',
        nombre: 'Picker Uno',
      );

      final ctrl = InventoryController(apiService: api, currentUser: user);
      ctrl.setMultiplicador(6);
      await ctrl.procesarCodigo('sku-10');
      expect(ctrl.conteo['SKU-10'], 6);
      expect(ctrl.totalUnidades, 6);

      ctrl.eliminarItem('SKU-10');
      expect(ctrl.isEmpty, isTrue);
      expect(ctrl.deshacerEliminacion(), isTrue);
      expect(ctrl.conteo['SKU-10'], 6);

      ctrl.dispose();
      // No debe lanzar FlutterError tras dispose()
      expect(() => ctrl.setMultiplicador(1), returnsNormally);
      api.dispose();
    });

    test('DispatchController aplica RBAC, cola offline y sincronizacion segura', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final prefs = await SharedPreferences.getInstance();
      final storage = StorageService(prefs);

      bool offline = true;
      final api = _StubApiService(
        storageService: storage,
        onScanDispatch: (code, target) async {
          if (offline) {
            throw ApiException(0, 'Sin red');
          }
          return ScanDispatchResult(ok: true, mensaje: 'OK $code');
        },
      );
      const operario = AuthUser(
        id: 2,
        username: 'oper1',
        role: 'operador',
        nombre: 'Operario',
      );

      final ctrl = DispatchController(apiService: api, currentUser: operario);
      // Operador no puede pasar a modo armado (solo admin/master)
      ctrl.setModo('armado');
      expect(ctrl.modoSeleccionado, 'auto');

      // Con fallo de red, guarda en cola offline persistente
      await ctrl.procesarEscaneo('REM-101');
      expect(ctrl.colaOffline.length, 1);

      // Al volver la red, sincroniza y vacia la cola
      offline = false;
      final synced = await ctrl.sincronizarColaOffline();
      expect(synced, 1);
      expect(ctrl.colaOffline, isEmpty);

      ctrl.dispose();
      expect(() => ctrl.setModo('despachado'), returnsNormally);
      api.dispose();
    });
  });
}
