from __future__ import annotations
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from django.utils import timezone
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import Assistida, DisparoPanico
from .broadcast import broadcast_panico_localizacao
import re, threading

# Rate limiting simples em memória (fallback se não houver cache configurado)
_rate_lock = threading.Lock()
_last_token_action: dict[str, float] = {}
_last_location_action: dict[str, float] = {}

def _rate_ok(token: str, bucket: str, min_interval: float) -> bool:
    now = timezone.now().timestamp()
    store = _last_token_action if bucket == 'panic' else _last_location_action
    with _rate_lock:
        last = store.get(token, 0)
        if now - last < min_interval:
            return False
        store[token] = now
    return True

class PublicAssistidaSolicitar(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]  # aceita multipart/form-data

    def post(self, request):
        nome = (request.POST.get('nome') or '').strip()
        cpf = (request.POST.get('cpf') or '').strip()
        telefone = (request.POST.get('telefone') or '').strip()
        processo_mp = (request.POST.get('processo_mp') or '').strip()
        endereco = (request.POST.get('endereco') or '').strip()
        documento = request.FILES.get('documento_mp')  # UploadedFile

        # Validações mínimas
        if not (nome and cpf and telefone and processo_mp and endereco and documento):
            return Response({'detail': 'Campos obrigatórios ausentes'}, status=status.HTTP_400_BAD_REQUEST)
        cpf_clean = re.sub(r'\D+', '', cpf)
        if len(cpf_clean) != 11:
            return Response({'detail': 'CPF inválido'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(documento, UploadedFile):
            return Response({'detail': 'Documento MP inválido'}, status=status.HTTP_400_BAD_REQUEST)
        # Evitar duplicidade de CPF
        if Assistida.objects.filter(cpf=cpf).exists():
            return Response({'detail': 'CPF já cadastrado ou em análise'}, status=status.HTTP_409_CONFLICT)
        try:
            with transaction.atomic():
                a = Assistida.objects.create(
                    nome=nome,
                    cpf=cpf,
                    telefone=telefone,
                    processo_mp=processo_mp,
                    endereco=endereco,
                    documento_mp=documento,
                    status='PENDENTE_VALIDACAO'
                )
        except Exception as e:
            return Response({'detail': f'Falha ao registrar: {e}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'id': a.id, 'status': a.status}, status=status.HTTP_201_CREATED)

class PublicDisparoCriar(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = (request.POST.get('token') or request.data.get('token') or '').strip()
        lat = request.POST.get('latitude') or request.data.get('latitude')
        lng = request.POST.get('longitude') or request.data.get('longitude')
        acc = request.POST.get('precisao') or request.data.get('precisao') or request.data.get('accuracy')
        origem = (request.POST.get('origem') or request.data.get('origem') or 'APP').upper()[:20]
        if not token:
            return Response({'detail': 'Token ausente'}, status=status.HTTP_400_BAD_REQUEST)
        if not _rate_ok(token, 'panic', 60.0):  # mínimo 1 min entre disparos
            return Response({'detail': 'Muitos disparos consecutivos, aguarde.'}, status=429)
        a = Assistida.objects.filter(token_panico=token, status='APROVADO').first()
        if not a:
            return Response({'detail': 'Token inválido ou assistida não aprovada'}, status=status.HTTP_403_FORBIDDEN)
        try:
            ua = (request.META.get('HTTP_USER_AGENT') or '')[:512]
            ip = request.META.get('REMOTE_ADDR') or request.META.get('HTTP_X_FORWARDED_FOR','').split(',')[0].strip() or None
            dp = DisparoPanico.objects.create(
                assistida=a,
                latitude=lat or None,
                longitude=lng or None,
                precisao_m=int(acc) if str(acc).isdigit() else None,
                origem=origem,
                origem_ip=ip,
                origem_user_agent=ua,
            )
        except Exception as e:
            return Response({'detail': f'Falha ao criar disparo: {e}'}, status=500)
        return Response({'id': dp.id, 'status': dp.status}, status=status.HTTP_201_CREATED)

class PublicDisparoLocalizacao(APIView):
    permission_classes = [AllowAny]

    def post(self, request, pk: int):
        token = (request.POST.get('token') or request.data.get('token') or '').strip()
        if not token:
            return Response({'detail': 'Token ausente'}, status=400)
        lat = request.POST.get('latitude') or request.data.get('latitude')
        lng = request.POST.get('longitude') or request.data.get('longitude')
        acc = request.POST.get('precisao') or request.data.get('precisao') or request.data.get('accuracy')
        if lat is None or lng is None:
            return Response({'detail': 'latitude/longitude obrigatórias'}, status=400)
        if not _rate_ok(token, 'loc', 5.0):
            return Response({'detail': 'Envio de localização muito frequente'}, status=429)
        dp = DisparoPanico.objects.select_related('assistida').filter(pk=pk, status__in=['ABERTA','EM_ATENDIMENTO']).first()
        if not dp:
            return Response({'detail': 'Disparo inexistente ou encerrado'}, status=404)
        if not (dp.assistida.token_panico == token and dp.assistida.status == 'APROVADO'):
            return Response({'detail': 'Token não corresponde ao disparo'}, status=403)
        try:
            dp.latitude = lat or dp.latitude
            dp.longitude = lng or dp.longitude
            if acc and str(acc).isdigit():
                dp.precisao_m = int(acc)
            dp.save(update_fields=['latitude','longitude','precisao_m','updated_at'])
            # Broadcast atualização de localização em tempo real
            try:
                broadcast_panico_localizacao(dp)
            except Exception:
                pass
        except Exception as e:
            return Response({'detail': f'Falha ao atualizar localização: {e}'}, status=500)
        return Response({'ok': True, 'atualizado_em': timezone.localtime(dp.updated_at).isoformat()})
