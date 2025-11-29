# 🔊 Como Trocar o Som da Sirene do Botão do Pânico

## 📍 Localização do Código

**Arquivo:** `templates\_layout\base.html`  
**Linhas:** 320-400 (aproximadamente)

---

## ✅ Opção 1: Usar Arquivo de Áudio Próprio (MP3, WAV, OGG)

### Passo 1: Adicionar o arquivo de som

1. Crie a pasta (se não existir):
   ```powershell
   mkdir c:\GCM_Sistema\static\sounds
   ```

2. Coloque seu arquivo de sirene lá:
   ```
   c:\GCM_Sistema\static\sounds\sirene.mp3
   ```

### Passo 2: Modificar o código em `templates\_layout\base.html`

Procure estas linhas (por volta da linha 323):

```javascript
var audioContext = null;
var audioPlaying = false;
var sireneOscillator = null;
var sireneGain = null;
var sireneInterval = null;

// Função para criar som de sirene (alternando entre grave e agudo)
function playAlertSound(){
  if(audioPlaying) return;
  console.log('[Pânico] 🔊 Iniciando SIRENE em loop');
  
  try{
    if(!audioContext) audioContext = new (window.AudioContext||window.webkitAudioContext)();
    ...
  }
}
```

**SUBSTITUA TODO O BLOCO ACIMA POR:**

```javascript
var audioElement = null;
var audioPlaying = false;

// Função para tocar arquivo de áudio em loop
function playAlertSound(){
  if(audioPlaying) return;
  console.log('[Pânico] 🔊 Iniciando SIRENE em loop');
  
  try{
    if(!audioElement){
      // ⚙️ CONFIGURAÇÃO DO SOM - EDITE AQUI:
      audioElement = new Audio('/static/sounds/sirene.mp3'); // ← Caminho do arquivo
      audioElement.loop = true;  // Repetir em loop
      audioElement.volume = 0.5; // Volume de 0.0 a 1.0 (50%)
    }
    
    audioElement.play()
      .then(function(){ 
        console.log('[Pânico] ✅ Sirene tocando'); 
        audioPlaying = true;
      })
      .catch(function(e){ 
        console.error('[Pânico] Erro ao tocar áudio:', e); 
      });
  }catch(e){ 
    console.error('[Pânico] Erro ao criar áudio:', e); 
  }
}

// Função para parar sirene
function stopAlertSound(){
  if(!audioPlaying) return;
  console.log('[Pânico] 🔇 Parando sirene');
  
  try{
    if(audioElement){
      audioElement.pause();
      audioElement.currentTime = 0; // Volta ao início
    }
  }catch(e){ console.warn('[Pânico] Erro ao parar sirene:', e); }
  
  audioPlaying = false;
}
```

### Passo 3: Rodar collectstatic (se estiver em produção)

```bash
python manage.py collectstatic --noinput
```

---

## 🎛️ Opção 2: Ajustar a Sirene Sintética (Atual)

Se quiser manter a sirene gerada por código mas modificar o som:

### Localização: mesma função `playAlertSound()` 

**Parâmetros que você pode ajustar:**

```javascript
// Linha ~345: Tipo de onda (muda o "timbre")
sireneOscillator.type = 'square'; // Opções: 'sine', 'square', 'sawtooth', 'triangle'

// Linha ~348: Volume
sireneGain.gain.value = 0.3; // De 0.0 a 1.0 (atualmente 30%)

// Linhas ~355-356: Frequências (grave e agudo)
var lowFreq = 400;   // Frequência grave (Hz) - som mais baixo
var highFreq = 800;  // Frequência aguda (Hz) - som mais alto

// Linha ~368: Velocidade de alternância
}, 600); // Alterna a cada 600 milissegundos (0.6 segundos)
```

### Exemplos de customização:

#### Sirene mais grave e lenta:
```javascript
var lowFreq = 300;
var highFreq = 600;
}, 800); // Mais devagar
```

#### Sirene mais aguda e rápida (polícia):
```javascript
var lowFreq = 600;
var highFreq = 1200;
}, 400); // Mais rápido
```

#### Sirene suave (senoidal):
```javascript
sireneOscillator.type = 'sine'; // Som mais "limpo"
sireneGain.gain.value = 0.2;    // Mais baixo
```

#### Sirene agressiva (dente de serra):
```javascript
sireneOscillator.type = 'sawtooth'; // Som mais "áspero"
sireneGain.gain.value = 0.4;        // Mais alto
```

---

## 🌐 Opção 3: Usar URL Externa (CDN)

Se tiver um arquivo online:

```javascript
audioElement = new Audio('https://exemplo.com/sirene.mp3');
```

---

## 🎯 Recomendação

Para melhor qualidade e controle:
- **Use Opção 1** (arquivo próprio MP3/WAV)
- Procure sons em sites como:
  - [Freesound.org](https://freesound.org/search/?q=siren)
  - [Zapsplat.com](https://www.zapsplat.com)
  - [Mixkit.co](https://mixkit.co/free-sound-effects/alarm/)

---

## ⚠️ Importante

Após qualquer modificação:
1. **Salve o arquivo** `base.html`
2. **Recarregue a página** (Ctrl+F5 para forçar)
3. Se não funcionar, **limpe o cache** do navegador
4. Em produção, rode `collectstatic`

---

## 🔧 Debugging

Se o som não tocar:
1. Abra o Console do navegador (F12)
2. Procure mensagens `[Pânico]`
3. Verifique se há erros em vermelho
4. Teste se o caminho do arquivo está correto acessando:
   ```
   http://127.0.0.1:8000/static/sounds/sirene.mp3
   ```
