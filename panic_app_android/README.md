# Botão do Pânico — App Android

App simples para acionar o Botão do Pânico do sistema via HTTPS.

## Funcionalidades
- Seleção de cidade (mapeada para URL do backend)
- Campo de token da assistida
- Botão “Acionar Pânico”
- Anti-spam: botão e inputs desabilitados durante o envio
- Exige HTTPS (cleartext desativado e validação no código)
- Envio automático de latitude/longitude/precisão (se permissões concedidas)
- Persistência de cidade e token
- Envio periódico de localização após disparo (com botão Parar)

## Requisitos
- Android Studio Flamingo ou superior
- Min SDK 23, Target SDK 34
- Backend acessível via HTTPS com certificado válido (ex.: Let's Encrypt)
- Google Play Services (para Fused Location Provider)

## Como abrir e rodar
1. Abra o Android Studio e clique em `Open`.
2. Selecione a pasta `panic_app_android`.
3. Aguarde a sincronização do Gradle. O projeto usa a estrutura moderna (repositórios definidos em `settings.gradle`). O arquivo `build.gradle` raiz está limpo (sem `buildscript`/`allprojects`).
4. Edite a lista de cidades/URLs em `app/src/main/java/com/seuprojeto/panico/MainActivity.kt`:
   ```kotlin
   private val cidades = mapOf(
       "Cidade A" to "https://sua-url-cidade-a.com/panic/public/disparo/",
       "Cidade B" to "https://sua-url-cidade-b.com/panic/public/disparo/"
   )
   ```
5. Execute no emulador/dispositivo.

### Localização
- O app solicita permissões e tenta capturar a posição atual (alta precisão).
- Se obtiver o ID do disparo, inicia um foreground service que envia localização a cada 15s para `/panic/public/disparo/{id}/localizacao/`.
- Uma notificação persistente indica "Botão do Pânico Ativo" durante o envio periódico.
- Há um botão "Parar Atualização de Localização" para interromper o serviço.

### Observações de build (Gradle moderno)
- Repositórios: definidos em `settings.gradle` (não use blocos em `build.gradle` raiz).
- Plugins: declarados via `plugins {}` em `app/build.gradle`.
- Se a sync falhar, use o Gradle Wrapper do Android Studio (menu Sync) e garanta conexão com `google()` e `mavenCentral()`.

## Segurança (HTTPS)
- O app bloqueia HTTP (cleartext) por Manifest (`android:usesCleartextTraffic="false"`).
- No código, URLs sem `https://` são rejeitadas.
- Certificados devem ser válidos e confiáveis (padrão do Android). Use Let's Encrypt com Nginx/Apache/Traefik.

## Endpoints do Backend
- Disparo: `POST /panic/public/disparo/`
  - Body (JSON): `{ "token": "<TOKEN_ASSISTIDA>", "latitude": -23.5, "longitude": -46.6, "precisao": 12 }` (latitude/longitude opcionais se indisponíveis)
  - 201: `{ id: number, status: string }`
  - 4xx/5xx: `{ detail: string }`

## Próximos passos (opcionais)
- Persistir cidade/token com `SharedPreferences`.
- Enviar atualizações periódicas de localização para `/panic/public/disparo/{id}/localizacao/` após receber o ID.
- Branding: ícones e splash.
- Integração de push para confirmação/enceramento.

## Suporte
Se precisar, posso adicionar persistência de preferências, envio de localização e pipeline de release (assinatura e `appbundle`).
