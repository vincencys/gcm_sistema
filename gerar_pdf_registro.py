#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para gerar PDF de Registro na Biblioteca Nacional
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from datetime import datetime

# Ler o arquivo markdown
with open('REGISTRO_BN_DESCRICAO_TECNICA.md', 'r', encoding='utf-8') as f:
    conteudo = f.read()

# Criar PDF
pdf_file = 'REGISTRO_BN_DESCRICAO_TECNICA.pdf'
doc = SimpleDocTemplate(
    pdf_file,
    pagesize=A4,
    rightMargin=2*cm,
    leftMargin=2*cm,
    topMargin=2*cm,
    bottomMargin=2*cm
)

# Estilos
styles = getSampleStyleSheet()

# Estilo customizado para título
titulo_style = ParagraphStyle(
    'CustomTitle',
    parent=styles['Heading1'],
    fontSize=18,
    textColor=colors.HexColor('#1a237e'),
    spaceAfter=30,
    alignment=TA_CENTER,
    fontName='Helvetica-Bold'
)

# Estilo para subtítulo
subtitulo_style = ParagraphStyle(
    'CustomSubtitle',
    parent=styles['Heading2'],
    fontSize=14,
    textColor=colors.HexColor('#283593'),
    spaceAfter=12,
    spaceBefore=12,
    fontName='Helvetica-Bold'
)

# Estilo para seção
secao_style = ParagraphStyle(
    'CustomSection',
    parent=styles['Heading3'],
    fontSize=12,
    textColor=colors.HexColor('#3949ab'),
    spaceAfter=8,
    spaceBefore=8,
    fontName='Helvetica-Bold'
)

# Estilo para corpo de texto
corpo_style = ParagraphStyle(
    'CustomBody',
    parent=styles['BodyText'],
    fontSize=10,
    alignment=TA_JUSTIFY,
    spaceAfter=6,
    fontName='Helvetica'
)

# Estilo para código
codigo_style = ParagraphStyle(
    'CustomCode',
    parent=styles['Code'],
    fontSize=8,
    fontName='Courier',
    textColor=colors.HexColor('#37474f'),
    backColor=colors.HexColor('#eceff1'),
    leftIndent=10,
    rightIndent=10
)

# Lista de elementos para o PDF
story = []

# Processar conteudo markdown
linhas = conteudo.split('\n')
i = 0

while i < len(linhas):
    linha = linhas[i].strip()
    
    # Título principal (# )
    if linha.startswith('# ') and not linha.startswith('## '):
        texto = linha[2:].strip()
        story.append(Paragraph(texto, titulo_style))
        story.append(Spacer(1, 0.5*cm))
    
    # Subtítulo (## )
    elif linha.startswith('## ') and not linha.startswith('### '):
        texto = linha[3:].strip()
        story.append(Paragraph(texto, subtitulo_style))
        story.append(Spacer(1, 0.3*cm))
    
    # Seção (### )
    elif linha.startswith('### '):
        texto = linha[4:].strip()
        story.append(Paragraph(texto, secao_style))
        story.append(Spacer(1, 0.2*cm))
    
    # Linha horizontal (---)
    elif linha == '---':
        story.append(Spacer(1, 0.3*cm))
    
    # Bloco de código (```)
    elif linha.startswith('```'):
        codigo_linhas = []
        i += 1
        while i < len(linhas) and not linhas[i].strip().startswith('```'):
            codigo_linhas.append(linhas[i])
            i += 1
        
        codigo_texto = '<br/>'.join(codigo_linhas)
        if codigo_texto.strip():
            story.append(Paragraph(codigo_texto, codigo_style))
            story.append(Spacer(1, 0.3*cm))
    
    # Lista com marcador (- )
    elif linha.startswith('- '):
        texto = '• ' + linha[2:].strip()
        story.append(Paragraph(texto, corpo_style))
    
    # Lista numerada
    elif len(linha) > 2 and linha[0].isdigit() and linha[1] == '.':
        story.append(Paragraph(linha, corpo_style))
    
    # Texto em negrito (**texto**)
    elif '**' in linha:
        # Converter markdown bold para HTML bold
        texto = linha.replace('**', '<b>', 1).replace('**', '</b>', 1)
        # Continuar substituindo pares
        while '**' in texto:
            texto = texto.replace('**', '<b>', 1).replace('**', '</b>', 1)
        story.append(Paragraph(texto, corpo_style))
    
    # Parágrafo normal
    elif linha and not linha.startswith('#'):
        # Escapar caracteres especiais para XML
        texto = linha.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        # Restaurar tags HTML válidas
        texto = texto.replace('&lt;b&gt;', '<b>').replace('&lt;/b&gt;', '</b>')
        
        story.append(Paragraph(texto, corpo_style))
    
    # Linha vazia - adicionar espaço
    elif not linha:
        story.append(Spacer(1, 0.2*cm))
    
    i += 1

# Adicionar informações de rodapé na última página
story.append(PageBreak())
story.append(Paragraph('INFORMAÇÕES DO DOCUMENTO', titulo_style))
story.append(Spacer(1, 0.5*cm))

info_data = [
    ['Título:', 'SISTEMA INTELIGENTE PARA GCMS'],
    ['Tipo:', 'Programa de Computador / Design de Website'],
    ['Autor:', 'MOISES SANTOS DE OLIVEIRA'],
    ['Data de Elaboração:', '28 de novembro de 2025'],
    ['Protocolo BN:', '000984.038/187/2025'],
    ['Versão:', '1.0'],
    ['Páginas:', 'Consultar contador do PDF'],
]

table = Table(info_data, colWidths=[5*cm, 11*cm])
table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e3f2fd')),
    ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
    ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
    ('ALIGN', (1, 0), (1, -1), 'LEFT'),
    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
    ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
    ('FONTSIZE', (0, 0), (-1, -1), 10),
    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('PADDING', (0, 0), (-1, -1), 8),
]))

story.append(table)
story.append(Spacer(1, 1*cm))

# Assinatura
story.append(Paragraph('_' * 60, corpo_style))
story.append(Paragraph('Assinatura do Titular', corpo_style))
story.append(Spacer(1, 0.3*cm))
story.append(Paragraph('MOISES SANTOS DE OLIVEIRA', corpo_style))
story.append(Paragraph('CPF: ___________________________', corpo_style))

# Gerar PDF
print('Gerando PDF...')
doc.build(story)
print(f'PDF gerado com sucesso: {pdf_file}')
print(f'Tamanho: {round(os.path.getsize(pdf_file) / 1024, 2)} KB')
