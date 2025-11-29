

from __future__ import annotations
from django.contrib.auth.decorators import login_required
from .models import Talao
from .forms import NovoTalaoForm

@login_required
def taloes_arquivados(request: HttpRequest):
    qs = Talao.objects.select_related("viatura", "codigo_ocorrencia", "codigo_ocorrencia__grupo")
    # Considera arquivado: talões FECHADOS
    if field_exists(Talao, "status"):
        qs = qs.filter(status="FECHADO")
    # Filtro "meus talões" (participação do usuário)
    meus = (request.GET.get("meus") == "1")
    if meus:
        from django.db.models import Q as _Q
        u = request.user
        qs = qs.filter(
            _Q(encarregado=u) | _Q(motorista=u) | _Q(auxiliar1=u) | _Q(auxiliar2=u) | _Q(criado_por=u)
        )

    # Filtro de busca por todos os campos da tabela
    q = (request.GET.get("q") or "").strip()
    if q:
        from django.db.models import Q, CharField
        from django.db.models.functions import Cast
        import re
        # Preparar casts para permitir busca textual em campos numéricos
        qs = qs.annotate(
            km_inicial_str=Cast("km_inicial", CharField()),
            km_final_str=Cast("km_final", CharField()),
        )
        filters = Q()
        # Coluna #: aceitar pk ou talao_numero
        if q.isdigit():
            try:
                num = int(q)
                filters |= Q(pk=num) | Q(talao_numero=num)
            except Exception:
                pass
        # Viatura (prefixo/placa como texto)
        filters |= Q(viatura__prefixo__icontains=q) | Q(viatura__placa__icontains=q)
        # Status
        filters |= Q(status__icontains=q)
        # Iniciado (data dd/mm/aaaa ou parte)
        # Busca textual no formato dd/mm/aaaa ou dd/mm
        # Dado que started é DateTime, usar string do dia formatada: aproximar via dia/mês
        # Estratégia: quando q parece data dd/mm/aaaa, tentar normalizar e filtrar por dia
        m = re.match(r"^(\d{1,2})/(\d{1,2})(?:/(\d{4}))?$", q)
        if m:
            dia = int(m.group(1)); mes = int(m.group(2)); ano = m.group(3)
            from datetime import date
            try:
                if ano:
                    d0 = date(int(ano), mes, dia)
                    filters |= Q(iniciado_em__date=d0)
                else:
                    # sem ano: filtra por dia e mês em qualquer ano
                    filters |= Q(iniciado_em__day=dia, iniciado_em__month=mes)
            except Exception:
                pass
        # KM (inicial/final como texto via cast)
        filters |= Q(km_inicial_str__icontains=q) | Q(km_final_str__icontains=q)
        # Ocorrência: sigla/descricao
        filters |= Q(codigo_ocorrencia__sigla__icontains=q) | Q(codigo_ocorrencia__descricao__icontains=q)
        # Nº BOGCM: relacionar por nome reverso 'bos' se existir no modelo
        if any(rel.get_accessor_name() == 'bos' for rel in Talao._meta.related_objects if hasattr(rel, 'get_accessor_name')):
            filters |= Q(bos__numero__icontains=q)
        # Local: bairro/rua
        filters |= Q(local_bairro__icontains=q) | Q(local_rua__icontains=q)
        qs = qs.filter(filters).distinct()
    qs = qs.order_by("-iniciado_em", "-pk")
    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    # Fallback adicional: integrantes do Plantão CECOM ativo por viatura
    ativos = PlantaoCECOM.objects.select_related('viatura').prefetch_related('participantes__usuario').filter(ativo=True, viatura__isnull=False)
    func_map = { 'ENC': 'Enc', 'MOT': 'Mot', 'AUX1': 'Aux1', 'AUX2': 'Aux2' }
    integrantes_map: dict[int, str] = {}
    for p in ativos:
        try:
            parts = []
            for part in p.participantes.select_related('usuario').filter(saida_em__isnull=True):
                u = part.usuario
                if not u:
                    continue
                nome = (getattr(u,'get_full_name',lambda: '')() or getattr(u,'username','')).strip()
                label = func_map.get(part.funcao or '', '')
                parts.append(f"{label+': ' if label else ''}{nome}")
            integrantes_map[p.viatura_id] = " · ".join(parts)
        except Exception:
            integrantes_map[p.viatura_id] = ""
    return render(
        request,
        "taloes/arquivados.html",
        {
            "taloes": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "meus": meus,
            "integrantes_map": integrantes_map,
            # Equipe selecionada no início do plantão (A/B/C/D) para exibir junto dos integrantes
            "plantao_equipe": request.session.get(SESSION_PLANTAO, ""),
        },
    )



@login_required
def editar_talao(request, pk):
    talao = get_object_or_404(Talao, pk=pk)
    # Buscar plantão ativo para travar a viatura
    from cecom.models import PlantaoCECOM
    ativo = PlantaoCECOM.ativo_do_usuario_ou_participado(request.user)
    if request.method == "POST":
        form = NovoTalaoForm(request.POST, instance=talao, plantao_ativo=ativo)
        if form.is_valid():
            obj = form.save(commit=False)
            km_final = form.cleaned_data.get("km_final")
            km_inicial = form.cleaned_data.get("km_inicial")
            if km_final is not None:
                if km_final < km_inicial:
                    form.add_error("km_final", "O KM final não pode ser menor que o KM inicial.")
                    try:
                        messages.error(request, "Coloque o KM igual ou superior ao inicial")
                    except Exception:
                        pass
                else:
                    # Para finalizar, exigir Ocorrência e Bairro preenchidos
                    codigo_oc = form.cleaned_data.get("codigo_ocorrencia")
                    bairro = (form.cleaned_data.get("local_bairro") or "").strip()
                    if not codigo_oc:
                        form.add_error("codigo_ocorrencia", "Selecione a Ocorrência para finalizar.")
                        try:
                            messages.error(request, "Selecione a Ocorrência para finalizar o talão")
                        except Exception:
                            pass
                    if not bairro:
                        form.add_error("local_bairro", "Informe o bairro para finalizar.")
                        try:
                            messages.error(request, "Informe o bairro para finalizar o talão")
                        except Exception:
                            pass
                    if not form.errors:
                        obj.status = "FECHADO"
                        if field_exists(Talao, "encerrado_em"):
                            obj.encerrado_em = timezone.now()
            if not form.errors:
                obj.save()
                messages.success(request, "Talão atualizado com sucesso.")
                return redirect("taloes:lista")
        # Se houver erro, exibe o form novamente
    else:
        form = NovoTalaoForm(instance=talao, plantao_ativo=ativo)
    return render(request, "taloes/editar_talao.html", {"form": form, "talao": talao})

from functools import reduce
import operator

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Q
from django.http import HttpRequest, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.core.paginator import Paginator

from .models import Talao, CodigoOcorrencia, Abastecimento, AitRegistro
from viaturas.models import Viatura
from cecom.models import PlantaoCECOM
from viaturas.models import ViaturaAvariaEstado
from .views_extra import (
    SESSION_RELATORIO,
    SESSION_EQUIPE_STR,
    SESSION_PLANTAO,
    SESSION_ENCARREGADO_ID,
    SESSION_MOTORISTA_ID,
    SESSION_AUX1_ID,
    SESSION_AUX2_ID,
)
from django.contrib.auth import get_user_model
from .forms import AbastecimentoForm, AitAddForm

# ===== helpers =====

def field_exists(model, name: str) -> bool:
    return any(f.name == name for f in model._meta.get_fields())

def get_field(model, name: str):
    try:
        return model._meta.get_field(name)
    except Exception:
        return None

def user_display_name(user) -> str:
    # Tenta nome completo; se não houver, usa username
    full = (getattr(user, "get_full_name", lambda: "")() or "").strip()
    if full:
        return full
    return (getattr(user, "get_username", lambda: "")() or "").strip()

def user_is_privileged(user) -> bool:
    # superuser, ou grupos "cecom" / "adm"
    if getattr(user, "is_superuser", False):
        return True
    try:
        return user.groups.filter(name__in=["cecom", "adm"]).exists()
    except Exception:
        return False

def talo_pertence_ao_usuario(t: Talao, user) -> bool:
    """
    Retorna True se, com base nos campos disponíveis no modelo,
    este talão está "no nome" do usuário (motorista/auxiliares/encarregado/criado_por).
    Suporta tanto FKs para usuário quanto campos texto (iexact).
    """
    nome = user_display_name(user)

    # criado_por (FK)?
    if field_exists(Talao, "criado_por"):
        try:
            if getattr(t, "criado_por_id", None) == user.id:
                return True
        except Exception:
            pass

    # campos de pessoal: podem ser FK para User ou texto
    for attr in ("motorista", "auxiliar1", "auxiliar2", "encarregado"):
        if field_exists(Talao, attr):
            f = get_field(Talao, attr)
            try:
                if isinstance(f, models.ForeignKey):
                    if getattr(t, f"{attr}_id", None) == user.id:
                        return True
                else:
                    val = getattr(t, attr, "") or ""
                    if isinstance(val, str) and val.strip().lower() == nome.lower():
                        return True
            except Exception:
                continue

    # Se houver FKs equivalentes (ex.: motorista_user), checa também
    for attr in ("motorista_user", "auxiliar1_user", "auxiliar2_user", "encarregado_user"):
        if field_exists(Talao, attr + "_id"):
            try:
                if getattr(t, attr + "_id", None) == user.id:
                    return True
            except Exception:
                continue

    return False

def usuario_pertence_ao_plantao_ativo(user) -> bool:
    """
    Retorna True se o usuário faz parte de um plantão ativo (CECOM).
    Checa: iniciado_por ou participante do plantão.
    """
    try:
        plantao = PlantaoCECOM.objects.filter(ativo=True).first()
        if not plantao:
            return False
        # Verifica se o usuário iniciou o plantão
        if getattr(plantao, "iniciado_por_id", None) == user.id:
            return True
        # Verifica se o usuário é participante do plantão (e não saiu ainda)
        if plantao.participantes.filter(usuario=user, saida_em__isnull=True).exists():
            return True
    except Exception:
        pass
    return False

def _build_equipe_from_session(request: HttpRequest) -> str:
    # Prioriza string pronta (se já montada pelo fluxo de iniciar plantão)
    txt = (request.session.get(SESSION_EQUIPE_STR) or '').strip()
    if txt:
        return txt
    # Caso contrário, monta pelos IDs de sessão
    ids = [
        request.session.get(SESSION_ENCARREGADO_ID),
        request.session.get(SESSION_MOTORISTA_ID),
        request.session.get(SESSION_AUX1_ID),
        request.session.get(SESSION_AUX2_ID),
    ]
    ids = [i for i in ids if i]
    if not ids:
        return ''
    User = get_user_model()
    nomes: list[str] = []
    for u in User.objects.filter(id__in=ids):
        nomes.append(user_display_name(u).title())
    return ", ".join(nomes)

def _build_equipe_labels(request: HttpRequest):
    roles = [
        ("Encarregado", SESSION_ENCARREGADO_ID),
        ("Motorista", SESSION_MOTORISTA_ID),
        ("Auxiliar 1", SESSION_AUX1_ID),
        ("Auxiliar 2", SESSION_AUX2_ID),
    ]
    id_list = [request.session.get(sess) for _, sess in roles]
    id_list = [i for i in id_list if i]
    if not id_list:
        return []
    User = get_user_model()
    users = {u.id: u for u in User.objects.filter(id__in=id_list)}
    labeled = []
    for label, sess in roles:
        uid = request.session.get(sess)
        if uid and uid in users:
            labeled.append((label, user_display_name(users[uid]).title()))
    return labeled

def build_owner_filter(user) -> Q:
    """
    Monta um Q dinâmico para filtrar os talões do usuário,
    apenas usando campos que EXISTEM no modelo atual.
    """
    clauses: list[Q] = []

    # criado_por (FK para User)
    if field_exists(Talao, "criado_por"):
        clauses.append(Q(criado_por=user))

    # FKs alternativas explícitas *_user
    for attr in ("motorista_user", "auxiliar1_user", "auxiliar2_user", "encarregado_user"):
        if field_exists(Talao, attr):
            clauses.append(Q(**{attr: user}))

    # Campos de pessoal (podem ser FK ou texto)
    nome = user_display_name(user)
    for attr in ("motorista", "auxiliar1", "auxiliar2", "encarregado"):
        if field_exists(Talao, attr):
            f = get_field(Talao, attr)
            if isinstance(f, models.ForeignKey):
                clauses.append(Q(**{attr: user}))
            else:
                clauses.append(Q(**{f"{attr}__iexact": nome}))

    # Se nada existir, retorna Q(vazio) que não filtra nada (caller tratará)
    if not clauses:
        # retorna Q que nunca é verdadeiro, para não expor todos sem querer
        return Q(pk__in=[])
    return reduce(operator.or_, clauses)


# ===== views =====

@login_required
def lista(request: HttpRequest):
    """
    Lista de talões com:
      - 10 por página
      - se usuário comum: vê apenas talões "no nome" dele (motorista/auxiliares/encarregado/criado_por)
      - se grupo 'cecom' ou 'adm' (ou superuser): vê todos
      - edição inline de status e km_final (POST por linha)
    """
    # ---- POST (edição inline de uma linha) ----
    if request.method == "POST" and request.POST.get("inline") == "1":
        pk = request.POST.get("pk")
        if not pk:
            return HttpResponseBadRequest("pk ausente")

        t = get_object_or_404(Talao, pk=pk)

        # Permissão de edição
        if not (user_is_privileged(request.user) or talo_pertence_ao_usuario(t, request.user)):
            messages.error(request, "Você não tem permissão para editar este talão.")
            return redirect(request.get_full_path())

        # km_final
        km_final_val = request.POST.get("km_final", "").strip()
        km_final = None
        if km_final_val != "":
            try:
                km_final = int(km_final_val)
                if km_final < 0:
                    km_final = None
            except Exception:
                km_final = None

        # Outros campos opcionais
        viatura_id_val = (request.POST.get("viatura") or "").strip()
        cod_id_val = (request.POST.get("codigo_ocorrencia") or "").strip()
        local_bairro = (request.POST.get("local_bairro") or "").strip()
        local_rua = (request.POST.get("local_rua") or "").strip()

        # Atualiza os campos que existem
        update_fields = []

        # status (permitir editar manualmente)
        status_val = (request.POST.get("status") or "").strip().upper()
        status_allowed = None
        if field_exists(Talao, "status"):
            try:
                choices = [c[0] for c in getattr(Talao._meta.get_field("status"), "choices", [])] or ["ABERTO", "FECHADO"]
                if status_val in choices:
                    status_allowed = status_val
            except Exception:
                pass

        if status_allowed and status_allowed != getattr(t, "status", None):
            t.status = status_allowed
            update_fields.append("status")
            if status_allowed == "FECHADO" and field_exists(Talao, "encerrado_em"):
                t.encerrado_em = timezone.now()
                update_fields.append("encerrado_em")
            if status_allowed == "ABERTO" and field_exists(Talao, "encerrado_em"):
                t.encerrado_em = None
                update_fields.append("encerrado_em")

        if km_final is not None and field_exists(Talao, "km_final"):
            t.km_final = km_final
            update_fields.append("km_final")
        # viatura (FK)
        if viatura_id_val and field_exists(Talao, "viatura"):
            try:
                v_id = int(viatura_id_val)
                if v_id != getattr(t, "viatura_id", None):
                    t.viatura = Viatura.objects.filter(id=v_id).first() or t.viatura
                    update_fields.append("viatura")
            except Exception:
                pass

        # código de ocorrência (FK)
        if cod_id_val and field_exists(Talao, "codigo_ocorrencia"):
            try:
                c_id = int(cod_id_val)
                if c_id != getattr(t, "codigo_ocorrencia_id", None):
                    t.codigo_ocorrencia = CodigoOcorrencia.objects.filter(id=c_id).first() or t.codigo_ocorrencia
                    update_fields.append("codigo_ocorrencia")
            except Exception:
                pass

        # local
        if field_exists(Talao, "local_bairro") and local_bairro != "" and local_bairro != getattr(t, "local_bairro", ""):
            t.local_bairro = local_bairro
            update_fields.append("local_bairro")
        if field_exists(Talao, "local_rua") and local_rua != "" and local_rua != getattr(t, "local_rua", ""):
            t.local_rua = local_rua
            update_fields.append("local_rua")

        if update_fields:
            try:
                t.save(update_fields=list(set(update_fields)))
                messages.success(request, f"Talão #{t.pk} atualizado.")
            except Exception as e:
                messages.error(request, f"Não foi possível salvar: {e}")

        # Volta para a mesma página/consulta
        return redirect(request.get_full_path())

    # ---- GET (lista) ----
    # Detecta plantão ativo uma vez para usar no filtro e no contexto
    plantao_ativo = PlantaoCECOM.ativo_do_usuario_ou_participado(request.user)

    qs = (Talao.objects.select_related("viatura", "codigo_ocorrencia", "codigo_ocorrencia__grupo").all())

    # Permissão/listagem: se há plantão compartilhado ativo, exibir talões de TODOS os participantes
    if plantao_ativo:
        try:
            participante_ids = list(plantao_ativo.participantes.values_list('usuario_id', flat=True))
            # Garante incluir o iniciador se ele estiver ativo sozinho
            if plantao_ativo.iniciado_por_id and plantao_ativo.iniciado_por_id not in participante_ids:
                participante_ids.append(plantao_ativo.iniciado_por_id)
            if participante_ids:
                qs = qs.filter(
                    Q(criado_por_id__in=participante_ids) |
                    Q(encarregado_id__in=participante_ids) |
                    Q(motorista_id__in=participante_ids) |
                    Q(auxiliar1_id__in=participante_ids) |
                    Q(auxiliar2_id__in=participante_ids)
                )
        except Exception:
            pass
    # Caso sem plantão compartilhado: restringe como antes
    if not plantao_ativo and not user_is_privileged(request.user):
        owner_q = build_owner_filter(request.user)
        qs = qs.filter(owner_q) if owner_q.children else qs.none()

    # Sempre oculta talões FECHADOS da lista (eles ficam apenas em Arquivados)
    if field_exists(Talao, "status"):
        qs = qs.exclude(status="FECHADO")

    # Ordenação
    if field_exists(Talao, "iniciado_em"):
        qs = qs.order_by("-iniciado_em", "-pk")
    else:
        qs = qs.order_by("-pk")

    # Paginação 10/página
    paginator = Paginator(qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Status choices para o select
    try:
        status_choices = [c[0] for c in Talao._meta.get_field("status").choices] or ["ABERTO", "FECHADO"]
    except Exception:
        status_choices = ["ABERTO", "FECHADO"]

    # Quais Pks podem ser editados por este usuário
    editable_pks = set()
    for t in page_obj.object_list:
        if user_is_privileged(request.user) or talo_pertence_ao_usuario(t, request.user):
            editable_pks.add(t.pk)

    # Modo edição de uma linha (GET ?edit=pk)
    edit_pk = None
    try:
        edit_pk = int(request.GET.get("edit") or 0) or None
    except Exception:
        edit_pk = None

    # Helpers para selects
    viaturas_all = list(Viatura.objects.all())
    codigos_all = list(CodigoOcorrencia.objects.select_related("grupo").all())

    participantes_labeled = plantao_ativo.participantes_labeled() if plantao_ativo else []
    # Avarias para a VTR do plantão ativo (fonte: estado persistente)
    avarias_vtr_plantao = []
    if plantao_ativo and getattr(plantao_ativo, 'viatura_id', None):
        try:
            estado = ViaturaAvariaEstado.objects.filter(viatura_id=plantao_ativo.viatura_id).first()
            avarias_vtr_plantao = estado.get_labels() if estado else []
        except Exception:
            avarias_vtr_plantao = []
    # Rascunho compartilhado: se o plantão ativo existe, o texto vem de plantao_ativo.relatorio_rascunho
    relatorio_rascunho = request.session.get(SESSION_RELATORIO, "")
    try:
        if plantao_ativo and getattr(plantao_ativo, 'relatorio_rascunho', None) is not None:
            relatorio_rascunho = plantao_ativo.relatorio_rascunho
    except Exception:
        pass
    
    # Verificar se o usuário atual é o encarregado do plantão ativo
    usuario_e_encarregado = False
    if plantao_ativo:
        try:
            participante = plantao_ativo.participantes.filter(usuario=request.user, saida_em__isnull=True).first()
            if participante and participante.funcao == 'ENC':
                usuario_e_encarregado = True
        except Exception:
            pass

    ctx = {
        "taloes": page_obj.object_list,
        "page_obj": page_obj,
        "status_choices": status_choices,
        "editable_pks": editable_pks,
        "relatorio_rascunho": relatorio_rascunho,
        "plantao_ativo": plantao_ativo,
        "usuario_e_encarregado": usuario_e_encarregado,
        # equipe textual antiga ainda usada para fallback
        "equipe_integrantes": _build_equipe_from_session(request),
        # sobrescreve com participantes reais se houver plantão compartilhado
        "equipe_labeled": participantes_labeled or _build_equipe_labels(request),
        # Letra da Equipe (A/B/C/D) selecionada ao iniciar/editar plantão
        "plantao_equipe": request.session.get(SESSION_PLANTAO, ""),
        "edit_pk": edit_pk,
        "viaturas_all": viaturas_all,
        "codigos_all": codigos_all,
        "avarias_vtr_plantao": avarias_vtr_plantao,
    }
    return render(request, "taloes/lista.html", ctx)




# === edição de ocorrência/local via form ===
try:
    # Se você tiver esse form no seu projeto
    from .forms import TalaoOcorrenciaForm  # type: ignore
except Exception:  # pragma: no cover
    TalaoOcorrenciaForm = None  # type: ignore


@login_required
def editar_ocorrencia(request: HttpRequest, pk: int):
    t = get_object_or_404(Talao.objects.select_related("viatura"), pk=pk)

    # Permissão de acesso à edição (mesma lógica da lista)
    if not (user_is_privileged(request.user) or talo_pertence_ao_usuario(t, request.user)):
        messages.error(request, "Você não tem permissão para editar este talão.")
        return redirect("taloes:detalhe", pk=t.pk)

    if TalaoOcorrenciaForm is None:
        messages.error(request, "Formulário de ocorrência não está configurado.")
        return redirect("taloes:detalhe", pk=t.pk)

    if request.method == "POST":
        form = TalaoOcorrenciaForm(request.POST, instance=t)
        if form.is_valid():
            form.save()
            messages.success(request, "Ocorrência/local atualizados.")
            return redirect("taloes:detalhe", pk=t.pk)
    else:
        form = TalaoOcorrenciaForm(instance=t)

    return render(request, "taloes/editar_ocorrencia.html", {"talao": t, "form": form})


# === finalizar (opcional, caso ainda use) ===
try:
    from .forms import FinalizarTalaoForm  # type: ignore
except Exception:
    FinalizarTalaoForm = None  # type: ignore


@login_required
def finalizar(request: HttpRequest, pk: int):
    """
    Finaliza um talão (status FECHADO e define km_final).
    """
    t = get_object_or_404(Talao, pk=pk)

    if not (user_is_privileged(request.user) or talo_pertence_ao_usuario(t, request.user)):
        messages.error(request, "Você não tem permissão para finalizar este talão.")
        return redirect("taloes:detalhe", pk=t.pk)

    if request.method == "POST":
        km_final_val = None
        if FinalizarTalaoForm:
            form = FinalizarTalaoForm(request.POST)
            if form.is_valid():
                km_final_val = form.cleaned_data.get("km_final")
        else:
            raw = (request.POST.get("km_final") or "").strip()
            if raw != "":
                try:
                    km_final_val = int(raw)
                except Exception:
                    km_final_val = None

        updates = []

        if field_exists(Talao, "status"):
            t.status = "FECHADO"
            updates.append("status")

        if field_exists(Talao, "encerrado_em"):
            t.encerrado_em = timezone.now()
            updates.append("encerrado_em")

        if field_exists(Talao, "km_final") and km_final_val is not None:
            t.km_final = km_final_val
            updates.append("km_final")

        try:
            t.save(update_fields=list(set(updates)) or None)
            messages.success(request, f"Talão #{t.pk} finalizado.")
        except Exception as e:
            messages.error(request, f"Não foi possível finalizar: {e}")

        return redirect("taloes:detalhe", pk=t.pk)

    return render(request, "taloes/detalhe.html", {"t": t, "mostrar_form_finalizar": True})


@login_required
def historico(request: HttpRequest):
    """
    Histórico simples (200 mais recentes), respeitando permissão.
    """
    qs = Talao.objects.select_related("viatura").all()

    if not user_is_privileged(request.user):
        owner_q = build_owner_filter(request.user)
        qs = qs.filter(owner_q) if owner_q.children else qs.none()

    if field_exists(Talao, "iniciado_em"):
        qs = qs.order_by("-iniciado_em", "-pk")
    else:
        qs = qs.order_by("-pk")

    return render(request, "taloes/historico.html", {"taloes": qs[:200]})


@login_required
def apagar(request: HttpRequest, pk: int):
    t = get_object_or_404(Talao, pk=pk)
    if request.method != "POST":
        return HttpResponseBadRequest("Método inválido")

    # Restrição: somente superuser 'moises' pode apagar talão via UI/API
    try:
        username = (request.user.get_username() or request.user.username or "").strip().lower()
    except Exception:
        username = ""
    if not (getattr(request.user, 'is_superuser', False) and username == 'moises'):
        messages.error(request, "Você não tem permissão para apagar este talão.")
        return redirect("taloes:lista")

    try:
        t.delete()
        messages.success(request, f"Talão #{pk} apagado com sucesso.")
    except Exception as e:
        messages.error(request, f"Não foi possível apagar: {e}")
    return redirect("taloes:lista")


# === Abordados ===

@login_required
def abordados_talao(request: HttpRequest, pk: int):
    """
    Página para gerenciar abordados de um talão específico.
    """
    from .models import Abordado
    from .forms_abordados import AbordadoForm
    
    talao = get_object_or_404(Talao, pk=pk)
    
    # Permissão: usuários privilegiados OU pertence ao talão OU pertence ao plantão ativo
    if not (user_is_privileged(request.user) or talo_pertence_ao_usuario(talao, request.user) or usuario_pertence_ao_plantao_ativo(request.user)):
        messages.error(request, "Você não tem permissão para editar este talão.")
        return redirect("taloes:lista")
    
    if request.method == "POST":
        form = AbordadoForm(request.POST)
        if form.is_valid():
            abordado = form.save(commit=False)
            abordado.talao = talao
            abordado.save()
            messages.success(request, "Abordado adicionado com sucesso.")
            return redirect("taloes:abordados", pk=talao.pk)
    else:
        form = AbordadoForm()
    
    abordados = talao.abordados.all().order_by("-criado_em")
    
    return render(request, "taloes/abordados.html", {
        "talao": talao,
        "abordados": abordados,
        "form": form,
    })


@login_required
def remover_abordado(request: HttpRequest, pk: int, abordado_id: int):
    """
    Remove um abordado específico.
    """
    from .models import Abordado
    
    talao = get_object_or_404(Talao, pk=pk)
    abordado = get_object_or_404(Abordado, pk=abordado_id, talao=talao)
    
    # Permissão: usuários privilegiados OU pertence ao talão OU pertence ao plantão ativo
    if not (user_is_privileged(request.user) or talo_pertence_ao_usuario(talao, request.user) or usuario_pertence_ao_plantao_ativo(request.user)):
        messages.error(request, "Você não tem permissão para editar este talão.")
        return redirect("taloes:lista")
    
    if request.method == "POST":
        abordado.delete()
        messages.success(request, "Abordado removido com sucesso.")
    
    return redirect("taloes:abordados", pk=talao.pk)


# === Abastecimento ===
@login_required
def abastecimento_novo(request: HttpRequest, pk: int):
    """Formulário para registrar abastecimento vinculado a um Talão.
    Só aparece/é permitido quando a ocorrência for Q-03 — Abastecimento.
    """
    t = get_object_or_404(Talao.objects.select_related("codigo_ocorrencia", "codigo_ocorrencia__grupo"), pk=pk)

    # Permissão de edição igual à da lista
    if not (user_is_privileged(request.user) or talo_pertence_ao_usuario(t, request.user)):
        messages.error(request, "Você não tem permissão para editar este talão.")
        return redirect("taloes:lista")

    # Valida ocorrência
    sigla = getattr(getattr(t, "codigo_ocorrencia", None), "sigla", "") or ""
    if sigla != "Q-03":
        messages.error(request, "Este talão não é de Abastecimento (Q-03).")
        return redirect("taloes:lista")

    if request.method == "POST":
        form = AbastecimentoForm(request.POST, request.FILES)
        if form.is_valid():
            ab: Abastecimento = form.save(commit=False)
            ab.talao = t
            ab.save()
            messages.success(request, "Abastecimento registrado com sucesso.")
            # Redirect para a mesma página para o usuário ver o registro salvo
            return redirect("taloes:abastecimento_novo", pk=t.pk)
    else:
        form = AbastecimentoForm()

    abastecimentos = t.abastecimentos.all().order_by("-criado_em")
    return render(request, "taloes/abastecimento_form.html", {"form": form, "talao_id": t.pk, "abastecimentos": abastecimentos})


# === AITs ===
@login_required
def aits_gerenciar(request: HttpRequest, pk: int):
    """Página simples para adicionar/remover números de AIT vinculados a um Talão."""
    t = get_object_or_404(Talao, pk=pk)
    sess_key_last = f"aits_last_integrante_{t.pk}"

    # Permissão: usuários privilegiados OU pertence ao talão OU pertence ao plantão ativo
    if not (user_is_privileged(request.user) or talo_pertence_ao_usuario(t, request.user) or usuario_pertence_ao_plantao_ativo(request.user)):
        messages.error(request, "Você não tem permissão para editar este talão.")
        return redirect("taloes:lista")

    if request.method == "POST":
        # Remoção
        if request.POST.get("remover"):
            try:
                aid = int(request.POST.get("remover"))
                AitRegistro.objects.filter(pk=aid, talao=t).delete()
                messages.success(request, "AIT removida.")
            except Exception:
                messages.error(request, "Não foi possível remover a AIT.")
            return redirect("taloes:aits", pk=t.pk)

        # Adição
        form = AitAddForm(request.POST)
        if form.is_valid():
            numero = (form.cleaned_data.get("numero") or "").strip()
            integrante = form.cleaned_data.get("integrante")
            if not numero:
                messages.error(request, "Informe o número da AIT.")
            else:
                try:
                    obj, created = AitRegistro.objects.get_or_create(talao=t, numero=numero, defaults={"integrante": integrante})
                    if not created:
                        # Atualiza integrante se mudou
                        if obj.integrante_id != getattr(integrante, 'id', None):
                            obj.integrante = integrante
                            obj.save(update_fields=["integrante"])
                    # Persistir último integrante selecionado para este talão
                    try:
                        if integrante and getattr(integrante, 'id', None):
                            request.session[sess_key_last] = integrante.id
                            request.session.modified = True
                    except Exception:
                        pass
                    nome_int = (integrante.get_full_name() or integrante.username) if integrante else '—'
                    messages.success(request, f"AIT {numero} adicionada para {nome_int}.")
                except Exception as e:
                    messages.error(request, f"Não foi possível adicionar: {e}")
            return redirect("taloes:aits", pk=t.pk)
    else:
        # Pré-seleciona: último integrante usado neste talão (sessão) ou o usuário atual
        initial_uid = None
        try:
            initial_uid = int(request.GET.get('u') or 0) or None
        except Exception:
            initial_uid = None
        if not initial_uid:
            initial_uid = request.session.get(sess_key_last) or request.user.id
        form = AitAddForm(initial={"integrante": initial_uid})

    aits = t.aits.select_related("integrante").all().order_by("-criado_em")
    return render(request, "taloes/aits.html", {"talao": t, "form": form, "aits": aits})
