# Fix: Botão "Baixar Formulário (HTML)" no Aplicativo Android

## Problema Identificado

O botão **"Baixar Formulário (HTML)"** funciona perfeitamente no Chrome do celular, mas **não funciona no aplicativo Android**.

### Causa Raiz

O código JavaScript usa `fetch()` para converter imagens em base64 antes de gerar o HTML offline. No **WebView do Android**, o `fetch()` falhava por falta de configurações adequadas no WebView.

## Solução Aplicada

### 1. Configurações do WebView (`MainActivity.java`)

Adicionadas as seguintes configurações para permitir `fetch()` e downloads:

```java
webView.getSettings().setAllowFileAccess(true);
webView.getSettings().setAllowContentAccess(true);
webView.getSettings().setAllowFileAccessFromFileURLs(false); // Segurança
webView.getSettings().setAllowUniversalAccessFromFileURLs(false); // Segurança
webView.getSettings().setDomStorageEnabled(true);
webView.getSettings().setDatabaseEnabled(true);
webView.getSettings().setJavaScriptCanOpenWindowsAutomatically(true);
```

### 2. Download Listener

Implementado um `DownloadListener` para interceptar downloads gerados via JavaScript (blobs):

```java
webView.setDownloadListener(new DownloadListener() {
    @Override
    public void onDownloadStart(String url, String userAgent, String contentDisposition, String mimetype, long contentLength) {
        try {
            DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url));
            request.setMimeType(mimetype);
            
            String filename = URLUtil.guessFileName(url, contentDisposition, mimetype);
            request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, filename);
            request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            request.setTitle(filename);
            
            DownloadManager dm = (DownloadManager) getSystemService(DOWNLOAD_SERVICE);
            if (dm != null) {
                dm.enqueue(request);
                Toast.makeText(getApplicationContext(), "Baixando: " + filename, Toast.LENGTH_SHORT).show();
            }
        } catch (Exception e) {
            Log.e("MainActivity", "Erro no download: " + e.getMessage(), e);
            Toast.makeText(getApplicationContext(), "Erro ao baixar arquivo", Toast.LENGTH_SHORT).show();
        }
    }
});
```

### 3. Permissões no AndroidManifest.xml

Adicionadas permissões de armazenamento:

```xml
<!-- Permissão para download de arquivos -->
<uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" 
                 android:maxSdkVersion="28" />
<uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" 
                 android:maxSdkVersion="32" />
```

**Nota**: As permissões têm `maxSdkVersion` porque a partir do Android 10 (API 29) o sistema usa **Scoped Storage**, que não requer essas permissões para a pasta Downloads.

## Arquivos Modificados

1. ✅ `mobile/android/app/src/main/java/br/gov/gcm/sistema/MainActivity.java`
   - Configurações do WebView
   - Download Listener
   - Imports adicionados

2. ✅ `mobile/android/app/src/main/AndroidManifest.xml`
   - Permissões de armazenamento

## Como Testar

### 1. Recompilar o APK

```powershell
cd C:\GCM_Sistema\mobile
ionic capacitor sync android
cd android
.\gradlew assembleDebug
```

### 2. Instalar no Celular

O APK estará em:
```
C:\GCM_Sistema\mobile\android\app\build\outputs\apk\debug\app-debug.apk
```

### 3. Testar Funcionalidade

1. Abrir o app
2. Navegar para qualquer BO
3. Ir em **"Veículos Envolvidos"**
4. Clicar em **"Baixar Formulário Offline"**
5. Na tela do formulário, preencher alguns dados
6. Clicar no botão **"Baixar Formulário (HTML)"**

**Resultado Esperado:**
- ✅ Aparece notificação "Baixando: formulario_veiculo_offline_boXXX.html"
- ✅ Arquivo é salvo na pasta **Downloads**
- ✅ Arquivo pode ser aberto offline e funciona completamente

## Compatibilidade

- ✅ **Android 6.0+** (API 23+): Funciona com permissões de runtime
- ✅ **Android 10+** (API 29+): Usa Scoped Storage automaticamente
- ✅ **Android 13+** (API 33+): Não requer permissões extras (Scoped Storage)

## Observações Técnicas

### Por que funciona no Chrome mas não no app?

**Chrome do Android:**
- Tem permissões nativas de download
- Gerencia automaticamente conversão de Blob URLs
- Suporta `fetch()` sem restrições de CORS para mesmo domínio

**WebView do App (antes da correção):**
- Precisa de configurações explícitas para `fetch()`
- Requer DownloadListener para interceptar downloads
- Depende de permissões de armazenamento declaradas

### Segurança

As configurações mantêm a segurança:
- `setAllowFileAccessFromFileURLs(false)`: Previne acesso cross-origin a arquivos locais
- `setAllowUniversalAccessFromFileURLs(false)`: Previne acesso universal de file:// URLs
- Permissões de armazenamento com `maxSdkVersion` para seguir as melhores práticas do Android

## Próximos Passos

1. ✅ Código corrigido
2. ⏳ Gerar novo APK
3. ⏳ Testar no dispositivo físico
4. ⏳ Publicar versão atualizada

---

**Data da Correção:** 07/12/2025
**Versão do App:** Próxima release (pós-correção)
