"""Launch without desktop Qt or any AIP private-session command files."""
import os
from pathlib import Path
import sys

root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'src')]
config=root/'ticotrader_web'/'.env'
if config.exists():
    for line in config.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#'): continue
        key,sep,value=line.partition('=')
        if sep: os.environ.setdefault(key.strip(),value.strip().strip("'\""))
os.environ.setdefault('AIP_EXECUTION_MODE','CONFIGURED')
if __name__=='__main__':
    import uvicorn
    uvicorn.run('ticotrader_web.app:app',host=os.getenv('TICOTRADER_BIND','127.0.0.1'),port=int(os.getenv('PORT','8080')),workers=1)
