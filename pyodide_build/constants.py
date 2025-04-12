# Some reusable constants that are used at various sources in our code.
# TODO: collect and add more constants here.

BASE_IGNORED_REQUIREMENTS: list[str] = [
    # mesonpy installs patchelf in linux platform but we don't want it.
    "patchelf",
    "oldest-supported-numpy",
]
