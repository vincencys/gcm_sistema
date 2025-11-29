from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import DisparoPanico
from .models import Assistida
from common.models import PushDevice
from common.views import enviar_push
from rest_framework.permissions import AllowAny

class DisparoListAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = DisparoPanico.objects.select_related('assistida').order_by('-created_at')
        status_f = request.GET.get('status')
        if status_f:
            qs = qs.filter(status=status_f)
        data = [
            {
                'id': d.id,
                'assistida': {
                    'id': d.assistida_id,
                    'nome': d.assistida.nome,
                    'cpf': d.assistida.cpf,
                },
                'status': d.status,
                'created_at': d.created_at.isoformat(),
                'em_atendimento_em': d.em_atendimento_em.isoformat() if d.em_atendimento_em else None,
                'encerrado_em': d.encerrado_em.isoformat() if d.encerrado_em else None,
                'coords': {
                    'lat': float(d.latitude or 0),
                    'lng': float(d.longitude or 0),
                    'accuracy': d.precisao_m,
                },
            }
            for d in qs[:200]
        ]
        return Response({'results': data})

class DisparoAssumirAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        d = get_object_or_404(DisparoPanico, pk=pk)
        if d.status not in {"ABERTA", "EM_ATENDIMENTO"}:
            return Response({'detail': 'Disparo não pode ser assumido.'}, status=status.HTTP_400_BAD_REQUEST)
        if d.status == "ABERTA":
            d.marcar_atendimento(request.user)
            # Push de transição para EM_ATENDIMENTO
            try:
                # Incluir dispositivos com user ativo OU sem user (apps anônimos como SafeBP)
                from django.db.models import Q
                tokens = list(PushDevice.objects.filter(
                    Q(user__is_active=True) | Q(user__isnull=True),
                    enabled=True
                ).values_list('token', flat=True)[:800])
                if tokens:
                    push_title = f"Pânico em atendimento - {d.assistida.nome}"
                    push_body = f"Disparo #{d.id} assumido."
                    enviar_push(
                        tokens,
                        title=push_title,
                        body=push_body,
                        data={
                            'kind': 'panico_status',
                            'disparo_id': str(d.id),
                            'status': d.status,
                            'action': 'assumir',
                            'title': push_title,  # Adicionar título no data
                            'body': push_body,
                        }
                    )
            except Exception:
                pass
        return Response({'id': d.id, 'status': d.status, 'em_atendimento_em': d.em_atendimento_em})

class DisparoEncerrarAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        d = get_object_or_404(DisparoPanico, pk=pk)
        if d.status not in {"ABERTA", "EM_ATENDIMENTO"}:
            return Response({'detail': 'Disparo não está ativo.'}, status=status.HTTP_400_BAD_REQUEST)
        relato = (request.data.get('relato_final') or '').strip()
        status_final = (request.data.get('status_final') or 'ENCERRADA').upper()
        if status_final not in {"ENCERRADA","CANCELADA","FALSO_POSITIVO","TESTE"}:
            status_final = "ENCERRADA"
        d.encerrar(relato, status_final=status_final)
        # Push de encerramento
        try:
            # Incluir dispositivos com user ativo OU sem user (apps anônimos como SafeBP)
            from django.db.models import Q
            tokens = list(PushDevice.objects.filter(
                Q(user__is_active=True) | Q(user__isnull=True),
                enabled=True
            ).values_list('token', flat=True)[:800])
            if tokens:
                action = 'confirm' if d.status=='ENCERRADA' else ('teste' if d.status=='TESTE' else 'recusa')
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"[PUSH] Enviando para {len(tokens)} dispositivos: status={d.status}, motivo={relato}, action={action}")
                # Títulos customizados por status
                push_title = (
                    "🚨 Equipes à caminho" if d.status == 'ENCERRADA'
                    else ("Pânico recusado" if d.status == 'CANCELADA'
                          else ("Pânico marcado como TESTE" if d.status == 'TESTE'
                                else "Atualização do pânico"))
                )
                push_body = relato or ""
                enviar_push(
                    tokens,
                    title=push_title,
                    body=push_body,
                    data={
                        'kind': 'panico_status',
                        'disparo_id': str(d.id),
                        'status': d.status,
                        'motivo': (relato or ''),
                        'action': action,
                        'title': push_title,  # Adicionar título no data para apps data-only
                        'body': push_body,
                    }
                )
                logger.info(f"[PUSH] Envio concluído com sucesso.")
            else:
                import logging
                logging.getLogger(__name__).warning("[PUSH] Nenhum token ativo encontrado no banco.")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"[PUSH] Erro ao enviar: {e}", exc_info=True)
        return Response({'id': d.id, 'status': d.status, 'encerrado_em': d.encerrado_em})


class DisparoDetalheAPI(APIView):
    """Retorna detalhes básicos (status, motivo, timestamps) de um disparo para o app consultar via polling/fallback."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        d = get_object_or_404(DisparoPanico.objects.select_related('assistida'), pk=pk)
        return Response({
            'id': d.id,
            'assistida': {
                'id': d.assistida_id,
                'nome': d.assistida.nome,
                'cpf': d.assistida.cpf,
            },
            'status': d.status,
            'motivo': d.relato_final or '',
            'created_at': d.created_at.isoformat() if d.created_at else None,
            'em_atendimento_em': d.em_atendimento_em.isoformat() if d.em_atendimento_em else None,
            'encerrado_em': d.encerrado_em.isoformat() if d.encerrado_em else None,
        })


class AssistidaAprovarAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        a = get_object_or_404(Assistida, pk=pk)
        if a.status not in {"PENDENTE_VALIDACAO","REPROVADO","SUSPENSO"}:
            return Response({'detail': 'Estado não permite aprovação'}, status=400)
        a.status = 'APROVADO'
        if not a.token_panico:
            a.gerar_token()
        else:
            a.save(update_fields=['status'])
        return Response({'id': a.id, 'status': a.status, 'token': a.token_panico})

class AssistidaReprovarAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        a = get_object_or_404(Assistida, pk=pk)
        if a.status not in {"PENDENTE_VALIDACAO","APROVADO"}:
            return Response({'detail': 'Estado não permite reprovação'}, status=400)
        obs = (request.data.get('observacao') or '').strip()[:500]
        a.status = 'REPROVADO'
        a.observacao_validacao = obs
        a.save(update_fields=['status','observacao_validacao'])
        return Response({'id': a.id, 'status': a.status})

class AssistidaSuspenderAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        a = get_object_or_404(Assistida, pk=pk)
        if a.status != 'APROVADO':
            return Response({'detail': 'Somente assistida aprovada pode ser suspensa'}, status=400)
        a.status = 'SUSPENSO'
        a.save(update_fields=['status'])
        return Response({'id': a.id, 'status': a.status})

class AssistidaReativarAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        a = get_object_or_404(Assistida, pk=pk)
        if a.status not in {'SUSPENSO','REPROVADO'}:
            return Response({'detail': 'Estado não permite reativação'}, status=400)
        a.status = 'APROVADO'
        if not a.token_panico:
            a.gerar_token()
        else:
            a.save(update_fields=['status'])
        return Response({'id': a.id, 'status': a.status, 'token': a.token_panico})

class AssistidaRotacionarTokenAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        a = get_object_or_404(Assistida, pk=pk)
        if a.status != 'APROVADO':
            return Response({'detail': 'Somente assistida aprovada pode rotacionar token'}, status=400)
        a.gerar_token(rotativo=True)
        return Response({'id': a.id, 'status': a.status, 'token': a.token_panico})
