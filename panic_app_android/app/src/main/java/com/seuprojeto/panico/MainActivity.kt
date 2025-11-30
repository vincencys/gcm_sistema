package com.seuprojeto.panico

import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.View
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.*
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume

class MainActivity : AppCompatActivity() {

    private var statusUpdateReceiver: BroadcastReceiver? = null
    private val PERMISSION_REQUEST_CODE = 1001
    private val NOTIFICATION_PERMISSION_REQUEST_CODE = 1002

    // Base URL definida por flavor (BuildConfig.API_BASE_URL)

    private fun buildDispatchUrl(base:String) = base.trimEnd('/') + "/panic/public/disparo/"
    private fun buildRegisterUrl(base:String) = base.trimEnd('/') + "/panic/public/assistida/solicitar/"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // Verificar e solicitar permissões obrigatórias
        verificarPermissoesObrigatorias()

        val layoutConfirmacao = findViewById<LinearLayout>(R.id.layoutConfirmacao)
        val layoutPanico = findViewById<LinearLayout>(R.id.layoutPanico)
        val bannerStatus = findViewById<TextView>(R.id.textStatusPanico)
        val editToken = findViewById<EditText>(R.id.editToken)
        val btnConfirmar = findViewById<Button>(R.id.btnConfirmar)
        val btnRegistro = findViewById<Button>(R.id.btnRegistro)
        val btnPanicoBig = findViewById<Button>(R.id.btnPanicoBig)
        val prefs = getSharedPreferences("panic_prefs", MODE_PRIVATE)
        val lastToken = prefs.getString("token", "")
        val confirmed = prefs.getBoolean("confirmed", false)
        // Persistir a base do flavor para componentes que usam SharedPreferences (ex.: FCM)
        prefs.edit().putString("base", BuildConfig.API_BASE_URL)
            .putString("base_url", BuildConfig.API_BASE_URL)
            .apply()
        if (!lastToken.isNullOrBlank()) editToken.setText(lastToken)
        
        val textFeedback = findViewById<TextView>(R.id.textFeedback)

        // Mostrar layout conforme estado salvo
        if (confirmed && !lastToken.isNullOrBlank()) {
            layoutConfirmacao.visibility = View.GONE
            layoutPanico.visibility = View.VISIBLE
            textFeedback.text = "Pronto para acionar o pânico."
            textFeedback.setTextColor(0xFF444444.toInt())
            atualizarBannerStatus(bannerStatus)
        } else {
            layoutConfirmacao.visibility = View.VISIBLE
            layoutPanico.visibility = View.GONE
        }

        btnConfirmar.setOnClickListener {
            val token = editToken.text.toString().trim()
            if (token.isEmpty()) {
                textFeedback.text = "Informe o token."
                textFeedback.setTextColor(0xFFB91C1C.toInt())
                return@setOnClickListener
            }
            // Persistir confirmação e dados
            prefs.edit()
                .putString("token", token)
                .putString("base", BuildConfig.API_BASE_URL)
                .putString("base_url", BuildConfig.API_BASE_URL)
                .putBoolean("confirmed", true)
                .apply()

            // Alternar para tela de pânico
            layoutConfirmacao.visibility = View.GONE
            layoutPanico.visibility = View.VISIBLE
            textFeedback.text = "Configuração salva. Pronto para acionar."
            textFeedback.setTextColor(0xFF444444.toInt())
        }

        btnRegistro.setOnClickListener {
            val intent = Intent(this, br.gov.pr.pbto.gcm.panic.RegisterActivity::class.java)
            startActivity(intent)
        }

        // Implementar contador de 2 segundos para acionar pânico
        val textContador = findViewById<TextView>(R.id.textContador)
        val progressBarContador = findViewById<ProgressBar>(R.id.progressBarContador)
        var contadorJob: Job? = null
        
        btnPanicoBig.setOnTouchListener { view, event ->
            when (event.action) {
                android.view.MotionEvent.ACTION_DOWN -> {
                    // Inicia contador e animação da barra
                    var segundos = 2
                    var progresso = 0
                    textContador.visibility = View.VISIBLE
                    progressBarContador.visibility = View.VISIBLE
                    textContador.text = segundos.toString()
                    progressBarContador.progress = 0
                    
                    contadorJob = lifecycleScope.launch {
                        val totalSteps = 20 // 20 steps em 2 segundos = 100ms por step
                        repeat(totalSteps) { step ->
                            delay(100)
                            progresso = ((step + 1) * 100) / totalSteps
                            progressBarContador.progress = progresso
                            
                            // Atualizar contador de segundos
                            val segundosRestantes = 2 - ((step + 1) / 10)
                            if (segundosRestantes != segundos && segundosRestantes > 0) {
                                segundos = segundosRestantes
                                textContador.text = segundos.toString()
                            }
                        }
                        // Completou 2 segundos - acionar!
                        textContador.visibility = View.GONE
                        progressBarContador.visibility = View.GONE
                        progressBarContador.progress = 0
                        acionarPanico()
                    }
                    true
                }
                android.view.MotionEvent.ACTION_UP,
                android.view.MotionEvent.ACTION_CANCEL -> {
                    // Cancelar contador se soltar antes de 2 segundos
                    contadorJob?.cancel()
                    textContador.visibility = View.GONE
                    progressBarContador.visibility = View.GONE
                    progressBarContador.progress = 0
                    true
                }
                else -> false
            }
        }
    }

    private fun acionarPanico() {
        val prefs = getSharedPreferences("panic_prefs", MODE_PRIVATE)
        val btnPanicoBig = findViewById<Button>(R.id.btnPanicoBig)
        val textFeedback = findViewById<TextView>(R.id.textFeedback)
        val token = prefs.getString("token", "").orEmpty().trim()
        val base = BuildConfig.API_BASE_URL
        if (token.isEmpty() || base.isBlank()) {
            // Caso raro: dados ausentes, volta para confirmação
            val layoutConfirmacao = findViewById<LinearLayout>(R.id.layoutConfirmacao)
            val layoutPanico = findViewById<LinearLayout>(R.id.layoutPanico)
            layoutConfirmacao.visibility = View.VISIBLE
            layoutPanico.visibility = View.GONE
            textFeedback.text = "Informe o token primeiro."
            textFeedback.setTextColor(0xFFB91C1C.toInt())
            return
        }
        val url = buildDispatchUrl(base)
        textFeedback.text = "Enviando..."
        textFeedback.setTextColor(0xFF888888.toInt())
        btnPanicoBig.isEnabled = false
        lifecycleScope.launch {
            try {
                val loc = obterLocalizacaoSegura()
                val (msg, color, id) = enviarPanico(url, token, loc)
                textFeedback.text = msg
                textFeedback.setTextColor(color)
                if (id != null) {
                    PanicLocationService.start(this@MainActivity, id, token, url)
                }
            } finally {
                btnPanicoBig.isEnabled = true
            }
        }
    }

    override fun onResume() {
        super.onResume()
        val bannerStatus = findViewById<TextView>(R.id.textStatusPanico)
        atualizarBannerStatus(bannerStatus)
        // Obtém e envia token FCM automaticamente ao abrir o app
        obterEEnviarTokenFCM()
        // Registrar BroadcastReceiver para atualizar banner quando receber push
        statusUpdateReceiver = object : BroadcastReceiver() {
            override fun onReceive(context: Context?, intent: Intent?) {
                atualizarBannerStatus(bannerStatus)
            }
        }
        val filter = IntentFilter("com.seuprojeto.panico.STATUS_UPDATED")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(statusUpdateReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(statusUpdateReceiver, filter)
        }
    }

    override fun onPause() {
        super.onPause()
        // Desregistrar BroadcastReceiver
        statusUpdateReceiver?.let {
            unregisterReceiver(it)
            statusUpdateReceiver = null
        }
    }

    private fun obterEEnviarTokenFCM() {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val prefs = getSharedPreferences("panic_prefs", MODE_PRIVATE)
                val baseUrl = prefs.getString("base_url", "") ?: ""
                if (baseUrl.isBlank()) return@launch
                // Obter token FCM
                com.google.firebase.messaging.FirebaseMessaging.getInstance().token.addOnSuccessListener { token ->
                    if (token.isNullOrBlank()) return@addOnSuccessListener
                    // Salvar local
                    prefs.edit().putString("fcm_token", token).apply()
                    // Enviar para backend
                    lifecycleScope.launch(Dispatchers.IO) {
                        try {
                            val url = URL("$baseUrl/common/push/register-device/")
                            val conn = url.openConnection() as HttpURLConnection
                            conn.requestMethod = "POST"
                            conn.setRequestProperty("Content-Type", "application/json")
                            conn.doOutput = true
                            val payload = JSONObject().apply {
                                put("token", token)
                                put("platform", "android")
                                put("device_info", "SafeBP")
                                put("app_id", "safebp")
                                try {
                                    val pm = packageManager
                                    val pkg = packageName
                                    val versionName = if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
                                        pm.getPackageInfo(pkg, android.content.pm.PackageManager.PackageInfoFlags.of(0)).versionName ?: "unknown"
                                    } else {
                                        @Suppress("DEPRECATION")
                                        pm.getPackageInfo(pkg, 0).versionName ?: "unknown"
                                    }
                                    put("app_version", versionName)
                                } catch (e: Exception) {
                                    put("app_version", "unknown")
                                }
                            }
                            conn.outputStream.use { it.write(payload.toString().toByteArray()) }
                            val code = conn.responseCode
                            android.util.Log.d("MainActivity", "Token FCM enviado: $code")
                        } catch (e: Exception) {
                            android.util.Log.e("MainActivity", "Erro ao enviar token FCM: ${e.message}")
                        }
                    }
                }
            } catch (e: Exception) {
                android.util.Log.e("MainActivity", "Erro ao obter token FCM: ${e.message}")
            }
        }
    }

    private fun atualizarBannerStatus(tv: TextView?) {
        tv ?: return
        val data = PanicoPrefs.readStatus(this)
        val status = (data["status"] as? String)?.uppercase()?.trim().orEmpty()
        val motivo = (data["motivo"] as? String).orEmpty()
        if (status.isBlank()) {
            tv.visibility = View.GONE; return
        }
        val (texto, cor) = when(status){
            "ENCERRADA" -> Pair("🚨 Equipes à caminho!" + if(motivo.isNotBlank()) " $motivo" else "", 0xFF065F46.toInt())
            "CANCELADA" -> Pair("Pânico recusado: ${motivo.ifBlank { "sem motivo informado" }}", 0xFFB91C1C.toInt())
            "TESTE" -> Pair("Disparo registrado como TESTE" + if(motivo.isNotBlank()) ": $motivo" else "", 0xFF1D4ED8.toInt())
            else -> Pair("Status: $status" + if(motivo.isNotBlank()) " ($motivo)" else "", 0xFF444444.toInt())
        }
        tv.text = texto
        tv.setTextColor(cor)
        tv.visibility = View.VISIBLE
    }

    data class Localizacao(val lat: Double?, val lon: Double?, val acc: Float?)

    private suspend fun obterLocalizacaoSegura(): Localizacao {
        val fineOk = ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        val coarseOk = ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
        if (!fineOk && !coarseOk) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION), 1001)
            return Localizacao(null, null, null)
        }
        val client = LocationServices.getFusedLocationProviderClient(this)
        return try {
            val loc = suspendCancellableCoroutine<android.location.Location?> { cont ->
                client.getCurrentLocation(Priority.PRIORITY_HIGH_ACCURACY, null)
                    .addOnSuccessListener { l -> cont.resume(l) }
                    .addOnFailureListener { _ -> cont.resume(null) }
            }
            if (loc != null) Localizacao(loc.latitude, loc.longitude, loc.accuracy) else Localizacao(null, null, null)
        } catch (e: Exception) {
            Localizacao(null, null, null)
        }
    }

    private suspend fun enviarPanico(url: String, token: String, loc: Localizacao): Triple<String, Int, Int?> {
        return withContext(Dispatchers.IO) {
            try {
                val obj = JSONObject()
                obj.put("token", token)
                if (loc.lat != null && loc.lon != null) {
                    obj.put("latitude", loc.lat)
                    obj.put("longitude", loc.lon)
                }
                if (loc.acc != null) {
                    obj.put("precisao", loc.acc.toInt())
                }
                val conn = URL(url).openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.setRequestProperty("Content-Type", "application/json")
                conn.setRequestProperty("Accept", "application/json")
                conn.connectTimeout = 10000
                conn.readTimeout = 10000
                conn.doOutput = true
                conn.outputStream.use { it.write(obj.toString().toByteArray()) }
                val code = conn.responseCode
                val stream = if (code in 200..299) conn.inputStream else (conn.errorStream ?: conn.inputStream)
                val response = stream?.bufferedReader()?.readText().orEmpty()
                if (code in 200..299) {
                    val rid = try { JSONObject(response).optInt("id", -1).takeIf { it > 0 } } catch (_:Exception){ null }
                    Triple("Pânico acionado com sucesso!", 0xFF15803D.toInt(), rid)
                } else {
                    val msg = JSONObject(response).optString("detail", "Falha ao acionar pânico.")
                    Triple(msg, 0xFFB91C1C.toInt(), null)
                }
            } catch (e: Exception) {
                android.util.Log.e("MainActivity", "Falha ao enviar pânico para $url: ${e.message}", e)
                Triple("Erro de conexão. Tente novamente.", 0xFFB91C1C.toInt(), null)
            }
        }
    }

    private fun verificarPermissoesObrigatorias() {
        val permissoesNecessarias = mutableListOf<String>()
        
        // Verificar permissão de localização
        val fineOk = ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
        val coarseOk = ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
        
        if (!fineOk) permissoesNecessarias.add(Manifest.permission.ACCESS_FINE_LOCATION)
        if (!coarseOk) permissoesNecessarias.add(Manifest.permission.ACCESS_COARSE_LOCATION)
        
        // Verificar permissão de notificação (Android 13+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val notificationOk = ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
            if (!notificationOk) permissoesNecessarias.add(Manifest.permission.POST_NOTIFICATIONS)
        }
        
        // Solicitar permissões se necessário
        if (permissoesNecessarias.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, permissoesNecessarias.toTypedArray(), PERMISSION_REQUEST_CODE)
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        
        when (requestCode) {
            PERMISSION_REQUEST_CODE -> {
                val todasConcedidas = grantResults.all { it == PackageManager.PERMISSION_GRANTED }
                
                if (!todasConcedidas) {
                    // Mostrar diálogo explicando que as permissões são obrigatórias
                    androidx.appcompat.app.AlertDialog.Builder(this)
                        .setTitle("Permissões Obrigatórias")
                        .setMessage("Este aplicativo precisa de acesso à localização e notificações para funcionar corretamente.\n\n• Localização: Para enviar sua posição em caso de emergência\n• Notificações: Para receber confirmações e atualizações do pânico")
                        .setPositiveButton("Conceder") { _, _ ->
                            verificarPermissoesObrigatorias()
                        }
                        .setNegativeButton("Sair") { _, _ ->
                            finish()
                        }
                        .setCancelable(false)
                        .show()
                }
            }
        }
    }
}
