package com.seuprojeto.panico

import android.Manifest
import android.app.*
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.IBinder
import androidx.core.app.ActivityCompat
import androidx.core.app.NotificationCompat
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import kotlinx.coroutines.*
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import kotlin.coroutines.resume

class PanicLocationService : Service() {
    private val serviceScope = CoroutineScope(Dispatchers.Default + SupervisorJob())
    private var updateJob: Job? = null

    companion object {
        const val EXTRA_DISPARO_ID = "disparo_id"
        const val EXTRA_TOKEN = "token"
        const val EXTRA_BASE_URL = "base_url"
        const val NOTIFICATION_ID = 9001
        const val CHANNEL_ID = "panic_location_channel"

        fun start(context: Context, disparoId: Int, token: String, baseUrl: String) {
            val intent = Intent(context, PanicLocationService::class.java).apply {
                putExtra(EXTRA_DISPARO_ID, disparoId)
                putExtra(EXTRA_TOKEN, token)
                putExtra(EXTRA_BASE_URL, baseUrl)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(intent)
            } else {
                context.startService(intent)
            }
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, PanicLocationService::class.java))
        }

        fun updateStatusNotification(context: Context, status: String?, motivo: String?) {
            val s = status?.uppercase() ?: ""
            val (title, body) = when (s) {
                "ENCERRADA" -> Pair("Equipes à caminho!", "Localização ativa")
                "CANCELADA" -> Pair("Pânico recusado", (motivo?.takeIf { it.isNotBlank() } ?: "sem motivo"))
                "TESTE" -> Pair("Disparo em modo TESTE", "Localização ativa")
                else -> Pair("Botão do Pânico Ativo", "Enviando localização...")
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val nm = context.getSystemService(NotificationManager::class.java)
                val existing = nm?.getNotificationChannel(CHANNEL_ID)
                if (existing == null) {
                    val ch = NotificationChannel(
                        CHANNEL_ID,
                        "Localização de Pânico",
                        NotificationManager.IMPORTANCE_LOW
                    ).apply { description = "Envia localização contínua durante emergência" }
                    nm?.createNotificationChannel(ch)
                }
            }
            val intent = Intent(context, MainActivity::class.java)
            val pi = PendingIntent.getActivity(context, 0, intent, PendingIntent.FLAG_IMMUTABLE)
            val notif = NotificationCompat.Builder(context, CHANNEL_ID)
                .setContentTitle(title)
                .setContentText(body)
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentIntent(pi)
                .setOngoing(s != "CANCELADA")
                .build()
            val nm2 = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            nm2.notify(NOTIFICATION_ID, notif)
            if (s == "CANCELADA") {
                stop(context)
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        val notification = buildNotification("Enviando localização...")
        startForeground(NOTIFICATION_ID, notification)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val disparoId = intent?.getIntExtra(EXTRA_DISPARO_ID, -1) ?: -1
        val token = intent?.getStringExtra(EXTRA_TOKEN) ?: ""
        val baseUrl = intent?.getStringExtra(EXTRA_BASE_URL) ?: ""
        if (disparoId <= 0 || token.isBlank() || baseUrl.isBlank()) {
            stopSelf()
            return START_NOT_STICKY
        }
        updateJob?.cancel()
        updateJob = serviceScope.launch {
            while (isActive) {
                try {
                    val loc = obterLocalizacao()
                    if (loc != null) {
                        enviarLocalizacao(disparoId, token, baseUrl, loc)
                    }
                } catch (_: Exception) { }
                delay(15000)
            }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        updateJob?.cancel()
        serviceScope.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Localização de Pânico",
                NotificationManager.IMPORTANCE_LOW
            ).apply { description = "Envia localização contínua durante emergência" }
            val nm = getSystemService(NotificationManager::class.java)
            nm?.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(text: String): Notification {
        val intent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(this, 0, intent, PendingIntent.FLAG_IMMUTABLE)
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Botão do Pânico Ativo")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build()
    }

    private suspend fun obterLocalizacao(): LocData? = withContext(Dispatchers.IO) {
        if (ActivityCompat.checkSelfPermission(this@PanicLocationService, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            return@withContext null
        }
        val client = LocationServices.getFusedLocationProviderClient(this@PanicLocationService)
        try {
            suspendCancellableCoroutine<LocData?> { cont ->
                client.getCurrentLocation(Priority.PRIORITY_HIGH_ACCURACY, null)
                    .addOnSuccessListener { loc ->
                        if (loc != null) {
                            cont.resume(LocData(loc.latitude, loc.longitude, loc.accuracy))
                        } else {
                            cont.resume(null)
                        }
                    }
                    .addOnFailureListener {
                        cont.resume(null)
                    }
            }
        } catch (e: Exception) {
            null
        }
    }

    private suspend fun enviarLocalizacao(disparoId: Int, token: String, baseUrl: String, loc: LocData) = withContext(Dispatchers.IO) {
        try {
            val locUrl = baseUrl.replace("/disparo/", "/disparo/$disparoId/localizacao/")
            val obj = JSONObject().apply {
                put("token", token)
                put("latitude", loc.lat)
                put("longitude", loc.lon)
                put("precisao", loc.acc.toInt())
            }
            val conn = URL(locUrl).openConnection() as HttpURLConnection
            conn.requestMethod = "POST"
            conn.setRequestProperty("Content-Type", "application/json")
            conn.setRequestProperty("Accept", "application/json")
            conn.connectTimeout = 8000
            conn.readTimeout = 8000
            conn.doOutput = true
            conn.outputStream.use { it.write(obj.toString().toByteArray()) }
            conn.inputStream.close()
        } catch (_: Exception) { }
    }

    data class LocData(val lat: Double, val lon: Double, val acc: Float)
}
