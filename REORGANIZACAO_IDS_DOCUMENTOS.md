# Reorganização de IDs - DocumentoAssinavel

## 📋 Problema Identificado

**Situação**: IDs fragmentados na tabela `common_documentoassinavel`
- Exemplo: ID 256 quando existem apenas 2 documentos
- Causa: Funções `recusar_documento` e `excluir_documento` deletam registros permanentemente
- Lacunas: 253 IDs sem uso (1-253 vazios, apenas 254-255 existem)

**Screenshot do Usuário**: IDs mostrados nas telas eram 254, 255, 256 quando deveriam ser 1, 2, 3.

---

## ✅ Solução Implementada

### Comando de Gerenciamento Django

**Arquivo**: `common/management/commands/reorganizar_ids_documentos.py`

**Funcionalidades**:
- ✅ Backup automático da tabela antes de modificar
- ✅ Reorganiza IDs sequencialmente (1, 2, 3, ...)
- ✅ Preserva ordem cronológica (`created_at`)
- ✅ Mantém todos os dados e relacionamentos intactos
- ✅ Atualiza sequência do SQLite
- ✅ Modo dry-run para preview sem aplicar mudanças
- ✅ Filtro opcional por tipo de documento
- ✅ Transação atômica (reverte tudo em caso de erro)
- ✅ Estatísticas detalhadas por tipo

---

## 🔧 Uso do Comando

### 1. Preview (Dry-Run)
```bash
python manage.py reorganizar_ids_documentos --dry-run
```

**Saída Exemplo**:
```
📊 SITUAÇÃO ATUAL:
   Total de documentos: 2
   IDs atuais: [254, 255]
   Maior ID: 255
   Lacunas encontradas: 253 (IDs: [1, 2, 3, 4, 5, ...])

🎯 RESULTADO ESPERADO:
   IDs reorganizados: [1, 2]
   Sem lacunas, sequência contínua de 1 até 2

📋 PREVIEW DAS MUDANÇAS:
  ID Atual → ID Novo    Tipo            Criado em            Status
--------------------------------------------------------------------------------
       254 → 1          Livro CECOM     25/11/2025 14:43     Pendente Assinatura...
       255 → 2          Relatório...    25/11/2025 14:45     Pendente Assinatura...
```

### 2. Reorganizar Todos os Documentos
```bash
python manage.py reorganizar_ids_documentos
```

### 3. Reorganizar Apenas um Tipo
```bash
# Apenas BOGCMIs
python manage.py reorganizar_ids_documentos --tipo BOGCMI

# Apenas Relatórios de Plantão
python manage.py reorganizar_ids_documentos --tipo PLANTAO

# Apenas Livros CECOM
python manage.py reorganizar_ids_documentos --tipo LIVRO_CECOM
```

---

## 📊 Resultado da Execução (25/11/2025)

### Antes da Reorganização
```
📊 SITUAÇÃO ATUAL:
   Total de documentos: 2
   IDs atuais: [254, 255]
   Maior ID: 255
   Lacunas encontradas: 253
```

### Processo de Reorganização
```bash
$ echo "SIM" | python manage.py reorganizar_ids_documentos

📦 Criando backup da tabela...
   ✓ Backup criado: 2 registros salvos

🔄 Coletando dados dos documentos...
   ✓ 2 documentos coletados

🗑️  Removendo documentos da tabela...
   ✓ Documentos removidos temporariamente

🔢 Resetando sequência de IDs...
   ✓ Sequência resetada para 0

💾 Reinserindo documentos com IDs sequenciais...
   ✓ 2 documentos reinseridos
   ✓ Sequência atualizada para 2

✅ SUCESSO! 2 documentos reorganizados
   IDs agora vão de 1 até 2
```

### Após a Reorganização
```
🔍 Verificando resultado...
   ✓ IDs estão sequenciais sem lacunas
   ✓ Sequência SQLite: 2

📈 ESTATÍSTICAS POR TIPO:
   Relatório de Plantão: 1 documentos (IDs: [2])
   Livro CECOM: 1 documentos (IDs: [1])
```

---

## 🔒 Segurança

### Backups Automáticos
1. **Backup do banco completo** (manual):
   ```bash
   db_backup_reorganizacao_20251125_144530.sqlite3
   ```

2. **Backup da tabela** (automático pelo comando):
   ```sql
   CREATE TABLE common_documentoassinavel_backup AS 
   SELECT * FROM common_documentoassinavel
   ```

### Transação Atômica
- Todas as operações dentro de `transaction.atomic()`
- Se qualquer erro ocorrer, TODAS as mudanças são revertidas
- Banco permanece no estado original em caso de falha

### Verificações de Segurança
- ✅ Nenhuma tabela tem ForeignKey apontando para DocumentoAssinavel
- ✅ Arquivos físicos não dependem dos IDs (usam timestamp/número BO)
- ✅ URLs não expõem IDs publicamente

---

## 🏗️ Como Funciona Internamente

### Estrutura do DocumentoAssinavel
```python
class DocumentoAssinavel(TimeStamped):
    id = BigAutoField (auto-incremento)
    tipo = CharField (PLANTAO, BOGCMI, LIVRO_CECOM)
    status = CharField (PENDENTE, ASSINADO, ...)
    usuario_origem = ForeignKey(User)
    arquivo = FileField(upload_to='documentos/origem/')
    arquivo_assinado = FileField(upload_to='documentos/assinados/')
    # ... outros campos
```

### Processo de Reorganização (Passo a Passo)

1. **Coleta de Documentos**
   - Busca todos os documentos (ou filtrados por tipo)
   - Ordena por `created_at` (preserva cronologia)
   - Armazena em memória com todos os dados

2. **Backup**
   - Cria tabela `common_documentoassinavel_backup`
   - Copia todos os registros atuais

3. **Limpeza Temporária**
   - Remove documentos da tabela original
   - Reseta sequência do SQLite para 0

4. **Reinserção Sequencial**
   - Insere documentos um por um
   - IDs começam em 1 e incrementam sequencialmente
   - Preserva todos os dados originais

5. **Atualização da Sequência**
   - Define `sqlite_sequence.seq` para o último ID usado
   - Próximos documentos continuarão da sequência correta

---

## 🎯 Por Que os IDs Ficam Fragmentados?

### Funções que Deletam Documentos

#### 1. `recusar_documento()` (common/views.py:1073)
```python
@comando_required
def recusar_documento(request: HttpRequest, pk: int):
    doc.delete()  # DELETE PERMANENTE
    messages.success(request, f'Documento #{pk} recusado')
```
**Cenário**: Comando recusa BO → documento deletado → lacuna no ID

#### 2. `excluir_documento()` (common/views.py:1085)
```python
@comando_required
def excluir_documento(request: HttpRequest, pk: int):
    """Somente superadmin 'moises' pode excluir."""
    doc.delete()  # DELETE PERMANENTE
```
**Cenário**: Moises exclui documento → lacuna no ID

### Como SQLite Gerencia IDs

```sql
-- Tabela de sequência do SQLite
SELECT * FROM sqlite_sequence WHERE name='common_documentoassinavel';
-- Resultado: (name, seq) onde seq = último ID usado (ex: 255)

-- Próximo INSERT usa: seq + 1 = 256
-- IDs deletados NÃO são reutilizados
```

**Exemplo**:
- Documentos criados: IDs 1, 2, 3, 4, 5
- Deletados: 1, 2, 3, 4
- Próximo documento: ID **6** (não reutiliza 1-4)
- Resultado: Apenas 2 documentos existem (5 e 6)

---

## 💡 Prevenção de Fragmentação Futura

### Opção 1: Soft Delete (Recomendado)
Em vez de deletar permanentemente, marcar como deletado:

```python
class DocumentoAssinavel(TimeStamped):
    # Adicionar campo
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # Custom manager
    objects = SoftDeleteManager()  # Filtra deleted_at=NULL

# Modificar funções
def recusar_documento(request, pk):
    doc.deleted_at = timezone.now()
    doc.save()  # Soft delete
```

**Benefício**: IDs nunca são "perdidos", apenas marcados como deletados

### Opção 2: Reorganização Periódica
- Executar comando mensalmente via cron
- Apenas quando fragmentação > 50%
- Automatizar com script

### Opção 3: Aceitar Fragmentação
- IDs são apenas identificadores internos
- Não afetam funcionalidade
- Reorganizar apenas quando necessário

---

## 📝 Checklist de Execução

Antes de executar em produção:

- [ ] ✅ Fazer backup do banco completo
- [ ] ✅ Executar em modo `--dry-run` primeiro
- [ ] ✅ Verificar preview das mudanças
- [ ] ✅ Parar servidor Django
- [ ] ✅ Executar comando de reorganização
- [ ] ✅ Verificar logs de sucesso
- [ ] ✅ Reiniciar servidor
- [ ] ✅ Testar acesso aos documentos
- [ ] ✅ Verificar que arquivos PDF continuam acessíveis
- [ ] ✅ Confirmar IDs sequenciais nas telas

---

## 🚨 Troubleshooting

### Erro: "not all arguments converted during string formatting"
**Causa**: Placeholders SQL incorretos (?, %s)  
**Solução**: Django usa `%s` para SQLite, não `?`

### Erro: "Transaction rolled back"
**Causa**: Erro durante reinserção  
**Solução**: Verificar logs, banco volta ao estado original automaticamente

### Documentos com IDs errados após reorganização
**Causa**: Cache do navegador  
**Solução**: Force refresh (Ctrl+F5) ou limpar cache

---

## 📅 Histórico de Execução

### 25/11/2025 - Primeira Reorganização
- **Antes**: IDs 254, 255 (253 lacunas)
- **Depois**: IDs 1, 2 (sem lacunas)
- **Documentos afetados**: 2 (1 CECOM, 1 Plantão)
- **Tempo de execução**: < 1 segundo
- **Status**: ✅ Sucesso

---

## 🎓 Aprendizados

1. **SQLite não reutiliza IDs**: Auto-increment sempre incrementa
2. **Soft delete é melhor**: Evita fragmentação permanente
3. **Backups são essenciais**: Sempre criar antes de modificar estrutura
4. **Transações atômicas**: Protegem contra falhas parciais
5. **Dry-run é crucial**: Permite validar antes de aplicar

---

## 📚 Referências

- [Django Management Commands](https://docs.djangoproject.com/en/5.0/howto/custom-management-commands/)
- [SQLite Autoincrement](https://www.sqlite.org/autoinc.html)
- [Django Transactions](https://docs.djangoproject.com/en/5.0/topics/db/transactions/)

---

**Status**: ✅ **IMPLEMENTADO E TESTADO**  
**Data**: 25/11/2025  
**Autor**: Sistema GCM
