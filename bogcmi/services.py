from django.db import transaction
from django.utils import timezone
from .models import SequenciaBO, BO

def proximo_numero_bo():
    """Retorna o próximo número de BO para o ano corrente no formato 'N-YYYY'.

    Nova lógica:
      - Reutiliza lacunas (gaps). Se existir uma sequência 1,2,4, devolve 3.
      - Se não existir nenhum BO no ano, devolve 1-YYYY.
      - Mantém registro em SequenciaBO apenas como referência do maior já utilizado
        (atualiza para o max vigente após atribuir a lacuna).
    Justificativa: permitir que, ao apagar o único BO (ex: 1-2025), o próximo volte a ser 1-2025.
    Obs.: Em cenários de alta concorrência, duas criações simultâneas poderiam tentar a mesma lacuna.
          Para mitigar, usamos transação + select_for_update na linha da sequência; em SQLite é
          suficiente na maioria dos casos. Em Postgres, poderíamos também usar um advisory lock
          ou "FOR UPDATE" sobre consulta dos BOs, mas aqui mantemos simples.
    """
    ano = timezone.now().year
    with transaction.atomic():
        # Lock/garante existência do registro de sequência
        seq, _ = SequenciaBO.objects.select_for_update().get_or_create(ano=ano)

        # Coleta todos os números existentes daquele ano
        existentes = BO.objects.filter(numero__endswith=f'-{ano}')\
            .values_list('numero', flat=True)
        usados = set()
        for num in existentes:
            # Formato esperado X-YYYY
            try:
                parte = num.split('-')[0]
                if parte.isdigit():
                    usados.add(int(parte))
            except Exception:
                continue

        # Encontra menor inteiro positivo não utilizado
        candidato = 1
        while candidato in usados:
            candidato += 1

        # Atualiza o valor máximo registrado (não quebrando possível relatório que usa SequenciaBO)
        max_util = max(usados | {candidato}) if usados else candidato
        if seq.valor != max_util:
            seq.valor = max_util
            seq.save(update_fields=['valor'])

        return f"{candidato}-{ano}"
