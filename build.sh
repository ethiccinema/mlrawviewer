#!/bin/sh

# clean up
rm -rf build

# compile icons
cd tools
./generateIconFile.py
cd ..

# build & run
python setup.py build
cp build/lib.linux-x86_64-2.7/bitunpack.so bitunpack.so
./mlrawviewer.py
