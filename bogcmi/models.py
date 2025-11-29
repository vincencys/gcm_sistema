from django.db import models
class Anexo(models.Model):
    # Pode ser um anexo geral do BO (bo) ou um anexo de Envolvido específico
    bo = models.ForeignKey('BO', on_delete=models.CASCADE, related_name='anexos_gerais', null=True, blank=True)
    envolvido = models.ForeignKey('Envolvido', on_delete=models.CASCADE, related_name='anexos', null=True, blank=True)
    descricao = models.CharField(max_length=120)
    arquivo = models.FileField(upload_to='anexos/')
    def __str__(self):
        return f"{self.descricao} ({self.arquivo.name})"
from django.db import models

def _normalize_cpf(cpf: str) -> str:
    try:
        return ''.join([c for c in (cpf or '') if c.isdigit()])
    except Exception:
        return ''

class CadastroEnvolvido(models.Model):
    """Cadastro persistente de pessoas envolvidas, indexado por CPF.

    Mantém dados principais para auto-preenchimento ao criar novos Envolvidos.
    """
    nome = models.CharField(max_length=120)
    nome_social = models.CharField(max_length=120, blank=True)
    telefone = models.CharField(max_length=30, blank=True)
    cep = models.CharField(max_length=20, blank=True)
    endereco = models.CharField(max_length=120, blank=True)
    numero = models.CharField(max_length=20, blank=True)
    ponto_referencia = models.CharField(max_length=120, blank=True)
    bairro = models.CharField(max_length=60, blank=True)
    uf = models.CharField(max_length=2, default='SP', blank=True)
    cidade = models.CharField(max_length=60, default='IBIUNA', blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    estado_civil = models.CharField(max_length=30, blank=True)
    pais_natural = models.CharField(max_length=60, default='Brasil', blank=True)
    uf_natural = models.CharField(max_length=2, default='SP', blank=True)
    cidade_natural = models.CharField(max_length=60, default='IBIUNA', blank=True)
    rg = models.CharField(max_length=30, blank=True)
    cpf = models.CharField(max_length=20, blank=True)
    cpf_normalizado = models.CharField(max_length=20, unique=True, db_index=True)
    outro_documento = models.CharField(max_length=60, blank=True)
    cnh = models.CharField(max_length=30, blank=True)
    categoria_cnh = models.CharField(max_length=10, blank=True)
    data_validacao_cnh = models.DateField(null=True, blank=True)
    cutis = models.CharField(max_length=30, blank=True)
    genero = models.CharField(max_length=30, blank=True)
    profissao = models.CharField(max_length=60, blank=True)
    trabalho = models.CharField(max_length=120, blank=True)
    vulgo = models.CharField(max_length=60, blank=True)
    nome_pai = models.CharField(max_length=120, blank=True)
    nome_mae = models.CharField(max_length=120, blank=True)
    sinais = models.TextField(blank=True)
    dados_adicionais = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        # Garante índice consistente por CPF (somente dígitos)
        self.cpf_normalizado = _normalize_cpf(self.cpf)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nome} ({self.cpf})"

class Envolvido(models.Model):
    bo = models.ForeignKey('BO', on_delete=models.CASCADE, related_name='envolvidos_bo', null=True, blank=True)
    cadastro = models.ForeignKey('CadastroEnvolvido', on_delete=models.SET_NULL, related_name='registros', null=True, blank=True, help_text='Cadastro base (auto-preenchimento por CPF).')
    nome = models.CharField(max_length=120)
    nome_social = models.CharField(max_length=120, blank=True)
    telefone = models.CharField(max_length=30, blank=True)
    condicao = models.CharField(max_length=60)
    outra_condicao = models.CharField(max_length=60, blank=True)
    cep = models.CharField(max_length=20, blank=True)
    endereco = models.CharField(max_length=120, blank=True)
    numero = models.CharField(max_length=20, blank=True)
    ponto_referencia = models.CharField(max_length=120, blank=True)
    bairro = models.CharField(max_length=60, blank=True)
    uf = models.CharField(max_length=2, default='SP')
    cidade = models.CharField(max_length=60, default='IBIUNA', blank=True)
    data_nascimento = models.DateField(null=True, blank=True)
    estado_civil = models.CharField(max_length=30, blank=True)
    pais_natural = models.CharField(max_length=60, default='Brasil', blank=True)
    uf_natural = models.CharField(max_length=2, default='SP')
    cidade_natural = models.CharField(max_length=60, default='IBIUNA', blank=True)
    rg = models.CharField(max_length=30, blank=True)
    cpf = models.CharField(max_length=20, blank=True)
    outro_documento = models.CharField(max_length=60, blank=True)
    matricula = models.CharField(max_length=30, blank=True)
    razao_social = models.CharField(max_length=120, blank=True)
    cnpj = models.CharField(max_length=30, blank=True)
    cnh = models.CharField(max_length=30, blank=True)
    categoria_cnh = models.CharField(max_length=10, blank=True)
    data_validacao_cnh = models.DateField(null=True, blank=True)
    cutis = models.CharField(max_length=30, blank=True)
    genero = models.CharField(max_length=30, blank=True)
    profissao = models.CharField(max_length=60, blank=True)
    trabalho = models.CharField(max_length=120, blank=True)
    vulgo = models.CharField(max_length=60, blank=True)
    nome_pai = models.CharField(max_length=120, blank=True)
    nome_mae = models.CharField(max_length=120, blank=True)
    sinais = models.TextField(blank=True)
    dados_adicionais = models.TextField(blank=True)
    providencia = models.CharField(max_length=60, blank=True)
    assinatura = models.ImageField(upload_to='assinaturas/', blank=True, null=True)
    def __str__(self):
        return f"{self.nome} ({self.cpf})"
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from common.models import TimeStamped
import uuid
User = get_user_model()

class SequenciaBO(models.Model):
    ano = models.IntegerField()
    valor = models.IntegerField(default=0)
    class Meta: unique_together = ('ano',)
    def __str__(self): return f'{self.ano}:{self.valor}'

class BO(TimeStamped):
    numero = models.CharField(max_length=30, unique=True, blank=True)
    emissao = models.DateTimeField(default=timezone.now)
    natureza = models.CharField(max_length=120)
    cod_natureza = models.CharField(max_length=20, blank=True)
    # Identificador local (offline) para permitir sincronização posterior.
    client_uuid = models.UUIDField(null=True, blank=True, unique=True)
    offline = models.BooleanField(default=False, help_text="Marcado como True se criado offline e ainda não sincronizado plenamente.")
    synced_at = models.DateTimeField(null=True, blank=True)
    solicitante = models.CharField(max_length=120, blank=True)
    endereco = models.CharField(max_length=200, blank=True)
    bairro = models.CharField(max_length=120, blank=True)
    encarregado = models.ForeignKey(User, on_delete=models.PROTECT, related_name='bos_enc')
    viatura = models.ForeignKey('viaturas.Viatura', null=True, on_delete=models.SET_NULL)
    motorista = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='bos_motorista')
    auxiliar1 = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='bos_aux1')
    auxiliar2 = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='bos_aux2')
    cecom = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='bos_cecom')
    envolvidos = models.TextField(blank=True)
    providencias = models.TextField(blank=True)
    cidade = models.CharField(max_length=60, default='IBIUNA', blank=True)
    uf = models.CharField(max_length=2, default='SP', blank=True)
    numero_endereco = models.CharField(max_length=20, blank=True)
    rua = models.CharField(max_length=120, blank=True)
    referencia = models.CharField(max_length=120, blank=True)
    # Deslocamento & Tempo
    km_inicio = models.IntegerField(null=True, blank=True)
    km_final = models.IntegerField(null=True, blank=True)
    horario_inicial = models.TimeField(null=True, blank=True)
    horario_final = models.TimeField(null=True, blank=True)
    duracao = models.CharField(max_length=5, blank=True, help_text="HH:MM")
    # Finalização
    numero_bopc = models.CharField(max_length=50, blank=True)
    numero_tco = models.CharField(max_length=50, blank=True)
    autoridade_policial = models.CharField(max_length=120, blank=True)
    escrivao = models.CharField(max_length=120, blank=True)
    algemas = models.CharField(max_length=10, blank=True)
    grande_vulto = models.CharField(max_length=10, blank=True)
    local_finalizacao = models.CharField(max_length=120, blank=True)
    flagrante = models.CharField(max_length=10, blank=True)
    status = models.CharField(max_length=16, default='EDICAO', choices=[
        ('EDICAO','Aberto (edição)'),
        ('FINALIZADO','Finalizado'),
        ('DESPACHO_CMT','Despacho CMT'),
        ('CORRIGIR_BO','Corrigir BO'),
        ('ARQUIVADO','Arquivado'),
    ])
    finalizado_em = models.DateTimeField(null=True, blank=True)
    edit_deadline = models.DateTimeField(null=True, blank=True)
    documento_html = models.TextField(blank=True)
    # Validação / QR Code
    validacao_token = models.CharField(max_length=40, blank=True, help_text="Token público para validação do documento")
    validacao_hash = models.CharField(max_length=64, blank=True, help_text="Hash interno para integridade")
    talao = models.ForeignKey('taloes.Talao', null=True, blank=True, on_delete=models.SET_NULL, related_name='bos', help_text='Talão de origem (se criado a partir de um talão).')
class Apreensao(models.Model):
    descricao = models.CharField(max_length=255)
    unidade_medida = models.CharField(max_length=50)
    bo = models.ForeignKey('BO', on_delete=models.CASCADE, related_name='apreensoes')
    quantidade = models.PositiveIntegerField()
    destino = models.CharField(max_length=100)
    recebedor = models.CharField(max_length=100)

class AnexoApreensao(models.Model):
    apreensao = models.ForeignKey(Apreensao, related_name='anexos', on_delete=models.CASCADE)
    descricao = models.CharField(max_length=255)
    arquivo = models.FileField(upload_to='apreensoes/')

class VeiculoEnvolvido(models.Model):
    bo = models.ForeignKey('BO', on_delete=models.CASCADE, related_name='veiculos', null=True, blank=True)
    SEMAFORO_CHOICES = [
        ('funcionando', 'Funcionando'),
        ('nao_funcionando', 'Não Funcionando'),
        ('intermitente', 'Intermitente'),
        ('nao_ha', 'Não Há'),
    ]
    
    TIPO_PISTA_CHOICES = [
        ('seca', 'Seca'),
        ('molhada', 'Molhada'),
        ('oleosa', 'Oleosa'),
        ('com_lama', 'Com Lama'),
        ('com_areia', 'Com Areia'),
    ]
    
    TIPO_ACIDENTE_CHOICES = [
        ('colisao_traseira', 'Colisão Traseira'),
        ('colisao_frontal', 'Colisão Frontal'),
        ('colisao_lateral', 'Colisão Lateral'),
        ('abalroamento', 'Abalroamento'),
        ('capotamento', 'Capotamento'),
        ('tombamento', 'Tombamento'),
        ('atropelamento', 'Atropelamento'),
        ('saida_pista', 'Saída de Pista'),
    ]
    
    TEMPO_CHOICES = [
        ('sol', 'Sol'),
        ('chuva', 'Chuva'),
        ('garoa', 'Garoa'),
        ('nevoeiro', 'Nevoeiro'),
        ('vento', 'Vento'),
        ('nublado', 'Nublado'),
    ]
    
    ILUMINACAO_CHOICES = [
        ('plena', 'Plena'),
        ('escuridao', 'Escuridão'),
        ('amanhecer', 'Amanhecer'),
        ('anoitecer', 'Anoitecer'),
        ('iluminacao_publica', 'Iluminação Pública'),
    ]
    
    SITUACAO_VEICULO_CHOICES = [
        ('circulando', 'Circulando'),
        ('estacionado', 'Estacionado'),
        ('parado_via', 'Parado na Via'),
        ('em_manobra', 'Em Manobra'),
        ('fugiu', 'Fugiu do Local'),
    ]
    
    # Dados do veículo
    marca = models.CharField(max_length=50)
    modelo = models.CharField(max_length=100)
    placa = models.CharField(max_length=10, blank=True)
    renavam = models.CharField(max_length=20, blank=True)
    numero_chassi = models.CharField(max_length=30, blank=True)
    numero_motor = models.CharField(max_length=30, blank=True)
    placa_cidade = models.CharField(max_length=100, blank=True)
    placa_estado = models.CharField(max_length=2, default='SP')
    cor = models.CharField(max_length=30, blank=True)
    ano_modelo = models.CharField(max_length=4, blank=True)
    ano_fabricacao = models.CharField(max_length=4, blank=True)
    
    # Condições do acidente
    semaforo = models.CharField(max_length=20, choices=SEMAFORO_CHOICES, blank=True)
    tipo_pista = models.CharField(max_length=20, choices=TIPO_PISTA_CHOICES, blank=True)
    tipo_acidente = models.CharField(max_length=30, choices=TIPO_ACIDENTE_CHOICES, blank=True)
    tempo = models.CharField(max_length=20, choices=TEMPO_CHOICES, blank=True)
    iluminacao = models.CharField(max_length=30, choices=ILUMINACAO_CHOICES, blank=True)
    
    # Dados do proprietário  
    proprietario = models.CharField(max_length=150, blank=True)
    cpf = models.CharField(max_length=20, blank=True)
    cnpj = models.CharField(max_length=25, blank=True)
    cnh = models.CharField(max_length=30, blank=True)
    categoria_cnh = models.CharField(max_length=10, blank=True)
    validade_cnh = models.DateField(null=True, blank=True)
    
    # Situação e observações
    situacao_veiculo = models.CharField(max_length=30, choices=SITUACAO_VEICULO_CHOICES, blank=True)
    observacao_situacao = models.TextField(blank=True)
    danos_identificados = models.TextField(blank=True, help_text="Lista de danos separados por vírgula")
    
    # Apreensão de Veículo
    apreensao_ait = models.CharField(max_length=120, blank=True, help_text="Nº das AIT's relacionadas")
    apreensao_crr = models.CharField(max_length=60, blank=True, help_text="Nº do CRR")
    apreensao_responsavel_guincho = models.CharField(max_length=120, blank=True)
    apreensao_destino = models.CharField(max_length=120, blank=True)
    
    def __str__(self):
        return f"{self.marca} {self.modelo} - {self.placa or 'Sem placa'}"

class AnexoVeiculo(models.Model):
    veiculo = models.ForeignKey(VeiculoEnvolvido, related_name='anexos', on_delete=models.CASCADE)
    descricao = models.CharField(max_length=255)
    arquivo = models.FileField(upload_to='veiculos/')

class EquipeApoio(models.Model):
    bo = models.ForeignKey('BO', on_delete=models.CASCADE, related_name='equipes', null=True, blank=True)
    viatura = models.ForeignKey('viaturas.Viatura', on_delete=models.CASCADE)
    instituicao = models.CharField(max_length=100)
    participantes = models.TextField(default="", help_text="Liste os participantes (GCMs, PMs, Polícia Civil, etc.)")
    observacoes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.viatura.prefixo} - {self.instituicao}"
