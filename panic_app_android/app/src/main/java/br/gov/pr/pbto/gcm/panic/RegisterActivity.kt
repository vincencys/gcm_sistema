package br.gov.pr.pbto.gcm.panic

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.text.Editable
import android.text.TextWatcher
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.*
import java.net.HttpURLConnection
import java.net.URL
import com.seuprojeto.panico.R

class RegisterActivity : AppCompatActivity() {

    private lateinit var etNome: EditText
    private lateinit var etCpf: EditText
    private lateinit var etTelefone: EditText
    private lateinit var etProcesso: EditText
    private lateinit var etRua: EditText
    private lateinit var etNumero: EditText
    private lateinit var etBairro: EditText
    private lateinit var etReferencia: EditText
    private lateinit var btnSelectFile: Button
    private lateinit var tvFileName: TextView
    private lateinit var btnSubmit: Button

    private var selectedFileUri: Uri? = null
    private var selectedFileName: String = ""

    private val PICK_FILE_REQUEST = 1001
    private val STORAGE_PERMISSION_CODE = 1002

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_register)

        // Inicializar views
        etNome = findViewById(R.id.etNome)
        etCpf = findViewById(R.id.etCpf)
        etTelefone = findViewById(R.id.etTelefone)
        etProcesso = findViewById(R.id.etProcesso)
        etRua = findViewById(R.id.etRua)
        etNumero = findViewById(R.id.etNumero)
        etBairro = findViewById(R.id.etBairro)
        etReferencia = findViewById(R.id.etReferencia)
        btnSelectFile = findViewById(R.id.btnSelectFile)
        tvFileName = findViewById(R.id.tvFileName)
        btnSubmit = findViewById(R.id.btnSubmit)
        
    // Aplicar máscaras dinâmicas (CPF, Telefone, Processo CNJ)
    etCpf.addTextChangedListener(CpfMask())
    etTelefone.addTextChangedListener(TelefoneMask())
    etProcesso.addTextChangedListener(ProcessoMask())

        btnSelectFile.setOnClickListener {
            if (checkStoragePermission()) {
                openFilePicker()
            } else {
                requestStoragePermission()
            }
        }

        btnSubmit.setOnClickListener {
            validarESolicitar()
        }
    }

    // Máscara para CPF (###.###.###-##)
    private inner class CpfMask : TextWatcher {
        private var isUpdating = false
        override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
        override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
        override fun afterTextChanged(s: Editable?) {
            if (isUpdating) return
            val raw = s?.toString() ?: return
            val digits = raw.filter { it.isDigit() }.take(11)
            val builder = StringBuilder()

            for (i in digits.indices) {
                if (i == 3 || i == 6) builder.append('.')
                if (i == 9) builder.append('-')
                builder.append(digits[i])
            }

            val formatted = builder.toString()
            if (formatted != raw) {
                isUpdating = true
                // Evita setSpan IndexOutOfBounds removendo o watcher antes
                etCpf.removeTextChangedListener(this)
                etCpf.setText(formatted)
                try {
                    etCpf.setSelection(formatted.length)
                } catch (_: Exception) { /* no-op */ }
                etCpf.addTextChangedListener(this)
                isUpdating = false
            }
        }
    }

    // Máscara para Telefone brasileiro (formato dinâmico com 10 ou 11 dígitos)
    private inner class TelefoneMask : TextWatcher {
        private var isUpdating = false
        override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
        override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
        override fun afterTextChanged(s: Editable?) {
            if (isUpdating) return
            isUpdating = true
            val digits = s.toString().replace(Regex("[^\\d]"), "")
            val formatted = when {
                digits.length > 10 -> "(${digits.substring(0,2)}) ${digits.substring(2,7)}-${digits.substring(7, minOf(11, digits.length))}"
                digits.length > 6 -> "(${digits.substring(0,2)}) ${digits.substring(2,6)}-${digits.substring(6)}"
                digits.length > 2 -> "(${digits.substring(0,2)}) ${digits.substring(2)}"
                else -> digits
            }
            s?.replace(0, s.length, formatted)
            isUpdating = false
        }
    }

    // Máscara para Número de Processo CNJ (#######-##.####.#.##.####)
    private inner class ProcessoMask : TextWatcher {
        private var isUpdating = false
        private val maxDigits = 20
        override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
        override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
        override fun afterTextChanged(s: Editable?) {
            if (isUpdating) return
            val raw = s?.toString() ?: return
            val digits = raw.filter { it.isDigit() }.take(maxDigits)
            val builder = StringBuilder()

            for (i in digits.indices) {
                // Inserir separadores nos pontos corretos
                if (i == 7) builder.append('-')      // depois de 7 dígitos
                if (i == 9) builder.append('.')      // depois de 2 dígitos (DD)
                if (i == 13) builder.append('.')     // depois de 4 dígitos (AAAA)
                if (i == 14) builder.append('.')     // depois de 1 dígito (J)
                if (i == 16) builder.append('.')     // depois de 2 dígitos (TR)
                builder.append(digits[i])
            }

            val formatted = builder.toString()
            if (formatted != raw) {
                isUpdating = true
                etProcesso.removeTextChangedListener(this)
                etProcesso.setText(formatted)
                try {
                    etProcesso.setSelection(formatted.length)
                } catch (_: Exception) { /* no-op */ }
                etProcesso.addTextChangedListener(this)
                isUpdating = false
            }
        }
    }

    private fun checkStoragePermission(): Boolean {
        return if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
            // Android 13+ não precisa de READ_EXTERNAL_STORAGE para file picker
            true
        } else {
            ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.READ_EXTERNAL_STORAGE
            ) == PackageManager.PERMISSION_GRANTED
        }
    }

    private fun requestStoragePermission() {
        if (android.os.Build.VERSION.SDK_INT < android.os.Build.VERSION_CODES.TIRAMISU) {
            ActivityCompat.requestPermissions(
                this,
                arrayOf(Manifest.permission.READ_EXTERNAL_STORAGE),
                STORAGE_PERMISSION_CODE
            )
        }
    }

    private fun openFilePicker() {
        val intent = Intent(Intent.ACTION_GET_CONTENT).apply {
            type = "*/*" // Aceita qualquer tipo de arquivo
            addCategory(Intent.CATEGORY_OPENABLE)
            putExtra(Intent.EXTRA_MIME_TYPES, arrayOf(
                "application/pdf",
                "image/*",
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ))
        }
        startActivityForResult(intent, PICK_FILE_REQUEST)
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == PICK_FILE_REQUEST && resultCode == Activity.RESULT_OK) {
            data?.data?.let { uri ->
                selectedFileUri = uri
                selectedFileName = getFileName(uri)
                tvFileName.text = "Arquivo: $selectedFileName"
            }
        }
    }

    private fun getFileName(uri: Uri): String {
        var result = "documento"
        contentResolver.query(uri, null, null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) {
                val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (nameIndex >= 0) {
                    result = cursor.getString(nameIndex)
                }
            }
        }
        return result
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == STORAGE_PERMISSION_CODE) {
            if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                openFilePicker()
            } else {
                Toast.makeText(this, "Permissão negada para acessar arquivos", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun validarESolicitar() {
        val nome = etNome.text.toString().trim()
        val cpf = etCpf.text.toString().replace(Regex("[^\\d]"), "")
        val telefone = etTelefone.text.toString().replace(Regex("[^\\d]"), "")
        val processo = etProcesso.text.toString().replace(Regex("[^\\d]"), "")
        val rua = etRua.text.toString().trim()
        val numero = etNumero.text.toString().trim()
        val bairro = etBairro.text.toString().trim()
        val referencia = etReferencia.text.toString().trim()

        // Validação de campos obrigatórios
        if (nome.isEmpty()) {
            etNome.error = "Nome é obrigatório"
            etNome.requestFocus()
            return
        }
        if (cpf.length != 11) {
            etCpf.error = "CPF inválido (deve ter 11 dígitos)"
            etCpf.requestFocus()
            return
        }
        if (telefone.length < 10) {
            etTelefone.error = "Telefone inválido"
            etTelefone.requestFocus()
            return
        }
        if (processo.length != 20) {
            etProcesso.error = "Processo inválido (deve ter 20 dígitos)"
            etProcesso.requestFocus()
            return
        }
        if (rua.isEmpty()) {
            etRua.error = "Rua é obrigatória"
            etRua.requestFocus()
            return
        }
        if (numero.isEmpty()) {
            etNumero.error = "Número é obrigatório"
            etNumero.requestFocus()
            return
        }
        if (bairro.isEmpty()) {
            etBairro.error = "Bairro é obrigatório"
            etBairro.requestFocus()
            return
        }
        if (selectedFileUri == null) {
            Toast.makeText(this, "Selecione o documento da medida protetiva", Toast.LENGTH_LONG).show()
            return
        }

        // Montar endereço completo
        val endereco = if (referencia.isNotEmpty()) {
            "$rua | $numero | $bairro | $referencia"
        } else {
            "$rua | $numero | $bairro"
        }

        // Desabilitar botão durante o envio
        btnSubmit.isEnabled = false
        btnSubmit.text = "Enviando..."

        // Enviar solicitação
        enviarSolicitacao(nome, cpf, telefone, processo, endereco, selectedFileUri!!)
    }

    private fun enviarSolicitacao(
        nome: String,
        cpf: String,
        telefone: String,
        processo: String,
        endereco: String,
        fileUri: Uri
    ) {
        CoroutineScope(Dispatchers.IO).launch {
            try {
                // Usa BASE_URL enviada pela MainActivity ou SharedPreferences como fallback
                val baseUrl = intent.getStringExtra("BASE_URL")
                    ?: getSharedPreferences("panic_prefs", MODE_PRIVATE).getString("base", "")
                    ?: ""
                val cidade = intent.getStringExtra("CIDADE") ?: getSharedPreferences("panic_prefs", MODE_PRIVATE).getString("cidade", "") ?: ""

                if (baseUrl.isBlank()) {
                    withContext(Dispatchers.Main) {
                        Toast.makeText(this@RegisterActivity, "Base URL ausente. Abra novamente a tela principal.", Toast.LENGTH_LONG).show()
                        btnSubmit.isEnabled = true
                        btnSubmit.text = "Solicitar Cadastro"
                    }
                    return@launch
                }

                val url = URL(baseUrl.trimEnd('/') + "/panic/public/assistida/solicitar/")

                val boundary = "===${System.currentTimeMillis()}==="
                
                val connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
                connection.connectTimeout = 30000
                connection.readTimeout = 30000

                val out = connection.outputStream
                val writer = out.bufferedWriter(Charsets.UTF_8)

                fun writeField(name: String, value: String) {
                    writer.write("--$boundary\r\n")
                    writer.write("Content-Disposition: form-data; name=\"$name\"\r\n\r\n")
                    writer.write("$value\r\n")
                }

                android.util.Log.d("RegisterActivity", "Enviando multipart para: $url")
                writeField("nome", nome)
                writeField("cpf", cpf)
                writeField("telefone", telefone)
                writeField("processo_mp", processo)
                writeField("endereco", endereco)
                writer.flush()

                // Arquivo obrigatório
                writer.write("--$boundary\r\n")
                writer.write("Content-Disposition: form-data; name=\"documento_mp\"; filename=\"$selectedFileName\"\r\n")
                writer.write("Content-Type: application/octet-stream\r\n\r\n")
                writer.flush()
                
                contentResolver.openInputStream(fileUri)?.use { inputStream ->
                    inputStream.copyTo(out)
                }
                
                writer.write("\r\n--$boundary--\r\n")
                writer.flush()
                writer.close()

                val responseCode = connection.responseCode
                val responseMessage = if (responseCode in 200..299) {
                    connection.inputStream.bufferedReader().readText()
                } else {
                    connection.errorStream?.bufferedReader()?.readText() ?: "Erro desconhecido"
                }
                connection.disconnect()

                android.util.Log.d("RegisterActivity", "Resposta: code=$responseCode, msg=$responseMessage")

                withContext(Dispatchers.Main) {
                    if (responseCode in 200..299) {
                        Toast.makeText(this@RegisterActivity, "Solicitação enviada! Aguarde aprovação.", Toast.LENGTH_LONG).show()
                        finish()
                    } else {
                        val errorMsg = try {
                            org.json.JSONObject(responseMessage).optString("detail", responseMessage)
                        } catch (_: Exception) { responseMessage }
                        Toast.makeText(this@RegisterActivity, "Erro ($responseCode): ${errorMsg.take(150)}", Toast.LENGTH_LONG).show()
                        btnSubmit.isEnabled = true
                        btnSubmit.text = "Solicitar Cadastro"
                    }
                }

            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@RegisterActivity, "Falha de rede: ${e.message}", Toast.LENGTH_LONG).show()
                    btnSubmit.isEnabled = true
                    btnSubmit.text = "Solicitar Cadastro"
                }
            }
        }
    }

    // Mantido para compatibilidade; agora usamos BASE_URL direto.
    private fun obterUrlBase(cidade: String): String = intent.getStringExtra("BASE_URL") ?: ""
}
