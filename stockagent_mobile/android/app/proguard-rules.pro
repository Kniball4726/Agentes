# Reglas R8 / ProGuard para StockAgent Móvil
-keep class io.flutter.app.** { *; }
-keep class io.flutter.plugin.** { *; }
-keep class io.flutter.util.** { *; }
-keep class io.flutter.view.** { *; }
-keep class io.flutter.** { *; }
-keep class io.flutter.plugins.** { *; }
-keep class com.stockagent.mobile.** { *; }
-dontwarn com.google.mlkit.**
