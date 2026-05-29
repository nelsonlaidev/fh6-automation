$ErrorActionPreference = "Stop"

uv sync --group dev

$v = uv run python -c "import re; from pathlib import Path; print(re.search(r'version\s*=\s*\`"(.+?)\`"', Path('pyproject.toml').read_text()).group(1))"

uv run python -c @"
from pathlib import Path
v = '$v'
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
  --add-data "pyproject.toml;." `
  --version-file version_info.txt `
  --paths src `
  --exclude-module tkinter `
  --exclude-module PyQt5 `
  --exclude-module PyQt6 `
  src/main.py

iscc /DMyAppVersion="$v" installer.iss
