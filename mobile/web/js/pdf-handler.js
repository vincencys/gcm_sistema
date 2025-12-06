(function(){
  console.log('[PDF Handler] Inicializado');
  
  // Detecta se é URL de documento que precisa de token
  function isPdfUrl(url){
    if (!url) return false;
    try {
      const u = new URL(url, window.location.href);
      return /\.pdf($|\?|#)/i.test(u.pathname) || 
             u.pathname.includes('/servir_documento_assinado/') ||
             u.pathname.includes('/documento-assinado/');
    } catch { return false; }
  }
  
  // Extrai doc_id da URL
  function extrairDocId(url){
    const match = url.match(/documento-assinado\/(\d+)|servir_documento_assinado\/(\d+)/);
    const docId = match ? (match[1] || match[2]) : null;
    console.log('[PDF Handler] extrairDocId:', url, '→', docId);
    return docId;
  }
  
  // Gera token para acessar PDF (requer autenticação)
  async function gerarToken(docId){
    console.log('[PDF Handler] Gerando token para doc:', docId);
    try {
      const response = await fetch(`/bogcmi/gerar-token-pdf/${docId}/`, {
        method: 'GET',
        credentials: 'include'
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const data = await response.json();
      console.log('[PDF Handler] Token gerado:', data.token?.substring(0, 8) + '...');
      return data;
    } catch(e) {
      console.error('[PDF Handler] Erro ao gerar token:', e);
      throw e;
    }
  }
  
  // Abre PDF usando token
  async function openPdfComToken(url){
    console.log('[PDF Handler] Abrindo PDF com token:', url);
    try {
      const docId = extrairDocId(url);
      if (!docId) {
        console.error('[PDF Handler] Não conseguiu extrair doc_id de:', url);
        throw new Error('Doc ID não encontrado');
      }
      
      // Gerar token (esta chamada requer login - ocorre na WebView autenticada)
      const tokenData = await gerarToken(docId);
      
      // URL do PDF com token (não requer login, usa token)
      const pdfUrl = tokenData.url;
      console.log('[PDF Handler] URL do PDF com token:', pdfUrl);
      
      const Capacitor = window.Capacitor;
      const { Browser } = Capacitor?.Plugins || {};
      
      if (Browser) {
        // Abrir em browser externo (Chrome) - agora funciona sem login porque usa token
        await Browser.open({ url: pdfUrl });
      } else {
        // Fallback
        window.location.href = pdfUrl;
      }
    } catch(e) {
      console.error('[PDF Handler] Erro:', e);
      // Fallback: tentar abrir URL original (vai pedir login no Chrome)
      try {
        const Capacitor = window.Capacitor;
        const { Browser } = Capacitor?.Plugins || {};
        await Browser?.open({ url });
      } catch(_) {
        window.location.href = url;
      }
    }
  }
  
  // Intercepta cliques
  document.addEventListener('click', function(e){
    const a = e.target?.closest('a');
    if (!a) return;
    
    const href = a.getAttribute('href');
    if (!href) return;
    
    console.log('[PDF Handler] Click em link:', href);
    
    if (isPdfUrl(href)) {
      console.log('[PDF Handler] Interceptando PDF');
      e.preventDefault();
      e.stopPropagation();
      openPdfComToken(href);
      return false;
    }
  }, true);
  
  // Também intercepta form submission para documentos (caso haja)
  document.addEventListener('submit', function(e){
    const form = e.target;
    if (!form) return;
    
    const action = form.getAttribute('action');
    if (action && isPdfUrl(action)) {
      console.log('[PDF Handler] Interceptando form para PDF:', action);
      e.preventDefault();
      e.stopPropagation();
      openPdfComToken(action);
      return false;
    }
  }, true);
  
  console.log('[PDF Handler] Setup completo');
})();
