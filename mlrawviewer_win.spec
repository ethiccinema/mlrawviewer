# -*- mode: python -*-
a = Analysis(['mlrawviewer.py'],
             pathex=[''],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)
for d in a.datas:
	if 'pyconfig' in d[0]:
		a.datas.remove(d)
		break
pyz = PYZ(a.pure)
a.datas += [('data/os.glf','data/os.glf','DATA')]
a.datas += [('data/icons.z','data/icons.z','DATA')]
a.binaries += [('ffmpeg.exe', 'ffmpeg.exe', 'DATA')]
a.binaries += [('glfw3.dll', 'glfw3.dll', 'DATA')]
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='mlrawviewer.exe',
          debug=False,
          strip=None,
          upx=True,
          console=False, icon='mlrawviewer-logo.ico' )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=None,
               upx=True,
               name='mlrawviewer')
