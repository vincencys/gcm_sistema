from __future__ import annotations
from django import forms
from .models import (
    CategoriaProduto, Produto, MovimentacaoEstoque,
    BemPatrimonial, MovimentacaoCautela, CautelaPermanente, DisparoArma, Municao
)
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError


# ===== Estoque =====
class CategoriaProdutoForm(forms.ModelForm):
    class Meta:
        model = CategoriaProduto
        fields = ["nome", "descricao"]


class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = ["categoria", "nome", "unidade", "estoque_minimo", "ativo"]


class MovimentacaoEstoqueForm(forms.ModelForm):
    class Meta:
        model = MovimentacaoEstoque
        fields = ["tipo", "quantidade", "observacao"]


# ===== Cautelas =====
class BemPatrimonialForm(forms.ModelForm):
    class Meta:
        model = BemPatrimonial
        fields = ["tipo", "nome", "tombamento", "numero_serie", "calibre", "observacoes", "ativo"]


class ArmamentoSuporteForm(forms.ModelForm):
    class Meta:
        model = BemPatrimonial
        fields = ["subtipo_armamento", "nome", "numero_serie", "calibre", "observacoes"]


class MunicaoSuporteForm(forms.ModelForm):
    class Meta:
        model = BemPatrimonial
        fields = ["nome", "calibre", "lote", "quantidade", "observacoes"]


class ArmamentoFixoForm(forms.ModelForm):
    class UserMatriculaChoiceField(forms.ModelChoiceField):
        def label_from_instance(self, obj):
            perfil = getattr(obj, "perfil", None)
            matricula = getattr(perfil, "matricula", "") or getattr(obj, "username", "")
            nome = (obj.get_full_name() or obj.first_name or obj.last_name or obj.username).upper()
            return f"{matricula} - {nome}"

    dono = UserMatriculaChoiceField(
        queryset=get_user_model().objects.none(),
        required=False,
        label="Agente responsável",
        help_text="Selecione o agente: matrícula - nome",
    )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # classe usada para ativar o filtro por texto no select (JS)
        self.fields["dono"].widget.attrs.update({"class": "js-searchable w-full"})
        User = get_user_model()
        self.fields["dono"].queryset = (
            User.objects.select_related("perfil")
            .filter(perfil__isnull=False)
            .order_by("perfil__matricula", "username")
        )
        self.fields["dono"].empty_label = "Selecione o agente: matrícula - nome"
    class Meta:
        model = BemPatrimonial
        fields = ["subtipo_armamento", "nome", "numero_serie", "calibre", "dono", "observacoes"]


class MunicaoFixoForm(forms.ModelForm):
    class UserMatriculaChoiceField(forms.ModelChoiceField):
        def label_from_instance(self, obj):
            perfil = getattr(obj, "perfil", None)
            matricula = getattr(perfil, "matricula", "") or getattr(obj, "username", "")
            nome = (obj.get_full_name() or obj.first_name or obj.last_name or obj.username).upper()
            return f"{matricula} - {nome}"

    dono = UserMatriculaChoiceField(
        queryset=get_user_model().objects.none(),
        required=False,
        label="Agente responsável",
        help_text="Selecione o agente: matrícula - nome",
    )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["dono"].widget.attrs.update({"class": "js-searchable w-full"})
        User = get_user_model()
        self.fields["dono"].queryset = (
            User.objects.select_related("perfil")
            .filter(perfil__isnull=False)
            .order_by("perfil__matricula", "username")
        )
        self.fields["dono"].empty_label = "Selecione o agente: matrícula - nome"
    class Meta:
        model = BemPatrimonial
        fields = ["nome", "calibre", "lote", "quantidade", "dono", "observacoes"]


class MovimentacaoCautelaForm(forms.ModelForm):
    class Meta:
        model = MovimentacaoCautela
        fields = ["tipo", "agente", "observacao", "checklist_saida_json", "checklist_entrada_json"]
        widgets = {
            "checklist_saida_json": forms.Textarea(attrs={"rows": 3}),
            "checklist_entrada_json": forms.Textarea(attrs={"rows": 3}),
        }


class CautelaPermanenteForm(forms.ModelForm):
    class Meta:
        model = CautelaPermanente
        fields = ["usuario", "observacao"]


class DisparoArmaForm(forms.ModelForm):
    class Meta:
        model = DisparoArma
        fields = ["usuario", "quantidade", "data", "observacao"]
        widgets = {"data": forms.DateInput(attrs={"type": "date"})}


class EntregaCautelaForm(forms.Form):
    checklist_saida = forms.CharField(
        label="Checklist de Saída (JSON)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 6, "placeholder": "{\n  \"numero_serie_confere\": true,\n  \"condicao\": \"ok\"\n}"}),
    )

    def clean_checklist_saida(self):
        data = self.cleaned_data.get("checklist_saida")
        if not data:
            return None
        try:
            import json
            return json.loads(data)
        except Exception as e:
            raise ValidationError("JSON inválido") from e


class DevolucaoCautelaForm(forms.Form):
    checklist_retorno = forms.CharField(
        label="Checklist de Retorno (JSON)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 6}),
    )
    municao_devolvida = forms.CharField(
        label="Munição devolvida (JSON: { municao_id: quantidade })",
        required=False,
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "{ 1: 10, 5: 20 }"}),
    )

    def clean_checklist_retorno(self):
        data = self.cleaned_data.get("checklist_retorno")
        if not data:
            return None
        try:
            import json
            return json.loads(data)
        except Exception as e:
            raise ValidationError("JSON inválido") from e

    def clean_municao_devolvida(self):
        data = self.cleaned_data.get("municao_devolvida")
        if not data:
            return None
        try:
            import json
            parsed = json.loads(data)
            if not isinstance(parsed, dict):
                raise ValidationError("Deve ser um objeto JSON { municao_id: quantidade }")
            return {int(k): int(v) for k, v in parsed.items()}
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError("JSON inválido ou valores não numéricos") from e


User = get_user_model()


class SolicitarCautelaSuporteForm(forms.Form):
    class ArmamentoBemMultipleChoice(forms.ModelMultipleChoiceField):
        def label_from_instance(self, obj: BemPatrimonial):
            # Exibe tipo + nome e acrescenta Nº de série e calibre quando existirem
            base = f"{obj.get_tipo_display()} - {obj.nome}".strip()
            detalhes = []
            ns = (obj.numero_serie or "").strip()
            if ns:
                detalhes.append(f"Nº {ns}")
            cal = (obj.calibre or "").strip()
            if cal:
                detalhes.append(f"Calibre {cal}")
            return base + (" • " + " • ".join(detalhes) if detalhes else "")
    class UserMatriculaChoiceField(forms.ModelChoiceField):
        def label_from_instance(self, obj):
            perfil = getattr(obj, "perfil", None)
            matricula = getattr(perfil, "matricula", "") or getattr(obj, "username", "")
            nome = (obj.get_full_name() or obj.first_name or obj.last_name or obj.username).upper()
            return f"{matricula} - {nome}"

    supervisor = UserMatriculaChoiceField(
        queryset=User.objects.none(),
        required=True,
        label="Supervisor",
        help_text="Obrigatório: quem aprova a entrega e a devolução",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        UserModel = get_user_model()
        self.fields["supervisor"].queryset = (
            UserModel.objects.select_related("perfil")
            .filter(perfil__isnull=False)
            .order_by("perfil__matricula", "username")
        )
        # classe para futura busca por texto (quando JS ativo)
        self.fields["supervisor"].widget.attrs.update({"class": "w-full js-searchable"})
        self.fields["supervisor"].empty_label = "--------"
    prevista_devolucao = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    armamentos = ArmamentoBemMultipleChoice(
        queryset=BemPatrimonial.objects.filter(classe='ARMAMENTO', grupo='SUPORTE', ativo=True).order_by('nome'),
        required=False,
        help_text="Selecione um ou mais armamentos do pool (opcional)",
        widget=forms.SelectMultiple(attrs={"size": 6}),
    )


class MuniicaoLinhaForm(forms.Form):
    class MunicaoBemChoiceField(forms.ModelChoiceField):
        def label_from_instance(self, obj: BemPatrimonial):
            desc = (obj.nome or "").strip()
            cal = (obj.calibre or "").strip()
            lote = (getattr(obj, "lote", "") or "").strip()
            disp = obj.quantidade or 0
            # Para itens cadastrados como BemPatrimonial não há controle de 'reservada'; exibir 0 para dar visibilidade
            res = 0
            obs = (obj.observacoes or "").strip()
            base = f"{desc}"
            if cal:
                base += f" • Calibre {cal}"
            if lote:
                base += f" • Lote {lote}"
            base += f" • disp {disp} / res {res}"
            if obs:
                base += f" • {obs}"
            return base

    municao = MunicaoBemChoiceField(
        queryset=BemPatrimonial.objects.filter(classe='MUNICAO', grupo='SUPORTE', ativo=True).order_by('nome', 'calibre'),
        required=False,
        label="Munição",
    )
    quantidade = forms.IntegerField(min_value=1, required=False)

    def clean(self):
        cleaned = super().clean()
        m = cleaned.get("municao")
        q = cleaned.get("quantidade")
        # Permitir linha vazia (ambos None) para facilitar extra
        if (m and not q) or (q and not m):
            raise ValidationError("Informe munição e quantidade ou deixe a linha vazia")
        return cleaned
