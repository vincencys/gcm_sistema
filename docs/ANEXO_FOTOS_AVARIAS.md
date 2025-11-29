# Funcionalidade de Anexos de Fotos em Avarias

## Resumo
Sistema implementado para permitir anexar fotos/arquivos aos itens marcados no checklist de viatura. As fotos aparecem na página de avarias da viatura.

## Como Usar

### 1. No Checklist de Viatura
1. Acesse o checklist durante o plantão
2. Marque qualquer item que tenha avaria/problema
3. Ao marcar um checkbox, aparecerá a opção "📎 Anexar Foto"
4. Clique no botão de anexo
5. Escolha uma foto (câmera ou galeria no mobile)
6. A foto será enviada e aparecerá como miniatura
7. Para remover, clique no "×" vermelho na miniatura

### 2. Visualizando na Página de Avarias
1. Acesse: Menu Viaturas → Selecionar viatura → Ver Avarias
2. Os itens marcados aparecem na lista
3. Se houver fotos anexadas, elas aparecem abaixo do item como miniaturas
4. Clique na foto para abrir em tamanho completo

## Implementação Técnica

### Arquivos Modificados/Criados

#### 1. Modelo de Dados (`taloes/models.py`)
```python
class AvariaAnexo(models.Model):
    checklist = models.ForeignKey(ChecklistViatura, related_name='anexos')
    campo_avaria = models.CharField(max_length=100)  # ex: "farol_dianteiro"
    arquivo = models.FileField(upload_to='avarias/%Y/%m/')
    descricao = models.CharField(max_length=255, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
```

#### 2. Views API AJAX (`taloes/views_extra.py`)
- `upload_anexo_avaria`: Recebe POST com arquivo e campo_avaria
- `remover_anexo_avaria`: Deleta anexo (com verificação de permissão)

#### 3. URLs (`taloes/urls.py`)
```python
path('avaria/anexo/upload/', views_extra.upload_anexo_avaria, name='upload_anexo_avaria'),
path('avaria/anexo/<int:anexo_id>/remover/', views_extra.remover_anexo_avaria, name='remover_anexo_avaria'),
```

#### 4. Template Checklist (`templates/taloes/checklist_viatura.html`)
- JavaScript para detectar checkbox marcado
- Botão de upload com `capture="environment"` para câmera mobile
- Preview de miniaturas
- AJAX para upload/delete sem reload

#### 5. View de Avarias (`viaturas/views.py`)
- Busca `AvariaAnexo` dos checklists do dia
- Agrupa por `campo_avaria` em `anexos_map`
- Passa para o template

#### 6. Template Avarias (`templates/viaturas/avarias.html`)
- Exibe fotos em grid 20x20
- Link para abrir em nova aba
- Mostra descrição se houver

#### 7. Template Tag (`viaturas/templatetags/viaturas_extras.py`)
- Filter `get_item` para acessar dicionário no template

### Migration
```bash
python manage.py makemigrations  # Criou taloes/migrations/0014_avariaanexo.py
python manage.py migrate         # Aplicou ao banco
```

## Estrutura de Arquivos
```
media/
  avarias/
    2025/
      01/
        foto1.jpg
        foto2.jpg
```

## Recursos
- ✅ Upload de fotos via AJAX
- ✅ Captura de câmera em dispositivos mobile
- ✅ Preview de miniaturas após upload
- ✅ Remoção de anexos
- ✅ Validação de permissões (apenas dono ou superuser)
- ✅ Exibição na página de avarias
- ✅ Organização por ano/mês
- ✅ Link para visualizar foto em tamanho completo

## Testes
Execute o script de teste:
```bash
python teste_anexo_avaria.py
```

## Fluxo Completo
1. Guarda marca avaria no checklist → anexa foto
2. Foto fica vinculada ao campo específico do checklist
3. Na página de avarias da viatura, as fotos aparecem agrupadas por item
4. Histórico permanece mesmo após resolver a avaria
5. Anexos podem ser removidos a qualquer momento

## Notas Importantes
- Fotos ficam vinculadas ao checklist do dia
- Mesmo após resolver a avaria, as fotos continuam visíveis no histórico
- Apenas o usuário que fez o upload ou superusers podem remover anexos
- Arquivos são salvos em `MEDIA_ROOT/avarias/YYYY/MM/`
- Formato suportado: qualquer formato de imagem aceito pelo navegador
