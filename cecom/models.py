from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.conf import settings

try:
    from users.models import Perfil
except Exception:  # pragma: no cover
    Perfil = None

User = get_user_model()

class PlantaoCECOM(models.Model):
    """Registro de plantão individual por usuário.

    Agora cada usuário mantém seu próprio plantão ativo. A viatura é salva aqui
    para permitir bloquear que dois usuários iniciem plantão simultâneo na mesma viatura.
    """
    iniciado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='plantoes_iniciados')
    viatura = models.ForeignKey('viaturas.Viatura', on_delete=models.PROTECT, null=True, blank=True)
    inicio = models.DateTimeField(default=timezone.now)
    fim_previsto = models.DateTimeField()
    encerrado_em = models.DateTimeField(null=True, blank=True)
    ativo = models.BooleanField(default=True)
    # Rascunho compartilhado do Relatório de Ronda entre os integrantes
    relatorio_rascunho = models.TextField(blank=True, default="")
    # Token de verificação pública para o Relatório de Plantão (QR Code)
    verificacao_token = models.CharField(max_length=64, null=True, blank=True, default=None, unique=True)

    class Meta:
        ordering = ('-inicio',)
        constraints = [
            models.UniqueConstraint(
                fields=['viatura'],
                condition=models.Q(ativo=True),
                name='cecom_viatura_unica_plantao_ativo'
            )
        ]

    # Mantido para retrocompatibilidade (retorna qualquer plantão ativo globalmente)
    @staticmethod
    def ativo_atual():
        return PlantaoCECOM.objects.filter(ativo=True).order_by('-inicio').first()

    @staticmethod
    def ativo_do_usuario(user):
        """Retorna o plantão ativo do usuário (ou None)."""
        if not user or not getattr(user, 'id', None):
            return None
        return PlantaoCECOM.objects.filter(iniciado_por=user, ativo=True).order_by('-inicio').first()

    @staticmethod
    def ativo_do_usuario_ou_participado(user):
        """Retorna o plantão ativo que o usuário iniciou ou participa."""
        if not user or not getattr(user, 'id', None):
            return None
        qs = PlantaoCECOM.objects.filter(ativo=True).filter(
            Q(iniciado_por=user) | Q(participantes__usuario=user)
        ).distinct().order_by('-inicio')
        for p in qs:
            # Se o usuário iniciou mas já saiu (não consta mais como participante) e ainda há outros participantes, ignora
            if p.iniciado_por_id == user.id and not p.participantes.filter(usuario=user).exists() and p.participantes.exists():
                continue
            return p
        return None

    def participantes_labeled(self):
        """Lista [(Label, Nome)] com base nos participantes cadastrados."""
        papel_map = {
            'ENC': 'Encarregado',
            'MOT': 'Motorista',
            'AUX1': 'Auxiliar 1',
            'AUX2': 'Auxiliar 2',
            '': 'Integrante'
        }
        out = []
        for p in self.participantes.select_related('usuario').filter(saida_em__isnull=True):
            user = p.usuario
            nome = (getattr(user, 'get_full_name', lambda: '')() or user.username or '').strip()
            out.append((papel_map.get(p.funcao, p.funcao), nome.title()))
        return out

    def __str__(self):  # pragma: no cover
        base = f"Plantão {self.id} de {getattr(self.iniciado_por, 'username', '?')}"
        if self.viatura_id:
            base += f" (VTR {self.viatura_id})"
        if self.ativo:
            return base + " [ATIVO]"
        return base + " [ENCERRADO]"


class PlantaoParticipante(models.Model):
    """Participantes (usuários) vinculados a um plantão compartilhado.
    Função opcional: ENC, MOT, AUX1, AUX2 para facilitar exibição.
    """
    FUNCOES = (
        ("ENC", "Encarregado"),
        ("MOT", "Motorista"),
        ("AUX1", "Auxiliar 1"),
        ("AUX2", "Auxiliar 2"),
    )
    plantao = models.ForeignKey(PlantaoCECOM, on_delete=models.CASCADE, related_name='participantes')
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='plantoes_participados')
    funcao = models.CharField(max_length=5, choices=FUNCOES, blank=True, default="")
    adicionado_em = models.DateTimeField(auto_now_add=True)
    saida_em = models.DateTimeField(null=True, blank=True, help_text="Momento em que o participante saiu do plantão (se aplicável).")

    class Meta:
        unique_together = ("plantao", "usuario")

    def __str__(self):  # pragma: no cover
        return f"{self.usuario} em {self.plantao} ({self.funcao or 'SEM FUNÇÃO'})"


# ---------------- NOVO: PLANTÃO CECOM (PRINCIPAL / AUX) + LIVRO ELETRÔNICO -----------------

class PlantaoCecomPrincipal(models.Model):
    """Controle de início/fim de plantão do CECOM por usuário (principal ou auxiliar).

    Similar à lógica de talões: cada usuário pode ter 1 plantão CECOM ativo.
    """
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='plantoes_cecom_principal')
    aux_cecom = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='plantoes_cecom_auxiliares')
    inicio = models.DateTimeField(default=timezone.now)
    encerrado_em = models.DateTimeField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ('-inicio',)
        constraints = [
            models.UniqueConstraint(fields=['usuario'], condition=Q(ativo=True), name='cecom_unique_principal_ativo'),
        ]

    @staticmethod
    def ativo_do_usuario(user):
        if not user or not getattr(user, 'id', None):
            return None
        return PlantaoCecomPrincipal.objects.filter(usuario=user, ativo=True).order_by('-inicio').first()

    @staticmethod
    def ativo_do_usuario_ou_aux(user):
        if not user or not getattr(user, 'id', None):
            return None
        return PlantaoCecomPrincipal.objects.filter(Q(usuario=user)|Q(aux_cecom=user), ativo=True).order_by('-inicio').first()

    def encerrar(self):
        if self.ativo:
            self.ativo = False
            self.encerrado_em = timezone.now()
            self.save(update_fields=['ativo','encerrado_em'])

    def __str__(self):  # pragma: no cover
        return f"Plantão CECOM #{self.pk} de {self.usuario} {'(ATIVO)' if self.ativo else '(ENCERRADO)'}"


class LivroPlantaoCecom(models.Model):
    """Livro eletrônico do plantão CECOM (um por plantão principal).

    Contém campos de equipe, CGA, anotações diversas e checklist.
    """
    plantao = models.OneToOneField(PlantaoCecomPrincipal, on_delete=models.CASCADE, related_name='livro')
    equipe_plantao = models.CharField(max_length=1, choices=Perfil.EQUIPE_CHOICES if Perfil else [('A','A'),('B','B')], blank=True)
    cga_do_dia = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cga_dia_plantoes')
    # Campos textuais
    dispensados = models.TextField(blank=True)
    atraso_servico = models.TextField(blank=True)
    banco_horas = models.TextField(blank=True)
    hora_extra = models.TextField(blank=True)
    ocorrencias_nao_atendidas = models.TextField(blank=True)
    ocorrencias_do_plantao = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)
    aits_recebidas = models.PositiveIntegerField(default=0)
    # Checklist
    chk_radio = models.BooleanField(default=False)
    chk_computador = models.BooleanField(default=False)
    chk_cameras = models.BooleanField(default=False)
    chk_celulares = models.BooleanField(default=False)
    chk_carregadores = models.BooleanField(default=False)
    chk_telefones = models.BooleanField(default=False)
    chk_livros = models.BooleanField(default=False)
    chk_monitor = models.BooleanField(default=False)
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):  # pragma: no cover
        return f"Livro Plantão CECOM {self.plantao_id}"


class LivroPlantaoCecomPessoa(models.Model):
    """Registros de pessoas por categoria no Livro do Plantão CECOM.

    Permite adicionar múltiplos usuários por tipo (dispensados, atraso, banco de horas, hora extra).
    """
    TIPO_CHOICES = (
        ("DISP", "Dispensados"),
        ("ATRASO", "Atraso ao Serviço"),
        ("BANCO", "Banco de Horas"),
        ("HORA_EXTRA", "Hora Extra"),
    )
    livro = models.ForeignKey(LivroPlantaoCecom, on_delete=models.CASCADE, related_name="pessoas")
    tipo = models.CharField(max_length=12, choices=TIPO_CHOICES)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    # Faixa horária opcional (obrigatória apenas para ATRASO, BANCO, HORA_EXTRA)
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fim = models.TimeField(null=True, blank=True)
    total_minutos = models.PositiveIntegerField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("livro", "tipo", "usuario")
        ordering = ("tipo", "id")

    def __str__(self):  # pragma: no cover
        return f"{self.get_tipo_display()} - {self.usuario} (Livro {self.livro_id})"


class LivroPlantaoCecomViatura(models.Model):
    livro = models.ForeignKey(LivroPlantaoCecom, on_delete=models.CASCADE, related_name='viaturas')
    viatura = models.ForeignKey('viaturas.Viatura', on_delete=models.PROTECT)
    integrante1 = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    integrante2 = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    integrante3 = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    integrante4 = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    def integrantes(self):
        return [u for u in [self.integrante1, self.integrante2, self.integrante3, self.integrante4] if u]


class LivroPlantaoCecomPostoFixo(models.Model):
    TIPO_CHOICES = [
        ('PREFEITURA','Prefeitura'),
        ('HOSPITAL','Hospital'),
        ('SUBSEDE_VERAVA','Subsede Verava'),
        ('ADM','ADM'),
        ('DELEGACIA','Delegacia'),
        ('RECEPCAO','Recepção'),
        ('CECOM','CECOM'),
        ('AUX_CECOM','AUX CECOM'),
        ('OUTROS','Outros'),
    ]
    livro = models.ForeignKey(LivroPlantaoCecom, on_delete=models.CASCADE, related_name='postos_fixos')
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)
    descricao_outros = models.CharField(max_length=120, blank=True)
    gcm1 = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    gcm2 = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    def __str__(self):  # pragma: no cover
        return f"Posto {self.get_tipo_display()} ({self.id})"


class LivroPlantaoCecomRelatorio(models.Model):
    """Relatório consolidado (PDF único) gerado ao encerrar o Plantão CECOM."""
    plantao = models.OneToOneField(PlantaoCecomPrincipal, on_delete=models.CASCADE, related_name='relatorio_pdf')
    arquivo = models.FileField(upload_to='cecom_livros/')
    criado_em = models.DateTimeField(auto_now_add=True)
    equipe_plantao = models.CharField(max_length=1, blank=True)
    cga_nome = models.CharField(max_length=120, blank=True)
    cga_matricula = models.CharField(max_length=30, blank=True)
    verificacao_token = models.CharField(max_length=64, blank=True, default='', unique=True)

    class Meta:
        ordering = ['-criado_em']

    def __str__(self):  # pragma: no cover
        return f"Relatório Livro Plantão {self.plantao_id}"


class DespachoOcorrencia(models.Model):
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('ACEITO', 'Aceito'),
        ('RECUSADO', 'Recusado'),
        ('EM_ANDAMENTO', 'Em Andamento'),
        ('FINALIZADO', 'Finalizado'),
        ('CANCELADO', 'Cancelado'),
    ]
    
    # Dados do despacho
    viatura = models.ForeignKey('viaturas.Viatura', on_delete=models.CASCADE, verbose_name="Viatura")
    endereco = models.CharField("Endereço", max_length=255)
    latitude = models.DecimalField("Latitude", max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField("Longitude", max_digits=11, decimal_places=8, null=True, blank=True)
    
    # Dados do solicitante
    nome_solicitante = models.CharField("Nome do solicitante", max_length=100, blank=True)
    telefone_solicitante = models.CharField("Telefone", max_length=20, blank=True)
    
    # Descrição da ocorrência
    descricao = models.TextField("Descrição da ocorrência")
    # Tipo/Código de ocorrência (inspirado no BOGCM):
    cod_natureza = models.CharField("Código da Ocorrência", max_length=30, blank=True, default="")
    natureza = models.CharField("Descrição da Ocorrência", max_length=120, blank=True, default="")
    
    # Controle
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default='PENDENTE')
    despachado_por = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="Despachado por")
    despachado_em = models.DateTimeField("Despachado em", default=timezone.now)
    
    # Controle de notificações e respostas
    notificado_em = models.DateTimeField("Notificado em", null=True, blank=True)
    respondido_em = models.DateTimeField("Respondido em", null=True, blank=True)
    respondido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                     related_name='respostas_despachos', verbose_name="Respondido por")
    aceito_em = models.DateTimeField("Aceito em", null=True, blank=True)
    finalizado_em = models.DateTimeField("Finalizado em", null=True, blank=True)
    arquivado = models.BooleanField("Arquivado", default=False)
    arquivado_em = models.DateTimeField("Arquivado em", null=True, blank=True)
    
    # Observações
    observacoes = models.TextField("Observações", blank=True)
    observacoes_encarregado = models.TextField("Observações do encarregado", blank=True)
    
    class Meta:
        verbose_name = "Despacho de Ocorrência"
        verbose_name_plural = "Despachos de Ocorrências"
        ordering = ['-despachado_em']
    
    def __str__(self):
        return f"Despacho #{self.pk} - {self.viatura} - {self.get_status_display()}"
    
    @property
    def esta_pendente_resposta(self):
        """Verifica se está aguardando resposta do encarregado"""
        return self.status == 'PENDENTE' and not self.respondido_em
    
    @property
    def foi_aceito(self):
        """Verifica se foi aceito pelo encarregado"""
        return self.status in ['ACEITO', 'EM_ANDAMENTO', 'FINALIZADO']
    
    @property
    def pode_ser_arquivado(self):
        """Verifica se pode ser arquivado"""
        return self.status in ['FINALIZADO', 'CANCELADO', 'RECUSADO'] and not self.arquivado
    
    def marcar_como_notificado(self):
        """Marca como notificado para o encarregado"""
        if not self.notificado_em:
            self.notificado_em = timezone.now()
            self.save(update_fields=['notificado_em'])
    
    def aceitar(self, user, observacoes=''):
        """Aceita o despacho"""
        self.status = 'ACEITO'
        self.respondido_em = timezone.now()
        self.respondido_por = user
        self.aceito_em = timezone.now()
        if observacoes:
            self.observacoes_encarregado = observacoes
        self.save()
    
    def recusar(self, user, observacoes=''):
        """Recusa o despacho"""
        self.status = 'RECUSADO'
        self.respondido_em = timezone.now()
        self.respondido_por = user
        if observacoes:
            self.observacoes_encarregado = observacoes
        self.save()
    
    def finalizar(self, observacoes=''):
        """Finaliza o despacho"""
        self.status = 'FINALIZADO'
        self.finalizado_em = timezone.now()
        if observacoes:
            self.observacoes += f"\n[Finalização] {observacoes}"
        self.save()
    
    def arquivar(self):
        """Arquiva o despacho"""
        if self.pode_ser_arquivado:
            self.arquivado = True
            self.arquivado_em = timezone.now()
            self.save(update_fields=['arquivado', 'arquivado_em'])


# ---------------- NOVO: Localização em tempo real das Viaturas -----------------

class ViaturaLocalizacao(models.Model):
    """Última localização conhecida de uma viatura.

    Mantemos apenas o registro mais recente por viatura (OneToOne) para facilitar
    a consulta no mapa em tempo real. Histórico pode ser adicionado futuramente
    com um modelo separado, se necessário.
    """
    viatura = models.OneToOneField('viaturas.Viatura', on_delete=models.CASCADE, related_name='localizacao')
    latitude = models.DecimalField(max_digits=10, decimal_places=8)
    longitude = models.DecimalField(max_digits=11, decimal_places=8)
    precisao_m = models.FloatField(null=True, blank=True)
    velocidade_kmh = models.FloatField(null=True, blank=True)
    direcao_graus = models.FloatField(null=True, blank=True, help_text="0-360, 0=Norte")
    atualizado_em = models.DateTimeField(auto_now=True)
    origem_usuario = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    origem_plantao = models.ForeignKey(PlantaoCECOM, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        indexes = [
            models.Index(fields=["atualizado_em"]),
        ]
        verbose_name = "Localização de Viatura"
        verbose_name_plural = "Localizações de Viaturas"

    def __str__(self):  # pragma: no cover
        return f"{getattr(self.viatura, 'prefixo', 'VTR')} @ {self.latitude}, {self.longitude} ({self.atualizado_em:%d/%m %H:%M:%S})"


class ViaturaLocalizacaoPonto(models.Model):
    """Histórico de pontos de localização para formar trilha.

    Armazena pontos capturados do app. Mantemos somente últimos N por viatura
    via limpeza periódica (ver serviços futuros) ou filtragem em consultas.
    """
    viatura = models.ForeignKey('viaturas.Viatura', on_delete=models.CASCADE, related_name='loc_pontos')
    plantao = models.ForeignKey(PlantaoCECOM, null=True, blank=True, on_delete=models.SET_NULL, related_name='loc_pontos')
    latitude = models.DecimalField(max_digits=10, decimal_places=8)
    longitude = models.DecimalField(max_digits=11, decimal_places=8)
    capturado_em = models.DateTimeField(default=timezone.now, db_index=True)
    origem_usuario = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    precisao_m = models.FloatField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['viatura','capturado_em']),
        ]
        ordering = ['-capturado_em']

    def __str__(self):  # pragma: no cover
        return f"Ponto VTR {getattr(self.viatura,'prefixo','?')} @ {self.latitude},{self.longitude} {self.capturado_em:%H:%M:%S}" 
