# -*- mode: python -*-
a = Analysis(['mlrawviewer.py'],
             pathex=['/Users/andrew/Projects/mlrawviewer'],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)
pyz = PYZ(a.pure)
a.datas += [('data/os.glf','data/os.glf','DATA')]
a.datas += [('data/icons.z','data/icons.z','DATA')]
a.binaries += [('ffmpeg', 'ffmpeg', 'DATA')]
a.binaries += [('libglfw3.dylib', 'libglfw3.dylib', 'DATA')]
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='mlrawviewer',
          debug=False,
          strip=None,
          upx=True,
          console=False )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=None,
               upx=True,
               name='mlrawviewer')
