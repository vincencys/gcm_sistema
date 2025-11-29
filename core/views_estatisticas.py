# Estatísticas - Abordados e Policiamentos
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.db.models import Count
from django.db.models.functions import TruncDate
from datetime import date
import csv
import json


# ======================
#   ESTATÍSTICAS ABORDADOS
# ======================

@login_required
def estatisticas_abordados(request):
    """Estatísticas de Abordados (veículos e pessoas registrados nos Talões).
    
    Base: taloes.Abordado (campo criado_em).
    Filtros: ?de=YYYY-MM-DD&ate=YYYY-MM-DD.
    """
    from taloes.models import Abordado
    from collections import Counter
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Select de integrantes (GCMs)
    try:
        from users.models import Perfil
        perfis = (
            Perfil.objects.select_related('user')
            .filter(ativo=True, user__is_active=True)
            .order_by('matricula', 'user__first_name', 'user__last_name')
        )
        user_options = []
        for p in perfis:
            nome = (p.user.get_full_name() or p.user.username).strip()
            label = f"{nome} — {p.matricula}" if p.matricula else nome
            user_options.append({'id': p.user_id, 'label': label})
    except Exception:
        user_options = []
    
    hoje = timezone.localdate()
    try:
        de_str = (request.GET.get('de') or f"{hoje.replace(day=1):%Y-%m-%d}")
        ate_str = (request.GET.get('ate') or f"{hoje:%Y-%m-%d}")
        from datetime import datetime
        de = datetime.strptime(de_str, '%Y-%m-%d').date()
        ate = datetime.strptime(ate_str, '%Y-%m-%d').date()
    except Exception:
        de = hoje.replace(day=1)
        ate = hoje
    
    try:
        uid = int(request.GET.get('user') or 0)
    except Exception:
        uid = 0

    # Query base por período
    qs = Abordado.objects.select_related('talao', 'talao__criado_por', 'talao__encarregado', 'talao__motorista', 'talao__auxiliar1', 'talao__auxiliar2').filter(criado_em__date__range=(de, ate))
    
    # Filtro por GCM (considera TODOS os campos: criado_por, encarregado, motorista, auxiliar1, auxiliar2)
    if uid:
        from django.db.models import Q
        qs = qs.filter(
            Q(talao__criado_por_id=uid) | 
            Q(talao__encarregado_id=uid) | 
            Q(talao__motorista_id=uid) | 
            Q(talao__auxiliar1_id=uid) | 
            Q(talao__auxiliar2_id=uid)
        )
    
    # Exportação CSV
    if (request.GET.get('export') or '').lower() == 'csv':
        resp = HttpResponse(content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = f"attachment; filename=abordados_{de:%Y%m%d}_{ate:%Y%m%d}{('_user_'+str(uid)) if uid else ''}.csv"
        w = csv.writer(resp)
        w.writerow(['ID','Criado em','Talao ID','GCM ID','GCM','Matrícula','Tipo','Nome/Placa'])
        for r in qs.select_related('talao__criado_por__perfil').order_by('criado_em'):
            u = r.talao.criado_por if r.talao else None
            nome = (u.get_full_name() or u.username).strip() if u else ''
            perf = getattr(u,'perfil',None) if u else None
            mat = getattr(perf,'matricula','') if perf else ''
            criado = timezone.localtime(r.criado_em).strftime('%Y-%m-%d %H:%M:%S') if r.criado_em else ''
            tipo = r.tipo
            nome_placa = r.nome if tipo == 'PESSOA' else r.placa
            w.writerow([r.id, criado, r.talao_id, u.id if u else '', nome, mat, tipo, nome_placa])
        return resp
    
    total = qs.count()
    total_veiculos = qs.filter(tipo='VEICULO').count()
    total_pessoas = qs.filter(tipo='PESSOA').count()
    
    # Top 5 por GCM (considera TODOS os integrantes do talão)
    contador_integrantes = Counter()
    for abordado in qs:
        talao = abordado.talao
        if not talao:
            continue
        # Coletar todos os integrantes do talão
        integrantes_ids = set()
        if talao.criado_por_id:
            integrantes_ids.add(talao.criado_por_id)
        if talao.encarregado_id:
            integrantes_ids.add(talao.encarregado_id)
        if talao.motorista_id:
            integrantes_ids.add(talao.motorista_id)
        if talao.auxiliar1_id:
            integrantes_ids.add(talao.auxiliar1_id)
        if talao.auxiliar2_id:
            integrantes_ids.add(talao.auxiliar2_id)
        
        # Incrementar contador para cada integrante
        for user_id in integrantes_ids:
            contador_integrantes[user_id] += 1
    
    # Montar top 5 com dados dos usuários
    top_integrantes = []
    for user_id, qtd in contador_integrantes.most_common(5):
        try:
            user = User.objects.get(pk=user_id)
            top_integrantes.append({
                'talao__criado_por_id': user_id,
                'talao__criado_por__first_name': user.first_name,
                'talao__criado_por__last_name': user.last_name,
                'talao__criado_por__username': user.username,
                'qtd': qtd
            })
        except User.DoesNotExist:
            pass
    
    # Top 10 por dia do período
    top_dias = (
        qs.extra(select={'dia': "DATE(criado_em)"})
        .values('dia')
        .annotate(qtd=Count('id'))
        .order_by('-qtd')[:10]
    )

    # Exportação PDF
    if (request.GET.get('export') or '').lower() == 'pdf':
        # Top 10 para PDF (mesma lógica do top 5)
        top_10_pdf = []
        for user_id, qtd in contador_integrantes.most_common(10):
            try:
                user = User.objects.get(pk=user_id)
                top_10_pdf.append({
                    'talao__criado_por__first_name': user.first_name,
                    'talao__criado_por__last_name': user.last_name,
                    'talao__criado_por__username': user.username,
                    'qtd': qtd
                })
            except User.DoesNotExist:
                pass
        
        html = render_to_string('core/adm_estatisticas_abordados_pdf.html', {
            'de': de,
            'ate': ate,
            'total': total,
            'total_veiculos': total_veiculos,
            'total_pessoas': total_pessoas,
            'top_integrantes': top_10_pdf,
            'top_dias': list(
                qs.extra(select={'dia': "DATE(criado_em)"})
                  .values('dia').annotate(qtd=Count('id')).order_by('-qtd')[:10]
            ),
            'uid': uid,
        })
        try:
            import tempfile, os, subprocess
            from django.conf import settings
            with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as fhtml:
                fhtml.write(html.encode('utf-8'))
                html_path = fhtml.name
            wkhtml = getattr(settings, 'WKHTMLTOPDF_CMD', None)
            if not wkhtml:
                raise FileNotFoundError('wkhtmltopdf não encontrado')
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as fpdf:
                pdf_path = fpdf.name
            args = [wkhtml, '--quiet', html_path, pdf_path]
            subprocess.check_call(args)
            with open(pdf_path, 'rb') as pf:
                pdf_bytes = pf.read()
            try:
                os.unlink(html_path)
                os.unlink(pdf_path)
            except Exception:
                pass
            resp = HttpResponse(pdf_bytes, content_type='application/pdf')
            resp['Content-Disposition'] = f"attachment; filename=abordados_{de:%Y%m%d}_{ate:%Y%m%d}.pdf"
            return resp
        except Exception:
            return HttpResponse(html)

    ctx = {
        'de': de,
        'ate': ate,
        'total': total,
        'total_veiculos': total_veiculos,
        'total_pessoas': total_pessoas,
        'top_integrantes': top_integrantes,
        'top_dias': top_dias,
        'user_options': user_options,
        'uid': uid,
    }
    return render(request, 'core/adm_estatisticas_abordados.html', ctx)


@login_required
def estatisticas_abordados_graficos(request):
    """Gráfico de linha (série diária) de Abordados por período, com filtro opcional por integrante."""
    from taloes.models import Abordado
    try:
        from users.models import Perfil
    except Exception:
        Perfil = None
    
    hoje = timezone.localdate()
    tab = (request.GET.get('tab') or 'mes').lower()
    if tab not in {'dia','mes','semestre','ano'}:
        tab = 'mes'
    
    if tab == 'dia':
        default_de, default_ate = hoje, hoje
    elif tab == 'mes':
        default_de, default_ate = hoje.replace(day=1), hoje
    elif tab == 'semestre':
        if hoje.month <= 6:
            default_de, default_ate = date(hoje.year,1,1), date(hoje.year,6,30)
        else:
            default_de, default_ate = date(hoje.year,7,1), date(hoje.year,12,31)
            if hoje < default_ate:
                default_ate = hoje
    else:
        default_de, default_ate = date(hoje.year,1,1), hoje
    
    try:
        from datetime import datetime
        de = datetime.strptime((request.GET.get('de') or f"{default_de:%Y-%m-%d}"), '%Y-%m-%d').date()
        ate = datetime.strptime((request.GET.get('ate') or f"{default_ate:%Y-%m-%d}"), '%Y-%m-%d').date()
    except Exception:
        de, ate = default_de, default_ate
    
    try:
        uid = int(request.GET.get('user') or 0)
    except Exception:
        uid = 0
    
    # Options para select
    user_options = []
    user_nome = ''
    if Perfil:
        perfis = (
            Perfil.objects.select_related('user')
            .filter(ativo=True, user__is_active=True)
            .order_by('matricula', 'user__first_name', 'user__last_name')
        )
        for p in perfis:
            nome = (p.user.get_full_name() or p.user.username).strip()
            label = f"{nome} — {p.matricula}" if p.matricula else nome
            user_options.append({'id': p.user_id, 'label': label})
            if p.user_id == uid:
                user_nome = nome
    
    # Query base
    qs = Abordado.objects.filter(criado_em__date__range=(de, ate))
    if uid:
        from django.db.models import Q
        qs = qs.filter(
            Q(talao__criado_por_id=uid) | 
            Q(talao__encarregado_id=uid) | 
            Q(talao__motorista_id=uid) | 
            Q(talao__auxiliar1_id=uid) | 
            Q(talao__auxiliar2_id=uid)
        )
    
    total = qs.count()
    serie = list(
        qs.annotate(dia=TruncDate('criado_em')).values('dia').annotate(qtd=Count('id')).order_by('dia')
    )
    serie_js = [
        {'dia': (row.get('dia').strftime('%Y-%m-%d') if row.get('dia') else ''), 'qtd': int(row.get('qtd') or 0)}
        for row in serie
    ]
    
    abas = [('dia','Dia'), ('mes','Mês'), ('semestre','Semestre'), ('ano','Ano')]
    ctx = {
        'tab': tab,
        'de': de,
        'ate': ate,
        'uid': uid,
        'user_nome': user_nome,
        'user_options': user_options,
        'total': total,
        'serie_por_dia': mark_safe(json.dumps(serie_js)),
        'abas': abas,
    }
    return render(request, 'core/adm_estatisticas_abordados_graficos.html', ctx)


# ======================
#   ESTATÍSTICAS POLICIAMENTOS
# ======================

@login_required
def estatisticas_policiamentos(request):
    """Estatísticas de Policiamentos (talões com ocorrência contendo 'Policiamento').
    
    Base: taloes.Talao (campo iniciado_em, status=FECHADO).
    Filtros: ?de=YYYY-MM-DD&ate=YYYY-MM-DD.
    """
    from taloes.models import Talao
    from collections import Counter
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Select de integrantes (GCMs)
    try:
        from users.models import Perfil
        perfis = (
            Perfil.objects.select_related('user')
            .filter(ativo=True, user__is_active=True)
            .order_by('matricula', 'user__first_name', 'user__last_name')
        )
        user_options = []
        for p in perfis:
            nome = (p.user.get_full_name() or p.user.username).strip()
            label = f"{nome} — {p.matricula}" if p.matricula else nome
            user_options.append({'id': p.user_id, 'label': label})
    except Exception:
        user_options = []
    
    hoje = timezone.localdate()
    try:
        de_str = (request.GET.get('de') or f"{hoje.replace(day=1):%Y-%m-%d}")
        ate_str = (request.GET.get('ate') or f"{hoje:%Y-%m-%d}")
        from datetime import datetime
        de = datetime.strptime(de_str, '%Y-%m-%d').date()
        ate = datetime.strptime(ate_str, '%Y-%m-%d').date()
    except Exception:
        de = hoje.replace(day=1)
        ate = hoje
    
    try:
        uid = int(request.GET.get('user') or 0)
    except Exception:
        uid = 0

    # Talões com ocorrência contendo "Policiamento"
    qs = Talao.objects.select_related(
        'codigo_ocorrencia', 
        'criado_por', 
        'encarregado', 
        'motorista', 
        'auxiliar1', 
        'auxiliar2'
    ).filter(
        status='FECHADO',
        iniciado_em__date__range=(de, ate),
        codigo_ocorrencia__descricao__icontains='Policiamento'
    )
    
    # Filtro por GCM (considera TODOS os campos)
    if uid:
        from django.db.models import Q
        qs = qs.filter(
            Q(criado_por_id=uid) | 
            Q(encarregado_id=uid) | 
            Q(motorista_id=uid) | 
            Q(auxiliar1_id=uid) | 
            Q(auxiliar2_id=uid)
        )
    
    # Exportação CSV
    if (request.GET.get('export') or '').lower() == 'csv':
        resp = HttpResponse(content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = f"attachment; filename=policiamentos_{de:%Y%m%d}_{ate:%Y%m%d}{('_user_'+str(uid)) if uid else ''}.csv"
        w = csv.writer(resp)
        w.writerow(['ID','Iniciado em','Encerrado em','Criado por','Matrícula','Ocorrência','Local'])
        for r in qs.select_related('criado_por__perfil', 'codigo_ocorrencia').order_by('iniciado_em'):
            u = getattr(r,'criado_por',None)
            nome = (u.get_full_name() or u.username).strip() if u else ''
            perf = getattr(u,'perfil',None) if u else None
            mat = getattr(perf,'matricula','') if perf else ''
            iniciado = timezone.localtime(getattr(r,'iniciado_em', None)).strftime('%Y-%m-%d %H:%M:%S') if getattr(r,'iniciado_em', None) else ''
            encerrado = timezone.localtime(getattr(r,'encerrado_em', None)).strftime('%Y-%m-%d %H:%M:%S') if getattr(r,'encerrado_em', None) else ''
            ocorrencia = str(getattr(r.codigo_ocorrencia,'descricao','')) if r.codigo_ocorrencia else ''
            local = f"{getattr(r,'local_bairro','')} - {getattr(r,'local_rua','')}"
            w.writerow([r.id, iniciado, encerrado, nome, mat, ocorrencia, local])
        return resp
    
    total = qs.count()
    
    # Top 5 por GCM (considera TODOS os integrantes do talão)
    contador_integrantes = Counter()
    for talao in qs:
        # Coletar todos os integrantes do talão
        integrantes_ids = set()
        if talao.criado_por_id:
            integrantes_ids.add(talao.criado_por_id)
        if talao.encarregado_id:
            integrantes_ids.add(talao.encarregado_id)
        if talao.motorista_id:
            integrantes_ids.add(talao.motorista_id)
        if talao.auxiliar1_id:
            integrantes_ids.add(talao.auxiliar1_id)
        if talao.auxiliar2_id:
            integrantes_ids.add(talao.auxiliar2_id)
        
        # Incrementar contador para cada integrante
        for user_id in integrantes_ids:
            contador_integrantes[user_id] += 1
    
    # Montar top 5 com dados dos usuários
    top_integrantes = []
    for user_id, qtd in contador_integrantes.most_common(5):
        try:
            user = User.objects.get(pk=user_id)
            top_integrantes.append({
                'criado_por_id': user_id,
                'criado_por__first_name': user.first_name,
                'criado_por__last_name': user.last_name,
                'criado_por__username': user.username,
                'qtd': qtd
            })
        except User.DoesNotExist:
            pass
    
    # Top 10 por dia do período
    top_dias = (
        qs.extra(select={'dia': "DATE(iniciado_em)"})
        .values('dia')
        .annotate(qtd=Count('id'))
        .order_by('-qtd')[:10]
    )

    # Top 10 Tipos de Policiamento (código de ocorrência)
    top_tipos = (
        qs.values('codigo_ocorrencia__descricao')
        .annotate(qtd=Count('id'))
        .order_by('-qtd')[:10]
    )
    
    # Top 10 Locais (normalizado - case insensitive)
    # Normalizar locais: combinar bairro + rua e converter para lowercase
    from collections import Counter as CollCounter
    contador_locais = CollCounter()
    
    for talao in qs:
        # Construir local completo
        bairro = (talao.local_bairro or '').strip()
        rua = (talao.local_rua or '').strip()
        
        if bairro and rua:
            local = f"{bairro} - {rua}"
        elif bairro:
            local = bairro
        elif rua:
            local = rua
        else:
            local = "Não informado"
        
        # Normalizar para lowercase para agrupar variações
        local_normalizado = local.lower()
        contador_locais[local_normalizado] += 1
    
    # Montar top 10 locais preservando capitalização original
    # (usar a primeira ocorrência encontrada como display)
    top_locais_raw = contador_locais.most_common(10)
    top_locais = []
    locais_vistos = {}
    
    for talao in qs:
        bairro = (talao.local_bairro or '').strip()
        rua = (talao.local_rua or '').strip()
        
        if bairro and rua:
            local = f"{bairro} - {rua}"
        elif bairro:
            local = bairro
        elif rua:
            local = rua
        else:
            local = "Não informado"
        
        local_norm = local.lower()
        if local_norm not in locais_vistos:
            locais_vistos[local_norm] = local
    
    for local_norm, qtd in top_locais_raw:
        top_locais.append({
            'local': locais_vistos.get(local_norm, local_norm.title()),
            'qtd': qtd
        })

    # Exportação PDF
    if (request.GET.get('export') or '').lower() == 'pdf':
        # Top 10 para PDF
        top_10_pdf = []
        for user_id, qtd in contador_integrantes.most_common(10):
            try:
                user = User.objects.get(pk=user_id)
                top_10_pdf.append({
                    'criado_por__first_name': user.first_name,
                    'criado_por__last_name': user.last_name,
                    'criado_por__username': user.username,
                    'qtd': qtd
                })
            except User.DoesNotExist:
                pass
        
        html = render_to_string('core/adm_estatisticas_policiamentos_pdf.html', {
            'de': de,
            'ate': ate,
            'total': total,
            'top_integrantes': top_10_pdf,
            'top_dias': list(
                qs.extra(select={'dia': "DATE(iniciado_em)"})
                  .values('dia').annotate(qtd=Count('id')).order_by('-qtd')[:10]
            ),
            'top_tipos': list(top_tipos),
            'top_locais': top_locais,
            'uid': uid,
        })
        try:
            import tempfile, os, subprocess
            from django.conf import settings
            with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as fhtml:
                fhtml.write(html.encode('utf-8'))
                html_path = fhtml.name
            wkhtml = getattr(settings, 'WKHTMLTOPDF_CMD', None)
            if not wkhtml:
                raise FileNotFoundError('wkhtmltopdf não encontrado')
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as fpdf:
                pdf_path = fpdf.name
            args = [wkhtml, '--quiet', html_path, pdf_path]
            subprocess.check_call(args)
            with open(pdf_path, 'rb') as pf:
                pdf_bytes = pf.read()
            try:
                os.unlink(html_path)
                os.unlink(pdf_path)
            except Exception:
                pass
            resp = HttpResponse(pdf_bytes, content_type='application/pdf')
            resp['Content-Disposition'] = f"attachment; filename=policiamentos_{de:%Y%m%d}_{ate:%Y%m%d}.pdf"
            return resp
        except Exception:
            return HttpResponse(html)

    ctx = {
        'de': de,
        'ate': ate,
        'total': total,
        'top_integrantes': top_integrantes,
        'top_dias': top_dias,
        'top_tipos': top_tipos,
        'top_locais': top_locais,
        'user_options': user_options,
        'uid': uid,
    }
    return render(request, 'core/adm_estatisticas_policiamentos.html', ctx)


@login_required
def estatisticas_policiamentos_graficos(request):
    """Gráfico de linha (série diária) de Policiamentos por período, com filtro opcional por integrante."""
    from taloes.models import Talao
    try:
        from users.models import Perfil
    except Exception:
        Perfil = None
    
    hoje = timezone.localdate()
    tab = (request.GET.get('tab') or 'mes').lower()
    if tab not in {'dia','mes','semestre','ano'}:
        tab = 'mes'
    
    if tab == 'dia':
        default_de, default_ate = hoje, hoje
    elif tab == 'mes':
        default_de, default_ate = hoje.replace(day=1), hoje
    elif tab == 'semestre':
        if hoje.month <= 6:
            default_de, default_ate = date(hoje.year,1,1), date(hoje.year,6,30)
        else:
            default_de, default_ate = date(hoje.year,7,1), date(hoje.year,12,31)
            if hoje < default_ate:
                default_ate = hoje
    else:
        default_de, default_ate = date(hoje.year,1,1), hoje
    
    try:
        from datetime import datetime
        de = datetime.strptime((request.GET.get('de') or f"{default_de:%Y-%m-%d}"), '%Y-%m-%d').date()
        ate = datetime.strptime((request.GET.get('ate') or f"{default_ate:%Y-%m-%d}"), '%Y-%m-%d').date()
    except Exception:
        de, ate = default_de, default_ate
    
    try:
        uid = int(request.GET.get('user') or 0)
    except Exception:
        uid = 0
    
    # Options para select
    user_options = []
    user_nome = ''
    if Perfil:
        perfis = (
            Perfil.objects.select_related('user')
            .filter(ativo=True, user__is_active=True)
            .order_by('matricula', 'user__first_name', 'user__last_name')
        )
        for p in perfis:
            nome = (p.user.get_full_name() or p.user.username).strip()
            label = f"{nome} — {p.matricula}" if p.matricula else nome
            user_options.append({'id': p.user_id, 'label': label})
            if p.user_id == uid:
                user_nome = nome
    
    # Query base
    qs = Talao.objects.filter(
        status='FECHADO',
        iniciado_em__date__range=(de, ate),
        codigo_ocorrencia__descricao__icontains='Policiamento'
    )
    if uid:
        from django.db.models import Q
        qs = qs.filter(
            Q(criado_por_id=uid) | 
            Q(encarregado_id=uid) | 
            Q(motorista_id=uid) | 
            Q(auxiliar1_id=uid) | 
            Q(auxiliar2_id=uid)
        )
    
    total = qs.count()
    serie = list(
        qs.annotate(dia=TruncDate('iniciado_em')).values('dia').annotate(qtd=Count('id')).order_by('dia')
    )
    serie_js = [
        {'dia': (row.get('dia').strftime('%Y-%m-%d') if row.get('dia') else ''), 'qtd': int(row.get('qtd') or 0)}
        for row in serie
    ]
    
    abas = [('dia','Dia'), ('mes','Mês'), ('semestre','Semestre'), ('ano','Ano')]
    ctx = {
        'tab': tab,
        'de': de,
        'ate': ate,
        'uid': uid,
        'user_nome': user_nome,
        'user_options': user_options,
        'total': total,
        'serie_por_dia': mark_safe(json.dumps(serie_js)),
        'abas': abas,
    }
    return render(request, 'core/adm_estatisticas_policiamentos_graficos.html', ctx)
