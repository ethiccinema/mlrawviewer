# -*- mode: python -*-
a = Analysis(['mlrawviewer.py'],
             pathex=['C:\\Projects\\mlrawviewer'],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)
for d in a.datas:
	if 'pyconfig' in d[0]:
		a.datas.remove(d)
		break
pyz = PYZ(a.pure)
a.datas += [('data/os.glf','data/os.glf','DATA')]
a.binaries += [('ffmpeg.exe', 'ffmpeg.exe', 'DATA')]
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='mlrawviewer.exe',
          debug=False,
          strip=None,
          upx=True,
          console=False, icon='mlrawviewer-logo.ico' )
