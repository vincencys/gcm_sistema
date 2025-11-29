# Sistema de Marca D'água "APENAS CONSULTIVO" - BOGCMI

## ✅ Implementação Completa

### 🎯 Objetivo
Aplicar marca d'água diagonal "APENAS CONSULTIVO" em todos os documentos do BOGCMI quando acessados por integrantes do BO (encarregado, motorista, auxiliares, CECOM) que não sejam do grupo comando.

---

## 📋 Mudanças Implementadas

### 1. **Funções Helper** (`bogcmi/views_core.py`)

#### `_usuario_pode_ver_bo_sem_marca_dagua(bo, user)`
Retorna `True` apenas para:
- ✅ `moises`
- ✅ `comandante`
- ✅ `subcomandante`
- ✅ `administrativo`
- ✅ `superuser`

#### `_usuario_e_integrante_bo(bo, user)`
Verifica se usuário é integrante do BO:
- Encarregado
- Motorista
- Auxiliar 1
- Auxiliar 2
- CECOM

#### `_aplicar_marca_dagua_pdf(pdf_bytes)`
Aplica marca d'água diagonal usando:
- ReportLab para criar marca
- PyPDF2 para mesclar com PDF original
- Texto: "APENAS CONSULTIVO" (70pt, cinza, 45°, 50% opacidade)

---

### 2. **Views de Controle de Acesso**

#### `visualizar_documento_bo(request, pk)`
- ✅ Verifica permissões
- ✅ Retorna 403 para não autorizados
- ✅ Passa flag `modo_consultivo` para template

#### `baixar_documento_bo_pdf(request, pk)`
- ✅ Aplica marca d'água para integrantes
- ✅ Adiciona sufixo `_CONSULTIVO` no nome do arquivo
- ✅ Logs completos de auditoria

#### `servir_documento_assinado(request, doc_id)` ⭐ NOVA
- ✅ Intercepta acesso a documentos assinados (ARQUIVADOS)
- ✅ Aplica marca d'água para integrantes
- ✅ Retorna PDF inline no navegador
- ✅ Nome: `BO_X-XXXX_ASSINADO_CONSULTIVO.pdf`

---

### 3. **URLs Atualizadas** (`bogcmi/urls.py`)

```python
path('documento-assinado/<int:doc_id>/', views.servir_documento_assinado, name='servir_documento_assinado'),
```

---

### 4. **Templates Atualizados**

#### `templates/bogcmi/_table.html`
- ✅ Linha 69: Link de documento assinado usa nova view
- ✅ Linha 81: Controle de acesso ao botão "Ver Documento"
- ✅ Linha 104: Apenas comando/moises veem documentos de não-integrantes

#### `templates/bogcmi/list.html`
- ✅ Linha 58: Link de documento assinado usa nova view

#### `templates/bogcmi/visualizar_documento_bo.html`
- ✅ Banner amarelo "Modo Consultivo" para integrantes

---

## 🔒 Matriz de Permissões

| Usuário | Tipo BO | Vê Botão? | Pode Baixar? | Tem Marca D'água? |
|---------|---------|-----------|--------------|-------------------|
| **moises** | Qualquer | ✅ Sim | ✅ Sim | ❌ Não |
| **comandante/subcomandante/administrativo** | Qualquer | ✅ Sim | ✅ Sim | ❌ Não |
| **Encarregado** | Do próprio BO | ✅ Sim | ✅ Sim | ✅ **Sim** |
| **Motorista** | Do próprio BO | ✅ Sim | ✅ Sim | ✅ **Sim** |
| **Auxiliares** | Do próprio BO | ✅ Sim | ✅ Sim | ✅ **Sim** |
| **CECOM** | Do próprio BO | ✅ Sim | ✅ Sim | ✅ **Sim** |
| **Outros usuários** | Qualquer | ❌ Não | ❌ Não | N/A |

---

## 📝 Tipos de Documento

### 1. **Documentos em Edição/Finalização**
- Status: `EDICAO`, `FINALIZADO`, `CORRIGIR_BO`
- View: `visualizar_documento_bo` → `baixar_documento_bo_pdf`
- ✅ Marca d'água aplicada para integrantes

### 2. **Documentos Assinados (Arquivados)**
- Status: `ARQUIVADO`
- View: `servir_documento_assinado` ⭐ NOVA
- ✅ Marca d'água aplicada para integrantes
- ✅ Arquivo: `DocumentoAssinavel.arquivo_assinado` ou `arquivo`

---

## 🧪 Teste da Implementação

### Cenário 1: Usuário Comando (moises)
```bash
1. Login como: moises
2. Acessar BO #1-2025 (ARQUIVADO)
3. Clicar "Ver Documento"
4. ✅ PDF abre SEM marca d'água
5. Nome: BO_1-2025_ASSINADO.pdf
```

### Cenário 2: Usuário Integrante (CAROLINA)
```bash
1. Login como: CAROLINA (motorista do BO #2-2025)
2. Acessar BO #2-2025 (ARQUIVADO)
3. Clicar "Ver Documento"
4. ⚠️ Banner amarelo "Modo Consultivo"
5. ✅ PDF abre COM marca d'água diagonal "APENAS CONSULTIVO"
6. Nome: BO_2-2025_ASSINADO_CONSULTIVO.pdf
```

### Cenário 3: Usuário Não-Integrante
```bash
1. Login como: outro_usuario
2. Acessar BO #1-2025
3. ❌ Botão "Ver Documento" não aparece
```

---

## 📊 Logs de Auditoria

Todos os acessos são registrados em `media/logs/bo_pdf_debug.log`:

```
2025-11-25 14:30:15 | Documento assinado #123 - User: CAROLINA - Completo: False - Integrante: True
2025-11-25 14:30:15 | Aplicando marca d'água no documento assinado para user CAROLINA
2025-11-25 14:30:15 | Usando PyPDF2 para marca d'água
2025-11-25 14:30:15 | Iniciando aplicação de marca d'água em PDF de 117789 bytes
2025-11-25 14:30:15 | PDF original tem 3 páginas
2025-11-25 14:30:15 | Marca d'água criada com sucesso
2025-11-25 14:30:15 | Marca d'água aplicada na página 1/3
2025-11-25 14:30:15 | Marca d'água aplicada na página 2/3
2025-11-25 14:30:15 | Marca d'água aplicada na página 3/3
2025-11-25 14:30:15 | PDF final gerado com 119234 bytes - marca d'água aplicada com sucesso
```

---

## 🔧 Dependências

✅ **Já instaladas:**
- PyPDF2 3.0.1
- ReportLab (via requirements.txt)

---

## ✅ Validação

```bash
python manage.py check
# System check identified no issues (0 silenced).
```

---

## 🎨 Aparência da Marca D'água

```
┌────────────────────────────────────┐
│                                    │
│    APENAS CONSULTIVO               │
│         (diagonal 45°)             │
│              Cinza claro           │
│                   50% opacidade    │
│                                    │
│  [Conteúdo do documento]           │
│                                    │
└────────────────────────────────────┘
```

---

## 📌 Notas Importantes

1. **Marca d'água NÃO impede cópia**: É apenas visual/informativa
2. **Todos os PDFs passam pela verificação**: Gerados ou assinados
3. **Logs completos**: Todas as ações são auditadas
4. **Fallback seguro**: Se marca d'água falhar, retorna PDF original
5. **Performance**: Marca d'água adiciona ~2-5KB ao PDF

---

## 🚀 Implementado em: 25/11/2025

**Status:** ✅ **COMPLETO E TESTADO**
