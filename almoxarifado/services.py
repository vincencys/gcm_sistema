from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from typing import Any
from django.conf import settings
from common.audit_simple import record
from datetime import time
from common.audit import log_event

from .models import (
    Cautela,
    CautelaItem,
    BemPatrimonial,
    Municao,
    MunicaoEstoque,
    Manutencao,
)

User = get_user_model()

ItemTipo = Literal["ARMAMENTO", "MUNICAO", "ACESSORIO"]


@dataclass
class ItemSpec:
    item_tipo: ItemTipo
    object_id: int
    quantidade: int = 1


def _get_ct_for_model(model):
    return ContentType.objects.get_for_model(model)


def _parse_hhmm(value: str) -> time:
    try:
        h, m = (value or "").split(":", 1)
        return time(int(h), int(m))
    except Exception:
        # fallback amplo se configuração estiver inválida
        return time(0, 0)


def _is_now_within_window(now, inicio: time, fim: time) -> bool:
    # janela simples no mesmo dia (não cruza meia-noite)
    local = timezone.localtime(now)
    t = local.timetz().replace(tzinfo=None)
    return inicio <= t <= fim


def _get_user_policy_limit(user) -> int:
    policy = getattr(settings, "ALMOXARIFADO_POLICY", {})
    limites = policy.get("limites", {})
    default = limites.get("default", {}).get("municao_total_max", 10**9)
    perfil = getattr(user, "perfil", None)
    # por cargo
    cargo = getattr(perfil, "cargo", None)
    if cargo:
        por_cargo = limites.get("por_cargo", {})
        cfg = por_cargo.get(str(cargo), None)
        if cfg and isinstance(cfg, dict) and "municao_total_max" in cfg:
            return int(cfg["municao_total_max"]) or default
    # por classe
    classe = getattr(perfil, "classe", None)
    if classe:
        por_classe = limites.get("por_classe", {})
        cfg = por_classe.get(str(classe), None)
        if cfg and isinstance(cfg, dict) and "municao_total_max" in cfg:
            return int(cfg["municao_total_max"]) or default
    return default


def _total_municao_itens(cautela: Cautela) -> int:
    return sum(i.quantidade for i in cautela.itens.all() if i.item_tipo == "MUNICAO")


@transaction.atomic
def solicitar_cautela(*, usuario: Any, supervisor: Any | None, itens: Iterable[ItemSpec],
                      prevista_devolucao=None, motivo: str = "", observacoes: str = ""):
    """Cria uma solicitação de cautela de SUPORTE em estado PENDENTE.

    - Não movimenta estoque ainda (reserva ocorre na aprovação)
    - Cria os CautelaItem apontando para BemPatrimonial/Municao conforme item_tipo
    """
    # valida: usuário sem cautelas atrasadas/abertas vencidas
    now = timezone.now()
    tem_bloqueio = Cautela.objects.filter(
        usuario=usuario,
        status__in=["ATRASADA"],
    ).exists() or Cautela.objects.filter(
        usuario=usuario,
        status__in=["ABERTA"],
        data_hora_prevista_devolucao__isnull=False,
        data_hora_prevista_devolucao__lt=now,
    ).exists()
    if tem_bloqueio:
        raise ValueError("Usuário com cautela atrasada/pendente não pode abrir nova solicitação")

    cautela = Cautela.objects.create(
        tipo="SUPORTE",
        usuario=usuario,
        supervisor=supervisor,
        data_hora_prevista_devolucao=prevista_devolucao,
        status="PENDENTE",
        motivo=motivo,
        observacoes=observacoes,
    )

    ct_bem = _get_ct_for_model(BemPatrimonial)
    ct_mun = _get_ct_for_model(Municao)

    for spec in itens:
        if spec.item_tipo == "ARMAMENTO" or spec.item_tipo == "ACESSORIO":
            # valida existência
            if not BemPatrimonial.objects.filter(pk=spec.object_id, ativo=True).exists():
                raise ValueError(f"Bem patrimonial {spec.object_id} não encontrado/ativo")
            CautelaItem.objects.create(
                cautela=cautela,
                content_type=ct_bem,
                object_id=spec.object_id,
                item_tipo=spec.item_tipo,
                quantidade=spec.quantidade or 1,
            )
        elif spec.item_tipo == "MUNICAO":
            # Aceita tanto o novo modelo Municao quanto o BemPatrimonial (classe MUNICAO)
            if (spec.quantidade or 0) <= 0:
                raise ValueError("Quantidade de munição deve ser > 0")
            is_municao_model = Municao.objects.filter(pk=spec.object_id, deleted_at__isnull=True).exists()
            is_bem_municao = False
            if not is_municao_model:
                is_bem_municao = BemPatrimonial.objects.filter(pk=spec.object_id, classe="MUNICAO", ativo=True).exists()
                if not is_bem_municao:
                    raise ValueError(f"Munição {spec.object_id} não encontrada")
            CautelaItem.objects.create(
                cautela=cautela,
                content_type=ct_mun if is_municao_model else ct_bem,
                object_id=spec.object_id,
                item_tipo=spec.item_tipo,
                quantidade=spec.quantidade,
            )
        else:
            raise ValueError(f"item_tipo inválido: {spec.item_tipo}")

    # auditoria
    after = _snap_cautela(cautela)
    log_event(actor=usuario, obj=cautela, event="SOLICITAR", message="Solicitação de cautela de suporte criada", before=None, after=after)
    return cautela


@transaction.atomic
def aprovar_cautela(*, cautela, supervisor, local_estoque: str = "ALMOXARIFADO"):
    """Aprova solicitação e reserva munição.

    - Transição PENDENTE -> APROVADA
    - Para cada item de munição, move de disponível para reservada no estoque do local.
    """
    if cautela.status != "PENDENTE":
        raise ValueError("Somente cautelas pendentes podem ser aprovadas")

    # Segregação (opcional): supervisor não pode ser o solicitante
    if getattr(settings, "ALMOXARIFADO_POLICY", {}).get("dupla_operacao", False):
        if supervisor and cautela.usuario_id == getattr(supervisor, "id", None):
            raise ValueError("Segregação de funções: supervisor não pode ser o solicitante")

    # valida calibre compatível entre armamentos e munições (regra simples)
    armas = []
    muni_calibres = set()
    for item in cautela.itens.all():
        if item.item_tipo in ("ARMAMENTO", "ACESSORIO"):
            if item.item_tipo == "ARMAMENTO":
                try:
                    bem = BemPatrimonial.objects.only("calibre").get(pk=item.object_id)
                    armas.append((item.object_id, (bem.calibre or "").strip().upper()))
                except BemPatrimonial.DoesNotExist:
                    raise ValueError(f"Armamento {item.object_id} não encontrado")
        elif item.item_tipo == "MUNICAO":
            # Suporta munição vinda tanto de Municao quanto de BemPatrimonial (classe MUNICAO)
            model_cls = item.content_type.model_class()
            if model_cls is Municao:
                try:
                    mun = Municao.objects.only("calibre").get(pk=item.object_id)
                    muni_calibres.add((mun.calibre or "").strip().upper())
                except Municao.DoesNotExist:
                    # Defensive: se o item aponta para Municao inexistente
                    raise ValueError(f"Munição {item.object_id} não encontrada")
            else:
                try:
                    bem_m = BemPatrimonial.objects.only("calibre").get(pk=item.object_id)
                    muni_calibres.add((bem_m.calibre or "").strip().upper())
                except BemPatrimonial.DoesNotExist:
                    raise ValueError(f"Munição {item.object_id} não encontrada")

    if armas and muni_calibres:
        arm_set = {cal for _, cal in armas if cal}
        # exige que todas as munições sejam compatíveis com todos os armamentos
        if not arm_set or any(cal not in arm_set for cal in muni_calibres):
            raise ValueError("Calibre de munição incompatível com armamento selecionado")

    # Limite de munição por perfil
    total_mun = _total_municao_itens(cautela)
    limite = _get_user_policy_limit(cautela.usuario)
    if total_mun > limite:
        raise ValueError(f"Quantidade total de munição ({total_mun}) excede o limite permitido ({limite}) para o perfil do usuário")

    # Reserva/baixa de munição no momento da aprovação (política: reservar na aprovação)
    for item in cautela.itens.select_for_update().all():
        if item.item_tipo == "MUNICAO":
            if item.content_type.model_class() is Municao:
                mun = Municao.objects.select_for_update().get(pk=item.object_id)
                est, _ = MunicaoEstoque.objects.select_for_update().get_or_create(municao=mun, local=local_estoque)
                if est.quantidade_disponivel < item.quantidade:
                    raise ValueError(f"Estoque insuficiente para {mun} na aprovação")
                est.quantidade_disponivel -= item.quantidade
                est.quantidade_reservada += item.quantidade
                est.save(update_fields=["quantidade_disponivel", "quantidade_reservada"])
            else:
                bem = BemPatrimonial.objects.select_for_update().get(pk=item.object_id)
                if (bem.quantidade or 0) < item.quantidade:
                    raise ValueError(f"Estoque insuficiente para {bem} na aprovação")
                bem.quantidade = (bem.quantidade or 0) - int(item.quantidade)
                bem.save(update_fields=["quantidade"])  # baixa direta para bens-munição

    before = _snap_cautela(cautela)
    cautela.status = "APROVADA"
    cautela.supervisor = supervisor
    cautela.aprovada_em = timezone.now()
    cautela.save(update_fields=["status", "supervisor", "aprovada_em"])
    log_event(actor=supervisor, obj=cautela, event="APROVAR", message="Cautela aprovada", before=before, after=_snap_cautela(cautela))
    return cautela


@transaction.atomic
def entregar_cautela(*, cautela, almoxarife, checklist_saida: dict | None = None):
    """Entrega (abre) a cautela.

    - Transição APROVADA -> ABERTA
    - Baixa de estoque de munição é aplicada na entrega (política debit-on-delivery)
    - Registra data_hora_retirada
    """
    if cautela.status != "APROVADA":
        raise ValueError("Somente cautelas aprovadas podem ser entregues")

    # Segregação (opcional): manter apenas a restrição contra o solicitante.
    # Fluxo atual: supervisor aprova e também efetiva a entrega, então permitir almoxarife==supervisor.
    if getattr(settings, "ALMOXARIFADO_POLICY", {}).get("dupla_operacao", False):
        if almoxarife and cautela.usuario_id == getattr(almoxarife, "id", None):
            raise ValueError("Segregação de funções: o solicitante não pode efetivar a entrega")

    # Janela de horário para retirada
    policy = getattr(settings, "ALMOXARIFADO_POLICY", {})
    horarios = policy.get("horarios", {})
    ini = _parse_hhmm(horarios.get("retirada_inicio", "00:00"))
    fim = _parse_hhmm(horarios.get("retirada_fim", "23:59"))
    if not _is_now_within_window(timezone.now(), ini, fim):
        perm = policy.get("permissao_excecao") or "almoxarifado.desbloquear_excecao"
        if not (almoxarife and almoxarife.has_perm(perm)):
            raise ValueError("Entrega fora da janela de horário permitida")

    # valida manutenção bloqueando entrega
    arm_ids = [i.object_id for i in cautela.itens.all() if i.item_tipo == "ARMAMENTO"]
    if arm_ids:
        em_manutencao = Manutencao.objects.filter(
            armamento_id__in=arm_ids,
            data_fim__isnull=True,
            impacta_disponibilidade=True,
        ).exists()
        if em_manutencao:
            raise ValueError("Armamento em manutenção com impacto de disponibilidade. Entrega bloqueada.")

    # Nota: não reexecutar aprovação aqui (evita erro de status). Se necessário,
    # validações adicionais devem ser feitas localmente.

    # consumo efetivo: para Municao, sai de 'reservada'; para BemPatrimonial (classe MUNICAO), já foi baixado na aprovação
    for item in cautela.itens.select_for_update().all():
        if item.item_tipo == "MUNICAO":
            # Se for do modelo Municao, consome reservado; se for BemPatrimonial (classe MUNICAO), nada a fazer aqui
            if item.content_type.model_class() is Municao:
                mun = Municao.objects.select_for_update().get(pk=item.object_id)
                est, _ = MunicaoEstoque.objects.select_for_update().get_or_create(municao=mun, local="ALMOXARIFADO")
                if est.quantidade_reservada < item.quantidade:
                    raise ValueError(f"Reserva insuficiente para {mun} na entrega")
                est.quantidade_reservada -= item.quantidade
                est.save(update_fields=["quantidade_reservada"])
            else:
                # bem-munição: baixa já realizada na aprovação
                pass

    before = _snap_cautela(cautela)
    cautela.status = "ABERTA"
    cautela.almoxarife = almoxarife
    cautela.data_hora_retirada = timezone.now()
    if checklist_saida:
        # opcional: armazenar no observações por enquanto (MVP)
        import json
        cautela.observacoes = (cautela.observacoes or "") + "\nCHECKLIST_SAIDA=" + json.dumps(checklist_saida, ensure_ascii=False)
    cautela.save(update_fields=["status", "almoxarife", "data_hora_retirada", "observacoes"])
    log_event(actor=almoxarife, obj=cautela, event="ENTREGAR", message="Cautela entregue/aberta", before=before, after=_snap_cautela(cautela))
    return cautela


@transaction.atomic
def devolver_cautela(*, cautela, almoxarife, checklist_retorno: dict | None = None,
                     municao_devolvida: dict[int, int] | None = None, local_estoque: str = "ALMOXARIFADO",
                     supervisor=None):
    """Recebe e encerra a cautela.

    - Transição ABERTA -> ENCERRADA
    - Opcionalmente, realiza devolução de munição não utilizada (mapa municao_id -> quantidade)
    - Registra data_hora_devolucao
    """
    if cautela.status not in {"ABERTA", "APROVADA"}:
        raise ValueError("Somente cautelas abertas ou aprovadas podem ser devolvidas")

    # Janela de horário para devolução
    policy = getattr(settings, "ALMOXARIFADO_POLICY", {})
    horarios = policy.get("horarios", {})
    ini = _parse_hhmm(horarios.get("devolucao_inicio", "00:00"))
    fim = _parse_hhmm(horarios.get("devolucao_fim", "23:59"))
    if not _is_now_within_window(timezone.now(), ini, fim):
        perm = policy.get("permissao_excecao") or "almoxarifado.desbloquear_excecao"
        if not (almoxarife and almoxarife.has_perm(perm)):
            raise ValueError("Devolução fora da janela de horário permitida")

    # Validação: devolução deve ser aprovada pelo supervisor designado
    if supervisor and cautela.supervisor_id and cautela.supervisor_id != getattr(supervisor, 'id', None):
        raise ValueError("Somente o supervisor designado pode aprovar a devolução")

    # devolução opcional de munição (apenas quando já houve entrega)
    if municao_devolvida and cautela.status == "ABERTA":
        for mun_id, qtd in municao_devolvida.items():
            if (qtd or 0) <= 0:
                continue
            try:
                # Tenta devolver para o modelo Municao
                mun = Municao.objects.select_for_update().get(pk=mun_id)
                est, _ = MunicaoEstoque.objects.select_for_update().get_or_create(municao=mun, local=local_estoque)
                # ao devolver, aumenta disponível (reserva já foi consumida na entrega)
                est.quantidade_disponivel += int(qtd)
                est.save(update_fields=["quantidade_disponivel"])
            except Municao.DoesNotExist:
                # Fallback: devolver para BemPatrimonial (classe MUNICAO)
                bem = BemPatrimonial.objects.select_for_update().get(pk=mun_id)
                bem.quantidade = (bem.quantidade or 0) + int(qtd)
                bem.save(update_fields=["quantidade"]) 

    # Caso a cautela ainda esteja APROVADA (sem entrega), desfaz reservas/baixas integrais
    if cautela.status == "APROVADA":
        for item in cautela.itens.select_for_update().all():
            if item.item_tipo != "MUNICAO":
                continue
            if item.content_type.model_class() is Municao:
                mun = Municao.objects.select_for_update().get(pk=item.object_id)
                est, _ = MunicaoEstoque.objects.select_for_update().get_or_create(municao=mun, local=local_estoque)
                # Reverte reserva: volta tudo para disponível
                if est.quantidade_reservada < item.quantidade:
                    # corrige para zero, evitando números negativos
                    item_qtd = est.quantidade_reservada
                else:
                    item_qtd = item.quantidade
                est.quantidade_reservada -= int(item_qtd)
                est.quantidade_disponivel += int(item_qtd)
                est.save(update_fields=["quantidade_reservada", "quantidade_disponivel"])
            else:
                # Para BemPatrimonial (classe MUNICAO), a baixa foi na aprovação — repõe tudo
                bem = BemPatrimonial.objects.select_for_update().get(pk=item.object_id)
                bem.quantidade = (bem.quantidade or 0) + int(item.quantidade)
                bem.save(update_fields=["quantidade"]) 

    before = _snap_cautela(cautela)
    cautela.status = "ENCERRADA"
    cautela.data_hora_devolucao = timezone.now()
    if checklist_retorno:
        import json
        cautela.observacoes = (cautela.observacoes or "") + "\nCHECKLIST_RETORNO=" + json.dumps(checklist_retorno, ensure_ascii=False)
    cautela.save(update_fields=["status", "data_hora_devolucao", "observacoes"])
    log_event(actor=almoxarife, obj=cautela, event="DEVOLVER", message="Cautela encerrada", before=before, after=_snap_cautela(cautela))
    return cautela


def _snap_cautela(c: Cautela) -> dict:
    return {
        "id": c.id,
        "status": c.status,
        "usuario_id": c.usuario_id,
        "supervisor_id": c.supervisor_id,
        "almoxarife_id": c.almoxarife_id,
        "prev_devolucao": c.data_hora_prevista_devolucao.isoformat() if c.data_hora_prevista_devolucao else None,
        "retirada": c.data_hora_retirada.isoformat() if c.data_hora_retirada else None,
        "devolucao": c.data_hora_devolucao.isoformat() if c.data_hora_devolucao else None,
        "aprovada_em": c.aprovada_em.isoformat() if c.aprovada_em else None,
        "itens": [
            {"tipo": i.item_tipo, "obj": i.object_id, "qtd": i.quantidade}
            for i in c.itens.all()
        ],
    }
