pyinstaller --onedir dialogs.py
copy /Y dist\dialogs\dialogs.exe .
pyinstaller mlrawviewer_win.spec
copy README dist\mlrawviewer\
move dist\mlrawviewer dist\MlRawViewer_1_3_1
cd dist
7z a MlRawViewer_1_3_0_win32.zip MlRawViewer_1_3_1
