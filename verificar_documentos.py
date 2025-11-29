from common.models import DocumentoAssinavel

docs = DocumentoAssinavel.objects.all().order_by('-created_at')
print(f'Total documentos: {docs.count()}')

if docs.exists():
    print('\nÚltimos documentos:')
    for doc in docs[:5]:
        print(f'- ID: {doc.id}')
        print(f'  Tipo: {doc.tipo}')
        print(f'  Status: {doc.status}')
        print(f'  Origem: {doc.usuario_origem.username}')
        print(f'  Arquivo: {doc.arquivo}')
        print(f'  Criado: {doc.created_at}')
        print('---')
else:
    print('Nenhum documento encontrado.')