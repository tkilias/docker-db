import sys

def is_py3():
    """
    Return true if the current interpreter is python 3.
    """
    return sys.version_info > (3,0)

def is_str(val):
    """
    Checks if the given value is a string.
    """
    if is_py3():
        return type(val) in [str]
    else:
        return type(val) in [str, unicode]

def to_ustr(val):
    """
    Returns a unicode string.
    """
    if is_py3():
        return str(val)
    else:
        return unicode(val)

