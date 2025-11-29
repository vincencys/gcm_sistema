"""Script de teste para verificar se a marca d'água funciona corretamente."""
import os
import sys

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gcm_project.settings')
import django
django.setup()

from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import Color

try:
    from PyPDF2 import PdfReader, PdfWriter
    print("✅ PyPDF2 importado com sucesso")
except ImportError:
    try:
        from pypdf import PdfReader, PdfWriter
        print("✅ pypdf importado com sucesso")
    except ImportError:
        print("❌ ERRO: PyPDF2/pypdf não instalado")
        sys.exit(1)

# Criar um PDF simples de teste
print("\n1. Criando PDF de teste...")
test_buffer = BytesIO()
test_canvas = canvas.Canvas(test_buffer, pagesize=A4)
test_canvas.setFont("Helvetica", 12)
test_canvas.drawString(100, 750, "Este é um documento de teste")
test_canvas.drawString(100, 730, "Para verificar a aplicação de marca d'água")
test_canvas.showPage()
test_canvas.drawString(100, 750, "Segunda página do documento de teste")
test_canvas.showPage()
test_canvas.save()
test_pdf_bytes = test_buffer.getvalue()
print(f"✅ PDF de teste criado ({len(test_pdf_bytes)} bytes)")

# Criar marca d'água
print("\n2. Criando marca d'água...")
watermark_buffer = BytesIO()
watermark_canvas = canvas.Canvas(watermark_buffer, pagesize=A4)
width, height = A4

watermark_canvas.setFont("Helvetica-Bold", 70)
watermark_canvas.setFillColor(Color(0.85, 0.85, 0.85, alpha=0.5))

watermark_canvas.saveState()
watermark_canvas.translate(width/2, height/2)
watermark_canvas.rotate(45)

text = "APENAS CONSULTIVO"
text_width = watermark_canvas.stringWidth(text, "Helvetica-Bold", 70)
watermark_canvas.drawString(-text_width/2, 0, text)

watermark_canvas.restoreState()
watermark_canvas.save()

watermark_buffer.seek(0)
print(f"✅ Marca d'água criada ({len(watermark_buffer.getvalue())} bytes)")

# Aplicar marca d'água
print("\n3. Aplicando marca d'água no PDF...")
pdf_reader = PdfReader(BytesIO(test_pdf_bytes))
pdf_writer = PdfWriter()
num_pages = len(pdf_reader.pages)
print(f"   PDF tem {num_pages} páginas")

watermark_buffer.seek(0)
watermark_pdf = PdfReader(watermark_buffer)
watermark_page = watermark_pdf.pages[0]

for i, page in enumerate(pdf_reader.pages):
    page.merge_page(watermark_page)
    pdf_writer.add_page(page)
    print(f"   ✅ Marca d'água aplicada na página {i+1}/{num_pages}")

output_buffer = BytesIO()
pdf_writer.write(output_buffer)
output_buffer.seek(0)
result_bytes = output_buffer.getvalue()

print(f"\n✅ PDF final gerado com marca d'água ({len(result_bytes)} bytes)")

# Salvar PDF de teste
output_path = os.path.join(os.path.dirname(__file__), 'teste_marca_dagua.pdf')
with open(output_path, 'wb') as f:
    f.write(result_bytes)

print(f"\n✅ PDF de teste salvo em: {output_path}")
print("\n🎉 Teste concluído com sucesso!")
print("   Abra o arquivo teste_marca_dagua.pdf para verificar a marca d'água")
