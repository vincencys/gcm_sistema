from __future__ import annotations

from io import BytesIO
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponseBadRequest, HttpRequest, HttpResponse, Http404, JsonResponse
from django.urls import reverse
from django.shortcuts import redirect, render, get_object_or_404
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import models
from django.views.decorators.http import require_POST

from .models import Talao, ChecklistViatura, AvariaAnexo
from cecom.models import PlantaoCECOM, PlantaoParticipante
from .forms import SetupPlantaoForm, NovoTalaoForm, RelatorioRondaForm, PlantaoEquipeForm, ChecklistViaturaForm
from .services import sync_codigos_from_naturezas
from django.contrib.auth import get_user_model

# Salva PDFs em: MEDIA_ROOT/plantao/<user_id>/
MEDIA_BASE = Path(getattr(settings, "MEDIA_ROOT", "media")) / "plantao"

# >>> CHAVES DE SESSÃO SEM PONTO (para funcionar no template)
SESSION_RELATORIO = "taloes_relatorio_ronda"
SESSION_EQUIPE_STR = "taloes_equipe_str"
SESSION_PLANTAO = "taloes_plantao"
SESSION_VIATURA_ID = "taloes_viatura_id"
SESSION_ENCARREGADO_ID = "taloes_encarregado_id"
SESSION_MOTORISTA_ID = "taloes_motorista_id"
SESSION_AUX1_ID = "taloes_aux1_id"
SESSION_AUX2_ID = "taloes_aux2_id"
SESSION_COORDENADOR_ID = "taloes_coord_id"


# ======================
#   FUNÇÕES DE TESTE
# ======================

def teste_pdf_assinatura(request):
    # Busca o encarregado (exemplo: primeiro perfil com assinatura)
    from users.models import Perfil
    from reportlab.pdfgen import canvas
    import io
    
    perfil = Perfil.objects.filter(assinatura__isnull=False).first()
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)
    p.drawString(100, 800, "Relatório de Teste com Assinatura do Encarregado")
    if perfil and perfil.assinatura:
        # Adiciona a imagem da assinatura, convertendo se necessário
        try:
            from PIL import Image
            assinatura_path = perfil.assinatura.path
            img = Image.open(assinatura_path)
            if img.mode in ("RGBA", "LA"):
                # Converte para RGB (fundo branco)
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)
                buffer_img = io.BytesIO()
                bg.save(buffer_img, format="PNG")
                buffer_img.seek(0)
                p.drawImage(buffer_img, 100, 700, width=200, height=80, mask='auto')
            else:
                buffer_img = io.BytesIO()
                img.save(buffer_img, format="PNG")
                buffer_img.seek(0)
                p.drawImage(buffer_img, 100, 700, width=200, height=80, mask='auto')
            p.drawString(100, 690, f"Assinatura: {perfil.user.get_full_name()}")
        except Exception as e:
            p.drawString(100, 690, f"Erro ao carregar assinatura: {e}")
    else:
        p.drawString(100, 690, "Sem assinatura cadastrada.")
    p.showPage()
    p.save()
    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf')


@login_required
def gerar_pdf_ultimo_plantao(request):
    """Gera PDF do plantão ativo do usuário ou o último encerrado dele."""
    plantao = (
        PlantaoCECOM.ativo_do_usuario(request.user)
        or PlantaoCECOM.objects.filter(iniciado_por=request.user, ativo=False).order_by('-encerrado_em').first()
    )
    if not plantao:
        messages.error(request, "Você não possui plantão ativo ou encerrado para gerar PDF.")
        return redirect("taloes:lista")
    try:
        out_path = _gerar_pdf_plantao_encerrado(request, plantao)
        messages.success(request, f"PDF gerado: {out_path.name}")
    except Exception as e:
        messages.error(request, f"Erro ao gerar PDF: {e}")
    return redirect("taloes:meus_documentos")


# ======================
#   FINALIZAR PLANTÃO
# ======================, HttpResponse
from django.shortcuts import redirect, render
from django.core.paginator import Paginator
from django.utils import timezone

from .models import Talao
from cecom.models import PlantaoCECOM
from .forms import SetupPlantaoForm, NovoTalaoForm, RelatorioRondaForm, PlantaoEquipeForm
from .services import sync_codigos_from_naturezas
from django.contrib.auth import get_user_model

# Salva PDFs em: MEDIA_ROOT/plantao/<user_id>/
MEDIA_BASE = Path(getattr(settings, "MEDIA_ROOT", "media")) / "plantao"

# >>> CHAVES DE SESSÃO SEM PONTO (para funcionar no template)
SESSION_RELATORIO = "taloes_relatorio_ronda"
SESSION_EQUIPE_STR = "taloes_equipe_str"
SESSION_PLANTAO = "taloes_plantao"
SESSION_VIATURA_ID = "taloes_viatura_id"
SESSION_ENCARREGADO_ID = "taloes_encarregado_id"
SESSION_MOTORISTA_ID = "taloes_motorista_id"
SESSION_AUX1_ID = "taloes_aux1_id"
SESSION_AUX2_ID = "taloes_aux2_id"

# ======================
#   ASSINATURA HELPERS
# ======================
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageChops
import secrets
import hashlib

def _limpar_margens(img: Image.Image) -> Image.Image:
    try:
        # Converte para L e cria máscara (traço escuro vira 0)
        gray = img.convert("L")
        # Inverte para que o traço seja branco para bbox (255)
        inv = Image.eval(gray, lambda p: 255 - p)
        bbox = inv.getbbox()
        if bbox:
            return img.crop(bbox)
    except Exception:
        pass
    return img

def _abrir_assinatura_base64(data_url: str) -> Image.Image | None:
    import base64, io
    if not data_url:
        return None
    try:
        if data_url.startswith('data:image'):
            data_url = data_url.split(',',1)[1]
        raw = base64.b64decode(data_url)
        img = Image.open(io.BytesIO(raw))
        return img
    except Exception:
        return None

def _normalizar_assinatura(img: Image.Image) -> Image.Image:
    # Garantir RGBA para separar alpha
    if img.mode not in ("RGBA","LA"):
        img = img.convert("RGBA")
    # Flatten sobre branco
    bg = Image.new("RGBA", img.size, (255,255,255,0))
    bg.alpha_composite(img)
    # Troca transparência por branco definitivo
    bg_bytes = Image.new("RGB", img.size, (255,255,255))
    alpha = bg.split()[3]
    bg_bytes.paste(bg, mask=alpha)
    # Limpa margens
    cleaned = _limpar_margens(bg_bytes)
    # Reduz muito grande
    max_w,max_h = 260,90
    w,h = cleaned.size
    esc = min(max_w/w, max_h/h, 1.0)
    if esc < 1.0:
        cleaned = cleaned.resize((int(w*esc), int(h*esc)), Image.LANCZOS)
    return cleaned

def _image_reader_from_image(img: Image.Image) -> tuple[ImageReader,int,int]:
    import io
    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    buf.seek(0)
    reader = ImageReader(buf)
    return reader, img.width, img.height

def _obter_imagem_assinatura(perfil) -> tuple[ImageReader,int,int] | None:
    # 1. Preferir assinatura desenhada (campo base64 assinatura_digital)
    base64_field = getattr(perfil,'assinatura_digital',None)
    if base64_field:
        img = _abrir_assinatura_base64(base64_field)
        if img:
            norm = _normalizar_assinatura(img)
            return _image_reader_from_image(norm)
    # 2. Arquivo de upload (assinatura_img / assinatura)
    for field_name in ('assinatura_img','assinatura'):
        f = getattr(perfil, field_name, None)
        if f and getattr(f,'path',None):
            try:
                img = Image.open(f.path)
                norm = _normalizar_assinatura(img)
                return _image_reader_from_image(norm)
            except Exception:
                continue
    return None


def _ensure_media() -> None:
    MEDIA_BASE.mkdir(parents=True, exist_ok=True)


def _user_dir(user) -> Path:
    return MEDIA_BASE / str(user.id or "anon")


def _session_get(request: HttpRequest, key: str, default=None):
    return request.session.get(key, default)


def _session_set(request: HttpRequest, key: str, value):
    request.session[key] = value
    request.session.modified = True


def _build_equipe_texto(cleaned_data) -> str:
    nomes = []
    for k in ["encarregado", "motorista", "auxiliar1", "auxiliar2"]:
        v = (cleaned_data.get(k) or "").strip()
        if v:
            nomes.append(v)
    equipe = ", ".join(nomes) if nomes else ""
    plantao = cleaned_data.get("plantao") or ""
    if plantao:
        equipe = (equipe + f" — Plantão {plantao}").strip(" —")
    return equipe


# ======================
#   FLUXO DO PLANTÃO
# ======================

@login_required
def setup_plantao(request: HttpRequest):
    """Configura dados iniciais (viatura/equipe textual) armazenados em sessão.
    Mantido para compatibilidade; não cria plantão, apenas salva preferências.
    """
    initial = {}
    if (vid := _session_get(request, SESSION_VIATURA_ID)):
        initial["viatura"] = vid
    if (pl := _session_get(request, SESSION_PLANTAO)):
        initial["plantao"] = pl

    if request.method == "POST":
        form = SetupPlantaoForm(request.POST)
        if form.is_valid():
            viatura = form.cleaned_data["viatura"]
            _session_set(request, SESSION_VIATURA_ID, viatura.id)
            _session_set(request, SESSION_PLANTAO, form.cleaned_data["plantao"])
            _session_set(request, SESSION_EQUIPE_STR, _build_equipe_texto(form.cleaned_data))
            messages.success(request, "Plantão configurado.")
            return redirect("taloes:lista")
    else:
        form = SetupPlantaoForm(initial=initial)

    return render(request, "taloes/setup.html", {"form": form})


@login_required
def iniciar_plantao(request: HttpRequest):
    """Inicia ou atualiza o plantão do PRÓPRIO usuário (isolado)."""
    initial = {}
    if (vid := _session_get(request, SESSION_VIATURA_ID)):
        initial["viatura"] = vid
    # Coordenador/Líder inicial da sessão (se já escolhido antes)
    if (cid := _session_get(request, SESSION_COORDENADOR_ID)):
        initial["coordenador_lider"] = cid
    for key, sess_key in (
        ("encarregado", SESSION_ENCARREGADO_ID),
        ("motorista", SESSION_MOTORISTA_ID),
        ("auxiliar1", SESSION_AUX1_ID),
        ("auxiliar2", SESSION_AUX2_ID),
    ):
        if (uid := _session_get(request, sess_key)):
            initial[key] = uid

    if request.method == "POST":
        form = PlantaoEquipeForm(request.POST)
        if form.is_valid():
            v = form.cleaned_data["viatura"]
            # Garantir que o usuário logado esteja em pelo menos um dos campos selecionados
            selecionados = [
                form.cleaned_data.get("encarregado"),
                form.cleaned_data.get("motorista"),
                form.cleaned_data.get("auxiliar1"),
                form.cleaned_data.get("auxiliar2"),
            ]
            ids_sel = {getattr(u, 'id', None) for u in selecionados if u}
            if request.user.id not in ids_sel:
                form.add_error(None, "Você precisa estar em uma das funções da equipe (inclua-se em algum campo).")
                return render(request, "taloes/viatura_wizard.html", {"form": form, "talao_id": None, "talao": None})
            _session_set(request, SESSION_VIATURA_ID, v.id)
            _session_set(request, SESSION_ENCARREGADO_ID, getattr(form.cleaned_data.get("encarregado"), "id", None))
            _session_set(request, SESSION_MOTORISTA_ID, getattr(form.cleaned_data.get("motorista"), "id", None))
            _session_set(request, SESSION_AUX1_ID, getattr(form.cleaned_data.get("auxiliar1"), "id", None))
            _session_set(request, SESSION_AUX2_ID, getattr(form.cleaned_data.get("auxiliar2"), "id", None))
            # Coordenador/Líder (opcional)
            _session_set(request, SESSION_COORDENADOR_ID, getattr(form.cleaned_data.get("coordenador_lider"), "id", None))
            # Equipe (A/B/C/D) para sair no relatório
            _session_set(request, SESSION_PLANTAO, (form.cleaned_data.get("plantao") or "").strip())
            # Monta string amigável
            try:
                User = get_user_model()
                ids = [
                    getattr(form.cleaned_data.get("encarregado"), "id", None),
                    getattr(form.cleaned_data.get("motorista"), "id", None),
                    getattr(form.cleaned_data.get("auxiliar1"), "id", None),
                    getattr(form.cleaned_data.get("auxiliar2"), "id", None),
                ]
                ids = [i for i in ids if i]
                nomes = [
                    ((u.get_full_name() or u.get_username() or "").strip().title())
                    for u in User.objects.filter(id__in=ids)
                ]
                _session_set(request, SESSION_EQUIPE_STR, ", ".join([n for n in nomes if n]))
            except Exception:
                pass
            # Participantes selecionados
            participantes = []
            for campo, func in (("encarregado","ENC"),("motorista","MOT"),("auxiliar1","AUX1"),("auxiliar2","AUX2")):
                u = form.cleaned_data.get(campo)
                if u:
                    participantes.append((u, func))
            # (Não incluir automaticamente o usuário; já validado que está presente em algum papel.)

            # Reutilizar plantão ativo se QUALQUER participante já tiver um que envolva a mesma viatura e esteja ativo
            ativo = None
            candidate_user_ids = [p[0].id for p in participantes]
            ativos = PlantaoCECOM.objects.filter(ativo=True, viatura=v, participantes__usuario_id__in=candidate_user_ids).distinct()
            if ativos.exists():
                ativo = ativos.first()
            else:
                # Verificar conflito de viatura (outros usuários totalmente externos)
                conflito = PlantaoCECOM.objects.filter(ativo=True, viatura=v).exclude(participantes__usuario_id__in=candidate_user_ids).exists()
                if conflito:
                    messages.error(request, f"Viatura {v} já está em plantão ativo por outro grupo.")
                    return redirect("taloes:lista")
                now = timezone.now()
                fim_previsto = now + timezone.timedelta(hours=12)
                ativo = PlantaoCECOM.objects.create(
                    iniciado_por=request.user,
                    viatura=v,
                    inicio=now,
                    fim_previsto=fim_previsto,
                    ativo=True,
                )
            # Sincronizar participantes com regras:
            # - Selecionados: se já existirem com saida_em != None, reativar (saida_em=None); atualizar funcao
            # - Não selecionados: marcar saida_em (saem do plantão)
            atuais = {p.usuario_id: p for p in ativo.participantes.all()}
            selecionados_ids = {u.id for u, _ in participantes}
            agora = timezone.now()
            # Fechar quem não está nos selecionados
            for uid, part in list(atuais.items()):
                if part.saida_em is None and uid not in selecionados_ids:
                    part.saida_em = agora
                    part.save(update_fields=["saida_em"])
            # Adicionar/reativar/atualizar função
            for usuario, func in participantes:
                p = atuais.get(usuario.id)
                if p:
                    updates = []
                    if p.saida_em is not None:
                        p.saida_em = None
                        updates.append("saida_em")
                    if p.funcao != func:
                        p.funcao = func
                        updates.append("funcao")
                    if updates:
                        p.save(update_fields=list(set(updates)))
                else:
                    PlantaoParticipante.objects.create(plantao=ativo, usuario=usuario, funcao=func)

            # Atualiza string de equipe na sessão (para PDF) baseada nos participantes ATIVOS do plantão
            try:
                labels = []
                papel_map = { 'ENC':'Encarregado', 'MOT':'Motorista', 'AUX1':'Auxiliar 1', 'AUX2':'Auxiliar 2', '':'Integrante' }
                for p in ativo.participantes.select_related('usuario').filter(saida_em__isnull=True):
                    nome = (p.usuario.get_full_name() or p.usuario.username or '').strip().title()
                    labels.append(f"{papel_map.get(p.funcao,p.funcao)}: {nome}")
                if labels:
                    _session_set(request, SESSION_EQUIPE_STR, ", ".join(labels))
            except Exception:
                pass

            # Atualiza viatura se mudou (edge case)
            if ativo.viatura_id != v.id:
                ativo.viatura = v
                ativo.save(update_fields=["viatura"])
            messages.success(request, "Plantão compartilhado ativo para a equipe selecionada.")
            # Alerta amigável: se houver avarias registradas para a VTR (estado persistente), avisar imediatamente
            try:
                from viaturas.models import ViaturaAvariaEstado
                estado = ViaturaAvariaEstado.objects.filter(viatura=v).first()
                if estado and estado.get_labels():
                    messages.warning(request, f"Atenção: VTR {getattr(v,'prefixo','')} possui avarias registradas. Veja o painel do CECOM.")
            except Exception:
                pass
            return redirect("taloes:lista")
    else:
        # Se nenhum encarregado ainda definido, default = usuário logado
        if not initial.get("encarregado"):
            initial["encarregado"] = request.user.id
        form = PlantaoEquipeForm(initial=initial)
    return render(request, "taloes/viatura_wizard.html", {"form": form, "talao_id": None, "talao": None})
    
@login_required
def editar_plantao(request: HttpRequest):
    """Editar equipe e viatura do plantão ativo que o usuário participa/iniciou.

    - Pré-carrega viatura e participantes atuais (sem saída)
    - Permite alterar VTR (com verificação de conflito)
    - Permite incluir/remover/atualizar funções dos integrantes
    - Garante que o usuário logado permaneça na equipe
    - Atualiza variáveis de sessão relacionadas ao plantão
    """
    plantao = PlantaoCECOM.ativo_do_usuario_ou_participado(request.user)
    if not plantao:
        messages.info(request, "Você não possui plantão ativo para editar.")
        return redirect("taloes:lista")

    # Montar initial com VTR e participantes atuais (ativos)
    initial: dict[str, object] = {}
    if getattr(plantao, "viatura_id", None):
        initial["viatura"] = plantao.viatura_id
    ativos = list(plantao.participantes.select_related("usuario").filter(saida_em__isnull=True))
    func_map = {p.funcao: p.usuario_id for p in ativos}
    if func_map.get("ENC"): initial["encarregado"] = func_map["ENC"]
    if func_map.get("MOT"): initial["motorista"] = func_map["MOT"]
    if func_map.get("AUX1"): initial["auxiliar1"] = func_map["AUX1"]
    if func_map.get("AUX2"): initial["auxiliar2"] = func_map["AUX2"]
    # Coordenador/Líder vindo da sessão (não faz parte dos participantes do modelo)
    if (cid := _session_get(request, SESSION_COORDENADOR_ID)):
        initial["coordenador_lider"] = cid

    if request.method == "POST":
        form = PlantaoEquipeForm(request.POST)
        if form.is_valid():
            v = form.cleaned_data["viatura"]
            # Validar que usuário logado permanece na equipe
            selecionados = [
                form.cleaned_data.get("encarregado"),
                form.cleaned_data.get("motorista"),
                form.cleaned_data.get("auxiliar1"),
                form.cleaned_data.get("auxiliar2"),
            ]
            ids_sel = {getattr(u, 'id', None) for u in selecionados if u}
            if request.user.id not in ids_sel:
                form.add_error(None, "Você precisa permanecer em uma das funções da equipe.")
                return render(request, "taloes/editar_plantao.html", {"form": form})

            # Verificar conflito de VTR caso troque
            if plantao.viatura_id != v.id:
                conflito = PlantaoCECOM.objects.filter(ativo=True, viatura=v).exclude(pk=plantao.pk).exists()
                if conflito:
                    form.add_error("viatura", f"Viatura {v} já está em plantão ativo por outro grupo.")
                    return render(request, "taloes/editar_plantao.html", {"form": form})

            # Atualizar VTR se mudou
            if plantao.viatura_id != v.id:
                plantao.viatura = v
                plantao.save(update_fields=["viatura"])

            # Sincronizar participantes
            selecionados_list: list[tuple[object,str]] = []
            for campo, func in (("encarregado","ENC"),("motorista","MOT"),("auxiliar1","AUX1"),("auxiliar2","AUX2")):
                u = form.cleaned_data.get(campo)
                if u:
                    selecionados_list.append((u, func))

            atuais_map = {p.usuario_id: p for p in plantao.participantes.all()}
            selecionados_ids = {u.id for u,_ in selecionados_list}

            # Fechar quem saiu
            agora = timezone.now()
            for uid, part in list(atuais_map.items()):
                if part.saida_em is None and uid not in selecionados_ids:
                    part.saida_em = agora
                    part.save(update_fields=["saida_em"])

            # Adicionar/reativar/atualizar função
            for usuario, func in selecionados_list:
                p = atuais_map.get(usuario.id)
                if p:
                    updates = []
                    if p.saida_em is not None:
                        p.saida_em = None
                        updates.append("saida_em")
                    if p.funcao != func:
                        p.funcao = func
                        updates.append("funcao")
                    if updates:
                        p.save(update_fields=list(set(updates)))
                else:
                    PlantaoParticipante.objects.create(plantao=plantao, usuario=usuario, funcao=func)

            # Atualizar sessões úteis
            _session_set(request, SESSION_VIATURA_ID, v.id)
            _session_set(request, SESSION_ENCARREGADO_ID, getattr(form.cleaned_data.get("encarregado"), "id", None))
            _session_set(request, SESSION_MOTORISTA_ID, getattr(form.cleaned_data.get("motorista"), "id", None))
            _session_set(request, SESSION_AUX1_ID, getattr(form.cleaned_data.get("auxiliar1"), "id", None))
            _session_set(request, SESSION_AUX2_ID, getattr(form.cleaned_data.get("auxiliar2"), "id", None))
            # Atualizar Equipe (A/B/C/D)
            _session_set(request, SESSION_PLANTAO, (form.cleaned_data.get("plantao") or "").strip())
            # Coordenador/Líder (opcional)
            _session_set(request, SESSION_COORDENADOR_ID, getattr(form.cleaned_data.get("coordenador_lider"), "id", None))

            # Atualizar string amigável da equipe na sessão
            try:
                labels = []
                papel_map = { 'ENC':'Encarregado', 'MOT':'Motorista', 'AUX1':'Auxiliar 1', 'AUX2':'Auxiliar 2', '':'Integrante' }
                for p in plantao.participantes.select_related('usuario').filter(saida_em__isnull=True):
                    nome = (p.usuario.get_full_name() or p.usuario.username or '').strip().title()
                    labels.append(f"{papel_map.get(p.funcao,p.funcao)}: {nome}")
                if labels:
                    _session_set(request, SESSION_EQUIPE_STR, ", ".join(labels))
            except Exception:
                pass

            messages.success(request, "Plantão atualizado com sucesso.")
            return redirect("taloes:lista")
    else:
        form = PlantaoEquipeForm(initial=initial)

    return render(request, "taloes/editar_plantao.html", {"form": form})


@login_required
def novo_talao(request: HttpRequest):
    """
    Abre um novo talão já puxando viatura da sessão (se houver).
    """
    # Garante que o combo de "Código de ocorrência" esteja atualizado
    try:
        sync_codigos_from_naturezas()
    except Exception:
        pass  # não bloqueia a abertura da página se a sync falhar
    initial = {}
    # Preferir a viatura da sessão; fallback para viatura do plantão ativo
    viatura_obj = None
    try:
        vid = _session_get(request, SESSION_VIATURA_ID)
        if vid:
            from viaturas.models import Viatura as _V
            viatura_obj = _V.objects.filter(id=vid).first()
    except Exception:
        viatura_obj = None
    if not viatura_obj:
        try:
            ativo_tmp = PlantaoCECOM.ativo_do_usuario_ou_participado(request.user)
            if ativo_tmp and getattr(ativo_tmp, 'viatura_id', None):
                from viaturas.models import Viatura as _V
                viatura_obj = _V.objects.filter(id=ativo_tmp.viatura_id).first()
        except Exception:
            pass
    if viatura_obj:
        initial["viatura"] = viatura_obj
        # Pré-preencher KM inicial com o KM final do último talão FECHADO dessa viatura
        try:
            # Usa o id da viatura preferida (sessão/plantão) para sugerir o KM inicial
            _pref_vid = getattr(viatura_obj, 'id', None)
            ultimo_fechado = (
                Talao.objects.filter(viatura_id=_pref_vid, status="FECHADO", km_final__isnull=False)
                .order_by("-encerrado_em", "-iniciado_em")
                .first()
            )
            if ultimo_fechado and ultimo_fechado.km_final is not None:
                initial["km_inicial"] = ultimo_fechado.km_final
        except Exception:
            # Qualquer problema ao buscar histórico não deve bloquear a abertura do formulário
            pass

    # Bloquear se já existir talão ABERTO no plantão corrente
    ativo = PlantaoCECOM.ativo_do_usuario(request.user)
    if ativo:
        aberto_existente = Talao.objects.filter(status="ABERTO", iniciado_em__gte=ativo.inicio, criado_por=request.user).exists()
        if aberto_existente and request.method != "POST":
            messages.error(request, "Feche o talão aberto antes de criar outro.")
            return redirect("taloes:lista")

    if request.method == "POST":
        form = NovoTalaoForm(request.POST, plantao_ativo=ativo)
        if form.is_valid():
            t: Talao = form.save(commit=False)
            # >>> ESSENCIAL: quem criou (evita IntegrityError)
            t.criado_por = request.user
            t.status = "ABERTO"
            
            # Se houver plantão ativo, força a viatura do plantão (campo pode estar disabled)
            if ativo and hasattr(ativo, 'viatura_id') and ativo.viatura_id:
                t.viatura_id = ativo.viatura_id
            
            # equipe_texto: string da sessão para o PDF
            t.equipe_texto = _session_get(request, SESSION_EQUIPE_STR, "") or ""
            # Número sequencial dentro do plantão
            if ativo:
                ultimo = Talao.objects.filter(iniciado_em__gte=ativo.inicio, criado_por=request.user).order_by('-talao_numero').first()
                t.talao_numero = (ultimo.talao_numero + 1) if ultimo else 1
            else:
                t.talao_numero = 1
            # iniciado_em é default no modelo (timezone.now)
            t.save()
            # Opcional: vincula equipe nos campos de FK se existirem
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                ids = {
                    "encarregado_id": _session_get(request, SESSION_ENCARREGADO_ID),
                    "motorista_id": _session_get(request, SESSION_MOTORISTA_ID),
                    "auxiliar1_id": _session_get(request, SESSION_AUX1_ID),
                    "auxiliar2_id": _session_get(request, SESSION_AUX2_ID),
                }
                updates = []
                for attr, uid in ids.items():
                    if uid and hasattr(t, attr):
                        setattr(t, attr, User.objects.filter(id=uid).first())
                        updates.append(attr[:-3])  # remove _id
                if updates:
                    t.save(update_fields=list(set(updates)))
            except Exception:
                pass
            messages.success(request, f"Talão #{t.talao_numero} aberto.")
            return redirect("taloes:lista")
    else:
        form = NovoTalaoForm(initial=initial, plantao_ativo=ativo)

    return render(request, "taloes/novo.html", {"form": form})


# ======================
#   RELATÓRIO DE RONDA
# ======================

@login_required
def relatorio_ronda_salvar(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseBadRequest("Método inválido")
    form = RelatorioRondaForm(request.POST)
    if form.is_valid():
        texto = form.cleaned_data["texto"] or ""
        # Se houver plantão ativo (iniciado ou participado), salvar no rascunho compartilhado
        try:
            ativo = PlantaoCECOM.ativo_do_usuario_ou_participado(request.user)
        except Exception:
            ativo = None
        if ativo:
            try:
                if ativo.relatorio_rascunho != texto:
                    ativo.relatorio_rascunho = texto
                    ativo.save(update_fields=["relatorio_rascunho"])
            except Exception:
                pass
        # Também manter na sessão como cache/local fallback
        _session_set(request, SESSION_RELATORIO, texto)
        messages.success(request, "Rascunho salvo (compartilhado com a equipe).")
    return redirect("taloes:lista")


@login_required
def relatorio_ronda_apagar(request: HttpRequest):
    # Limpar rascunho do plantão compartilhado (se houver)
    try:
        ativo = PlantaoCECOM.ativo_do_usuario_ou_participado(request.user)
        if ativo and getattr(ativo, 'relatorio_rascunho', None) is not None:
            ativo.relatorio_rascunho = ""
            ativo.save(update_fields=["relatorio_rascunho"])
    except Exception:
        pass
    _session_set(request, SESSION_RELATORIO, "")
    messages.info(request, "Rascunho apagado para a equipe.")
    return redirect("taloes:lista")


# ======================
#   FINALIZAR PLANTÃO
# ======================

def _render_pdf_reportlab(title: str, linhas: list[str], encarregado_user=None, meta: dict | None = None) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    import base64
    from reportlab.lib.utils import ImageReader
    import io
    from PIL import Image

    buff = BytesIO()
    c = canvas.Canvas(buff, pagesize=A4)
    w, h = A4
    y = h - 50

    # ================= Cabeçalho Institucional (sem logo/brasão) =================
    if meta is None:
        meta = {}
    agora = timezone.now()
    user_name = meta.get('user_name') or meta.get('user') or ''
    plantao_id = meta.get('plantao_id')
    verificacao_token = (meta or {}).get('verificacao_token') or ''
    site_base_url = (meta or {}).get('site_base_url') or ''
    # Cabeçalho simplificado: apenas duas linhas
    header_lines = [
        "Secretaria Municipal de Segurança",
        "Relatório de Ronda",
    ]
    line_spacing = 12
    header_height = (len(header_lines) - 1) * line_spacing
    header_top_y = y

    c.setFont("Helvetica-Bold", 10)
    for i, hl in enumerate(header_lines):
        c.drawCentredString(w/2, header_top_y - (i*line_spacing), hl)

    # Avança Y para baixo do cabeçalho e desce a linha separadora um pouco mais
    y = header_top_y - (len(header_lines)*line_spacing) - 16
    c.setLineWidth(0.6)
    c.line(50, y, w-50, y)
    # Espaço entre linha e título (ajustável) - antes 10, agora 20 para afastar mais
    LINE_TITLE_GAP = 20
    y -= LINE_TITLE_GAP
    # Título
    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, y, title)
    y -= 22

    c.setFont("Helvetica", 10)
    # Função de quebra de linha por largura disponível
    def _wrap_parts(text: str, draw_x: float, max_w: float) -> list[str]:
        # quebra por palavras com fallback em caracteres longos
        words = (text or "").split(" ")
        out: list[str] = []
        cur = ""
        for wword in words:
            test = (cur + (" " if cur else "") + wword).strip()
            if c.stringWidth(test, "Helvetica", 10) <= max_w:
                cur = test
            else:
                if cur:
                    out.append(cur)
                # palavra sozinha maior que a largura -> cortar por caracteres
                chunk = ""
                for ch in wword:
                    if c.stringWidth(chunk + ch, "Helvetica", 10) <= max_w:
                        chunk += ch
                    else:
                        if chunk:
                            out.append(chunk)
                        chunk = ch
                cur = chunk
        if cur:
            out.append(cur)
        return out

    for ln in linhas:
        for part in (ln or "").split("\n"):
            # Token especial para desenhar imagem de recibo: "[IMG] /caminho/arquivo.jpg"
            if part.startswith("[IMG] "):
                img_path = part[6:].strip()
                try:
                    from PIL import Image as _PILImage
                    if img_path and Path(img_path).exists():
                        with _PILImage.open(img_path) as im:
                            # Converte para RGB se necessário
                            if im.mode in ("RGBA", "LA"):
                                bg = _PILImage.new("RGB", im.size, (255, 255, 255))
                                bg.paste(im, mask=im.split()[3] if im.mode == "RGBA" else None)
                                im = bg
                            # Dimensionar para caber (largura máx 340pt, altura máx 220pt)
                            max_w, max_h = 340.0, 220.0
                            iw, ih = im.size
                            # px->pt 1:1 é ok para reportlab com ImageReader; ajustamos por escala
                            esc = min(max_w / iw, max_h / ih, 1.0)
                            w_img, h_img = iw * esc, ih * esc
                            # Nova página se não couber
                            if y - h_img < 120:
                                c.showPage()
                                y = h - 60
                                c.setFont("Helvetica-Bold", 11)
                                c.drawString(50, y, title)
                                y -= 24
                                c.setFont("Helvetica", 10)
                            from reportlab.lib.utils import ImageReader
                            buf = io.BytesIO()
                            im.save(buf, format="PNG")
                            buf.seek(0)
                            reader = ImageReader(buf)
                            c.drawImage(reader, 60, y - h_img, width=w_img, height=h_img, mask='auto')
                            y -= (h_img + 10)
                            continue
                except Exception:
                    # Se falhar, cai para texto simples com o caminho
                    pass
            # Texto comum com quebra automática por largura
            # Detecta indentação simples (bullet "• " ou espaços à esquerda)
            draw_x = 50
            clean_part = part
            if part.startswith("• "):
                draw_x = 66
                clean_part = part
            else:
                # conta espaços iniciais (até 6 para evitar excesso)
                leading_spaces = len(part) - len(part.lstrip(' '))
                if leading_spaces:
                    draw_x = 50 + min(leading_spaces, 6) * 6
                    clean_part = part.lstrip(' ')

            max_text_w = (w - 50) - draw_x  # margem direita de 50
            wrapped = _wrap_parts(clean_part, draw_x, max_text_w)
            if not wrapped:
                wrapped = [""]
            for seg in wrapped:
                if y < 150:  # Mais espaço para assinatura
                    c.showPage()
                    # Redesenhar cabeçalho mínimo nas páginas seguintes (título curto)
                    y = h - 60
                    c.setFont("Helvetica-Bold", 11)
                    c.drawString(50, y, title)
                    y -= 24
                    c.setFont("Helvetica", 10)
                c.drawString(draw_x, y, seg)
                y -= 14

    # Bloco de assinatura com QR ao lado (estilo semelhante ao BO)
    perfil = getattr(encarregado_user, 'perfil', None) if encarregado_user else None
    nome_completo = (encarregado_user.get_full_name() or getattr(encarregado_user, 'username', '') or '').strip() if encarregado_user else ''
    cargo = getattr(perfil, 'cargo', 'Guarda Civil Municipal') if perfil else 'Guarda Civil Municipal'
    matricula = getattr(perfil, 'matricula', '') if perfil else ''

    # Espaço antes do bloco
    y -= 30
    box_left = 50
    box_right = w - 50
    box_width = box_right - box_left
    box_height = 130
    if y - box_height < 60:
        c.showPage(); y = h - 80
    # Contêiner (opcional uma borda leve)
    c.setLineWidth(0.5)
    c.roundRect(box_left, y - box_height, box_width, box_height, 6, stroke=1, fill=0)

    # Área esquerda: assinatura e linha
    left_pad = 12
    sig_area_w = box_width * 0.60
    sig_x = box_left + left_pad
    # Cabeçalho do bloco de assinatura
    c.setFont("Helvetica-Bold", 10)
    c.drawString(sig_x, y - 16, "Encarregado")
    sig_y_top = y - 32
    sig_y_bottom = y - box_height + 18
    # Tentar obter imagem da assinatura digital
    result = None
    if perfil:
        try:
            result = _obter_imagem_assinatura(perfil)
        except Exception:
            result = None
    # Dimensões padrão caso não haja assinatura
    draw_w = 0
    draw_h = 0
    if result:
        reader, w_img, h_img = result
        # Limitar para caber na área (levemente reduzido) e centralizar
        max_w, max_h = sig_area_w - 60, (sig_y_top - sig_y_bottom) - 60
        esc = min(max_w / w_img, max_h / h_img, 1.0) * 1.8
        draw_w, draw_h = w_img * esc, h_img * esc
        draw_x = sig_x + (sig_area_w - draw_w) / 2
        draw_y = sig_y_bottom + ((sig_y_top - sig_y_bottom) - draw_h) / 2 + 10
        c.drawImage(reader, draw_x, draw_y, width=draw_w, height=draw_h, mask='auto')
    # Linha de assinatura (mais curta e centralizada abaixo da assinatura)
    line_y = y - box_height + 28
    # Definir comprimento da linha relativo à assinatura (com mínimo/máximo)
    line_len = max(180, min(sig_area_w - 80, (draw_w or 200) + 60))
    line_x1 = sig_x + (sig_area_w - line_len) / 2
    line_x2 = line_x1 + line_len
    c.line(line_x1, line_y, line_x2, line_y)
    c.setFont("Helvetica", 8)
    label_nome = nome_completo or "Encarregado"
    mid_x = (line_x1 + line_x2) / 2
    c.drawCentredString(mid_x, line_y - 12, label_nome)
    # Informações abaixo da linha: Classe e Cargo (sem matrícula)
    # Exibir a classe no formato legível (ex.: "1ª Classe")
    classe_legivel = getattr(perfil, 'classe_legivel', '') if perfil else ''
    extras = []
    if classe_legivel:
        extras.append(f"Classe: {classe_legivel}")
    if cargo:
        extras.append(f"Cargo: {cargo}")
    if extras:
        c.drawCentredString(mid_x, line_y - 24, "  •  ".join(extras))

    # Área direita: QR code e label
    qr_pad = 12
    qr_side = min(95, box_height - 30)
    qr_x = box_left + sig_area_w + qr_pad
    qr_y = y - box_height + (box_height - qr_side) / 2
    try:
        import qrcode, io as _io
        # URL absoluta para verificação pública
        ver_path = reverse('taloes:verificar_relatorio_plantao', args=[verificacao_token or ''])
        base = (site_base_url or '').rstrip('/')
        if not base:
            # fallback: tentar construir de settings ou raiz
            from django.conf import settings as _settings
            base = getattr(_settings, 'SITE_BASE_URL', '') or ''
            base = (base or '').rstrip('/')
        ver_url = (base + ver_path) if base else ver_path
        qr_img = qrcode.make(ver_url)
        buf_qr = _io.BytesIO(); qr_img.save(buf_qr, format='PNG'); buf_qr.seek(0)
        from reportlab.lib.utils import ImageReader as _IR
        qr_reader = _IR(buf_qr)
        c.drawImage(qr_reader, qr_x, qr_y, width=qr_side, height=qr_side, mask='auto')
        c.setFont("Helvetica", 7)
        # Posicionar textos à direita do QR, centralizados verticalmente ao QR
        text_x = qr_x + qr_side + 8
        # Garantir que não ultrapasse a borda direita da caixa
        max_text_w = (box_right - 8) - text_x
        # Linhas: label acima, depois duas linhas do token
        mid_y = qr_y + (qr_side / 2.0)
        line_gap = 10
        text_y_label = mid_y + line_gap
        text_y_t1 = mid_y
        text_y_t2 = mid_y - line_gap
        # Desenhar label
        c.drawString(text_x, text_y_label, "Verificação Online")
        # Token em duas linhas (16+16) se disponível
        if verificacao_token:
            t1 = verificacao_token[:16]
            t2 = verificacao_token[16:32]
            c.drawString(text_x, text_y_t1, t1)
            if t2:
                c.drawString(text_x, text_y_t2, t2)
    except Exception:
        pass

    # Atualiza Y após bloco
    y = y - box_height - 20

    c.showPage()
    c.save()
    return buff.getvalue()


def _gerar_pdf_plantao_encerrado(request: HttpRequest, plantao_encerrado):
    """Gera PDF de um plantão específico (usado no encerramento)."""
    if not plantao_encerrado or not plantao_encerrado.inicio:
        raise Exception("Plantão inválido ou sem data de início")
    
    dt_ini = plantao_encerrado.inicio
    dt_fim = plantao_encerrado.encerrado_em or timezone.now()
    hoje = timezone.localdate(dt_ini)

    viatura_id = _session_get(request, SESSION_VIATURA_ID)
    taloes = (
        Talao.objects.select_related("viatura", "codigo_ocorrencia", "codigo_ocorrencia__grupo")
        .filter(iniciado_em__range=(dt_ini, dt_fim))
        .order_by("iniciado_em")
    )
    if viatura_id:
        taloes = taloes.filter(viatura_id=viatura_id)

    # Determinar encarregado: prioridade ENC do plantão; fallback sessão
    encarregado_user = None
    try:
        # Participante com funcao ENC
        enc_part = plantao_encerrado.participantes.select_related('usuario__perfil').filter(funcao='ENC').first()
        if enc_part:
            encarregado_user = enc_part.usuario
        else:
            encarregado_id = _session_get(request, SESSION_ENCARREGADO_ID)
            if encarregado_id:
                User = get_user_model()
                encarregado_user = User.objects.select_related('perfil').get(id=encarregado_id)
    except Exception:
        pass

    # Montar equipe detalhada diretamente dos participantes do plantão (ignora sessão)
    equipe_detalhada_linhas = []
    papel_map = { 'ENC':'Encarregado', 'MOT':'Motorista', 'AUX1':'Auxiliar 1', 'AUX2':'Auxiliar 2', '':'Integrante' }
    try:
        parts = plantao_encerrado.participantes.select_related('usuario__perfil').all()
        for p in parts:
            u = p.usuario
            perfil = getattr(u, 'perfil', None)
            nome = (u.get_full_name() or u.username or '').strip().title()
            matricula = getattr(perfil, 'matricula', '') if perfil else ''
            # Classe legível (ex.: "1ª Classe")
            classe = getattr(perfil, 'classe_legivel', '') if perfil else ''
            cargo = getattr(perfil, 'cargo', '') if perfil else ''
            desc = f"{papel_map.get(p.funcao,p.funcao)}: {nome}"
            extra = []
            if matricula:
                extra.append(f"Mat: {matricula}")
            if classe:
                extra.append(f"Classe: {classe}")
            if cargo and cargo != 'Guarda Civil Municipal':
                extra.append(cargo)
            if p.saida_em:
                extra.append(f"Saiu: {timezone.localtime(p.saida_em):%H:%M}")
            if extra:
                desc += " (" + ", ".join(extra) + ")"
            equipe_detalhada_linhas.append(desc)
    except Exception:
        pass

    equipe = " | ".join(equipe_detalhada_linhas)
    plantao = _session_get(request, SESSION_PLANTAO, "")
    relatorio = _session_get(request, SESSION_RELATORIO, "")
    try:
        if getattr(plantao_encerrado, 'relatorio_rascunho', None) not in (None, ""):
            relatorio = plantao_encerrado.relatorio_rascunho
    except Exception:
        pass

    # Coordenador/Líder para o relatório (da sessão; fallback: encarregado do plantão)
    coord_user = None
    try:
        cid = _session_get(request, SESSION_COORDENADOR_ID)
        if cid:
            User = get_user_model()
            coord_user = User.objects.select_related('perfil').filter(id=cid).first()
    except Exception:
        coord_user = None

    linhas: list[str] = []
    # Exibir apenas o usuário (sem a data ao lado)
    linhas.append(f"Usuário: {request.user.get_username()}")
    # Cabeçalho com período do plantão
    try:
        ini_str = timezone.localtime(dt_ini).strftime('%d/%m/%Y %H:%M') if dt_ini else '-'
        fim_str = timezone.localtime(dt_fim).strftime('%d/%m/%Y %H:%M') if dt_fim else '-'
        linhas.append(f"Plantão: Início {ini_str} — Fim {fim_str}")
    except Exception:
        pass
    # Coordenador/Líder (se existir)
    try:
        if coord_user:
            perfil = getattr(coord_user, 'perfil', None)
            mat = getattr(perfil, 'matricula', '') if perfil else ''
            nome = (coord_user.get_full_name() or coord_user.username or '').strip().title()
            left = (mat or '').strip()
            label = f"{left} - {nome}" if left else nome
            linhas.append(f"Coordenador / Líder: {label}")
    except Exception:
        pass

    if plantao:
        linhas.append(f"Equipe: {plantao}")
    if equipe_detalhada_linhas:
        for ln_eq in equipe_detalhada_linhas:
            linhas.append(f"• {ln_eq}")
        linhas.append("")
    else:
        linhas.append("")
    linhas.append("Talões do dia:")

    if taloes.exists():
        # Preparar mapa de números lógicos (caso exista atributo numerado no modelo)
        # Se o modelo tiver campo 'talao_numero', usamos; senão enumeramos sequencialmente a partir de 1
        for idx, t in enumerate(taloes, start=1):
            vtr = getattr(t.viatura, "prefixo", "-") if t.viatura else "-"
            cod = f"{t.codigo_ocorrencia.sigla} — {t.codigo_ocorrencia.descricao}" if t.codigo_ocorrencia else "-"
            km = f"{t.km_inicial}" + (f" → {t.km_final}" if t.km_final is not None else "")
            numero_logico = getattr(t, 'talao_numero', None) or idx
            ini_str = timezone.localtime(t.iniciado_em).strftime('%d/%m/%Y %H:%M') if getattr(t, 'iniciado_em', None) else '-'
            fim_dt = getattr(t, 'encerrado_em', None)
            fim_str = timezone.localtime(fim_dt).strftime('%d/%m/%Y %H:%M') if fim_dt else None
            tempo_str = f"Início {ini_str}" + (f" — Fim {fim_str}" if fim_str else "")
            # Número do BOGCM (último BO do talão)
            bo_str = "—"
            try:
                bo = t.bos.last()
                if bo and getattr(bo, 'numero', None):
                    bo_str = bo.numero
                elif bo:
                    bo_str = f"#{bo.pk}"
            except Exception:
                pass
            # Local + Referência (bairro — rua)
            try:
                local_str = getattr(t, 'local_display', None) or (
                    (t.local_bairro or '') + ((' — ' + t.local_rua) if getattr(t, 'local_rua', '') else '')
                )
            except Exception:
                local_str = (t.local_bairro or '')
            linhas.append(
                f"• Talão #{numero_logico} — VTR {vtr} — KM {km} — {cod} — Nº BOGCM: {bo_str} — Local: {local_str or '—'} — {tempo_str}"
            )
            
            # Incluir abastecimentos (se houver)
            try:
                abs_list = t.abastecimentos.all()
                if abs_list.exists():
                    linhas.append("  Abastecimentos:")
                    for ab in abs_list:
                        recibo = getattr(ab.recibo_do_posto, 'path', None) or None
                        linhas.append(
                            f"    - Req: {ab.requisicao_numero or '—'} | Comb: {ab.get_tipo_combustivel_display()} | Litros: {ab.litros}"
                            + (f" | Recibo: {Path(getattr(ab.recibo_do_posto,'name','')).name}" if getattr(ab, 'recibo_do_posto', None) else "")
                        )
                        # Se houver anexo imagem/PDF, tentar desenhar imagem (PDF ignorado aqui)
                        try:
                            if recibo and str(recibo).lower().endswith((".jpg", ".jpeg", ".png", ".gif")):
                                linhas.append(f"[IMG] {recibo}")
                        except Exception:
                            pass
            except Exception:
                pass

            # Incluir AITs (se houver)
            try:
                aits = t.aits.all()
                if aits.exists():
                    linhas.append("  AIT's emitidas:")
                    for a in aits.select_related('integrante').order_by('criado_em'):
                        try:
                            nome = (a.integrante.get_full_name() or a.integrante.username).strip() if a.integrante else '—'
                            perfil = getattr(a.integrante, 'perfil', None)
                            mat = getattr(perfil, 'matricula', '') if perfil else ''
                            pre = (mat + ' - ') if mat else ''
                            linhas.append(f"    - {pre}{nome}: {a.numero}")
                        except Exception:
                            linhas.append(f"    - {a.numero}")
            except Exception:
                pass

            # Incluir abordados se existirem
            try:
                abordados = t.abordados.all()
                if abordados.exists():
                    linhas.append(f"  Abordados:")
                    for ab in abordados:
                        if ab.tipo == "PESSOA":
                            linha_ab = f"    - Pessoa: {ab.nome or 'N/I'}"
                            if ab.documento:
                                linha_ab += f" (Doc: {ab.documento})"
                        else:
                            linha_ab = f"    - Veículo: {ab.placa or 'N/I'}"
                            if ab.modelo:
                                linha_ab += f" - {ab.modelo}"
                            if ab.cor:
                                linha_ab += f" ({ab.cor})"
                        if ab.observacoes:
                            linha_ab += f" | Obs: {ab.observacoes}"
                        linhas.append(linha_ab)
            except Exception:
                pass
    else:
        linhas.append("• (nenhum)")

    # Checklist de avarias (usar registro ligado ao plantão ou do dia)
    try:
        ck = ChecklistViatura.objects.filter(plantao_id=getattr(plantao_encerrado, 'id', None)).first() or \
             ChecklistViatura.objects.filter(usuario=request.user, data=timezone.localdate(dt_ini)).first()
        if ck:
            marcados = ck.itens_marcados()
            if marcados:
                linhas.append("")
                linhas.append("Checklist de Viatura (itens com avaria):")
                for item in marcados:
                    linhas.append(f"• {item}")
    except Exception:
        pass

    linhas.append("")
    linhas.append("Relatório de Ronda:")
    linhas.append(relatorio or "(vazio)")

    # Garantir token de verificação no plantão
    try:
        if plantao_encerrado and not (plantao_encerrado.verificacao_token or '').strip():
            plantao_encerrado.verificacao_token = secrets.token_hex(16)
            plantao_encerrado.save(update_fields=['verificacao_token'])
    except Exception:
        pass

    # gera PDF com assinatura do encarregado
    pdf_bytes = _render_pdf_reportlab(
        f"Relatório de Plantão — {hoje.strftime('%d/%m/%Y')}",
        linhas,
        encarregado_user,
        meta={
            'user_name': request.user.get_username(),
            'plantao_id': getattr(plantao_encerrado, 'id', None),
            'verificacao_token': getattr(plantao_encerrado, 'verificacao_token', ''),
            'site_base_url': (getattr(settings, 'SITE_BASE_URL', '') or request.build_absolute_uri('/').rstrip('/')),
        }
    )

    # salva e registra documento assinável
    _ensure_media()
    out_dir = _user_dir(request.user)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{hoje.isoformat()}.pdf"
    out_path.write_bytes(pdf_bytes)

    # Registrar documento assinável para Comando
    try:
        from common.models import DocumentoAssinavel
        # Verificar se já existe documento para este plantão específico
        plantao_id = getattr(plantao_encerrado, 'id', None)
        arquivo_nome = f"plantao_{plantao_id}_{hoje.isoformat()}.pdf"
        ja_existe = DocumentoAssinavel.objects.filter(
            tipo="PLANTAO",
            usuario_origem=request.user,
            arquivo__icontains=arquivo_nome
        ).exists()
        
        if not ja_existe:
            from django.core.files.base import File
            with open(out_path, 'rb') as fpdf:
                doc = DocumentoAssinavel(
                    tipo="PLANTAO",
                    usuario_origem=request.user,
                    encarregado_assinou=True,
                )
                doc.arquivo.save(out_path.name, File(fpdf), save=True)
                print(f"Documento criado para comando - ID: {doc.id}")
        else:
            print(f"Documento já existe para o plantão {plantao_id}")
    except Exception as e:
        print(f"Erro ao criar documento: {e}")
        pass

    return out_path


@login_required
def finalizar_plantao_pdf(request: HttpRequest):
    """
    Gera PDF com:
      - Talões do período do plantão ativo (filtrados pela viatura escolhida no setup, se houver)
      - Equipe/Plantão da sessão
      - Relatório de Ronda (rascunho)
      - Assinatura do encarregado
    Salva o PDF em MEDIA_ROOT/plantao/<user_id>/YYYY-MM-DD.pdf e faz o download.
    """
    # Buscar plantão ativo para usar o período correto
    ativo = PlantaoCECOM.ativo_do_usuario(request.user)
    hoje = timezone.localdate()
    
    if ativo and ativo.inicio:
        dt_ini = ativo.inicio
        dt_fim = timezone.now()  # até agora
    else:
        # Se não há plantão ativo, não gerar PDF
        messages.error(request, "Não há plantão ativo. Inicie um plantão primeiro.")
        return redirect("taloes:lista")

    viatura_id = _session_get(request, SESSION_VIATURA_ID)
    taloes = (
        Talao.objects.select_related("viatura", "codigo_ocorrencia", "codigo_ocorrencia__grupo")
        .filter(iniciado_em__range=(dt_ini, dt_fim), criado_por=request.user)
        .order_by("iniciado_em")
    )
    if viatura_id:
        taloes = taloes.filter(viatura_id=viatura_id)

    # Buscar o encarregado da sessão
    encarregado_user = None
    encarregado_id = _session_get(request, SESSION_ENCARREGADO_ID)
    if encarregado_id:
        try:
            User = get_user_model()
            encarregado_user = User.objects.select_related('perfil').get(id=encarregado_id)
        except:
            pass

    equipe = _session_get(request, SESSION_EQUIPE_STR, "")
    plantao = _session_get(request, SESSION_PLANTAO, "")
    relatorio = _session_get(request, SESSION_RELATORIO, "")
    try:
        if ativo and getattr(ativo, 'relatorio_rascunho', None) not in (None, ""):
            relatorio = ativo.relatorio_rascunho
    except Exception:
        pass

    # Coordenador/Líder para o relatório (da sessão)
    coord_user = None
    try:
        cid = _session_get(request, SESSION_COORDENADOR_ID)
        if cid:
            User = get_user_model()
            coord_user = User.objects.select_related('perfil').filter(id=cid).first()
    except Exception:
        coord_user = None

    linhas: list[str] = []
    linhas.append(f"Usuário: {request.user.get_username()} — Data: {hoje.strftime('%d/%m/%Y')}")
    # Coordenador/Líder (se existir)
    try:
        if coord_user:
            perfil = getattr(coord_user, 'perfil', None)
            mat = getattr(perfil, 'matricula', '') if perfil else ''
            nome = (coord_user.get_full_name() or coord_user.username or '').strip().title()
            left = (mat or '').strip()
            label = f"{left} - {nome}" if left else nome
            linhas.append(f"Coordenador / Líder: {label}")
    except Exception:
        pass
    if plantao:
        linhas.append(f"Equipe: {plantao}")
    if equipe:
        linhas.append(f"Equipe: {equipe}")
    linhas.append("")
    linhas.append("Talões do dia:")

    if taloes.exists():
        for idx, t in enumerate(taloes, start=1):
            vtr = getattr(t.viatura, "prefixo", "-") if t.viatura else "-"
            cod = f"{t.codigo_ocorrencia.sigla} — {t.codigo_ocorrencia.descricao}" if t.codigo_ocorrencia else "-"
            km = f"{t.km_inicial}" + (f" → {t.km_final}" if t.km_final is not None else "")
            numero_logico = getattr(t, 'talao_numero', None) or idx
            ini_str = timezone.localtime(t.iniciado_em).strftime('%d/%m/%Y %H:%M') if getattr(t, 'iniciado_em', None) else '-'
            fim_dt = getattr(t, 'encerrado_em', None)
            fim_str = timezone.localtime(fim_dt).strftime('%d/%m/%Y %H:%M') if fim_dt else None
            tempo_str = f"Início {ini_str}" + (f" — Fim {fim_str}" if fim_str else "")
            # Número do BOGCM (último BO do talão)
            bo_str = "—"
            try:
                bo = t.bos.last()
                if bo and getattr(bo, 'numero', None):
                    bo_str = bo.numero
                elif bo:
                    bo_str = f"#{bo.pk}"
            except Exception:
                pass
            # Local + Referência (bairro — rua)
            try:
                local_str = getattr(t, 'local_display', None) or (
                    (t.local_bairro or '') + ((' — ' + t.local_rua) if getattr(t, 'local_rua', '') else '')
                )
            except Exception:
                local_str = (t.local_bairro or '')
            linhas.append(
                f"• Talão #{numero_logico} — VTR {vtr} — KM {km} — {cod} — Nº BOGCM: {bo_str} — Local: {local_str or '—'} — {tempo_str}"
            )
            
            # Incluir abastecimentos (se houver)
            try:
                abs_list = t.abastecimentos.all()
                if abs_list.exists():
                    linhas.append("  Abastecimentos:")
                    for ab in abs_list:
                        recibo = getattr(ab.recibo_do_posto, 'path', None) or None
                        linhas.append(
                            f"    - Req: {ab.requisicao_numero or '—'} | Comb: {ab.get_tipo_combustivel_display()} | Litros: {ab.litros}"
                            + (f" | Recibo: {Path(getattr(ab.recibo_do_posto,'name','')).name}" if getattr(ab, 'recibo_do_posto', None) else "")
                        )
                        try:
                            if recibo and str(recibo).lower().endswith((".jpg", ".jpeg", ".png", ".gif")):
                                linhas.append(f"[IMG] {recibo}")
                        except Exception:
                            pass
            except Exception:
                pass

            # Incluir AITs (se houver)
            try:
                aits = t.aits.all()
                if aits.exists():
                    linhas.append("  AIT's emitidas:")
                    for a in aits.select_related('integrante').order_by('criado_em'):
                        try:
                            nome = (a.integrante.get_full_name() or a.integrante.username).strip() if a.integrante else '—'
                            perfil = getattr(a.integrante, 'perfil', None)
                            mat = getattr(perfil, 'matricula', '') if perfil else ''
                            pre = (mat + ' - ') if mat else ''
                            linhas.append(f"    - {pre}{nome}: {a.numero}")
                        except Exception:
                            linhas.append(f"    - {a.numero}")
            except Exception:
                pass

            # Incluir abordados se existirem
            try:
                abordados = t.abordados.all()
                if abordados.exists():
                    linhas.append(f"  Abordados:")
                    for ab in abordados:
                        if ab.tipo == "PESSOA":
                            linha_ab = f"    - Pessoa: {ab.nome or 'N/I'}"
                            if ab.documento:
                                linha_ab += f" (Doc: {ab.documento})"
                        else:
                            linha_ab = f"    - Veículo: {ab.placa or 'N/I'}"
                            if ab.modelo:
                                linha_ab += f" - {ab.modelo}"
                            if ab.cor:
                                linha_ab += f" ({ab.cor})"
                        if ab.observacoes:
                            linha_ab += f" | Obs: {ab.observacoes}"
                        linhas.append(linha_ab)
            except Exception:
                # Se não existir o relacionamento, ignora
                pass
    else:
        linhas.append("• (nenhum)")

    linhas.append("")
    # Checklist (itens marcados) para geração manual
    try:
        ck = ChecklistViatura.objects.filter(usuario=request.user, data=timezone.localdate()).first()
        if ck:
            marcados = ck.itens_marcados()
            if marcados:
                linhas.append("")
                linhas.append("Checklist de Viatura (itens com avaria):")
                for item in marcados:
                    linhas.append(f"• {item}")
    except Exception:
        pass
    linhas.append("")
    linhas.append("Relatório de Ronda:")
    linhas.append(relatorio or "(vazio)")

    # Garantir token de verificação no plantão ativo
    try:
        if ativo and not (ativo.verificacao_token or '').strip():
            ativo.verificacao_token = secrets.token_hex(16)
            ativo.save(update_fields=['verificacao_token'])
    except Exception:
        pass

    # gera PDF com assinatura do encarregado
    try:
        pdf_bytes = _render_pdf_reportlab(
            f"Relatório de Plantão — {hoje.strftime('%d/%m/%Y')}",
            linhas,
            encarregado_user,
            meta={
                'user_name': request.user.get_username(),
                'plantao_id': getattr(ativo, 'id', None),
                'verificacao_token': getattr(ativo, 'verificacao_token', ''),
                'site_base_url': (getattr(settings, 'SITE_BASE_URL', '') or request.build_absolute_uri('/').rstrip('/')),
            }
        )
    except Exception as e:
        messages.error(request, f"Não foi possível gerar o PDF ({e}).")
        return redirect("taloes:lista")

    # salva e devolve
    _ensure_media()
    out_dir = _user_dir(request.user)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{hoje.isoformat()}.pdf"
    out_path.write_bytes(pdf_bytes)

    # Registrar documento assinável (relatório de plantão) para Comando
    try:
        from common.models import DocumentoAssinavel
        if not DocumentoAssinavel.objects.filter(arquivo__icontains=out_path.name).exists():
            # Abrir arquivo para salvar via FileField
            from django.core.files.base import File
            with open(out_path, 'rb') as fpdf:
                doc = DocumentoAssinavel(
                    tipo="PLANTAO",
                    usuario_origem=request.user,
                    encarregado_assinou=True,
                )
                doc.arquivo.save(out_path.name, File(fpdf), save=True)
    except Exception:
        pass

    return FileResponse(open(out_path, "rb"), as_attachment=True, filename=out_path.name, content_type="application/pdf")


# ======================
#   VERIFICAÇÃO PÚBLICA
# ======================

def verificar_relatorio_plantao(request: HttpRequest, token: str):
    """Página pública de verificação do Relatório de Plantão via token.

    Exibe status OK com informações do plantão associado ao token.
    """
    token = (token or '').strip()
    from django.shortcuts import get_object_or_404
    from cecom.models import PlantaoCECOM

    plantao = get_object_or_404(PlantaoCECOM, verificacao_token=token)
    participantes = []
    try:
        participantes = plantao.participantes_labeled()
    except Exception:
        participantes = []

    contexto = {
        'ok': True,
        'token': token,
        'plantao': plantao,
        'inicio': plantao.inicio,
        'encerrado_em': plantao.encerrado_em,
        'ativo': plantao.ativo,
        'iniciado_por': plantao.iniciado_por,
        'viatura': getattr(plantao, 'viatura', None),
        'participantes': participantes,
        'gerado_em': timezone.now(),
    }
    return render(request, 'taloes/verificar_relatorio_plantao.html', contexto)


# ======================
#   INICIAR/ENCERRAR PLANTÃO
# ======================

@login_required
def encerrar_plantao(request: HttpRequest):
    """Encerra o plantão ativo, gera PDF do dia e redireciona para Documentos."""
    # Plantão ativo em que o usuário é participante
    ativo = PlantaoCECOM.objects.filter(ativo=True, participantes__usuario=request.user).order_by('-inicio').first()
    if not ativo:
        messages.info(request, "Você não participa de um plantão ativo.")
        return redirect("taloes:lista")
    
    # Verificar se o usuário é o encarregado
    participante = ativo.participantes.filter(usuario=request.user, saida_em__isnull=True).first()
    if not participante or participante.funcao != 'ENC':
        messages.error(request, "Apenas o Encarregado pode realizar essa ação.")
        return redirect("taloes:lista")

    # Verificar se há talões no período do plantão
    inicio = getattr(ativo, "inicio", None)
    if not inicio:
        messages.error(request, "Plantão ativo sem data de início definida.")
        return redirect("taloes:lista")
    
    viatura_id = _session_get(request, SESSION_VIATURA_ID)
    # Filtrar talões entre início do plantão e agora
    # Talões de qualquer participante durante o período
    participante_ids = list(ativo.participantes.values_list('usuario_id', flat=True))
    taloes_plantao = Talao.objects.filter(
        iniciado_em__gte=inicio,
        iniciado_em__lte=timezone.now(),
    ).filter(
        models.Q(criado_por_id__in=participante_ids) |
        models.Q(encarregado_id__in=participante_ids) |
        models.Q(motorista_id__in=participante_ids) |
        models.Q(auxiliar1_id__in=participante_ids) |
        models.Q(auxiliar2_id__in=participante_ids)
    ).distinct()
    if viatura_id:
        taloes_plantao = taloes_plantao.filter(viatura_id=viatura_id)
    
    # Regra: não permitir encerrar se houver talões ABERTOS no período deste plantão
    abertos = taloes_plantao.filter(status="ABERTO")
    if abertos.exists():
        messages.error(request, "Existem talões ABERTOS. Feche todos antes de encerrar o plantão.")
        return redirect("taloes:lista")
    
    # Regra: deve haver pelo menos um talão no período do plantão
    if not taloes_plantao.exists():
        messages.error(request, "Não há talões registrados neste plantão. Registre pelo menos um talão antes de encerrar.")
        return redirect("taloes:lista")
    
    # Verificar relatório de ronda
    relatorio = _session_get(request, SESSION_RELATORIO, "")
    if not relatorio or not relatorio.strip():
        messages.error(request, "O relatório de ronda não foi preenchido. Complete o relatório antes de encerrar o plantão.")
        return redirect("taloes:lista")

    # Marcar encerrado
    ativo.encerrado_em = timezone.now()
    ativo.ativo = False
    ativo.save(update_fields=["encerrado_em", "ativo"])

    # Limpar string de equipe da sessão (somente deste usuário; outros limpam ao acessar)
    _session_set(request, SESSION_EQUIPE_STR, "")

    # Associar checklist do dia ao plantão e preparar para novo plantão (opcional reset)
    try:
        hoje = timezone.localdate()
        ck = ChecklistViatura.objects.filter(usuario=request.user, data=hoje, plantao_id__isnull=True).first()
        if ck:
            ck.plantao_id = getattr(ativo, 'id', None)
            ck.save(update_fields=["plantao_id"])
        # Para o próximo plantão usuário terá que marcar de novo (mantemos registro histórico)
    except Exception:
        pass

    # Gera PDF do plantão recém-encerrado
    try:
        # Gerar PDF usando dados do plantão que acabou de ser encerrado
        response = _gerar_pdf_plantao_encerrado(request, ativo)
        messages.success(request, "Plantão encerrado e PDF gerado.")
    except Exception as e:  # pragma: no cover
        messages.error(request, f"Plantão encerrado, mas houve erro ao gerar o PDF: {e}")

    return redirect("taloes:meus_documentos")


# ======================
#   MEUS DOCUMENTOS
# ======================

@login_required
def meus_documentos(request: HttpRequest):
    _ensure_media()
    media_base = MEDIA_BASE
    media_base.mkdir(parents=True, exist_ok=True)

    # Identificar se é o superusuário especial 'moises'
    try:
        is_moises = getattr(request.user, 'is_superuser', False) and ((request.user.get_username() or request.user.username or '').strip().lower() == 'moises')
    except Exception:
        is_moises = False

    arquivos = []

    if not is_moises:
        # Comportamento normal: apenas documentos do próprio usuário
        out_dir = _user_dir(request.user)
        out_dir.mkdir(parents=True, exist_ok=True)
        arquivos_raw = sorted(out_dir.glob("*.pdf"), reverse=True)
        base_url = (settings.MEDIA_URL or "/media/").rstrip("/") + f"/plantao/{request.user.id}/"

        # Extrair datas a partir do nome do arquivo (yyyy-mm-dd.pdf)
        datas = set(); nome_para_data = {}
        from datetime import datetime
        for p in arquivos_raw:
            try:
                d = datetime.strptime(p.name[:10], "%Y-%m-%d").date()
                datas.add(d); nome_para_data[p.name] = d
            except Exception:
                continue

        # Mapear plantões do usuário (iniciados por ele OU que ele participou) nessas datas
        plantoes_map = {}
        if datas:
            from django.db.models import Q as _Q
            qs = PlantaoCECOM.objects.filter(
                _Q(iniciado_por=request.user) | _Q(participantes__usuario=request.user),
                inicio__date__in=datas,
            ).prefetch_related('participantes__usuario').order_by('inicio').distinct()
            for pl in qs:
                plantoes_map[pl.inicio.date()] = pl

        # Montagem
        for p in arquivos_raw:
            pl = None
            d = nome_para_data.get(p.name)
            if d:
                pl = plantoes_map.get(d)
                if not pl:
                    # Fallback: buscar diretamente por este dia
                    from django.db.models import Q as _Q
                    pl = PlantaoCECOM.objects.filter(
                        _Q(iniciado_por=request.user) | _Q(participantes__usuario=request.user),
                        inicio__date=d,
                    ).order_by('-inicio').first()
            if not pl:
                # Fallback final: último plantão do usuário (iniciado ou participado)
                from django.db.models import Q as _Q
                pl = PlantaoCECOM.objects.filter(
                    _Q(iniciado_por=request.user) | _Q(participantes__usuario=request.user)
                ).order_by('-inicio').first()
            equipe_str = "-"; plantao_id = inicio_fmt = encerrado_fmt = "-"
            if pl:
                plantao_id = pl.id
                from django.utils import timezone as _tz
                inicio_fmt = _tz.localtime(pl.inicio).strftime('%d/%m/%Y %H:%M') if pl.inicio else '-'
                encerrado_fmt = _tz.localtime(pl.encerrado_em).strftime('%d/%m/%Y %H:%M') if pl.encerrado_em else ('(ativo)' if pl.ativo else '-')
                try:
                    participantes = pl.participantes_labeled()
                    if participantes:
                        equipe_str = " | ".join(f"{lbl}: {nome}" for lbl, nome in participantes)
                except Exception:
                    pass
            arquivos.append({
                'name': p.name,
                'url': base_url + p.name,
                'download_url': reverse('taloes:download_documento') + f"?nome={p.name}",
                'plantao_id': plantao_id,
                'inicio': inicio_fmt,
                'encerrado': encerrado_fmt,
                'equipe': equipe_str,
                'encerrado_dt': getattr(pl, 'encerrado_em', None) or getattr(pl, 'inicio', None),
            })
    else:
        # Modo administrador (moises): listar PDFs de todos os usuários
        from datetime import datetime
        # Coletar todos os arquivos por usuário
        uid_to_files: dict[int, list[Path]] = {}
        for d in media_base.iterdir():
            if d.is_dir():
                try:
                    uid = int(d.name)
                except Exception:
                    continue
                files = sorted(d.glob('*.pdf'), reverse=True)
                if files:
                    uid_to_files[uid] = files
        # Preparar datas por uid
        dates_by_uid: dict[int, set] = {}
        for uid, files in uid_to_files.items():
            s = set()
            for p in files:
                try:
                    d = datetime.strptime(p.name[:10], "%Y-%m-%d").date()
                    s.add(d)
                except Exception:
                    continue
            if s:
                dates_by_uid[uid] = s
        # Buscar plantões por uid/data
        from django.db.models import Q
        pl_map = {}  # (uid, date) -> PlantaoCECOM
        for uid, dates in dates_by_uid.items():
            if not dates:
                continue
            qs = PlantaoCECOM.objects.filter(iniciado_por_id=uid, inicio__date__in=list(dates)).prefetch_related('participantes__usuario').order_by('inicio')
            for pl in qs:
                pl_map[(uid, pl.inicio.date())] = pl
        # Montar saída
        media_url_root = (settings.MEDIA_URL or "/media/").rstrip("/") + "/plantao/"
        for uid, files in uid_to_files.items():
            base_url = f"{media_url_root}{uid}/"
            for p in files:
                d = None
                try:
                    d = datetime.strptime(p.name[:10], "%Y-%m-%d").date()
                except Exception:
                    pass
                pl = pl_map.get((uid, d)) if d else None
                equipe_str = "-"; plantao_id = inicio_fmt = encerrado_fmt = "-"
                if pl:
                    plantao_id = pl.id
                    from django.utils import timezone as _tz
                    inicio_fmt = _tz.localtime(pl.inicio).strftime('%d/%m/%Y %H:%M') if pl.inicio else '-'
                    encerrado_fmt = _tz.localtime(pl.encerrado_em).strftime('%d/%m/%Y %H:%M') if pl.encerrado_em else ('(ativo)' if pl.ativo else '-')
                    try:
                        participantes = pl.participantes_labeled()
                        if participantes:
                            equipe_str = " | ".join(f"{lbl}: {nome}" for lbl, nome in participantes)
                    except Exception:
                        pass
                arquivos.append({
                    'name': p.name,
                    'url': base_url + p.name,
                    'download_url': reverse('taloes:download_documento') + f"?nome={p.name}&uid={uid}",
                    'plantao_id': plantao_id,
                    'inicio': inicio_fmt,
                    'encerrado': encerrado_fmt,
                    'equipe': equipe_str,
                    'uid': uid,
                    'encerrado_dt': getattr(pl, 'encerrado_em', None) or getattr(pl, 'inicio', None),
                })

    # Ordenar como a lista de Talões do Django (mais recentes primeiro para numerar inversamente)
    try:
        from datetime import datetime as _dt
        def _as_dt(item):
            v = item.get('encerrado_dt') or None
            return v or _dt.min
        arquivos.sort(key=_as_dt, reverse=True)
    except Exception:
        pass

    # Buscar todos os plantões e numerar sequencialmente conforme admin
    from django.db.models import Q as _Q
    if is_moises:
        # Moises vê todos os plantões do sistema
        plantoes_all = PlantaoCECOM.objects.all().order_by('inicio').distinct()
    else:
        # Usuário vê apenas seus plantões
        plantoes_all = PlantaoCECOM.objects.filter(
            _Q(iniciado_por=request.user) | _Q(participantes__usuario=request.user)
        ).order_by('inicio').distinct()

    # Criar mapa de plantao_id -> número sequencial
    plantao_to_numero = {pl.id: idx + 1 for idx, pl in enumerate(plantoes_all)}

    # Adicionar número sequencial aos arquivos
    for arq in arquivos:
        pid = arq.get('plantao_id')
        arq['numero_sequencial'] = plantao_to_numero.get(pid) if pid and pid != '-' else None

    paginator = Paginator(arquivos, 30)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, "taloes/documentos.html", {"page_obj": page_obj})


@login_required
def checklist_viatura(request: HttpRequest):
    """Formulário do checklist (marcar apenas itens com avaria)."""
    ativo = PlantaoCECOM.ativo_do_usuario_ou_participado(request.user)
    if not ativo:
        messages.error(request, "Inicie um plantão para usar o checklist.")
        return redirect("taloes:lista")
    hoje = timezone.localdate()
    ck, _ = ChecklistViatura.objects.get_or_create(usuario=request.user, data=hoje, defaults={'plantao_id': getattr(ativo,'id',None)})
    if request.method == 'POST':
        form = ChecklistViaturaForm(request.POST, instance=ck)
        if form.is_valid():
            saved = form.save()
            # Garante vinculação ao plantão atual SEMPRE, para refletir a VTR em uso
            # (um checklist por usuário/dia; ao trocar de plantão no mesmo dia, reata este checklist ao plantão ativo)
            if getattr(ativo, 'id', None) and saved.plantao_id != ativo.id:
                saved.plantao_id = ativo.id
                saved.save(update_fields=["plantao_id"])
            # Registrar log desta submissão para auditoria
            try:
                from django.apps import apps
                import json
                AvariaLog = apps.get_model('taloes','AvariaLog')
                viatura = getattr(ativo, 'viatura', None)
                itens = saved.itens_marcados()
                AvariaLog.objects.create(
                    viatura=viatura,
                    plantao_id=getattr(ativo,'id',None),
                    usuario=request.user,
                    data=timezone.localdate(),
                    itens_json=json.dumps(itens, ensure_ascii=False),
                )
                # Atualizar estado persistente da viatura (união dos itens)
                try:
                    from viaturas.models import ViaturaAvariaEstado
                    if viatura:
                        estado, _ = ViaturaAvariaEstado.objects.get_or_create(viatura=viatura)
                        atuais = set(estado.get_labels())
                        novas = sorted(atuais.union(set(itens)))
                        estado.set_labels(novas)
                        estado.save(update_fields=["labels_json","atualizado_em"])
                except Exception:
                    pass
            except Exception:
                pass
            messages.success(request, "Checklist salvo.")
            # Conforme solicitado: sempre voltar para Talões após salvar
            return redirect('taloes:lista')
    else:
        form = ChecklistViaturaForm(instance=ck)
    return render(request, 'taloes/checklist_viatura.html', {'form': form, 'plantao': ativo})


@login_required
def apagar_documento(request: HttpRequest):
    if request.method != "POST":
        return HttpResponseBadRequest("Método inválido")

    # Restrição: somente superuser 'moises'
    try:
        username = (request.user.get_username() or request.user.username or "").strip().lower()
    except Exception:
        username = ""
    if not (getattr(request.user, 'is_superuser', False) and username == 'moises'):
        messages.error(request, "Você não tem permissão para excluir documentos.")
        return redirect("taloes:meus_documentos")

    nome = (request.POST.get("nome") or "").strip()
    uid_raw = (request.POST.get("uid") or "").strip()
    target_user_id = None
    try:
        if uid_raw:
            target_user_id = int(uid_raw)
    except Exception:
        target_user_id = None
    if not nome or "/" in nome or ".." in nome:
        messages.error(request, "Nome de arquivo inválido.")
        return redirect("taloes:meus_documentos")

    _ensure_media()
    # Se moises passou uid, atua no diretório daquele usuário
    out_dir = _user_dir(request.user)
    try:
        is_moises = getattr(request.user, 'is_superuser', False) and ((request.user.get_username() or request.user.username or '').strip().lower() == 'moises')
    except Exception:
        is_moises = False
    if is_moises and target_user_id:
        out_dir = MEDIA_BASE / str(target_user_id)
    target = out_dir / nome
    try:
        if target.exists() and target.is_file() and target.suffix.lower() == ".pdf":
            target.unlink()
            messages.success(request, f"Documento '{nome}' apagado.")
        else:
            messages.error(request, "Arquivo não encontrado.")
    except Exception as e:
        messages.error(request, f"Não foi possível apagar: {e}")
    return redirect("taloes:meus_documentos")


@login_required
def download_documento(request: HttpRequest):
    """Força download (Content-Disposition attachment) de um PDF do usuário."""
    nome = (request.GET.get("nome") or "").strip()
    uid_raw = (request.GET.get("uid") or "").strip()
    target_user_id = None
    try:
        if uid_raw:
            target_user_id = int(uid_raw)
    except Exception:
        target_user_id = None
    if not nome or "/" in nome or ".." in nome:
        return HttpResponseBadRequest("Nome inválido")
    _ensure_media()
    out_dir = _user_dir(request.user)
    try:
        is_moises = getattr(request.user, 'is_superuser', False) and ((request.user.get_username() or request.user.username or '').strip().lower() == 'moises')
    except Exception:
        is_moises = False
    if is_moises and target_user_id:
        out_dir = MEDIA_BASE / str(target_user_id)
    target = out_dir / nome
    if not (target.exists() and target.is_file() and target.suffix.lower() == ".pdf"):
        raise Http404("Arquivo não encontrado")
    with open(target, "rb") as f:
        data = f.read()
    resp = HttpResponse(data, content_type="application/pdf")
    resp["Content-Disposition"] = f"attachment; filename={nome}"
    resp["Content-Length"] = len(data)
    return resp


@login_required
def sair_plantao(request: HttpRequest):
    """Remove somente este usuário do plantão ativo que ele participa.
    Se ele for o iniciador e ficar sozinho, encerra o plantão.
    """
    plantao = PlantaoCECOM.objects.filter(ativo=True, participantes__usuario=request.user).order_by('-inicio').first()
    if not plantao:
        messages.info(request, "Você não participa de um plantão ativo.")
        return redirect('taloes:lista')
    try:
        pp = PlantaoParticipante.objects.filter(plantao=plantao, usuario=request.user, saida_em__isnull=True).first()
        if pp:
            pp.saida_em = timezone.now()
            pp.save(update_fields=['saida_em'])
        # Verifica se ainda há participantes ativos (sem saida_em)
        if not plantao.participantes.filter(saida_em__isnull=True).exists():
            plantao.ativo = False
            plantao.encerrado_em = timezone.now()
            plantao.save(update_fields=['ativo','encerrado_em'])
            messages.success(request, "Você saiu e o plantão foi encerrado (sem participantes ativos).")
        else:
            messages.success(request, "Sua saída foi registrada.")
    except Exception as e:
        messages.error(request, f"Não foi possível sair do plantão: {e}")
    # Limpa equipe textual local
    _session_set(request, SESSION_EQUIPE_STR, "")
    return redirect('taloes:lista')


# ======================
#   API AUXILIAR (AJAX)
# ======================

@login_required
def api_ultimo_km(request: HttpRequest):
    """Retorna em JSON o km_final do último talão FECHADO para a viatura informada.

    GET params:
      - viatura: ID da viatura (inteiro)

    Resposta:
      { "km_inicial": 12345 }  // se encontrado
      { "km_inicial": null }   // se não encontrado ou inválido
    """
    try:
        vid = int(request.GET.get("viatura") or 0)
    except Exception:
        vid = 0

    if not vid:
        return JsonResponse({"km_inicial": None})

    try:
        ultimo_fechado = (
            Talao.objects.filter(viatura_id=vid, status="FECHADO", km_final__isnull=False)
            .order_by("-encerrado_em", "-iniciado_em")
            .first()
        )
        km = getattr(ultimo_fechado, "km_final", None) if ultimo_fechado else None
        return JsonResponse({"km_inicial": km})
    except Exception:
        return JsonResponse({"km_inicial": None})


# ======================
#   ANEXOS DE AVARIAS
# ======================

@login_required
@require_POST
def upload_anexo_avaria(request):
    """API AJAX para upload de anexo de avaria durante o checklist."""
    from .models import AvariaAnexo
    
    campo_avaria = request.POST.get('campo_avaria')
    arquivo = request.FILES.get('arquivo')
    descricao = request.POST.get('descricao', '')
    
    if not campo_avaria or not arquivo:
        return JsonResponse({'ok': False, 'error': 'Campos obrigatórios faltando'}, status=400)
    
    # Buscar ou criar checklist do dia
    hoje = timezone.localdate()
    ck, _ = ChecklistViatura.objects.get_or_create(
        usuario=request.user,
        data=hoje
    )
    
    # Criar anexo
    anexo = AvariaAnexo.objects.create(
        checklist=ck,
        campo_avaria=campo_avaria,
        arquivo=arquivo,
        descricao=descricao
    )
    
    return JsonResponse({
        'ok': True,
        'id': anexo.id,
        'url': anexo.arquivo.url,
        'nome': anexo.arquivo.name.split('/')[-1],
        'criado_em': anexo.criado_em.strftime('%d/%m/%Y %H:%M')
    })


@login_required
@require_POST
def remover_anexo_avaria(request, anexo_id):
    """Remove um anexo de avaria."""
    from .models import AvariaAnexo
    
    anexo = get_object_or_404(AvariaAnexo, pk=anexo_id)
    
    # Verificar permissão (só o dono ou admin pode remover)
    if anexo.checklist.usuario != request.user and not request.user.is_superuser:
        return JsonResponse({'ok': False, 'error': 'Sem permissão'}, status=403)
    
    # Deletar arquivo físico
    if anexo.arquivo:
        try:
            anexo.arquivo.delete()
        except:
            pass
    
    anexo.delete()
    
    return JsonResponse({'ok': True})
