import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'models/auth_user.dart';
import 'screens/config_screen.dart';
import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'services/storage_service.dart';
import 'theme/app_theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final storageService = await StorageService.init();
  final bool usarTemaClaro = storageService.isLightTheme;
  AppTheme.themeModeNotifier.value =
      usarTemaClaro ? ThemeMode.light : ThemeMode.dark;

  SystemChrome.setSystemUIOverlayStyle(
    SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: usarTemaClaro ? Brightness.dark : Brightness.light,
      systemNavigationBarColor: usarTemaClaro ? AppTheme.lightBg : AppTheme.darkBg,
      systemNavigationBarIconBrightness:
          usarTemaClaro ? Brightness.dark : Brightness.light,
    ),
  );

  final bool yaConfigurado = storageService.hasValidConfig();

  AuthUser? usuarioActivo;
  if (yaConfigurado) {
    final rawUser = storageService.getAuthUser();
    final token = storageService.getAuthToken();
    if (token != null && token.trim().isNotEmpty) {
      usuarioActivo = AuthUser.deserialize(rawUser);
    }
  }

  runApp(StockAgentMobileApp(
    storageService: storageService,
    iniciarEnConfiguracion: !yaConfigurado,
    usuarioActivo: usuarioActivo,
  ));
}

class StockAgentMobileApp extends StatelessWidget {
  final StorageService storageService;
  final bool iniciarEnConfiguracion;
  final AuthUser? usuarioActivo;

  const StockAgentMobileApp({
    super.key,
    required this.storageService,
    required this.iniciarEnConfiguracion,
    this.usuarioActivo,
  });

  @override
  Widget build(BuildContext context) {
    final Widget pantallaInicial;

    if (iniciarEnConfiguracion) {
      pantallaInicial = ConfigScreen(storageService: storageService);
    } else if (usuarioActivo != null) {
      pantallaInicial = HomeScreen(
        storageService: storageService,
        currentUser: usuarioActivo!,
      );
    } else {
      pantallaInicial = LoginScreen(storageService: storageService);
    }

    return ValueListenableBuilder<ThemeMode>(
      valueListenable: AppTheme.themeModeNotifier,
      builder: (context, currentMode, _) {
        return MaterialApp(
          title: 'StockAgent Móvil',
          debugShowCheckedModeBanner: false,
          theme: AppTheme.lightTheme,
          darkTheme: AppTheme.darkTheme,
          themeMode: currentMode,
          home: pantallaInicial,
        );
      },
    );
  }
}
