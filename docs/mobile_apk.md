# App Android (APK) integrado ao site – Capacitor + FCM

Este guia mostra como empacotar o site Django dentro de um app Android (APK) usando Capacitor, com notificações push via Firebase Cloud Messaging (FCM). O app carrega seu site em uma WebView e compartilha o mesmo backend, então tudo que for feito no site reflete no app e vice‑versa.

## Visão geral

- O aplicativo é um “wrapper” do seu site: server.url aponta para a URL pública do Django (HTTPS).
- A ponte do Capacitor fica disponível em window.Capacitor na página, permitindo registrar o token de push. Já incluímos `static/js/mobile.js` para isso.
- O backend Django recebe e armazena tokens (modelo `common.PushDevice`) e envia notificações via `firebase-admin`.

## Pré‑requisitos

- Node.js 18+ e Java 17+ instalados em sua máquina de build (Windows pode usar Android Studio Bundle).
- Android Studio com SDKs atualizados.
- Conta no Firebase com um projeto criado.
- Seu site Django acessível por HTTPS com domínio público (cookies/sessão exigem HTTPS em produção).

## 1) Configurar Firebase

1. Crie um projeto no Firebase Console.
2. Adicione um app Android (ex.: pacote `br.gov.gcm.sistema`).
3. Baixe o arquivo `google-services.json` e coloque em `android/app/google-services.json` (na pasta do app móvel que você criará no passo 2).
4. Habilite Cloud Messaging (FCM) e copie a Service Account (chave JSON) do projeto Firebase para o servidor do Django. Exponha o caminho via variável de ambiente `FIREBASE_CREDENTIALS_JSON` no deploy.

## 2) Criar o projeto Capacitor (wrapper)

Você criará um projeto separado do Django, por exemplo numa pasta irmã `mobile/`:

- Inicialize um app web simples (pode ser vanilla). O importante é configurar o Capacitor para carregar seu site remoto:

`capacitor.config.ts` (exemplo):

```ts
import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'br.gov.gcm.sistema',
  appName: 'Sistema GCM',
  bundledWebRuntime: false,
  server: {
    url: 'https://SEU-DOMINIO-HTTPS',
    cleartext: false,
    allowNavigation: ['SEU-DOMINIO-HTTPS']
  },
  android: {
    allowMixedContent: false
  }
};
export default config;
```

- Instale o plugin de push notifications:
  - `@capacitor/push-notifications`
- Rode `npx cap add android` e abra o projeto Android no Android Studio.
- Coloque `google-services.json` em `android/app/` e aplique o plugin do Google Services no `build.gradle` do módulo.

Com `server.url`, o app carregará o site remoto, mas com a ponte do Capacitor injetada. Nosso `mobile.js` detecta `window.Capacitor` e registra o token automaticamente.

## 3) Backend Django (já pronto aqui)

- Modelo `common.PushDevice` e endpoints:
  - `POST /common/push/register-device/` (autenticado): registra/atualiza token.
  - `GET /common/push/test` (somente comando): envia notificação de teste para os dispositivos do usuário.
- Util de envio: função `enviar_push(tokens, title, body, data)` em `common/views.py` (seção Push) usando `firebase-admin`.
- Variável `FIREBASE_CREDENTIALS_JSON` adicionada em `settings.py`.
- Dependência incluída: `firebase-admin` em `requirements-prod.txt`.
- Script `static/js/mobile.js` incluído em `_layout/base.html` registra token quando rodando dentro do app.

Execute migrações no servidor (já criadas aqui): `common.0004_pushdevice`.

## 4) Sessão, CSRF e CORS

- Como o app carrega a URL HTTPS do próprio site, cookies de sessão e CSRF funcionam normalmente.
- Garanta que `CSRF_COOKIE_SECURE=True`, `SESSION_COOKIE_SECURE=True` no ambiente de produção.
- Não é necessário CORS para mesma origem. Se usar subdomínios, avalie `CSRF_TRUSTED_ORIGINS`.

## 5) Build e assinatura do APK

- No Android Studio, selecione Build > Generate Signed Bundle / APK…
- Crie/aponte para um keystore, defina senha e alias.
- Gere APK/ABB. Para publicar na Play Store, prefira AAB.

## 6) Testes

1. Instale o APK num Android.
2. Abra o app, faça login no site (dentro do app) e navegue.
3. O `mobile.js` deverá registrar o token (não há UI, mas você pode checar no admin ou DB).
4. Acesse `GET /common/push/test` autenticado como comando para disparar uma notificação de teste.

## 7) Disparando notificações reais

Use a função `enviar_push` em pontos do sistema (ex.: quando um BO for assinado, quando um despacho for criado para um usuário alvo). Exemplo (pseudo‑código em uma view):

```python
from common.models import PushDevice
from common.views import enviar_push

tokens = list(PushDevice.objects.filter(user=destino, enabled=True).values_list('token', flat=True))
if tokens:
    enviar_push(tokens, title='Novo despacho', body='Você tem um novo despacho pendente.', data={'screen': 'despachos'})
```

## Alternativas

- PWA (Web Push): funciona bem para Android/Chrome, mas iOS tem limitações e precisa VAPID. Integra menos com hardware.
- TWA (Trusted Web Activity): empacota sua PWA para Play Store. Depende de você ter PWA completa e web push configurado.

## Checklist de produção

- [ ] Site em HTTPS público.
- [ ] Variável `FIREBASE_CREDENTIALS_JSON` apontando para JSON de service account no servidor.
- [ ] `firebase-admin` instalado no ambiente de produção.
- [ ] Migração aplicada (tabela `common_pushdevice`).
- [ ] App Android com `server.url` para seu domínio e `google-services.json` em `android/app`.
- [ ] Teste de push concluído.

---
Dúvidas na criação do projeto Capacitor/Android Studio? Posso montar o esqueleto do app híbrido e commitar uma pasta `mobile/` com as configs básicas, se preferir.
