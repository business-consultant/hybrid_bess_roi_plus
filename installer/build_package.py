"""
Script para construir el paquete distribuible de BESS Simulator.

Genera un directorio autocontenido en dist/bess-simulator/ con:
  - Python embebido (embed-amd64)
  - Todas las dependencias instaladas
  - Código fuente
  - Launcher .bat

Uso:
    python installer/build_package.py
"""
from __future__ import annotations

import io
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

PYTHON_VERSION = "3.11.9"
PYTHON_EMBED_URL = (
    f"https://www.python.org/ftp/python/{PYTHON_VERSION}/"
    f"python-{PYTHON_VERSION}-embed-amd64.zip"
)
PTH_FILENAME = f"python311._pth"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist" / "bess-simulator"
INSTALLER_DIR = ROOT / "installer"


def clean():
    if DIST.exists():
        print(f"Limpiando {DIST}...")
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)


def download_python_embed():
    python_dir = DIST / "python"
    python_dir.mkdir()
    print(f"Descargando Python {PYTHON_VERSION} embebido...")
    data, _ = urllib.request.urlretrieve(PYTHON_EMBED_URL)
    with zipfile.ZipFile(data) as zf:
        zf.extractall(python_dir)
    print(f"  -> Extraído en {python_dir}")

    pth_file = python_dir / PTH_FILENAME
    content = pth_file.read_text()
    content = content.replace("#import site", "import site")
    pth_file.write_text(content)
    print("  -> Habilitado import site en ._pth")
    return python_dir


def install_pip(python_dir: Path):
    python_exe = python_dir / "python.exe"
    print("Instalando pip...")
    get_pip = python_dir / "get-pip.py"
    urllib.request.urlretrieve(GET_PIP_URL, str(get_pip))
    subprocess.run(
        [str(python_exe), str(get_pip), "--no-warn-script-location"],
        check=True,
    )
    get_pip.unlink()
    print("  -> pip instalado")


def install_dependencies(python_dir: Path):
    python_exe = python_dir / "python.exe"
    req_file = INSTALLER_DIR / "requirements.txt"
    print("Instalando dependencias...")
    subprocess.run(
        [
            str(python_exe), "-m", "pip", "install",
            "-r", str(req_file),
            "--no-warn-script-location",
        ],
        check=True,
    )
    print("  -> Dependencias instaladas")


def copy_source():
    src_dest = DIST / "src"
    print("Copiando código fuente...")
    shutil.copytree(
        ROOT / "src",
        src_dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    print(f"  -> Copiado a {src_dest}")


def copy_launcher():
    print("Copiando launcher...")
    shutil.copy2(INSTALLER_DIR / "launch_bess.bat", DIST / "launch_bess.bat")
    print("  -> launch_bess.bat copiado")


def copy_streamlit_config():
    config_dir = DIST / ".streamlit"
    config_dir.mkdir(exist_ok=True)
    shutil.copy2(ROOT / ".streamlit" / "config.toml", config_dir / "config.toml")
    print("  -> .streamlit/config.toml copiado")


def create_pth_file():
    site_packages = DIST / "python" / "Lib" / "site-packages"
    pth_file = site_packages / "bess.pth"
    pth_file.write_text("../../../src\n")
    print("  -> bess.pth creado (agrega src/ al sys.path)")


def create_data_dir():
    (DIST / "data").mkdir(exist_ok=True)
    (DIST / "data" / "parquet").mkdir(exist_ok=True)


def main():
    print("=" * 60)
    print("  BESS Simulator — Build Package")
    print("=" * 60)

    clean()
    python_dir = download_python_embed()
    install_pip(python_dir)
    install_dependencies(python_dir)
    copy_source()
    copy_launcher()
    copy_streamlit_config()
    create_pth_file()
    create_data_dir()

    print()
    print("=" * 60)
    print(f"  Paquete generado en: {DIST}")
    print(f"  Ejecutar: {DIST / 'launch_bess.bat'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
