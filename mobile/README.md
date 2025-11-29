# App móvel (Capacitor) – Sistema GCM

Este diretório contém o esqueleto do projeto Capacitor para empacotar o site em um APK Android.

Sumário rápido:
- O app carrega a URL pública HTTPS do seu Django.
- Notificações push: @capacitor/push-notifications + Firebase Cloud Messaging (FCM).

## Como gerar um APK (passo a passo)

1) Pré-requisitos
- Windows com PowerShell, Node.js 18+, Java 17+, Android Studio (SDKs Android instalados)
- Dispositivo Android com depuração USB ativada (ou emulador)
- Opcional: Projeto no Firebase com FCM habilitado (para Push)

2) Instalar dependências

```powershell
# dentro da pasta mobile\
npm init -y
npm install @capacitor/core @capacitor/cli @capacitor/android @capacitor/push-notifications
```

3) Arquivos importantes deste esqueleto
- `capacitor.config.ts`: aponta para a URL do seu site.
- `web/index.html`: página mínima só para debug (não será usada em produção com server.url).

4) Adicionar Android e abrir no Android Studio (se ainda não existir)

```powershell
# ainda na pasta mobile\
npx cap add android
npx cap open android
```

5) Firebase
- Coloque `google-services.json` em `android/app/google-services.json`.
- No `android/app/build.gradle`, aplique o plugin `com.google.gms.google-services`.
- Certifique-se de ter o BOM do Firebase nas dependências do módulo app.

5) Gerar APK Debug rapidamente (linha de comando)

Dentro da pasta `mobile\android` você já tem o projeto Gradle. Para gerar um APK debug:

```powershell
# dentro de c:\GCM_Sistema\mobile\android
./gradlew.bat assembleDebug
```

O APK será gerado em:

- `mobile\android\app\build\outputs\apk\debug\app-debug.apk`

Para instalar no seu celular via USB:

```powershell
# verifique se o ADB está disponível no PATH (SDK Platform-Tools)
adb devices
adb install -r .\app\build\outputs\apk\debug\app-debug.apk
```

6) Gerar APK Release assinado (linha de comando)

6.1) Criar um keystore (apenas uma vez):

```powershell
# escolha um caminho seguro para o keystore
keytool -genkeypair -v -keystore C:\caminho\meu-release.keystore -alias gcmapp -keyalg RSA -keysize 2048 -validity 3650
```

6.2) Configure as credenciais no `mobile\android\gradle.properties` (ou variáveis de ambiente):

```
MYAPP_UPLOAD_STORE_FILE=C:\\caminho\\meu-release.keystore
MYAPP_UPLOAD_KEY_ALIAS=gcmapp
MYAPP_UPLOAD_STORE_PASSWORD=xxxxxxxx
MYAPP_UPLOAD_KEY_PASSWORD=xxxxxxxx
```

6.3) Garanta que `android/app/build.gradle` use essas propriedades (padrão do template Capacitor já suporta assinatura). Depois gere o APK release:

```powershell
# dentro de c:\GCM_Sistema\mobile\android
./gradlew.bat assembleRelease
```

O APK ficará em:

- `mobile\android\app\build\outputs\apk\release\app-release.apk`

Instale no dispositivo:

```powershell
adb install -r .\app\build\outputs\apk\release\app-release.apk
```

7) Observações importantes

- O app está configurado para carregar a URL do servidor em `capacitor.config.ts` (server.url). Para usar no celular físico, ajuste a URL para o IP da sua máquina na mesma rede (ex.: `http://192.168.1.7:8000`) e adicione esse host em `allowNavigation`.
- Após alterar `capacitor.config.ts`, rode `npm run sync` para atualizar o projeto Android:

```powershell
# dentro de c:\GCM_Sistema\mobile
npm run sync
```

- Para abrir no Android Studio e gerar pelo IDE: `npm run android` (isso roda `npx cap add android && npx cap open android`).
- Se for usar Firebase/FCM, coloque `google-services.json` em `mobile\android\app\` e aplique o plugin `com.google.gms.google-services` no `build.gradle` do módulo app.

Mais detalhes em `../docs/mobile_apk.md`.
