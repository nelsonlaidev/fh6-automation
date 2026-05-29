$ErrorActionPreference = "Stop"

uv sync --group dev

uv run python -c @"
import re
from pathlib import Path
v = re.search(r'version\s*=\s*\"(.+?)\"', Path('pyproject.toml').read_text()).group(1)
p = (v.split('.') + ['0']*4)[:4]
Path('version_info.txt').write_text(f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers=({p[0]},{p[1]},{p[2]},{p[3]}),prodvers=({p[0]},{p[1]},{p[2]},{p[3]})),
  kids=[
    StringFileInfo([StringTable('040904B0',[
      StringStruct('FileDescription','FH6 Automation'),
      StringStruct('FileVersion','{v}'),
      StringStruct('ProductName','FH6 Automation'),
      StringStruct('ProductVersion','{v}'),
      StringStruct('CompanyName','nelsonlaidev'),
      StringStruct('LegalCopyright','AGPL-3.0'),
    ])]),
    VarFileInfo([VarStruct('Translation',[0x0409,1200])])
  ]
)''')
"@

uv run python -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --windowed `
  --name FH6Automation `
  --add-data "src/templates;templates" `
  --version-file version_info.txt `
  --paths src `
  src/main.py
