import os
import sys

from clang.cindex import Index
from persistence import load_components


def fully_qualified(child, path):
    if child.location.file is None:
        return ""
    elif child.location.file.name != path:
        return ""
    else:
        res = fully_qualified(child.semantic_parent, path)
        if res != "":
            return res + "::" + child.spelling
    return child.spelling


def find_symbol(path, root):
    symbol = []
    index = Index.create()
    header = os.path.join(root, "rte", "rtebase", "include")
    args_list = ["-x", "c++",
                 "-I" + root, "-I" + header]
    tu = index.parse(path, args_list)
    decl_kinds = [
        "FUNCTION_DECL",
        "CXX_METHOD",
        "CONSTRUCTOR",
        "CONVERSION_FUNCTION"
    ]
    for child in tu.cursor.walk_preorder():
        if child.location.file is not None and child.location.file.name == path:
            # text = child.spelling or child.displayname
            kind = str(child.kind)[str(child.kind).index('.') + 1:]
            if kind in decl_kinds:
                symbol.append(fully_qualified(child, path))
    return symbol


def best_matched(path):
    components = load_components()
    if path in components:
        com = components[path]
    else:
        while True:
            slash = "\\" if sys.platform == "win32" else "/"
            path = path[:path.rindex(slash)]
            if path in components:
                com = components[path]
                break
    return com


def update_symbols(path, symbols):
    # get file path and root
    file_path, root = path
    extension = os.path.splitext(file_path)
    if extension[-1] in [".h", ".hpp"]:
        symbol_set = set(find_symbol(file_path, root))
        for symbol in symbol_set:
            symbols[symbol] = best_matched(file_path)


__all__ = [
    "find_symbol",
    "best_matched",
    "update_symbols"
]
