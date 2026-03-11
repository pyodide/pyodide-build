"""This is the module-level docstring.

It spans multiple lines and should be removed.
"""

import os

# A regular comment — should be preserved.
VERSION = "1.0.0"


def greet(name: str) -> str:
    """Return a greeting for *name*."""
    return f"Hello, {name}!"


def no_docstring():
    # This function has no docstring.
    return 42


class Example:
    """Example class docstring."""

    class_var = "keep me"

    def method(self):
        """Method docstring."""
        return self.class_var

    async def async_method(self):
        """Async method docstring."""
        return True


class NoDocstring:
    pass


def multiline():
    """
    This is a triple-single-quoted
    multi-line docstring.
    """
    x = 1
    return x
