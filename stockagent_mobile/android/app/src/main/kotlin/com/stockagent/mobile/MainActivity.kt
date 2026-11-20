package com.stockagent.mobile

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.OpenableColumns
import android.provider.Settings
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.core.content.FileProvider
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.security.KeyStore
import java.security.MessageDigest
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class MainActivity : FlutterActivity() {
    companion object {
        private const val CHANNEL = "com.stockagent.mobile/file_picker"
        private const val UPDATER_CHANNEL = "com.stockagent.mobile/app_updater"
        private const val SECURE_STORAGE_CHANNEL = "com.stockagent.mobile/secure_storage"
        private const val KEYSTORE_PROVIDER = "AndroidKeyStore"
        private const val KEY_ALIAS = "stockagent_master_key"
        private const val SECURE_PREFS_NAME = "stockagent_secure_store"
        private const val FILE_PICKER_REQUEST_CODE = 9412
    }

    private var pendingFilePickerResult: MethodChannel.Result? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
            .setMethodCallHandler { call, result ->
                if (call.method == "pickFiles") {
                    val allowMultiple = call.argument<Boolean>("allowMultiple") ?: true
                    launchFilePicker(allowMultiple, result)
                } else {
                    result.notImplemented()
                }
            }

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, SECURE_STORAGE_CHANNEL)
            .setMethodCallHandler { call, result ->
                val key = call.argument<String>("key")
                if (key.isNullOrBlank()) {
                    result.error("INVALID_KEY", "Clave de almacén seguro vacía", null)
                    return@setMethodCallHandler
                }
                when (call.method) {
                    "writeSecure" -> {
                        val value = call.argument<String>("value") ?: ""
                        try {
                            writeEncryptedValue(key, value)
                            result.success(true)
                        } catch (e: Exception) {
                            result.error("SECURE_WRITE_ERROR", e.message, null)
                        }
                    }
                    "readSecure" -> {
                        try {
                            result.success(readEncryptedValue(key))
                        } catch (e: Exception) {
                            result.error("SECURE_READ_ERROR", e.message, null)
                        }
                    }
                    "deleteSecure" -> {
                        try {
                            val prefs = getSharedPreferences(SECURE_PREFS_NAME, Context.MODE_PRIVATE)
                            prefs.edit().remove(key).apply()
                            result.success(true)
                        } catch (e: Exception) {
                            result.error("SECURE_DELETE_ERROR", e.message, null)
                        }
                    }
                    else -> result.notImplemented()
                }
            }

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, UPDATER_CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "getAppInfo" -> {
                        try {
                            val pInfo = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                                packageManager.getPackageInfo(packageName, PackageManager.PackageInfoFlags.of(0))
                            } else {
                                @Suppress("DEPRECATION")
                                packageManager.getPackageInfo(packageName, 0)
                            }
                            val versionCode = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                                pInfo.longVersionCode
                            } else {
                                @Suppress("DEPRECATION")
                                pInfo.versionCode.toLong()
                            }
                            val versionName = pInfo.versionName ?: "1.0.0"
                            result.success(
                                mapOf(
                                    "versionCode" to versionCode,
                                    "versionName" to versionName,
                                    "packageName" to packageName
                                )
                            )
                        } catch (e: Exception) {
                            result.error("VERSION_ERROR", e.message, null)
                        }
                    }
                    "getCacheDirectory" -> {
                        val updatesDir = File(cacheDir, "updates")
                        if (!updatesDir.exists()) {
                            updatesDir.mkdirs()
                        }
                        result.success(cacheDir.absolutePath)
                    }
                    "computeFileSha256" -> {
                        val filePath = call.argument<String>("filePath")
                        if (filePath.isNullOrBlank()) {
                            result.error("INVALID_PATH", "Ruta vacía", null)
                            return@setMethodCallHandler
                        }
                        val f = File(filePath)
                        if (!f.exists()) {
                            result.error("FILE_NOT_FOUND", "Archivo no existe", null)
                            return@setMethodCallHandler
                        }
                        try {
                            result.success(computeSha256File(f))
                        } catch (e: Exception) {
                            result.error("HASH_ERROR", e.message, null)
                        }
                    }
                    "installApk" -> {
                        val filePath = call.argument<String>("filePath")
                        val expectedSha256 = call.argument<String>("expectedSha256")?.trim()?.lowercase()
                        if (filePath.isNullOrBlank()) {
                            result.error("INVALID_PATH", "Ruta de archivo vacía", null)
                            return@setMethodCallHandler
                        }
                        val apkFile = File(filePath)
                        if (!apkFile.exists()) {
                            result.error("FILE_NOT_FOUND", "El archivo APK no existe en $filePath", null)
                            return@setMethodCallHandler
                        }

                        try {
                            val allowedDir = File(cacheDir, "updates").apply { if (!exists()) mkdirs() }
                            if (!apkFile.canonicalPath.startsWith(allowedDir.canonicalPath)) {
                                result.error(
                                    "FORBIDDEN_PATH",
                                    "El APK debe residir exclusivamente dentro de la carpeta segura de actualizaciones.",
                                    null
                                )
                                return@setMethodCallHandler
                            }

                            if (!expectedSha256.isNullOrEmpty()) {
                                val actualHash = computeSha256File(apkFile)
                                if (actualHash != expectedSha256) {
                                    apkFile.delete()
                                    result.error(
                                        "INTEGRITY_ERROR",
                                        "La firma SHA-256 del APK no coincide con la publicada por el servidor.",
                                        null
                                    )
                                    return@setMethodCallHandler
                                }
                            }

                            val archiveInfo = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                                packageManager.getPackageArchiveInfo(
                                    apkFile.absolutePath,
                                    PackageManager.PackageInfoFlags.of(0)
                                )
                            } else {
                                @Suppress("DEPRECATION")
                                packageManager.getPackageArchiveInfo(apkFile.absolutePath, 0)
                            }
                            if (archiveInfo == null || archiveInfo.packageName != packageName) {
                                apkFile.delete()
                                result.error(
                                    "PACKAGE_MISMATCH",
                                    "El paquete descargado no corresponde a StockAgent ($packageName).",
                                    null
                                )
                                return@setMethodCallHandler
                            }

                            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                                if (!packageManager.canRequestPackageInstalls()) {
                                    val manageIntent = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES).apply {
                                        data = Uri.parse("package:$packageName")
                                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                                    }
                                    startActivity(manageIntent)
                                }
                            }

                            val apkUri = FileProvider.getUriForFile(
                                this@MainActivity,
                                "$packageName.fileprovider",
                                apkFile
                            )

                            val installIntent = Intent(Intent.ACTION_VIEW).apply {
                                setDataAndType(apkUri, "application/vnd.android.package-archive")
                                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                            }
                            startActivity(installIntent)
                            result.success(true)
                        } catch (e: Exception) {
                            result.error("INSTALL_ERROR", e.message, null)
                        }
                    }
                    else -> result.notImplemented()
                }
            }
    }

    private fun getOrCreateSecretKey(): SecretKey {
        val keyStore = KeyStore.getInstance(KEYSTORE_PROVIDER).apply { load(null) }
        val existing = keyStore.getEntry(KEY_ALIAS, null) as? KeyStore.SecretKeyEntry
        if (existing != null) {
            return existing.secretKey
        }
        val keyGenerator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE_PROVIDER)
        val spec = KeyGenParameterSpec.Builder(
            KEY_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .build()
        keyGenerator.init(spec)
        return keyGenerator.generateKey()
    }

    private fun writeEncryptedValue(key: String, plainText: String) {
        val prefs = getSharedPreferences(SECURE_PREFS_NAME, Context.MODE_PRIVATE)
        if (plainText.isEmpty()) {
            prefs.edit().remove(key).apply()
            return
        }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateSecretKey())
        val iv = Base64.encodeToString(cipher.iv, Base64.NO_WRAP)
        val encrypted = Base64.encodeToString(cipher.doFinal(plainText.toByteArray(Charsets.UTF_8)), Base64.NO_WRAP)
        prefs.edit().putString(key, "$iv:$encrypted").apply()
    }

    private fun readEncryptedValue(key: String): String? {
        val prefs = getSharedPreferences(SECURE_PREFS_NAME, Context.MODE_PRIVATE)
        val stored = prefs.getString(key, null) ?: return null
        val parts = stored.split(":", limit = 2)
        if (parts.size != 2) return null
        val iv = Base64.decode(parts[0], Base64.NO_WRAP)
        val cipherBytes = Base64.decode(parts[1], Base64.NO_WRAP)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, getOrCreateSecretKey(), GCMParameterSpec(128, iv))
        return String(cipher.doFinal(cipherBytes), Charsets.UTF_8)
    }

    private fun computeSha256File(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { fis ->
            val buffer = ByteArray(16384)
            var read = fis.read(buffer)
            while (read > 0) {
                digest.update(buffer, 0, read)
                read = fis.read(buffer)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun launchFilePicker(allowMultiple: Boolean, result: MethodChannel.Result) {
        // Si había una solicitud previa colgada, cerrarla limpiamente para no bloquear el WebView
        pendingFilePickerResult?.success(emptyList<String>())
        pendingFilePickerResult = result

        try {
            val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                addCategory(Intent.CATEGORY_OPENABLE)
                type = "*/*"
                putExtra(Intent.EXTRA_ALLOW_MULTIPLE, allowMultiple)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            startActivityForResult(intent, FILE_PICKER_REQUEST_CODE)
        } catch (_: Exception) {
            try {
                val fallback = Intent(Intent.ACTION_GET_CONTENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = "*/*"
                    putExtra(Intent.EXTRA_ALLOW_MULTIPLE, allowMultiple)
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                }
                startActivityForResult(
                    Intent.createChooser(fallback, "Seleccionar archivo"),
                    FILE_PICKER_REQUEST_CODE
                )
            } catch (_: Exception) {
                pendingFilePickerResult = null
                result.success(emptyList<String>())
            }
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        if (requestCode == FILE_PICKER_REQUEST_CODE) {
            val callback = pendingFilePickerResult
            pendingFilePickerResult = null
            if (callback == null) {
                super.onActivityResult(requestCode, resultCode, data)
                return
            }

            if (resultCode != Activity.RESULT_OK || data == null) {
                callback.success(emptyList<String>())
                return
            }

            val uris = mutableListOf<Uri>()
            val clipData = data.clipData
            if (clipData != null) {
                for (i in 0 until clipData.itemCount) {
                    clipData.getItemAt(i)?.uri?.let { uris.add(it) }
                }
            } else {
                data.data?.let { uris.add(it) }
            }

            val resolvedPaths = mutableListOf<String>()
            for (uri in uris) {
                val cachedUri = copyUriToCacheWithOriginalName(uri)
                if (cachedUri != null) {
                    resolvedPaths.add(cachedUri)
                } else {
                    resolvedPaths.add(uri.toString())
                }
            }
            callback.success(resolvedPaths)
            return
        }
        super.onActivityResult(requestCode, resultCode, data)
    }

    private fun copyUriToCacheWithOriginalName(uri: Uri): String? {
        return try {
            val displayName = resolveDisplayName(uri) ?: "archivo_${System.currentTimeMillis()}"
            val safeName = displayName
                .replace(Regex("[\\\\/:*?\"<>|\\x00]"), "_")
                .trim()
                .ifEmpty { "archivo_${System.currentTimeMillis()}" }

            val uploadDir = File(cacheDir, "picker_uploads")
            if (!uploadDir.exists()) {
                uploadDir.mkdirs()
            }

            val destFile = File(uploadDir, safeName)
            if (destFile.exists()) {
                destFile.delete()
            }

            contentResolver.openInputStream(uri)?.use { input ->
                FileOutputStream(destFile).use { output ->
                    input.copyTo(output)
                }
            } ?: return null

            Uri.fromFile(destFile).toString()
        } catch (_: Exception) {
            null
        }
    }

    private fun resolveDisplayName(uri: Uri): String? {
        if (uri.scheme == "content") {
            try {
                contentResolver.query(
                    uri,
                    arrayOf(OpenableColumns.DISPLAY_NAME),
                    null,
                    null,
                    null
                )?.use { cursor ->
                    if (cursor.moveToFirst()) {
                        val idx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                        if (idx >= 0) {
                            val name = cursor.getString(idx)
                            if (!name.isNullOrBlank()) {
                                return name
                            }
                        }
                    }
                }
            } catch (_: Exception) {
            }
        }
        return uri.lastPathSegment?.substringAfterLast('/')
    }
}
