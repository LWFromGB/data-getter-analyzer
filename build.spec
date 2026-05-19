# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置 - 文件夹模式（启动快、打包快）
# 使用方法: pyinstaller build.spec

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'pandas',
        'numpy',
        'plotly',
        'plotly.express',
        'plotly.graph_objects',
        'plotly.subplots',
        'requests',
        'bs4',
        'lxml',
        'openpyxl',
        'app',
        'app.main_window',
        'app.modules',
        'app.modules.data_loader',
        'app.modules.crawler',
        'app.modules.cleaner',
        'app.modules.analyzer',
        'app.modules.visualizer',
        'app.modules.exporter',
        'app.modules.converter',
        'app.modules.merger',
        'app.logger',
        'pdfplumber',
        'docx',
        'app.plugins',
        'app.plugins.base_plugin',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'test'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='数据分析工具',
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='数据分析工具',
)
