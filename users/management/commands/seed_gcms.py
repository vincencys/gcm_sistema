# users/management/commands/seed_gcms.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

DADOS = [
    ("3199","MARCELO"),("11953","PATRÍCIA"),("11951","ZARBOCH"),("3183","DINIZ"),
    ("11945","MOURA"),("9300","SALVETI"),("3063","CARVALHO"),("3064","MORAES"),
    ("9314","MARCOS"),("3181","APOLLO"),("3066","BORBA"),("11946","CALDAS"),
    ("11954","B.LUIZ"),("3190","CORREA"),("3068","CESAR"),("11947","CLAUDEILTON"),
    ("3193","CLAUDINEI"),("11962","VALLE"),("8530","CONCEIÇÃO"),("3071","BEKER"),
    ("9504","CRISTIANO"),("10677","MENEZES"),("6975","DANIEL SANTOS"),("3073","DANIEL"),
    ("10678","CARDOSO"),("3186","DANILO"),("10679","DENIS"),("11952","GOMES"),
    ("3200","DIEGO"),("10693","ROBERTO"),("6976","DOUGLAS"),("3075","ALVES"),
    ("11983","VICENTE"),("11949","MARTINS"),("3194","FABIO"),("3078","LOPES"),
    ("10681","FLAVIO"),("9313","VAZ"),("6979","MUNIER"),("11955","ANDRADE"),
    ("11327","DOMINGUES"),("3081","GRAZIELLY"),("3198","ISAIAS"),("10682","CALIXTO"),
    ("9606","JACOB"),("10691","DELMASSO"),("3085","EDUARDO"),("10683","LEITE"),
    ("10684","LUIS"),("9299","LEANDRO"),("3087","LUCIANO"),("3088","LUCIMARA"),
    ("9311","RAMALHO"),("9315","GIANCOLI"),("10686","CAROLINA"),("10687","MARLI"),
    ("9302","MERCEDES"),("11957","ANTONIO"),("10688","MOISES"),("3096","PEREIRA"),
    ("3195","OSLEY"),("6982","OLIVEIRA"),("10689","PRISCILLA"),("11960","PIMENTEL"),
    ("3192","RENATO"),("6983","RENATO FILHO"),("9316","MARREIRO"),("11961","RICARDO"),
    ("8531","STELLUTO"),("6984","XAVIER"),("11943","TRINDADE"),("3099","ROBISOM"),
    ("9312","RUBENS"),("9301","SAMUEL"),("11950","LEONARDO"),("9303","TACCONI"),
    ("10690","THAMY LUMA"),("11942","ARAUJO"),("8827","CRUZOLETO"),("10692","DA SILVA"),
    ("10694","BRAVO"),("3202","VALMIR"),("10695","SATURNINO"),("11944","VINICIUS"),
    ("6987","GONÇALVES"),("10696","WELLINGTON"),("3203","FERREIRA"),("7490","RENATA"),
]

class Command(BaseCommand):
    help = "Cria/atualiza usuários GCM: username=matrícula, senha=matrícula, first_name=nome."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-reset-passwords",
            action="store_true",
            help="Não redefinir senhas dos usuários já existentes."
        )

    def handle(self, *args, **options):
        User = get_user_model()
        reset_pw = not options["no_reset_passwords"]

        criados = 0
        atualizados = 0

        for matricula, nome in DADOS:
            # username = matrícula
            u, created = User.objects.get_or_create(username=str(matricula), defaults={
                "first_name": nome,
                "is_active": True,
            })
            if created:
                u.set_password(str(matricula))
                u.save()
                criados += 1
                self.stdout.write(self.style.SUCCESS(f"[create] {matricula} {nome}"))
            else:
                # atualiza nome e (opcionalmente) senha
                mudanca = False
                if u.first_name != nome:
                    u.first_name = nome
                    mudanca = True
                if reset_pw:
                    u.set_password(str(matricula))
                    mudanca = True
                if not u.is_active:
                    u.is_active = True
                    mudanca = True
                if mudanca:
                    u.save()
                    atualizados += 1
                    self.stdout.write(self.style.NOTICE(f"[update] {matricula} {nome}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Concluído. Criados: {criados} | Atualizados: {atualizados}"))
        if not reset_pw:
            self.stdout.write(self.style.WARNING("Senhas existentes foram mantidas (use sem --no-reset-passwords para resetar)."))
