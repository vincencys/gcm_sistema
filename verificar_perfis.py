from django.contrib.auth import get_user_model

User = get_user_model()

for username in ['comandante', 'subcomandante', 'administrativo']:
    try:
        user = User.objects.get(username=username)
        tem_perfil = hasattr(user, 'perfil')
        print(f'{username}: perfil={tem_perfil}')
        if tem_perfil:
            perfil = user.perfil
            tem_assinatura = bool(getattr(perfil, 'assinatura_digital', None))
            print(f'  - assinatura_digital: {tem_assinatura}')
    except User.DoesNotExist:
        print(f'{username}: não encontrado')