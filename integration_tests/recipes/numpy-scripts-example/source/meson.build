project('numpy-scripts-example', 'c',
  version: '0.1.0',
  license: 'MIT',
  meson_version: '>= 1.3.0',
)

py_mod = import('python')
py3 = py_mod.find_installation()
py3_dep = py3.dependency()

# The only point of this recipe is to verify that NumPy's console scripts
# are discoverable on PATH when it is a build-time dependency.
f2py = find_program('f2py')
numpy_cflags = run_command('numpy-config', '--cflags', check: true).stdout().strip().split()

incdir_numpy = run_command(py3,
  ['-c', 'import numpy; print(numpy.get_include())'],
  check: true,
).stdout().strip()

py3.install_sources(['numpy_scripts_example/__init__.py'],
  pure: false,
  subdir: 'numpy_scripts_example')

py3.extension_module('_add',
  'numpy_scripts_example/_add.c',
  include_directories: incdir_numpy,
  c_args: numpy_cflags,
  dependencies: py3_dep,
  install: true,
  subdir: 'numpy_scripts_example',
)
