import pathlib
p=pathlib.Path('c:/GCM_Sistema/bogcmi/views.py')
for i,l in enumerate(p.read_bytes().splitlines(keepends=True), start=1):
    if 60<=i<=90:
        specials=['TAB' if b'\t' in l else '', 'NBSP' if b'\xc2\xa0' in l else '']
        hex_bytes=' '.join(f'{b:02x}' for b in l)
        print(f'{i:03d}: {l.decode("utf-8","replace").rstrip()} || {" ".join(filter(None,specials))} || {hex_bytes}')
