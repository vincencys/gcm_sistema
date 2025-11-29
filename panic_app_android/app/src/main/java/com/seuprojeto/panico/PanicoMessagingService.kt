package com.seuprojeto.panico

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import java.net.HttpURLConnection
import java.net.URL
import org.json.JSONObject

class PanicoMessagingService : FirebaseMessagingService() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        // Salva token localmente
        getSharedPreferences("panic_prefs", MODE_PRIVATE)
            .edit().putString("fcm_token", token).apply()
        // Envia token ao backend automaticamente
        scope.launch {
            enviarTokenParaBackend(token)
        }
    }

    private fun enviarTokenParaBackend(token: String) {
        try {
            val prefs = getSharedPreferences("panic_prefs", MODE_PRIVATE)
            val baseUrl = prefs.getString("base_url", "") ?: ""
            if (baseUrl.isBlank()) return
            val url = URL("$baseUrl/common/push/register-device/")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.doOutput = true
            val payload = JSONObject().apply {
                put("token", token)
                put("platform", "android")
                put("app_version", getAppVersionName())
                put("device_info", "SafeBP")
                put("app_id", "safebp")
            }
            conn.outputStream.use { it.write(payload.toString().toByteArray()) }
            val code = conn.responseCode
            if (code in 200..299) {
                android.util.Log.d("PanicoMsg", "Token registrado: $code")
            } else {
                android.util.Log.w("PanicoMsg", "Falha ao registrar token: $code")
            }
        } catch (e: Exception) {
            android.util.Log.e("PanicoMsg", "Erro ao enviar token: ${e.message}")
        }
    }

    private fun getAppVersionName(): String {
        return try {
            val pm = packageManager
            val pkg = packageName
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                pm.getPackageInfo(pkg, PackageManager.PackageInfoFlags.of(0)).versionName ?: "unknown"
            } else {
                @Suppress("DEPRECATION")
                pm.getPackageInfo(pkg, 0).versionName ?: "unknown"
            }
        } catch (e: Exception) {
            "unknown"
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        android.util.Log.d("PanicoMsg", "Mensagem recebida! data=${message.data}")
        val data = message.data ?: return
        val kind = data["kind"] ?: return
        if (kind != "panico_status") return
        val status = data["status"] ?: ""
        val action = data["action"] ?: ""
        val motivo = data["motivo"] ?: ""
        val id = data["disparo_id"] ?: ""
        val title = data["title"] ?: "Atualização do Pânico"
        val body = data["body"] ?: ""
        android.util.Log.d("PanicoMsg", "Processando: kind=$kind, status=$status, action=$action, motivo=$motivo, id=$id")
        PanicoPrefs.saveStatus(this, id, status, motivo, action)
        // Notificação local amigável
        showNotification(title, body, status, motivo)
        // Broadcast para atualizar UI da MainActivity
        val broadcastIntent = Intent("com.seuprojeto.panico.STATUS_UPDATED")
        sendBroadcast(broadcastIntent)
    }

    private fun showNotification(title: String, body: String, status: String, motivo: String) {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channelId = "panico_status_channel"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            nm.createNotificationChannel(
                NotificationChannel(channelId, "Status do Pânico", NotificationManager.IMPORTANCE_HIGH)
            )
        }
        val intent = Intent(this, MainActivity::class.java)
        val pi = PendingIntent.getActivity(this, 0, intent, PendingIntent.FLAG_IMMUTABLE)
        // Usar título do backend se disponível, senão usar customizado
        val displayTitle = if (title.isNotBlank()) title else {
            when(status.uppercase()){
                "ENCERRADA" -> "🚨 Equipes à caminho"
                "CANCELADA" -> "Pânico recusado"
                "TESTE" -> "Pânico marcado como TESTE"
                else -> "Atualização do Pânico"
            }
        }
        val displayBody = body.ifBlank { motivo }
        val notif = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(displayTitle)
            .setContentText(displayBody)
            .setStyle(NotificationCompat.BigTextStyle().bigText(displayBody))
            .setAutoCancel(true)
            .setContentIntent(pi)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()
        nm.notify(2001, notif)
        android.util.Log.d("PanicoMsg", "Notificação exibida: $displayTitle - $displayBody")
    }
}
