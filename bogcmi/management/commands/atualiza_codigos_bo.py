from django.core.management.base import BaseCommand
from bogcmi.models import BO

class Command(BaseCommand):
    help = "Preenche cod_natureza para BOs antigos que tenham natureza no formato 'SIGLA - Descrição' e cod_natureza em branco."

    def handle(self, *args, **options):
        total = 0
        atualizados = 0
        for bo in BO.objects.filter(cod_natureza=''):
            total += 1
            if bo.natureza and ' - ' in bo.natureza:
                sigla = bo.natureza.split(' - ', 1)[0].strip()
                if sigla:
                    bo.cod_natureza = sigla
                    bo.save(update_fields=['cod_natureza'])
                    atualizados += 1
        self.stdout.write(self.style.SUCCESS(f"BOs verificados: {total} | Atualizados: {atualizados}"))
