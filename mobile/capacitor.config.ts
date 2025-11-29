import { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'br.gov.gcm.sistema',
  appName: 'Sistema GCM',
  // Aponta o diretório de assets do app para a pasta 'web' deste projeto
  webDir: 'web',
  server: {
    // Desenvolvendo com backend local: apontar URL garante que o bridge do Capacitor
    // e os plugins (PushNotifications) sejam injetados corretamente nas páginas remotas.
    // Em emulador Android use 10.0.2.2; em dispositivo físico use o IP da sua máquina (ex.: 192.168.1.7)
  // Produção: usar domínio HTTPS
  url: 'https://gcmsysint.online',
    cleartext: false,
    // Permitir navegação para o domínio de produção
    allowNavigation: ['gcmsysint.online', 'www.gcmsysint.online']
  },
  android: {
    allowMixedContent: true
  }
};

export default config;
