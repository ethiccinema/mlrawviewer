pyinstaller mlrawviewer_win.spec
copy README dist\mlrawviewer\
move dist\mlrawviewer dist\MlRawViewer_1_4_2
cd dist
7z a MlRawViewer_1_4_2_win32.zip MlRawViewer_1_4_2
