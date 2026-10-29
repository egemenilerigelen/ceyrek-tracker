# -*- mode: python ; coding: utf-8 -*-
# Derleme: python -m PyInstaller --noconfirm CeyrekTakip.spec
#
# PyInstaller'ın PySide6 hook'u yalnızca import edilen modülleri toplar; widget
# uygulamasının kullanmadığı Qt modülleri ve kütüphaneleri ayrıca dışarıda
# bırakılarak exe ~28 MB'ta tutulur.

EXCLUDES = [
    "PyQt5", "PyQt6", "tkinter", "unittest", "pydoc",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtMultimedia",
    "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtNetwork", "PySide6.QtOpenGL", "PySide6.QtSql", "PySide6.QtSvg",
]

# Qt eklentilerinin dolaylı olarak çektiği ama widget uygulamasının kullanmadığı
# kütüphaneler. opengl32sw.dll tek başına ~20 MB (yazılımsal OpenGL; raster
# çizim yapan bir QWidget uygulamasına gerekmez).
DROP_PATTERNS = (
    "opengl32sw.dll",
    "qt6quick", "qt6qml", "qt6pdf", "qt6opengl", "qt6network", "qt6virtualkeyboard",
    "imageformats\\qpdf", "platforminputcontexts", "qmltooling", "networkinformation",
    "\\tls\\", "translations\\",
)


def _keep(entry):
    name = entry[0].replace("/", "\\").lower()
    return not any(pattern in name for pattern in DROP_PATTERNS)


a = Analysis(
    ["main.py"],
    pathex=["src"],
    datas=[("src/ceyrek_tracker/assets", "ceyrek_tracker/assets")],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=1,
)
a.binaries = [b for b in a.binaries if _keep(b)]
a.datas = [d for d in a.datas if _keep(d)]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CeyrekTakip",
    icon="src/ceyrek_tracker/assets/icon.ico",
    debug=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
)
