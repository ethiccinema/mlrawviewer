pyinstaller mlrawviewer_win.spec
copy README dist\mlrawviewer\
move dist\mlrawviewer dist\MlRawViewer_1_4_3
cd dist
7z a MlRawViewer_1_4_3_win32.zip MlRawViewer_1_4_3
