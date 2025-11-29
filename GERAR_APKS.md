# 📱 Guia Completo: Gerar APKs dos Apps Android

**Data:** 28/11/2025  
**Backend produção:** https://gcmsysint.online

---

## ✅ Alterações já feitas

- ✅ `mobile/capacitor.config.ts` → URL: `https://gcmsysint.online`
- ✅ `panic_app_android/.../MainActivity.kt` → Adicionado "GCM Sistema (Produção)"

---

## 📋 Pré-requisitos

### 1. Instalar Java JDK 17

- Download: https://www.oracle.com/java/technologies/javase/jdk17-archive-downloads.html
- Ou via Chocolatey (PowerShell admin):
  ```powershell
  choco install openjdk17
  ```
- Verificar instalação:
  ```powershell
  java -version
  ```

### 2. Instalar Android Studio

- Download: https://developer.android.com/studio
- Durante instalação, marcar:
  - ✅ Android SDK
  - ✅ Android SDK Platform
  - ✅ Android Virtual Device

### 3. Configurar variáveis de ambiente

Adicionar no Windows (Painel de Controle → Sistema → Variáveis de ambiente):

```
ANDROID_HOME=C:\Users\SEU_USUARIO\AppData\Local\Android\Sdk
JAVA_HOME=C:\Program Files\Java\jdk-17
```

Adicionar ao PATH:
```
%ANDROID_HOME%\platform-tools
%ANDROID_HOME%\tools
%JAVA_HOME%\bin
```

---

## 🔐 PASSO 1: Criar Keystores (Chaves de Assinatura)

### Para panic_app_android (Play Store)

```powershell
cd C:\GCM_Sistema\panic_app_android

# Criar keystore de release
keytool -genkey -v -keystore panic-release-key.keystore -alias panic-key -keyalg RSA -keysize 2048 -validity 10000

# Preencha quando pedir:
# - Senha do keystore (GUARDE MUITO BEM!)
# - Nome completo: GCM Sistema
# - Unidade organizacional: Guarda Civil Municipal
# - Organização: Prefeitura
# - Cidade/Estado/País: preencher
```

⚠️ **IMPORTANTE:** Guarde `panic-release-key.keystore` e a senha em local seguro! Sem ela não consegue atualizar app na Play Store.

### Para mobile (uso interno)

```powershell
cd C:\GCM_Sistema\mobile\android

# Criar keystore de release
keytool -genkey -v -keystore mobile-release-key.keystore -alias mobile-key -keyalg RSA -keysize 2048 -validity 10000
```

---

## 🏗️ PASSO 2: Build do panic_app_android (Play Store)

### 2.1. Configurar signing no Gradle

Criar arquivo `C:\GCM_Sistema\panic_app_android\keystore.properties`:

```properties
storePassword=SUA_SENHA_AQUI
keyPassword=SUA_SENHA_AQUI
keyAlias=panic-key
storeFile=../panic-release-key.keystore
```

### 2.2. Editar build.gradle do app

Abrir `panic_app_android/app/build.gradle` e adicionar antes de `android {`:

```gradle
def keystorePropertiesFile = rootProject.file("keystore.properties")
def keystoreProperties = new Properties()
if (keystorePropertiesFile.exists()) {
    keystoreProperties.load(new FileInputStream(keystorePropertiesFile))
}
```

Dentro de `android {`, adicionar:

```gradle
signingConfigs {
    release {
        keyAlias keystoreProperties['keyAlias']
        keyPassword keystoreProperties['keyPassword']
        storeFile file(keystoreProperties['storeFile'])
        storePassword keystoreProperties['storePassword']
    }
}

buildTypes {
    release {
        signingConfig signingConfigs.release
        minifyEnabled false
        proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
    }
}
```

### 2.3. Gerar AAB (Android App Bundle) para Play Store

```powershell
cd C:\GCM_Sistema\panic_app_android

# Limpar build anterior
.\gradlew clean

# Gerar AAB assinado
.\gradlew bundleRelease
```

**Arquivo gerado:**  
`panic_app_android/app/build/outputs/bundle/release/app-release.aab`

### 2.4. (Opcional) Gerar APK também

```powershell
.\gradlew assembleRelease
```

**Arquivo gerado:**  
`panic_app_android/app/build/outputs/apk/release/app-release.apk`

---

## 📱 PASSO 3: Build do mobile (Ionic/Capacitor)

### 3.1. Instalar Node.js (se não tiver)

- Download: https://nodejs.org/ (versão LTS)

### 3.2. Instalar dependências

```powershell
cd C:\GCM_Sistema\mobile

# Instalar pacotes Node.js
npm install

# Atualizar Capacitor
npx cap sync android
```

### 3.3. Configurar signing

Criar `mobile/android/keystore.properties`:

```properties
storePassword=SUA_SENHA_AQUI
keyPassword=SUA_SENHA_AQUI
keyAlias=mobile-key
storeFile=../../mobile-release-key.keystore
```

Editar `mobile/android/app/build.gradle` (mesmo processo do passo 2.2, ajustando caminhos).

### 3.4. Build web assets

```powershell
cd C:\GCM_Sistema\mobile

# Gerar build otimizado do front-end
npm run build
# ou se usar outro comando: npm run prod

# Copiar para Android
npx cap copy android
npx cap sync android
```

### 3.5. Gerar APK assinado

```powershell
cd C:\GCM_Sistema\mobile\android

# Limpar
.\gradlew clean

# Gerar APK release
.\gradlew assembleRelease
```

**Arquivo gerado:**  
`mobile/android/app/build/outputs/apk/release/app-release.apk`

---

## 🚀 PASSO 4: Publicar panic_app_android no Play Store

### 4.1. Criar conta Google Play Console

1. Acesse: https://play.google.com/console/signup
2. Pague taxa única de US$ 25
3. Preencha dados da conta de desenvolvedor

### 4.2. Criar novo app

1. "Criar app" → Preencher:
   - Nome: **Pânico GCM**
   - Idioma padrão: Português (Brasil)
   - Tipo: App
   - Categoria: Produtividade
2. Upload do AAB em "Produção" → "Criar nova versão"
3. Preencher:
   - Título (até 50 caracteres)
   - Descrição curta (até 80 caracteres)
   - Descrição completa (até 4000 caracteres)
   - Capturas de tela (mínimo 2)
   - Ícone 512x512 px
   - Imagem de recurso 1024x500 px
4. Questionário de conteúdo
5. Enviar para análise (pode levar 1-7 dias)

---

## 📦 PASSO 5: Distribuir mobile (APK interno)

### Opção A: Firebase App Distribution (Recomendado)

1. Criar projeto no Firebase: https://console.firebase.google.com
2. Adicionar app Android (package: `br.gov.gcm.sistema`)
3. Baixar `google-services.json` → `mobile/android/app/`
4. Instalar Firebase CLI:
   ```powershell
   npm install -g firebase-tools
   firebase login
   ```
5. Upload do APK:
   ```powershell
   firebase appdistribution:distribute mobile/android/app/build/outputs/apk/release/app-release.apk \
     --app SEU_APP_ID \
     --groups testers
   ```

### Opção B: Hospedar direto no servidor

```powershell
# Copiar APK para servidor
scp mobile/android/app/build/outputs/apk/release/app-release.apk ec2-user@18.229.134.75:/home/ec2-user/gcm_sistema/media/downloads/

# No servidor, criar link público
# Acesso: https://gcmsysint.online/media/downloads/app-release.apk
```

---

## ✅ Checklist Final

### panic_app_android (Play Store)
- [ ] Keystore criado e guardado em local seguro
- [ ] AAB gerado (`app-release.aab`)
- [ ] Conta Play Console criada e paga
- [ ] App criado no Play Console
- [ ] Metadados preenchidos (descrição, screenshots)
- [ ] AAB enviado para análise

### mobile (interno)
- [ ] Keystore criado
- [ ] APK gerado (`app-release.apk`)
- [ ] APK distribuído (Firebase ou servidor)
- [ ] Link de download compartilhado com equipe

---

## 🔧 Troubleshooting

### Erro: "SDK location not found"

Criar `local.properties` em `panic_app_android/` e `mobile/android/`:
```properties
sdk.dir=C:\\Users\\SEU_USUARIO\\AppData\\Local\\Android\\Sdk
```

### Erro: "JAVA_HOME not set"

PowerShell (admin):
```powershell
[Environment]::SetEnvironmentVariable("JAVA_HOME", "C:\Program Files\Java\jdk-17", "Machine")
```

### Erro de assinatura

Verificar se `keystore.properties` está correto:
```powershell
Get-Content panic_app_android/keystore.properties
```

---

## 📞 Próximos passos recomendados

1. **Testar APKs em dispositivos reais** antes de publicar
2. **Configurar versionamento** (`versionCode` e `versionName` no `build.gradle`)
3. **Configurar Firebase Cloud Messaging** para notificações push
4. **Criar ícones adaptativos** para Android 8+
5. **Configurar ProGuard/R8** para ofuscar código (segurança)

---

**Dúvidas?** Consulte:
- Documentação Android: https://developer.android.com/studio/publish
- Capacitor Docs: https://capacitorjs.com/docs/android
- Play Console Help: https://support.google.com/googleplay/android-developer

