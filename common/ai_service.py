"""
Serviço de IA para assistência em relatórios
"""
import requests
from django.conf import settings
from typing import Optional
import json


class RelatorioAIService:
    """Serviço para melhorar relatórios usando IA gratuita"""
    
    def __init__(self):
        self.groq_api_key = getattr(settings, 'GROQ_API_KEY', None)
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
    
    def melhorar_relatorio(self, texto_original: str) -> dict:
        """
        Melhora o texto do relatório usando IA
        
        Args:
            texto_original: Texto original do relatório
            
        Returns:
            dict: {'sucesso': bool, 'texto_melhorado': str, 'erro': str}
        """
        if not texto_original or not texto_original.strip():
            return {
                'sucesso': False,
                'erro': 'Texto vazio ou inválido'
            }
        
        # Se não há API key, usar versão offline
        if not self.groq_api_key:
            return self._melhorar_offline(texto_original)
        
        try:
            return self._melhorar_groq(texto_original)
        except Exception as e:
            # Fallback para versão offline
            return self._melhorar_offline(texto_original)
    
    def _melhorar_groq(self, texto: str) -> dict:
        """Usa API do Groq para melhorar o texto"""
        prompt = f"""
        Você é um assistente especializado em relatórios da Guarda Civil Municipal brasileira.
        
        INSTRUÇÕES:
        - Corrija gramática, ortografia e pontuação
        - Use linguagem formal e técnica apropriada
        - Mantenha TODAS as informações originais
        - Melhore a clareza e organização
        - Use termos técnicos policiais quando apropriado
        - Mantenha a objetividade e concisão
        
        TEXTO ORIGINAL:
        {texto}
        
        RESPONDA APENAS COM O TEXTO MELHORADO:
        """
        
        headers = {
            'Authorization': f'Bearer {self.groq_api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': 'llama-3.1-70b-versatile',
            'messages': [
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': 0.3,
            'max_tokens': 1000
        }
        
        response = requests.post(
            self.base_url,
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            texto_melhorado = result['choices'][0]['message']['content'].strip()
            return {
                'sucesso': True,
                'texto_melhorado': texto_melhorado
            }
        else:
            return {
                'sucesso': False,
                'erro': f'Erro da API: {response.status_code}'
            }
    
    def _melhorar_offline(self, texto: str) -> dict:
        """Versão offline aprimorada: corrige acentuação, pontuação, capitalização e linguagem técnica"""
        import re
        melhorado = texto.strip()
        # Corrigir erros comuns de digitação e acentuação
        padroes = [
            (r'plantao', 'plantão'),
            (r'patrulhaento', 'patrulhamento'),
            (r'patrulhamanto', 'patrulhamento'),
            (r'patrulhamenento', 'patrulhamento'),
            (r' relatorio', ' relatório'),
            (r'ocorrencia', 'ocorrência'),
            (r'municipes', 'munícipes'),
            (r'nao', 'não'),
            (r'sao', 'são'),
            (r'estao', 'estão'),
            (r'esta ', 'está '),
            (r' voce ', ' você '),
            (r' tem ', ' têm '),
            (r' vem ', ' vêm '),
            (r' ok ', ' conforme '),
            (r' beleza ', ' adequadamente '),
            (r' sem problemas', ' sem intercorrências'),
            (r' tudo normal', ' atividades transcorreram normalmente'),
            (r' nada a relatar', ' nada mais há a relatar'),
            (r' nada mais a relatar', ' nada mais há a relatar'),
        ]
        for padrao, sub in padroes:
            melhorado = re.sub(padrao, sub, melhorado, flags=re.IGNORECASE)

        # Corrigir pontuação duplicada
        melhorado = re.sub(r'\.{2,}', '.', melhorado)
        melhorado = re.sub(r'\s+,', ',', melhorado)
        melhorado = re.sub(r'\s+\.', '.', melhorado)
        melhorado = re.sub(r'\s+', ' ', melhorado)

        # Capitalizar início e após ponto
        frases = re.split(r'([.!?])', melhorado)
        resultado = ''
        for i in range(0, len(frases)-1, 2):
            frase = frases[i].strip()
            pont = frases[i+1]
            if frase:
                frase = frase[0].upper() + frase[1:]
                resultado += frase + pont + ' '
        resultado = resultado.strip()

        # Garantir ponto final
        if resultado and not resultado.endswith(('.', '!', '?')):
            resultado += '.'

        # Melhorias de linguagem técnica
        if 'patrulhamento' in resultado and 'intercorrência' not in resultado:
            resultado += ' Atividades transcorreram normalmente sem intercorrências.'

        return {
            'sucesso': True,
            'texto_melhorado': resultado,
            'modo': 'offline'
        }
    
    def gerar_sugestoes(self, taloes_data: list) -> str:
        """Gera sugestões de relatório baseado nos talões"""
        if not taloes_data:
            return "Nenhuma ocorrência registrada no período."
        
        # Análise básica
        total_taloes = len(taloes_data)
        tipos_ocorrencia = {}
        
        for talao in taloes_data:
            tipo = getattr(talao, 'codigo_ocorrencia', None)
            if tipo:
                nome_tipo = str(tipo)
                tipos_ocorrencia[nome_tipo] = tipos_ocorrencia.get(nome_tipo, 0) + 1
        
        # Gerar sugestão
        sugestao = f"Durante o plantão foram registrados {total_taloes} talões de ocorrência"
        
        if tipos_ocorrencia:
            mais_comum = max(tipos_ocorrencia.items(), key=lambda x: x[1])
            sugestao += f", sendo {mais_comum[1]} relacionados a {mais_comum[0]}"
        
        sugestao += ". O patrulhamento transcorreu sem maiores intercorrências."
        
        return sugestao
    
    def corrigir_relatorio(self, texto_original: str) -> str:
        """
        Corrige gramática e linguagem do relatório
        
        Args:
            texto_original: Texto original do relatório
            
        Returns:
            str: Texto corrigido
        """
        resultado = self.melhorar_relatorio(texto_original)
        if resultado.get('sucesso'):
            return resultado.get('texto_melhorado', texto_original)
        return texto_original
    
    def sugerir_relatorio(self, texto_base: str = "") -> str:
        """
        Sugere um relatório baseado no texto fornecido ou cria um novo
        
        Args:
            texto_base: Texto base para sugestão (opcional)
            
        Returns:
            str: Texto sugerido ou melhorado
        """
        if not texto_base or not texto_base.strip():
            # Se não há texto base, retornar um template básico
            return "Durante o plantão não foram registradas ocorrências de relevância. As atividades transcorreram normalmente sem intercorrências."
        
        # Se há texto base, melhorá-lo
        return self.corrigir_relatorio(texto_base)