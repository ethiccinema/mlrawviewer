from distutils.core import setup, Extension

module1 = Extension('bitunpack', sources = ["bitunpack.c","amaze_demosaic_RT.c"],  extra_compile_args=['-fopenmp','-msse2'], extra_link_args=['-fopenmp'])


setup ( name = "bitunpack", version = 1.0, description = "Fast bit unpacking functions", ext_modules = [module1])


