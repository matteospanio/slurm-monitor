# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the SlurmHub desktop GUI (one-dir build).

Bundles the package's data files (the QSS theme) and the entire Alembic
migration tree (loaded at runtime by file path, so it must ship as data, not
just as importable modules), plus the QtCharts add-on used by the History
screen. Build with:  pyinstaller slurmhub.spec
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

import slurmhub

_pkg_dir = Path(slurmhub.__file__).parent

# Non-Python data files under the package (e.g. qt/resources/theme.qss,
# db/alembic.ini) plus qtawesome's bundled icon fonts.
datas = collect_data_files("slurmhub") + collect_data_files("qtawesome")

# The Alembic migration scripts are imported dynamically by file path at
# startup, so ship the whole versions/ tree as data alongside env.py.
alembic_dir = _pkg_dir / "db" / "alembic"
datas += [
    (str(p), str(Path("slurmhub/db/alembic") / p.relative_to(alembic_dir).parent))
    for p in alembic_dir.rglob("*.py")
]

hiddenimports = (
    collect_submodules("slurmhub.db.alembic.versions")
    + ["PySide6.QtCharts"]
)

block_cipher = None

a = Analysis(
    ["packaging/slurmhub_app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="slurmhub",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI app — no console window on Windows/macOS
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="slurmhub",
)
