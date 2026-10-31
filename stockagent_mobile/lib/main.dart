import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'screens/app_screen.dart';
import 'screens/config_screen.dart';
import 'services/storage_service.dart';
import 'theme/app_theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Forzar barra de navegación y estado con estilo oscuro
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
      systemNavigationBarColor: AppTheme.darkBg,
      systemNavigationBarIconBrightness: Brightness.light,
    ),
  );

  final storageService = await StorageService.init();
  final bool tieneConfiguracion = storageService.hasValidConfig();

  runApp(StockAgentMobileApp(
    storageService: storageService,
    iniciarEnConfiguracion: !tieneConfiguracion,
  ));
}

class StockAgentMobileApp extends StatelessWidget {
  final StorageService storageService;
  final bool iniciarEnConfiguracion;

  const StockAgentMobileApp({
    super.key,
    required this.storageService,
    required this.iniciarEnConfiguracion,
  });

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'StockAgent Móvil',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      home: iniciarEnConfiguracion
          ? ConfigScreen(storageService: storageService)
          : AppScreen(storageService: storageService),
    );
  }
}
