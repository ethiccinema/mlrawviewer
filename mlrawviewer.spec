# -*- mode: python -*-
a = Analysis(['mlrawviewer.py'],
             pathex=['/Users/admin/Projects/mlrawviewer'],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)
pyz = PYZ(a.pure)
a.datas += [('data/os.glf','data/os.glf','DATA')]
a.binaries += [('ffmpeg', 'ffmpeg', 'DATA')]
a.binaries += [('libglfw3.dylib', 'libglfw3.dylib', 'DATA')]
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='mlrawviewer',
          debug=False,
          strip=None,
          upx=True,
          console=False )
app = BUNDLE(exe,
             name='mlrawviewer.app',
             icon=None)
