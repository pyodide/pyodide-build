#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <numpy/arrayobject.h>

static PyObject *
add(PyObject *self, PyObject *args)
{
    double a, b;
    if (!PyArg_ParseTuple(args, "dd", &a, &b))
        return NULL;
    return PyFloat_FromDouble(a + b);
}

static PyMethodDef methods[] = {
    {"add", add, METH_VARARGS, "Add two floats."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT, "_add", NULL, -1, methods
};

PyMODINIT_FUNC
PyInit__add(void)
{
    import_array();
    return PyModule_Create(&module);
}
