pyinstaller mlrawviewer_win.spec
copy README dist\mlrawviewer\
move dist\mlrawviewer dist\MlRawViewer_1_4_1
cd dist
7z a MlRawViewer_1_4_1_win32.zip MlRawViewer_1_4_1
