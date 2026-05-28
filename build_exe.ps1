$ErrorActionPreference = "Stop"

uv sync --group dev

uv run python -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --windowed `
  --name FH6Automation `
  --add-data "src/templates;templates" `
  --paths src `
  src/main.py
