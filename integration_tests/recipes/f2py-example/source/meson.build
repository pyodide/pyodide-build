project('f2py-example', 'c',
  version: '0.1.0',
  license: 'MIT',
  meson_version: '>= 1.3.0',
  default_options: [
    'buildtype=debugoptimized',
    'c_args=-Wno-unused-function -Wno-conversion -Wno-misleading-indentation -Wno-incompatible-pointer-types',
    'fortran_args=-Wno-conversion',
    'fortran_std=legacy',
  ],
)

add_languages('fortran', native: false)

py_mod = import('python')
py3 = py_mod.find_installation()
py3_dep = py3.dependency()

numpy_cflags = run_command('numpy-config', '--cflags', check: true).stdout().strip().split()

f2py = find_program('f2py')

incdir_f2py = run_command(py3,
  ['-c', 'from numpy import f2py; print(f2py.get_include())'],
  check: true
).stdout().strip()

fib_source = custom_target('fibmodule.c',
  input: ['src/fibonacci.f'],
  output: ['fibmodule.c', 'fib-f2pywrappers.f'],
  command: [f2py, '@INPUT@', '-m', 'fib', '--lower']
)

inc_dirs = include_directories(incdir_f2py)

py3.install_sources(['f2py_example/__init__.py'],
  pure: false,
  subdir: 'f2py_example')

py3.extension_module('fib',
  ['src/fibonacci.f', fib_source],
  incdir_f2py / 'fortranobject.c',
  include_directories: inc_dirs,
  c_args: numpy_cflags,
  dependencies: py3_dep,
  install: true,
  subdir: 'f2py_example',
)
