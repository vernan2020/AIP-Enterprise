"""Personal provider credentials, stored outside the repository with private permissions."""
import json
import os
import tempfile
from pathlib import Path


def path():
    return Path(os.getenv('TICOTRADER_CONNECTIONS_FILE',str(Path.home()/'.config'/'ticotrader'/'connections.json')))


def read():
    file=path()
    if not file.exists(): return {}
    return json.loads(file.read_text(encoding='utf-8'))


def write(token,email,name):
    file=path(); file.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    payload={'bccr_token':token,'bccr_email':email,'bccr_name':name}
    fd,tmp=tempfile.mkstemp(dir=file.parent,prefix='.connections-')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(payload,stream); stream.flush(); os.fsync(stream.fileno())
        os.replace(tmp,file)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def status():
    saved=read()
    return {'bccr_token_configured':bool(saved.get('bccr_token') or os.getenv('TICOTRADER_BCCR_TOKEN') or os.getenv('AIP_BCCR_TOKEN')),
            'sugef':'API pública; no requiere token personal',
            'note':'Credencial configurada no implica conexión verificada. Actualice BCCR para comprobarla.'}


def redact(value):
    if isinstance(value,dict): return {k:redact(v) for k,v in value.items()}
    if isinstance(value,list): return [redact(v) for v in value]
    if not isinstance(value,str): return value
    saved=read()
    for secret in (saved.get('bccr_token'),os.getenv('TICOTRADER_BCCR_TOKEN'),os.getenv('AIP_BCCR_TOKEN')):
        if secret: value=value.replace(secret,'[CREDENCIAL OCULTA]')
    return value
