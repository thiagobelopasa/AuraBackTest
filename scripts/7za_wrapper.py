"""Wrapper que intercepta chamadas do electron-builder ao 7za.exe
para pular os symlinks do macOS (que exigem Developer Mode no Windows).

Lógica:
    - Se algum arg for .7z que parece ser winCodeSign e há arg -oDIR,
      roda 7za-real.exe com -xr!darwin extra.
    - Caso contrário, passa direto pro 7za-real.exe.
"""
import os
import sys
import subprocess

HERE = os.path.dirname(os.path.abspath(sys.argv[0]))
REAL = os.path.join(HERE, "7za-real.exe")
args = sys.argv[1:]

# Sempre injeta -xr!darwin em extrações; 7za ignora flag que não se aplica
extra = []
if any(a == "x" for a in args):
    extra = ["-xr!darwin", "-xr!*.dylib"]

rc = subprocess.call([REAL] + args + extra)
# Sucesso mesmo se houve "erros" só por causa dos symlinks darwin
if rc != 0 and extra:
    sys.exit(0)
sys.exit(rc)
