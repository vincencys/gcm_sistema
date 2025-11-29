from cecom.models import PlantaoCECOM
from django.db.models import Q
from .models import OficioInterno
from common.models import DocumentoAssinavel

def plantao(request):
    try:
        ativo = PlantaoCECOM.objects.filter(ativo=True).order_by('-inicio').first()
    except Exception:
        ativo = None
    return {'plantao_ativo': ativo}

def user_permissions(request):
    """Context processor para permissões do usuário"""
    is_comando = False
    if request.user.is_authenticated:
        # Verificar se é superuser ou usuário específico do comando
        is_comando = (
            request.user.is_superuser or 
            request.user.username in ['comandante', 'subcomandante', 'administrativo']
        )
    return {'is_comando': is_comando}


def oficios_pendentes(request):
    """Quantidades para o topo: ofícios pendentes, despachos pendentes e soma.

    - Ofícios:
      * Supervisor: status PEND_SUP onde ele é o supervisor
      * Subcomandante: status PEND_SUB
      * Comandante: status PEND_CMT
    - Despachos:
      * Despachos pendentes vinculados às viaturas em que o usuário tem vínculo
        (talão ativo em qualquer função ou plantão CECOM ativo com viatura e participação).
    """
    oficios_count = 0
    despachos_count = 0
    try:
        if request.user.is_authenticated:
            # Ofícios pendentes
            uname = (request.user.username or '').lower()
            cond = Q(status='PEND_SUP', supervisor=request.user)
            if uname == 'subcomandante':
                cond |= Q(status='PEND_SUB')
            if uname == 'comandante':
                cond |= Q(status='PEND_CMT')
            oficios_count = OficioInterno.objects.filter(cond).count()

            # Despachos pendentes por vínculo de viatura
            try:
                from cecom.models import DespachoOcorrencia, PlantaoCECOM
                from taloes.models import Talao
                from django.db.models import Q as _Q

                viaturas_ids = set()
                # Talões ativos em que o usuário participa
                for t in (
                    Talao.objects
                    .select_related('viatura')
                    .filter(status='ABERTO')
                    .filter(
                        _Q(encarregado=request.user) |
                        _Q(motorista=request.user) |
                        _Q(auxiliar1=request.user) |
                        _Q(auxiliar2=request.user)
                    )
                ):
                    if t.viatura_id:
                        viaturas_ids.add(t.viatura_id)
                # Plantões ativos com viatura vinculada em que o usuário participa
                for p in (
                    PlantaoCECOM.objects.select_related('viatura')
                    .filter(ativo=True)
                    .filter(
                        _Q(iniciado_por=request.user) |
                        _Q(participantes__usuario=request.user, participantes__saida_em__isnull=True)
                    )
                    .distinct()
                ):
                    if p.viatura_id:
                        viaturas_ids.add(p.viatura_id)
                if viaturas_ids:
                    despachos_count = (
                        DespachoOcorrencia.objects
                        .filter(
                            viatura_id__in=list(viaturas_ids),
                            status='PENDENTE',
                            respondido_em__isnull=True
                        )
                        .count()
                    )
            except Exception:
                despachos_count = 0
            # Assinaturas pendentes (CMT/SUBCMT: PLANTAO/BOGCMI; ADM: LIVRO_CECOM)
            try:
                if uname in {'comandante','subcomandante'}:
                    assin_count = DocumentoAssinavel.objects.filter(status='PENDENTE', tipo__in=['PLANTAO','BOGCMI']).count()
                elif uname in {'administrativo','admnistrativo'}:
                    assin_count = DocumentoAssinavel.objects.filter(status='PENDENTE_ADM', tipo='LIVRO_CECOM').count()
                else:
                    assin_count = 0
            except Exception:
                assin_count = 0
            # BOs ativos (em edição) onde o usuário é integrante (para somar no badge)
            bos_ativos_count = 0
            try:
                from bogcmi.models import BO
                integrante_q = (
                    Q(encarregado=request.user) |
                    Q(motorista=request.user) |
                    Q(auxiliar1=request.user) |
                    Q(auxiliar2=request.user) |
                    Q(cecom=request.user)
                )
                bos_ativos_count = BO.objects.filter(integrante_q, status='EDICAO').count()
            except Exception:
                bos_ativos_count = 0
            # Avisos do usuário (notificações persistentes não lidas)
            avisos_count = 0
            try:
                from .models import UserNotification
                avisos_count = UserNotification.objects.filter(user=request.user, read_at__isnull=True).count()
            except Exception:
                avisos_count = 0
    except Exception:
        oficios_count = 0
        despachos_count = 0
        assin_count = 0
        bos_ativos_count = 0
        avisos_count = 0
    return {
        'oficios_pendentes_count': oficios_count,
        'despachos_pendentes_count': despachos_count,
        'assinaturas_pendentes_count': locals().get('assin_count', 0),
        'bos_ativos_count': locals().get('bos_ativos_count', 0),
        'avisos_pendentes_count': locals().get('avisos_count', 0),
        'navbar_notif_count': (
            (oficios_count or 0)
            + (despachos_count or 0)
            + (locals().get('assin_count', 0) or 0)
            + (locals().get('bos_ativos_count', 0) or 0)
            + (locals().get('avisos_count', 0) or 0)
        ),
    }


def viaturas_avarias_nav(request):
    """Conta quantas viaturas ativas possuem avarias em aberto.

    Critério: Existem labels registradas no estado persistente (ViaturaAvariaEstado)
    diferentes de [] e a viatura está ativa. É leve e independente do checklist do dia.
    """
    try:
        from viaturas.models import Viatura, ViaturaAvariaEstado
        # IDs com labels registradas
        vids = list(
            ViaturaAvariaEstado.objects
            .exclude(labels_json__isnull=True)
            .exclude(labels_json="[]")
            .values_list('viatura_id', flat=True)
        )
        if not vids:
            return { 'viaturas_avarias_count': 0 }
        count = Viatura.objects.filter(id__in=vids, ativo=True).distinct().count()
        return { 'viaturas_avarias_count': count }
    except Exception:
        return { 'viaturas_avarias_count': 0 }
