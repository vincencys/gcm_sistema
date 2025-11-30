set -e

echo "[1/8] Entrando no diretório do app"
cd /home/ec2-user/gcm_sistema

echo "[2/8] Backups dos arquivos alvo"
cp bogcmi/models.py bogcmi/models.py.bak.$(date +%F-%H%M)
cp bogcmi/views_core.py bogcmi/views_core.py.bak.$(date +%F-%H%M)

echo "[3/8] Ajustando permissões temporárias no diretório bogcmi (se necessário)"
chmod u+w bogcmi || true

echo "[4/8] Inserindo método save() em VeiculoEnvolvido se ainda não existir"
python3 - <<'EOF_PY_SAVE'
import re, pathlib, sys
p = pathlib.Path("bogcmi/models.py")
txt = p.read_text(encoding="utf-8")
if "class VeiculoEnvolvido" not in txt:
    print("ERRO: Classe VeiculoEnvolvido não encontrada.")
    sys.exit(1)
if re.search(r"class VeiculoEnvolvido[\\s\\S]*?def save\\s*\\(", txt):
    print("Método save já existe – não modificado.")
    sys.exit(0)

pattern = re.compile(r"(class VeiculoEnvolvido[\\s\\S]*?:)(\\s*\\n)")
m = pattern.search(txt)
if not m:
    print("Não localizei início da classe.")
    sys.exit(1)

insercao = """
    def save(self, *args, **kwargs):
        import re
        try:
            if self.danos_identificados:
                parts = [p.strip() for p in str(self.danos_identificados).split(',') if p.strip()]
                norm = []
                for p in parts:
                    p = (p
                         .lower()
                         .replace('ç', 'c')
                         .replace('á','a').replace('à','a').replace('â','a').replace('ã','a')
                         .replace('é','e').replace('ê','e')
                         .replace('í','i')
                         .replace('ó','o').replace('ô','o').replace('õ','o')
                         .replace('ú','u')
                    )
                    p = re.sub(r'[^a-z0-9\\-\\s]', '', p)
                    p = re.sub(r'\\s+', '-', p).strip('-')
                    if p:
                        norm.append(p)
                self.danos_identificados = ','.join(norm)
        except Exception:
            self.danos_identificados = ''
        return super().save(*args, **kwargs)
"""
new_txt = txt[:m.end()] + insercao + txt[m.end():]
p.write_text(new_txt, encoding="utf-8")
print("Método save inserido.")
EOF_PY_SAVE

echo "[5/8] Patch em views_core.py: timeout=60, tratamento TimeoutExpired e traceback"
python3 - <<'EOF_PY_VIEWS'
import pathlib, re
p = pathlib.Path("bogcmi/views_core.py")
txt = p.read_text(encoding="utf-8")
orig = txt

# Reduz timeout de 90 para 60
txt = re.sub(r"(subprocess\\.run\\([^\\n]*timeout=)90", r"\\g<1>60", txt)

# Adiciona tratamento TimeoutExpired se não existir
if "TimeoutExpired" not in txt:
    pat = re.compile(r"try:\\n(\\s+res = subprocess\\.run[\\s\\S]*?)(\\n\\s+except Exception as e:)")
    m = pat.search(txt)
    if m:
        bloco = m.group(1)
        indent = re.findall(r"^(\\s+)", bloco, re.MULTILINE)[0]
        extra = f"\\n{indent}except subprocess.TimeoutExpired:\\n{indent}    logger.error(\"TIMEOUT (60s) - PDF muito complexo ou sistema lento\")\\n{indent}    raise"
        txt = txt.replace(m.group(0), "try:\n" + bloco + extra + m.group(2))

# Import traceback e log completo no despacho
if "bo_despachar_cmt" in txt and "traceback.format_exc()" not in txt:
    if "import traceback" not in txt:
        txt = re.sub(r"(import logging\\n)", r"\\1import traceback\n", txt, 1)
    txt = re.sub(r"(def bo_despachar_cmt[\\s\\S]*?except Exception as e:\\n)(\\s+logger\\.error\\([^\n]*\\))",
                 r"\\1\\2\n\\g<1>    logger.error(\"TRACEBACK:\\n%s\", traceback.format_exc())", txt)
    if "Verifique o log bo_pdf_debug.log" not in txt:
        txt = re.sub(r"messages\\.error\\(request, \"[^\"]+\"\\)",
                     "messages.error(request, \"O documento foi salvo, mas não pôde ser despachado. Verifique o log bo_pdf_debug.log.\")",
                     txt)

if txt != orig:
    p.write_text(txt, encoding="utf-8")
    print("views_core.py atualizado.")
else:
    print("Nenhuma mudança aplicada (já estava patchado?).")
EOF_PY_VIEWS

echo "[6/8] Ajustando service para WKHTMLTOPDF_PATH real (/usr/bin/wkhtmltopdf) se distinto"
sudo sed -i 's|WKHTMLTOPDF_PATH=/usr/local/bin/wkhtmltopdf|WKHTMLTOPDF_PATH=/usr/bin/wkhtmltopdf|' /etc/systemd/system/gunicorn-gcm.service
sudo systemctl daemon-reload

echo "[7/8] Reiniciando serviços"
sudo systemctl restart gunicorn-gcm
sudo systemctl restart daphne-gcm

echo "[8/8] Verificando status"
sudo systemctl status gunicorn-gcm --no-pager -n 20 || true

echo "OK: Patch concluído. Teste no app e monitore:"
echo "tail -f /home/ec2-user/gcm_sistema/media/logs/bo_pdf_debug.log"
