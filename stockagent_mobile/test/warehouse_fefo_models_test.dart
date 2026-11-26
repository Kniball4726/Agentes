import 'package:flutter_test/flutter_test.dart';
import 'package:stockagent_mobile/models/auth_user.dart';
import 'package:stockagent_mobile/models/product_item.dart';
import 'package:stockagent_mobile/models/warehouse_fefo.dart';

void main() {
  group('ProductItem disponibilidad y retrocompatibilidad', () {
    test('calcula disponibleNeto, hasReservas e isCritical con reservas activas', () {
      final item = ProductItem.fromJson({
        'code': 'SKU-100',
        'name': 'Sellador Acrílico',
        'stock': 12,
        'stock_fisico': 12,
        'stock_reservado': 8,
        'stock_disponible': 4,
        'stock_minimo': 5,
        'stock_maximo': 30,
        'cod_barras': '7790001112223',
        'ubicacion': 'A-01-2',
        'active': true,
      });

      expect(item.code, 'SKU-100');
      expect(item.stock, 12);
      expect(item.stockReservado, 8);
      expect(item.disponibleNeto, 4);
      expect(item.hasReservas, isTrue);
      expect(item.isCritical, isTrue);
      expect(item.hasLocation, isTrue);
      expect(item.hasBarcode, isTrue);

      final roundtrip = ProductItem.fromJson(item.toJson());
      expect(roundtrip.disponibleNeto, 4);
      expect(roundtrip.stockReservado, 8);
    });

    test('mantiene compatibilidad cuando faltan stock_reservado y stock_disponible', () {
      final legacy = ProductItem.fromJson({
        'code': 'LEG-1',
        'name': 'Producto Legacy',
        'stock': 15,
        'stock_minimo': 5,
      });

      expect(legacy.stockReservado, 0);
      expect(legacy.disponibleNeto, 15);
      expect(legacy.hasReservas, isFalse);
      expect(legacy.isCritical, isFalse);
    });
  });

  group('Modelos multi-ubicación, lotes FEFO y reservas', () {
    test('ProductLocationsSummary parsea zonas ordenadas', () {
      final summary = ProductLocationsSummary.fromJson({
        'product_code': 'SKU-100',
        'product_name': 'Sellador Acrílico',
        'stock_fisico': 40,
        'stock_reservado': 5,
        'stock_disponible': 35,
        'ubicaciones': [
          {
            'id': 1,
            'product_code': 'SKU-100',
            'ubicacion': 'A-01-2',
            'tipo_zona': 'picking',
            'stock': 10,
            'capacidad_max': 25,
            'es_principal': true,
          },
          {
            'id': 2,
            'product_code': 'SKU-100',
            'ubicacion': 'P-03-1',
            'tipo_zona': 'pulmon',
            'stock': 30,
            'capacidad_max': 100,
            'es_principal': false,
          },
        ],
      });

      expect(summary.stockDisponible, 35);
      expect(summary.ubicaciones.length, 2);
      expect(summary.ubicaciones.first.tipoZona, 'picking');
      expect(summary.ubicaciones.first.esPrincipal, isTrue);
      expect(summary.ubicaciones.last.tipoZona, 'pulmon');
    });

    test('StockLot y StockReservation mapean campos FEFO y reservas', () {
      final lote = StockLot.fromJson({
        'id': 9,
        'product_code': 'SKU-100',
        'product_name': 'Sellador Acrílico',
        'lote': 'L-FEFO-01',
        'ubicacion': 'A-01-2',
        'fecha_vencimiento': '2026-12-05',
        'stock': 8,
        'estado': 'disponible',
        'dias_para_vencer': 5,
        'vencido': false,
        'nivel_alerta': 'CRITICO',
      });
      expect(lote.lote, 'L-FEFO-01');
      expect(lote.nivelAlerta, 'CRITICO');
      expect(lote.vencido, isFalse);

      final reserva = StockReservation.fromJson({
        'id': 4,
        'referencia_tipo': 'ola_picking',
        'referencia_id': 'OLA-2026-01',
        'product_code': 'SKU-100',
        'product_name': 'Sellador Acrílico',
        'cantidad': 6,
        'estado': 'activa',
        'ubicacion': 'A-01-2',
        'usuario': 'picker_1',
        'nota': 'Ola mañana',
      });
      expect(reserva.referenciaTipo, 'ola_picking');
      expect(reserva.referenciaId, 'OLA-2026-01');
      expect(reserva.cantidad, 6);
    });

    test('AuthUser expone permisos RBAC esperados', () {
      const picker = AuthUser(
        id: 2,
        username: 'picker1',
        role: 'picker',
        nombre: 'Picker Uno',
      );
      expect(picker.isPicker, isTrue);
      expect(picker.canEditCatalog, isFalse);

      const consulta = AuthUser(
        id: 3,
        username: 'vista',
        role: 'consulta',
        nombre: 'Solo Lectura',
      );
      expect(consulta.isConsulta, isTrue);
      expect(consulta.isPicker, isFalse);
      expect(consulta.canEditCatalog, isFalse);
    });
  });
}
