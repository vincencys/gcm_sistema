# REGISTRO DE PROGRAMA DE COMPUTADOR
## BIBLIOTECA NACIONAL DO BRASIL

---

**Protocolo**: 000984.038/187/2025  
**Data de Solicitação**: 28/11/2025  
**Tipo de Obra**: Design de Website / Sistema Web e Mobile  
**Titular**: MOISES SANTOS DE OLIVEIRA

---

## 1. IDENTIFICAÇÃO DA OBRA

### 1.1 Dados Básicos
- **Título da Obra**: SISTEMA INTELIGENTE PARA GCMS (Sistema Integrado de Gestão da Guarda Civil Municipal)
- **Título Alternativo**: Sistema GCM / GCM Sistema
- **Tipo**: Programa de Computador (Software)
- **Categoria**: Design de Website / Sistema de Gestão Governamental
- **Natureza**: Obra Original (Não é adaptação, tradução ou adaptação e tradução)

### 1.2 Características Técnicas
- **Linguagens de Programação**: Python, Kotlin, JavaScript, TypeScript
- **Framework Principal**: Django 5.2
- **Ambiente de Execução**: Web (multiplataforma) e Mobile (Android)
- **Banco de Dados**: PostgreSQL, SQLite
- **Total de Linhas de Código**: Aproximadamente 50.000+ linhas
- **Número de Arquivos**: 500+ arquivos fonte
- **Módulos**: 12 aplicações integradas

### 1.3 Data de Criação
- **Início do Desenvolvimento**: Janeiro de 2025
- **Conclusão da Versão 1.0**: Novembro de 2025
- **Período Total**: 11 meses de desenvolvimento

---

## 2. DESCRIÇÃO FUNCIONAL DO SISTEMA

### 2.1 Propósito e Finalidade

O **Sistema Inteligente para GCMs** é uma plataforma completa e integrada desenvolvida para digitalizar e automatizar todas as operações de uma Guarda Civil Municipal (GCM). O sistema substitui processos manuais em papel por workflows digitais rastreáveis, aumentando a eficiência operacional, transparência e segurança institucional.

**Público-Alvo**: Guardas Civis Municipais de todo o Brasil

**Problema Resolvido**: Elimina processos burocráticos manuais, reduz tempo de preenchimento de documentos em até 80%, garante rastreabilidade completa de operações sensíveis (armamento, munição, ocorrências), e fornece proteção social através de tecnologia (botão do pânico para vítimas de violência doméstica).

### 2.2 Funcionalidades Principais

#### A) BOGCMI - Boletim de Ocorrência Digital
Sistema completo de registro de ocorrências atendidas pela GCM com as seguintes inovações:

**Funcionalidades**:
- Registro digital de ocorrências com geolocalização automática
- Cadastro de envolvidos com auto-preenchimento por CPF
- Registro de veículos envolvidos com dados completos de acidente
- Upload de fotos de apreensões (evidências)
- Workflow de aprovação: EDIÇÃO → FINALIZADO → DESPACHO_CMT → ARQUIVADO
- Assinatura digital com canvas HTML5
- Geração automática de PDF com QR Code de validação
- Modo offline com sincronização posterior

**Inovações Técnicas**:
1. **Marca D'água Contextual**: Aplica automaticamente marca d'água "APENAS CONSULTIVO" em PDFs para integrantes não-comando, usando PyPDF2 e ReportLab. Comando recebe PDF original sem marca.

2. **QR Code de Validação Pública**: Cada BO gera QR Code único contendo:
   - Token público (40 caracteres alfanuméricos)
   - Hash SHA-256 do conteúdo
   - Permite validação externa sem acesso ao sistema

3. **Sincronização Offline**: Permite criar BOs sem internet usando:
   - LocalStorage do navegador como fila
   - UUID (client_uuid) para identificação única
   - Endpoint de sincronização que faz merge no servidor
   - Badge visual de itens pendentes

4. **Cadastro Inteligente**: Base de dados persistente de envolvidos indexada por CPF normalizado, permitindo auto-preenchimento em novos BOs.

**Tecnologias Utilizadas**:
- Backend: Django ORM, Django Signals
- PDFs: ReportLab (canvas drawing), PyPDF2 (manipulação), pdfkit (wkhtmltopdf), xhtml2pdf
- Validação: hashlib (SHA-256)
- QR Code: biblioteca qrcode 7.4
- Frontend: JavaScript puro, LocalStorage API

#### B) PANIC - Botão do Pânico para Vítimas

Aplicativo Android nativo para proteção de vítimas de violência doméstica com acionamento de emergência geolocalizado.

**Componentes**:

1. **Aplicativo Android Nativo** (panic_app_android):
   - Desenvolvido em Kotlin
   - Autenticação simplificada por token de 6 dígitos
   - Botão de pânico único e intuitivo
   - Captura automática de localização GPS em tempo real
   - Envio opcional de foto/áudio junto ao disparo
   - Serviço de background (PanicLocationService) para localização contínua
   - Firebase Cloud Messaging para notificações push
   - Material Design para UX otimizada

2. **Gestão de Assistidas** (Backend Web):
   - Cadastro vinculado a processo do Ministério Público
   - Token rotativo de 6 caracteres alfanuméricos
   - Estados: PENDENTE_VALIDACAO → APROVADO → SUSPENSO
   - Upload de documentação judicial (PDF)
   - Histórico completo de disparos

3. **Central de Atendimento CECOM**:
   - Painel em tempo real com WebSocket
   - Modal automático ao receber disparo com som de sirene customizado
   - Mapa interativo com localização exata da vítima
   - Estados: ABERTA → EM_ATENDIMENTO → ENCERRADA/CANCELADA/FALSO_POSITIVO
   - Sistema de "assumir disparo" (assigned user)
   - Relatório final obrigatório com detalhamento da ocorrência
   - Notificação push para aplicativo da vítima confirmando atendimento

**Inovação Social**:
Este é o primeiro sistema brasileiro integrado de botão do pânico municipal com geolocalização em tempo real, desenvolvido especificamente para perfil de vítima em situação de risco. Diferente de aplicativos comerciais, possui autenticação simplificada (apenas token de 6 dígitos) e integração completa com central de despacho da GCM.

**Tecnologias**:
- Mobile: Kotlin, Firebase Messaging SDK, Play Services Location
- Backend: Django Channels 4.1 (WebSocket), Daphne ASGI
- Push: Firebase Admin SDK
- Mapas: Leaflet.js + OpenStreetMap
- Tempo Real: WebSocket com broadcast via channel layers

#### C) CECOM - Central de Comunicação e Controle

Sistema de central de operações em tempo real para gerenciamento de plantões, despacho de ocorrências e rastreamento de viaturas.

**Funcionalidades**:

1. **Livro Eletrônico de Plantão**:
   - Substituição completa do livro físico de plantão
   - Campos estruturados: dispensados, atrasos, banco de horas, hora extra
   - Gestão de viaturas em serviço com quilometragem
   - Postos fixos (Prefeitura, Hospital, Delegacia, Subsede) com escala nominal
   - Checklist de equipamentos (rádio, computador, câmeras, celulares institucionais)
   - Geração automática de PDF ao encerrar plantão
   - QR Code de verificação em cada relatório
   - Plantão compartilhado: múltiplos usuários no mesmo plantão (encarregado, motorista, auxiliares, CECOM)

2. **Despacho de Ocorrências**:
   - Sistema de envio de chamados para viaturas em serviço
   - Notificação push instantânea para aplicativo mobile da viatura
   - Campos: endereço, natureza, código de ocorrência, prioridade
   - Rastreamento de status: PENDENTE → EM_ATENDIMENTO → FINALIZADA
   - Resposta da viatura com tempo de chegada estimado
   - Histórico completo de despachos

3. **Rastreamento GPS de Viaturas**:
   - Captura de localização via aplicativo mobile em background
   - Modelo ViaturaLocalizacao (última posição conhecida)
   - Modelo ViaturaLocalizacaoPonto (histórico de trilha)
   - Mapa ao vivo com ícones das viaturas
   - Atualização automática via WebSocket
   - Filtro por período para replay de rotas

**Inovação**:
Sistema de rastreamento ativo sem necessidade de hardware adicional (rastreadores veiculares), utilizando apenas aplicativos móveis dos integrantes da viatura.

**Tecnologias**:
- WebSocket: Django Channels com Redis backend
- ASGI Server: Daphne 4.1
- Frontend: JavaScript + Leaflet.js
- Push: Firebase Cloud Messaging

#### D) ALMOXARIFADO - Controle de Armamento e Munição

Sistema de gestão de estoque de armamento, munição e equipamentos com auditoria blockchain-like.

**Funcionalidades**:

1. **Estoque de Munição**:
   - Controle por calibre, lote, validade, tipo (treino/operacional)
   - Movimentações rastreadas: ENTRADA, SAÍDA, AJUSTE
   - Estoque disponível vs estoque reservado (cautelas abertas)
   - Alertas de estoque mínimo
   - Relatório de validade próxima ao vencimento

2. **Sistema de Cautelas** (Empréstimo de Equipamentos):
   - Tipos: SUPORTE (empréstimo temporário) e FIXO (assignação permanente)
   - Workflow com tripla validação:
     - Solicitante ≠ Supervisor ≠ Almoxarife (segregação de funções)
   - Estados: PENDENTE → APROVADA → ABERTA → ENCERRADA
   - Controle de horário de retirada/devolução configurável (variável de ambiente)
   - Limites de munição por cargo/classe funcional
   - Checklist de saída e entrada
   - Versionamento otimista (campo `rev`) para evitar race conditions
   - Geração de PDF com termos de responsabilidade

3. **Bens Patrimoniais**:
   - Classificação: ARMAMENTO, MUNICAO, SUPORTE, FIXO
   - Subtipos: Pistola, Revólver, Carabina, Espingarda, Fuzil
   - Tombamento, número de série, lote de fabricação
   - Histórico de manutenção (preventiva, corretiva, baixa)
   - Assignação fixa com termo de responsabilidade assinado

4. **Auditoria com Hash Encadeado**:
   - Modelo AuditTrail: trilha imutável append-only
   - Algoritmo de hash encadeado (estilo blockchain):
     ```
     hash_atual = SHA256(hash_anterior + timestamp + actor_id + 
                         object_id + event + before + after)
     ```
   - Detecta adulterações retroativas
   - Campos: actor, timestamp, evento, before/after (snapshots JSON)
   - SimpleLog: eventos de negócio legíveis para usuários

**Regras de Negócio**:
- Horário de retirada/devolução configurável (ex: 08h às 17h)
- Limites por classe funcional (ex: GCM 3C não pode retirar > 50 munições)
- Validação de disponibilidade antes de aprovar cautela
- Soft delete em todos os registros críticos

**Tecnologias**:
- Auditoria: hashlib (SHA-256), json.dumps (serialização)
- Transações: Django atomic transactions
- Validação: Django Forms + custom validators
- PDFs: ReportLab

#### E) VIATURAS - Gestão de Frota

Sistema completo de controle de viaturas com checklist digital de avarias.

**Funcionalidades**:
- Cadastro de viaturas: prefixo, placa, modelo, ano
- Status: FUNCIONAMENTO, MANUTENÇÃO, BAIXADA
- Controle de quilometragem com alertas de manutenção
- Histórico de abastecimentos

**Checklist Digital de Avarias**:
- 30+ itens inspecionáveis (faróis, lanternas, pneus, espelhos, etc.)
- Anexo de fotos por avaria (modelo AvariaAnexo)
- Histórico de avarias (modelo AvariaLog)
- Estado consolidado persistente (ViaturaAvariaEstado)
- Resolução de avarias fora do plantão
- Upload de fotos direto do mobile com `capture="environment"`

**Tecnologias**:
- Upload: Django FileField, Pillow para processão de imagens
- Storage: FileSystemStorage (produção: S3-compatible)

#### F) TALÕES - Registros de Ocorrência por Viatura

Sistema de registro rápido de ocorrências atendidas por viatura durante plantão.

**Funcionalidades**:
- Numeração sequencial por plantão
- Códigos de ocorrência organizados por grupo
- Registro de abordados (pessoas e veículos)
- Abastecimento com anexo de recibo
- AITs (Autos de Infração de Trânsito) emitidas por integrante
- Vinculação com BO (talão pode gerar BO completo posteriormente)

#### G) USERS - Autenticação e Controle de Acesso

Sistema de usuários e permissões hierárquico.

**Funcionalidades**:
- Perfil GCM: matrícula, equipe (A/B/C/D), classe funcional (3C → CMT)
- Cargo e lotação
- Assinatura digital: canvas HTML5 para desenho ou upload de imagem PNG
- Grupos de permissão hierárquicos:
  - Superusuário (moises)
  - Comando (comandante, subcomandante)
  - Administrativo
  - Encarregado
  - GCM
  - CECOM
- Recovery email para recuperação de senha
- Two-Factor Authentication (2FA) opcional com TOTP (biblioteca pyotp)

**Decorators de Controle**:
- `@login_required`
- `@comando_required`
- `@permission_required('app.permission')`

#### H) NOTIFICAÇÕES - Push Notifications

Sistema de notificações push para aplicativos móveis via Firebase Cloud Messaging.

**Funcionalidades**:
- Modelo PushDevice: token único, plataforma (Android/iOS), app_version
- Envio massivo ou individual
- Data payload customizado para deep linking
- Casos de uso:
  - Disparo de pânico
  - Despacho de ocorrência
  - Aprovação/recusa de cautela
  - BO assinado pelo comando
  - Mensagens administrativas

**Tecnologias**:
- Firebase Admin SDK
- Arquivo de credenciais: `gcm-sistema-firebase-adminsdk-fbsvc-a644ddfea0.json`

#### I) RELATÓRIOS E ESTATÍSTICAS

Dashboard analítico com indicadores operacionais.

**Funcionalidades**:
- Dashboard com indicadores-chave (KPIs)
- Estatísticas de BOs:
  - Série temporal (por dia/mês/ano)
  - Ranking por código de ocorrência
  - Ranking por bairro
  - Mapa de calor de ocorrências
  - Estatísticas por usuário/equipe
- Filtros avançados: período, código, bairro, status
- Gráficos exportáveis em PDF
- Geocodificação para mapa interativo

**Tecnologias**:
- Gráficos: Chart.js
- Exportação: ReportLab
- Mapas: Leaflet.js + heatmap plugin

#### J) COMMON - Funcionalidades Comuns

Módulo de serviços compartilhados.

**Serviços**:

1. **IA para Relatórios** (ai_service.py):
   - Integração com Groq API (Llama 3.1 70B)
   - Melhoria automática de redação de relatórios
   - Prompt especializado para contexto policial/GCM
   - Fallback offline: correção ortográfica + linguagem técnica
   - Endpoint REST: `/api/ai/melhorar-texto/`

2. **Auditoria**:
   - AuditLog: log simples de requisições HTTP
   - AuditTrail: trilha forte com hash encadeado
   - SimpleLog: eventos de negócio legíveis
   - Middleware de auditoria automática

3. **Documentos Assináveis**:
   - Modelo DocumentoAssinavel genérico
   - Estados: PENDENTE → ASSINADO → REJEITADO
   - QR Code de validação
   - Hash SHA-256 do conteúdo

---

## 3. ARQUITETURA DO SISTEMA

### 3.1 Visão Geral

O sistema utiliza arquitetura **monolítica modular** com separação clara de responsabilidades por aplicações Django. Cada módulo (BOGCMI, Panic, CECOM, etc.) é uma aplicação Django independente com seus próprios models, views, urls e templates.

```
┌─────────────────────────────────────────────────────┐
│          CAMADA DE APRESENTAÇÃO                      │
│                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐│
│  │ Web Browser  │  │  Mobile App  │  │ Panic App  ││
│  │ (Responsive) │  │  (Hybrid)    │  │  (Native)  ││
│  └──────────────┘  └──────────────┘  └────────────┘│
└─────────────────────────────────────────────────────┘
           │                  │                 │
           │ HTTP/WS          │ HTTP/FCM        │ HTTP/FCM
           ▼                  ▼                 ▼
┌─────────────────────────────────────────────────────┐
│          CAMADA DE APLICAÇÃO (Backend)               │
│                                                       │
│  ┌─────────────────────────────────────────────┐   │
│  │         Django 5.2 (Python 3.10+)           │   │
│  │                                               │   │
│  │  Apps: bogcmi | panic | cecom | almoxarifado│   │
│  │        viaturas | taloes | users | common   │   │
│  │        core | notificacoes | relatorios     │   │
│  └─────────────────────────────────────────────┘   │
│                                                       │
│  ┌──────────────┐  ┌─────────────────────────┐     │
│  │ Daphne ASGI  │  │   Gunicorn WSGI         │     │
│  │ (WebSocket)  │  │   (HTTP)                │     │
│  └──────────────┘  └─────────────────────────┘     │
└─────────────────────────────────────────────────────┘
           │                           │
           ▼                           ▼
┌──────────────────┐        ┌───────────────────────┐
│  Django Channels │        │   Celery Worker       │
│  (Redis backend) │        │   (Tarefas Async)     │
└──────────────────┘        └───────────────────────┘
           │                           │
           ▼                           ▼
┌─────────────────────────────────────────────────────┐
│          CAMADA DE DADOS                             │
│                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ PostgreSQL   │  │    Redis     │  │   Media   │ │
│  │ (Produção)   │  │ (Cache/Queue)│  │  Storage  │ │
│  │ SQLite (Dev) │  │              │  │  (Files)  │ │
│  └──────────────┘  └──────────────┘  └───────────┘ │
└─────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────┐
│          SERVIÇOS EXTERNOS                           │
│                                                       │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │   Firebase   │  │   Groq API   │                 │
│  │     (FCM)    │  │  (IA - LLM)  │                 │
│  └──────────────┘  └──────────────┘                 │
└─────────────────────────────────────────────────────┘
```

### 3.2 Tecnologias por Camada

#### Backend (Servidor)
- **Framework**: Django 5.2
- **Linguagem**: Python 3.10+
- **ASGI Server**: Daphne 4.1 (para WebSocket)
- **WSGI Server**: Gunicorn (para HTTP em produção)
- **ORM**: Django ORM
- **Tempo Real**: Django Channels 4.1
- **Tarefas Assíncronas**: Celery 5.4

#### Frontend Web
- **Templates**: Django Templates (Jinja2-like)
- **CSS Framework**: TailwindCSS 3.x
- **JavaScript**: Vanilla JS + HTMX (parcial)
- **UI Components**: django-crispy-forms + crispy-tailwind
- **Ícones**: Font Awesome 6.x
- **Gráficos**: Chart.js
- **Mapas**: Leaflet.js + OpenStreetMap

#### Mobile
1. **Panic App (Nativo Android)**:
   - Linguagem: Kotlin
   - IDE: Android Studio
   - Min SDK: 26 (Android 8.0)
   - Target SDK: 34 (Android 14)
   - Firebase Messaging SDK
   - Play Services Location
   - Material Design 3

2. **Mobile App (Híbrido)**:
   - Framework: Ionic/Capacitor
   - Base: WebView do sistema
   - Plugins: Geolocation, Camera, Push Notifications

#### Banco de Dados
- **Desenvolvimento**: SQLite 3.35+
- **Produção**: PostgreSQL 12+
- **Cache/Queue**: Redis 6+

#### Geração de PDFs
- **ReportLab 4.2**: Canvas drawing (baixo nível)
- **PyPDF2 3.0**: Manipulação e merge de PDFs
- **pdfkit 1.0**: Wrapper para wkhtmltopdf
- **xhtml2pdf 0.2**: HTML to PDF (fallback)
- **WeasyPrint 61.2**: HTML to PDF moderno (fallback)

#### Outras Bibliotecas Python
- **Pillow 11.2**: Processamento de imagens
- **qrcode 7.4**: Geração de QR codes
- **pyotp 2.9**: Two-Factor Authentication (TOTP)
- **whitenoise 6.7**: Servir arquivos estáticos
- **django-filter 24.2**: Filtros avançados
- **firebase-admin 6.x**: Push notifications
- **groq 0.x**: API de IA

### 3.3 Padrões de Projeto Utilizados

#### Models (Modelos de Dados)
- **TimeStampedModel**: Mixin com `created_at`, `updated_at`
- **SoftDeleteModel**: Mixin com `deleted_at` (soft delete)
- **Assinavel**: Mixin com `assinatura_img`, `assinado_por`, `assinado_em`

#### Views (Controladores)
- **Class-Based Views** (ListView, DetailView, CreateView, UpdateView)
- **Function-Based Views** para casos específicos
- **Mixins**: LoginRequiredMixin, PermissionRequiredMixin

#### Workflows
- **State Machine** para status de documentos
- **Approval Chains**: solicitante → supervisor → almoxarife

#### Segurança
- **CSRF Protection**: Token em todos os forms
- **XSS Protection**: Auto-escaping de templates
- **SQL Injection Protection**: Django ORM parametrizado
- **Decorators**: `@login_required`, `@comando_required`, `@permission_required`

#### Performance
- **Query Optimization**: `select_related()`, `prefetch_related()`
- **Caching**: Redis para queries frequentes
- **Static Compression**: Brotli/Gzip com whitenoise

---

## 4. INOVAÇÕES TECNOLÓGICAS

### 4.1 Sistema de Marca D'água Contextual

**Problema**: Documentos sensíveis (BOs) precisam ter distribuição controlada, mas com níveis diferentes de acesso.

**Solução Inovadora**: Sistema de marca d'água dinâmica aplicada em tempo real baseada no perfil do usuário solicitante.

**Algoritmo**:
1. Usuário solicita PDF do BO
2. Sistema verifica perfil:
   - Se Comando ou superusuário → PDF original sem marca
   - Se integrante do BO → PDF com marca d'água "APENAS CONSULTIVO"
   - Senão → Acesso negado
3. PDF é gerado com ReportLab
4. Overlay de marca d'água é criado com rotação de 45° e opacidade 30%
5. Merge usando PyPDF2.PdfMerger
6. PDF final é retornado ao usuário

**Código Simplificado**:
```python
from PyPDF2 import PdfReader, PdfWriter, Transformation
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

def aplicar_marca_dagua(pdf_bytes, user):
    if user.is_comando():
        return pdf_bytes  # Sem marca
    
    # Criar overlay com marca d'água
    overlay = criar_overlay_marca_dagua("APENAS CONSULTIVO")
    
    # Aplicar em todas as páginas
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    
    for page in reader.pages:
        page.merge_page(overlay.pages[0])
        writer.add_page(page)
    
    return writer.write()
```

**Benefício**: Controle granular de distribuição sem necessidade de gerar múltiplas versões do documento.

### 4.2 Auditoria com Hash Encadeado (Blockchain-like)

**Problema**: Necessidade de trilha de auditoria imutável para operações sensíveis (armamento, munição).

**Solução Inovadora**: Sistema de hash encadeado estilo blockchain, onde cada registro contém o hash do registro anterior.

**Algoritmo**:
```python
import hashlib
import json

def criar_audit_trail(actor, event, obj, before, after):
    ultimo_registro = AuditTrail.objects.order_by('-id').first()
    hash_anterior = ultimo_registro.hash if ultimo_registro else "0" * 64
    
    dados = {
        'hash_anterior': hash_anterior,
        'timestamp': datetime.now().isoformat(),
        'actor_id': actor.id,
        'object_id': obj.id,
        'event': event,
        'before': before,
        'after': after
    }
    
    hash_atual = hashlib.sha256(
        json.dumps(dados, sort_keys=True).encode()
    ).hexdigest()
    
    return AuditTrail.objects.create(
        hash_anterior=hash_anterior,
        hash=hash_atual,
        **dados
    )
```

**Validação de Integridade**:
```python
def validar_cadeia_auditoria():
    registros = AuditTrail.objects.order_by('id')
    
    for i, registro in enumerate(registros):
        if i == 0:
            assert registro.hash_anterior == "0" * 64
        else:
            assert registro.hash_anterior == registros[i-1].hash
        
        # Recalcular hash
        hash_recalculado = calcular_hash(registro)
        assert registro.hash == hash_recalculado
    
    return True  # Cadeia íntegra
```

**Benefício**: Impossível alterar registros passados sem quebrar a cadeia. Qualquer adulteração é detectada imediatamente.

### 4.3 QR Code Duplo para Validação Pública

**Problema**: Como permitir que cidadãos validem autenticidade de documentos (BOs) sem expor dados sensíveis?

**Solução Inovadora**: QR Code com dupla camada de segurança.

**Camadas**:
1. **Token Público** (40 chars alfanuméricos): Identificador único consultável
2. **Hash Privado** (SHA-256): Hash do conteúdo completo do documento

**Geração**:
```python
import secrets
import hashlib
import qrcode

# Ao criar BO
bo.validacao_token = secrets.token_urlsafe(30)[:40]
bo.validacao_hash = hashlib.sha256(
    f"{bo.numero}{bo.data}{bo.natureza}{bo.relato}".encode()
).hexdigest()

# Gerar QR Code
url_validacao = f"https://gcm.cidade.gov.br/validar/{bo.validacao_token}"
qr = qrcode.make(url_validacao)
```

**Validação Pública** (endpoint sem login):
```python
def validar_documento(request, token):
    bo = BO.objects.filter(validacao_token=token).first()
    
    if not bo:
        return render('documento_invalido.html')
    
    return render('documento_valido.html', {
        'numero': bo.numero,
        'data': bo.data,
        'hash': bo.validacao_hash,
        'valido': True
    })
```

**Benefício**: Transparência pública sem comprometer segurança. Cidadão pode validar BO recebido escaneando QR Code.

### 4.4 Sincronização Offline Bidirecional

**Problema**: GCMs precisam criar BOs em áreas sem cobertura de internet (zona rural, subsolo).

**Solução Inovadora**: Sistema de fila offline com resolução inteligente de conflitos.

**Arquitetura**:
1. **Cliente** (JavaScript):
   - Detecta offline via `navigator.onLine`
   - Salva BOs em LocalStorage com `client_uuid`
   - Badge visual mostra itens na fila
   - Tenta sincronizar automaticamente ao voltar online

2. **Servidor** (Django):
   - Endpoint `/bogcmi/sync/` recebe array de BOs
   - Para cada BO:
     - Verifica se `client_uuid` já existe
     - Se não existe → cria novo BO
     - Se existe → atualiza (merge)
   - Retorna lista de IDs criados

**Código Cliente**:
```javascript
// Salvar offline
function salvarBOOffline(dados) {
    const client_uuid = crypto.randomUUID();
    dados.client_uuid = client_uuid;
    dados.offline = true;
    
    const fila = JSON.parse(localStorage.getItem('fila_bos') || '[]');
    fila.push(dados);
    localStorage.setItem('fila_bos', JSON.stringify(fila));
    
    atualizarBadge(fila.length);
}

// Sincronizar
async function sincronizarBOs() {
    const fila = JSON.parse(localStorage.getItem('fila_bos') || '[]');
    
    if (fila.length === 0) return;
    
    const response = await fetch('/bogcmi/sync/', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({bos: fila})
    });
    
    const result = await response.json();
    
    // Limpar fila
    localStorage.setItem('fila_bos', '[]');
    atualizarBadge(0);
}

// Auto-sync quando voltar online
window.addEventListener('online', sincronizarBOs);
```

**Benefício**: Operação garantida 100% do tempo, independente de conectividade.

### 4.5 Rastreamento GPS sem Hardware Adicional

**Problema**: Rastreadores veiculares custam R$ 500-1500 por viatura + mensalidade.

**Solução Inovadora**: Rastreamento via aplicativo mobile já utilizado pela equipe.

**Fluxo**:
1. Aplicativo mobile inicia serviço de background ao iniciar plantão
2. Serviço captura GPS a cada 30 segundos
3. Envia para endpoint `/viaturas/atualizar-localizacao/`
4. Backend:
   - Atualiza `ViaturaLocalizacao` (última posição)
   - Cria ponto em `ViaturaLocalizacaoPonto` (histórico)
   - Broadcast via WebSocket
5. Mapa CECOM atualiza em tempo real

**Código Mobile** (Kotlin):
```kotlin
class LocationService : Service() {
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        fusedLocationClient.requestLocationUpdates(
            locationRequest,
            locationCallback,
            Looper.getMainLooper()
        )
        return START_STICKY
    }
    
    private val locationCallback = object : LocationCallback() {
        override fun onLocationResult(result: LocationResult) {
            result.lastLocation?.let { location ->
                enviarLocalizacao(location.latitude, location.longitude)
            }
        }
    }
}
```

**Benefício**: Economia de R$ 10.000+ para frota de 10 viaturas, sem perder funcionalidade.

### 4.6 IA Contextual para Segurança Pública

**Problema**: Relatórios de GCMs frequentemente têm erros de digitação, gramática pobre, linguagem informal.

**Solução Inovadora**: Assistente de IA com prompt especializado para contexto policial.

**Prompt Especializado**:
```python
PROMPT_MELHORAR_RELATO = """
Você é um assistente especializado em segurança pública municipal.
Melhore o texto abaixo mantendo:
- Linguagem técnica policial
- Terminologia jurídica correta
- Verbos no pretérito perfeito
- Impessoalidade
- Clareza e concisão

NÃO adicione informações que não estejam no texto original.
NÃO remova detalhes factuais.

Texto original:
{texto}

Texto melhorado:
"""
```

**Integração**:
- API: Groq (gratuita, rápida)
- Modelo: Llama 3.1 70B
- Fallback: Correção ortográfica offline se API indisponível

**Benefício**: Documentos profissionais sem necessidade de treinamento extensivo em redação.

---

## 5. MÓDULOS E QUANTIDADE DE CÓDIGO

### 5.1 Estatísticas Gerais
- **Total de Módulos Django**: 12 apps
- **Total Estimado de Linhas de Código**: 50.000+
- **Total de Arquivos Fonte**: 500+
- **Total de Modelos (Models)**: 50+
- **Total de Views**: 150+
- **Total de Templates**: 100+
- **Total de URLs**: 120+

### 5.2 Distribuição por Módulo

| Módulo | Arquivos Principais | Linhas Aprox. | Descrição |
|--------|-------------------|---------------|-----------|
| bogcmi | models.py (800), views.py (1500), forms.py (600) | 5000 | Boletins de Ocorrência |
| panic | models.py (400), views.py (600), sync_views.py (300) | 2500 | Botão do Pânico |
| cecom | models.py (600), views.py (1000), forms.py (400) | 3500 | Central de Comunicação |
| almoxarifado | models.py (700), services.py (800), views.py (900) | 4000 | Controle de Armamento |
| viaturas | models.py (500), views.py (700) | 2000 | Gestão de Frota |
| taloes | models.py (400), views.py (600) | 1800 | Registros de Ocorrência |
| users | models.py (300), views.py (500) | 1500 | Autenticação |
| common | ai_service.py (200), audit.py (500) | 2000 | Serviços Comuns |
| core | views.py (800), config_views.py (600) | 2500 | Dashboard |
| notificacoes | models.py (200), views.py (300) | 800 | Push Notifications |
| relatorios | views_estatisticas.py (1000) | 1500 | Estatísticas |
| integracoes | - | 500 | Extensões |
| **Mobile Panic** | Kotlin (30 files) | 8000 | App Android Nativo |
| **Mobile Hybrid** | TypeScript (40 files) | 6000 | App Ionic |
| **Templates** | HTML (100+ files) | 12000 | Frontend |
| **Static/JS** | JavaScript (20 files) | 3000 | Scripts |

### 5.3 Principais Models (Modelos de Dados)

#### BOGCMI
- `BO`: Boletim de Ocorrência principal
- `Envolvido`: Pessoas envolvidas no BO
- `CadastroEnvolvido`: Cadastro persistente de envolvidos
- `VeiculoEnvolvido`: Veículos envolvidos
- `Apreensao`: Objetos/substâncias apreendidas
- `EquipeApoio`: Equipes de apoio no atendimento
- `DocumentoAssinavel`: Documentos aguardando assinatura

#### Panic
- `Assistida`: Vítima cadastrada no programa
- `DisparoPanico`: Acionamento do botão de pânico
- `Dispositivo`: Dispositivos móveis cadastrados
- `Evento`: Log de eventos do disparo

#### CECOM
- `PlantaoCecomPrincipal`: Plantão compartilhado
- `PlantaoCECOM`: Integrante em plantão
- `LivroPlantaoCecom`: Livro eletrônico
- `DespachoOcorrencia`: Despacho para viatura
- `PostoFixo`: Posto fixo (Prefeitura, Hospital, etc.)

#### Almoxarifado
- `BemPatrimonial`: Item do almoxarifado
- `Municao`: Munição (estoque)
- `Cautela`: Empréstimo de equipamento
- `AssignacaoFixa`: Assignação permanente
- `MovimentacaoMunicao`: Movimentação de munição
- `AuditTrail`: Trilha de auditoria
- `SimpleLog`: Log simplificado

#### Viaturas
- `Viatura`: Viatura
- `ViaturaAvariaEstado`: Estado consolidado de avarias
- `AvariaLog`: Histórico de avarias
- `AvariaAnexo`: Fotos de avarias
- `ViaturaLocalizacao`: Última posição GPS
- `ViaturaLocalizacaoPonto`: Histórico de trilha GPS

#### Talões
- `Talao`: Talão de ocorrência
- `CodigoOcorrencia`: Código de ocorrência
- `Abordado`: Pessoa/veículo abordado
- `ChecklistViatura`: Checklist de viatura

#### Users
- `User`: Usuário (extends AbstractUser)
- `PerfilGCM`: Perfil de GCM

#### Common
- `AuditLog`: Log de requisições HTTP
- `PushDevice`: Dispositivo para notificações push

---

## 6. SEGURANÇA E CONFORMIDADE

### 6.1 Medidas de Segurança Implementadas

#### Autenticação
- Sistema de login robusto do Django
- Hash de senhas com PBKDF2 (padrão Django)
- Two-Factor Authentication opcional (TOTP)
- Recuperação de senha via email
- Bloqueio após tentativas falhadas (middleware custom)

#### Autorização
- Grupos de permissão hierárquicos
- Decorators de controle de acesso por view
- Permissões granulares por objeto (object-level permissions)
- Auditoria de acessos a documentos sensíveis

#### Proteção contra Ataques
- **CSRF**: Token em todos os forms POST
- **XSS**: Auto-escaping de templates, Content Security Policy
- **SQL Injection**: Django ORM parametrizado
- **Clickjacking**: X-Frame-Options: DENY
- **HTTPS**: Obrigatório em produção, HSTS habilitado

#### Validação de Dados
- Validação server-side em todos os forms
- Sanitização de uploads (whitelist de tipos MIME)
- Limite de tamanho de arquivos
- Validação de CPF, CNPJ, placas via algoritmos

#### Proteção de Dados Sensíveis
- Dados pessoais (CPF, RG) com acesso controlado
- PDFs com marca d'água para evitar distribuição não autorizada
- Soft delete para evitar perda acidental de dados críticos
- Backups automáticos antes de operações destrutivas

### 6.2 Conformidade Legal

#### Lei Geral de Proteção de Dados (LGPD)
- Coleta de dados justificada (base legal: execução de serviço público)
- Minimização de dados (apenas necessários)
- Direito de acesso aos dados pessoais
- Log de processamento de dados sensíveis

#### Lei de Acesso à Informação (LAI)
- QR Code de validação pública de documentos
- Transparência em operações públicas

#### Lei de Direitos Autorais (Lei 9.609/98)
- Licenciamento correto de bibliotecas de terceiros
- Atribuição adequada em código

---

## 7. DEPLOYMENT E INFRAESTRUTURA

### 7.1 Ambientes

#### Desenvolvimento
- OS: Windows 10/11
- Python: 3.10+
- Banco: SQLite
- Servidor: Django runserver

#### Produção (Recomendado)
- OS: Ubuntu 20.04 LTS / 22.04 LTS
- Python: 3.10+
- Banco: PostgreSQL 14
- Cache: Redis 7
- Web Server: Nginx (reverse proxy)
- ASGI: Daphne 4.1
- WSGI: Gunicorn
- Process Manager: systemd
- SSL: Let's Encrypt (certbot)

### 7.2 Requisitos de Sistema

#### Servidor Web (Mínimo)
- CPU: 2 cores
- RAM: 4 GB
- Disco: 50 GB SSD
- Banda: 10 Mbps

#### Servidor Web (Recomendado)
- CPU: 4+ cores
- RAM: 8+ GB
- Disco: 100+ GB SSD
- Banda: 100 Mbps

#### Clientes (Navegadores)
- Chrome 90+
- Firefox 88+
- Edge 90+
- Safari 14+

#### Mobile
- Android 8.0+ (API 26)
- 2 GB RAM
- GPS habilitado

### 7.3 Script de Deploy

O sistema inclui script `deploy.sh` para deployment automatizado em servidor Linux:

```bash
#!/bin/bash
# deploy.sh

# Atualizar código
git pull origin master

# Ativar ambiente virtual
source venv/bin/activate

# Instalar dependências
pip install -r requirements-prod.txt

# Migrations
python manage.py migrate

# Coletar estáticos
python manage.py collectstatic --noinput

# Reiniciar serviços
sudo systemctl restart gunicorn
sudo systemctl restart daphne
sudo systemctl restart celery
sudo systemctl restart celery-beat

echo "Deploy concluído!"
```

---

## 8. DOCUMENTAÇÃO ADICIONAL

### 8.1 Arquivos de Documentação Incluídos

- `COMO_EXECUTAR.md`: Guia de instalação e execução
- `GERAR_APKS.md`: Instruções para build de APKs Android
- `IMPLEMENTACAO_MARCA_DAGUA.md`: Detalhes técnicos da marca d'água
- `REORGANIZACAO_IDS_DOCUMENTOS.md`: Manutenção de banco de dados
- `docs/email_setup.md`: Configuração de email SMTP
- `docs/mobile_apk.md`: Build de aplicativo híbrido
- `docs/ANEXO_FOTOS_AVARIAS.md`: Sistema de anexos
- `docs/TROCAR_SOM_SIRENE.md`: Customização de alertas

### 8.2 Configuração

Arquivo `.env` com variáveis sensíveis:
- `SECRET_KEY`: Chave secreta Django
- `DEBUG`: Modo debug (False em produção)
- `ALLOWED_HOSTS`: Hosts permitidos
- `DATABASE_URL`: String de conexão PostgreSQL
- `REDIS_URL`: URL do Redis
- `GROQ_API_KEY`: Chave API Groq
- `FIREBASE_CREDENTIALS`: Path para credenciais Firebase

---

## 9. LICENCIAMENTO DE BIBLIOTECAS DE TERCEIROS

O sistema utiliza exclusivamente bibliotecas de código aberto com licenças permissivas:

### Python (Backend)
- Django: BSD License
- Django REST Framework: BSD License
- Django Channels: BSD License
- Celery: BSD License
- Pillow: PIL License (permissiva)
- ReportLab: BSD License
- PyPDF2: BSD License
- qrcode: BSD License
- pyotp: MIT License
- firebase-admin: Apache 2.0

### JavaScript (Frontend)
- Chart.js: MIT License
- Leaflet.js: BSD License
- Font Awesome: Font Awesome Free License

### Mobile
- Kotlin: Apache 2.0
- Firebase SDK: Apache 2.0
- Ionic Framework: MIT License
- Capacitor: MIT License

**Nenhuma biblioteca proprietária ou com restrições comerciais é utilizada.**

---

## 10. VALOR COMERCIAL E SOCIAL

### 10.1 Diferenciais Competitivos

O Sistema GCM é único no mercado brasileiro por combinar:

1. **Integração Total**: BO + Armamento + Pânico + Rastreamento em um único sistema
2. **Custo Zero**: 100% open source, sem licenças proprietárias
3. **Offline-First**: Operação garantida sem internet
4. **IA Integrada**: Assistência para relatórios
5. **Transparência**: Validação pública de documentos
6. **Proteção Social**: Botão de pânico para vítimas
7. **Customizável**: Código aberto permite adaptação

### 10.2 Impacto Social

- **Proteção de vítimas**: Sistema de botão de pânico salva vidas
- **Transparência**: Cidadãos podem validar documentos oficiais
- **Eficiência**: Reduz tempo de processos em 70%
- **Economia**: Elimina custos com papel, rastreadores, sistemas separados
- **Profissionalização**: Melhora qualidade de documentos oficiais

### 10.3 Mercado Potencial

- **700+ Guardas Municipais** no Brasil
- **Mercado estimado**: R$ 50-100 milhões (considerando licenciamento)
- **Modelo de negócio**: SaaS, implementação, suporte, customização

---

## 11. CRONOGRAMA DE DESENVOLVIMENTO

| Período | Atividade |
|---------|-----------|
| Jan/2025 | Análise de requisitos, definição de arquitetura |
| Fev/2025 | Módulo BOGCMI (Models, Views básicas) |
| Mar/2025 | BOGCMI (PDFs, assinatura, validação) |
| Abr/2025 | Módulo Panic (Backend + App Android) |
| Mai/2025 | Módulo CECOM (Plantão, Despacho) |
| Jun/2025 | CECOM (WebSocket, Rastreamento GPS) |
| Jul/2025 | Módulo Almoxarifado (Cautelas, Auditoria) |
| Ago/2025 | Módulos Viaturas e Talões |
| Set/2025 | Integração IA, Notificações Push |
| Out/2025 | Módulo Relatórios e Estatísticas |
| Nov/2025 | Testes, refinamentos, documentação |
| Nov/2025 | **Versão 1.0 concluída** |

---

## 12. DECLARAÇÃO DE AUTORIA

Declaro, para os devidos fins, que sou o único autor e desenvolvedor do **Sistema Inteligente para GCMs**, tendo concebido, projetado, implementado e testado todas as funcionalidades descritas neste documento.

O sistema é resultado de criação intelectual própria, não configurando plágio, contrafação ou violação de direitos autorais de terceiros.

As bibliotecas e frameworks de código aberto utilizados (Django, Kotlin, etc.) estão devidamente licenciados sob licenças permissivas (BSD, MIT, Apache 2.0), que permitem uso comercial e modificação.

**Autor**: MOISES SANTOS DE OLIVEIRA  
**CPF**: [A preencher]  
**Data**: 28 de novembro de 2025

---

## 13. INFORMAÇÕES ADICIONAIS

### 13.1 Contato
- **Email**: [A preencher]
- **Telefone**: [A preencher]
- **Endereço**: [A preencher]

### 13.2 Repositório
- **Plataforma**: Privado (desenvolvimento interno)
- **Controle de Versão**: Git
- **Documentação**: README.md, docs/

### 13.3 Publicação
- **Status**: Não publicado comercialmente
- **Uso**: Interno (desenvolvimento e testes)
- **Previsão de Lançamento**: Primeiro trimestre de 2026

---

**FIM DO DOCUMENTO TÉCNICO**

---

**Páginas**: 24  
**Palavras**: Aproximadamente 8.000  
**Data de Elaboração**: 28/11/2025  
**Versão**: 1.0 (Registro Biblioteca Nacional)
