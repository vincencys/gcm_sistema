"""
Views para funcionalidades de IA
"""
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
import json
from .ai_service import RelatorioAIService


@login_required
@require_http_methods(["POST"])
def melhorar_relatorio_ai(request):
    """
    Endpoint para corrigir texto do relatório usando IA
    """
    try:
        data = json.loads(request.body)
        texto_original = data.get('texto', '').strip()
        
        if not texto_original:
            return JsonResponse({
                'sucesso': False,
                'erro': 'Texto não fornecido'
            }, status=400)
        
        # Usar serviço de IA para corrigir
        ai_service = RelatorioAIService()
        texto_corrigido = ai_service.corrigir_relatorio(texto_original)
        
        return JsonResponse({
            'sucesso': True,
            'texto_melhorado': texto_corrigido
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'sucesso': False,
            'erro': 'JSON inválido'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'sucesso': False,
            'erro': f'Erro interno: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def sugerir_relatorio_ai(request):
    """
    Endpoint para sugerir texto de relatório
    """
    try:
        data = json.loads(request.body)
        texto_base = data.get('texto', '').strip()
        
        # Usar serviço de IA para sugerir
        ai_service = RelatorioAIService()
        texto_sugerido = ai_service.sugerir_relatorio(texto_base)
        
        return JsonResponse({
            'sucesso': True,
            'texto_melhorado': texto_sugerido
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'sucesso': False,
            'erro': 'JSON inválido'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'sucesso': False,
            'erro': f'Erro interno: {str(e)}'
        }, status=500)