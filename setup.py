from distutils.core import setup, Extension

module1 = Extension('bitunpack', sources = ["bitunpack.c"])

setup ( name = "bitunpack", version = 1.0, description = "Fast bit unpacking functions", ext_modules = [module1])


