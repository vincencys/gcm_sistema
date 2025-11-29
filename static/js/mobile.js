// Detecta Capacitor e registra push notifications, enviando o token para o backend Django
(function(){
  const TAG = '[PushInit]';
  const isCap = (()=>{
    try{
      const C = window.Capacitor || {};
      if (typeof C.isNativePlatform === 'function') return !!C.isNativePlatform();
      if (typeof C.getPlatform === 'function') {
        const p = (C.getPlatform()||'').toString().toLowerCase();
        if (p === 'android' || p === 'ios') return true;
      }
      if (/Capacitor|Android/i.test(navigator.userAgent||'')) return true;
    }catch(_){ }
    return false;
  })();
  if(!isCap){ console.debug(TAG, 'Não é plataforma nativa, abortando push'); return; }

  async function waitForPushPlugin(maxMs){
    const start = Date.now();
    while (Date.now() - start < (maxMs||5000)){
      const PN = window.Capacitor?.Plugins?.PushNotifications || window.PushNotifications;
      if (PN) return PN;
      await new Promise(r=>setTimeout(r, 200));
    }
    return null;
  }

  function toast(msg, ok=true){ /* silenciado por padrão */ }

  function getBaseUrl(){
    try{
      const m = document.querySelector('meta[name="backend-base"]');
      if (m && m.content) return m.content.replace(/\/$/, '');
    }catch(_){ }
    try{
      if (location && /^https?:/.test(location.protocol)) return location.origin.replace(/\/$/, '');
    }catch(_){ }
    // Fallback para emulador Android
    return 'http://10.0.2.2:8000';
  }

  function getCSRF(){
    try{
      const m = document.cookie && document.cookie.match(/csrftoken=([^;]+)/);
      if(m) return decodeURIComponent(m[1]);
    }catch(_){ }
    // Fallback: tenta pegar de meta tag se existir
    try{
      const meta = document.querySelector('meta[name="csrf-token"], meta[name="csrfmiddlewaretoken"]');
      if(meta && meta.content) return meta.content;
    }catch(_){ }
    return '';
  }

  async function register(){
    console.debug(TAG, 'Iniciando fluxo de registro push');
    try{
      // Ping leve para sabermos que o JS carregou (silencioso)
      const BASE = getBaseUrl();
      try{ fetch(BASE + '/healthz/?src=mobilejs&cap=1', { cache:'no-store', credentials:'include' }); }catch(_){ }
      // silencioso
  // Espera plugin
  const PushNotifications = await waitForPushPlugin(5000);
  if(!PushNotifications){ return; }
  // Adiciona listeners ANTES do register() por segurança
  PushNotifications.addListener('registration', async (token) => {
        console.debug(TAG, 'Evento registration recebido', token);
        // silencioso
        try{
          const form = new FormData();
          form.append('token', token.value || token);
          form.append('platform', 'android');
          form.append('device_info', navigator.userAgent || 'Capacitor Android');
          const resp = await fetch(BASE + '/common/push/register-device/', {
            method: 'POST',
            headers: {
              'X-CSRFToken': getCSRF(),
            },
            body: form,
            credentials: 'include'
          });
          if (resp && resp.ok){
            console.debug(TAG, 'Token enviado ao backend');
          } else {
            let txt=''; try{ txt = await resp.text(); }catch(_){ }
            console.warn(TAG, 'Falha ao registrar token no backend', resp?.status, txt);
            toast('Push: falha registrar token ('+(resp?.status||'')+')', false);
          }
          // Diagnóstico silencioso removido (não mostrar contagem de dispositivos)
        }catch(err){ console.warn('Falha ao registrar token:', err); }
      });
  PushNotifications.addListener('registrationError', (err)=>{
        console.warn(TAG, 'Erro de registro de push:', err);
      });
  PushNotifications.addListener('pushNotificationReceived', (notif)=>{
        try{
          // Se Local Notifications estiver disponível, dispara uma notificação local (em foreground)
          const LN = window.Capacitor?.Plugins?.LocalNotifications || window.LocalNotifications;
          const title = (notif && notif.title) || 'GCM';
          const body  = (notif && notif.body)  || 'Nova notificação';
          if (LN && LN.schedule) {
            (async ()=>{
              try{
                await LN.requestPermissions();
                await LN.schedule({ notifications: [{ id: Date.now()%2147483647, title, body, channelId: 'default', sound: 'default', smallIcon: 'ic_launcher' }] });
              }catch(_){
                // fallback visual simples
                const div = document.createElement('div');
                div.style.cssText = 'position:fixed;bottom:16px;left:50%;transform:translateX(-50%);background:#111;color:#fff;padding:10px 14px;border-radius:8px;z-index:9999;';
                div.textContent = title+': '+body; document.body.appendChild(div); setTimeout(()=>div.remove(), 3500);
              }
            })();
          } else {
            // Sem LocalNotifications, não exibe toast (silencioso)
          }
        }catch(e){}
      });
  const perm = await PushNotifications.requestPermissions();
      console.debug(TAG, 'requestPermissions retornou', perm);
      if (perm && perm.receive === 'denied') { return; }
  await PushNotifications.register();
      console.debug(TAG, 'Chamado register()');
    }catch(e){ console.warn('Falha geral push:', e); }
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', register);
  } else {
    register();
  }
})();
