rm -rf dist/*
#pyinstaller --log-level=DEBUG mlrawviewer.spec
pyinstaller mlrawviewer.spec
cp Info.plist dist/mlrawviewer.app/Contents/
cp mlrawviewer.icns dist/mlrawviewer.app/Contents/Resources/icon-windowed.icns
rm -rf macdmg
rm *.dmg
mkdir macdmg
mv dist/mlrawviewer.app macdmg/MlRawViewer.app
cp README macdmg/
hdiutil create -srcfolder "macdmg" -volname "MlRawViewer" -fs HFS+ -fsargs "-c c=64,a=16,e=16" -format UDRW -size 20000k mlrawviewer.temp.dmg
hdiutil convert "mlrawviewer.temp.dmg" -format UDZO -imagekey zlib-level=9 -o "MlRawViewer_1_1_3"

