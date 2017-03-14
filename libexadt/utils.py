#! /usr/bin/env python2.7

import re, base64, string, random

#{{{ Units to bytes

def units2bytes(data):
    ma_units = units2bytes.re_parse.match(str(data))
    if not ma_units: raise RuntimeError('Could not parse %s as number with units.' % repr(data))
    num1, num2, unit, two = ma_units.groups()
    num1 = num1.strip().replace(' ', '')
    if unit is not None: unit = unit.lower()
    if num2 is None: num = int(num1)
    else: num = float("%s.%s" % (num1, num2.strip()))
    if two is None:
        return num * units2bytes.convd[unit]
    return num * units2bytes.convb[unit]
units2bytes.re_parse = re.compile(r'^\s*([0-9]+)(?:[.]([0-9]+))?\s*(?:([KkMmGgTtPpEeZzYy])(i)?)?[Bb]?\s*$')
units2bytes.convf = lambda x: {'k': x ** 1, 'm': x ** 2, 'g': x ** 3, 't': x ** 4, 'p': x ** 5, 'e': x ** 6, 'z': x ** 7, 'y': x ** 8, None: 1}
units2bytes.convd = units2bytes.convf(1000)
units2bytes.convb = units2bytes.convf(1024)

#}}}

#{{{ Bytes to units
def bytes2units(num):
    for x in ['B', 'KiB', 'MiB', 'GiB', 'TiB']:
        if num < 1024.0:
            return "%3.1f %s" % (num, x)
        num /= 1024.0
#}}}
 
#{{{ Gen passwd
def gen_passwd(length):
    """
    Generates a new password with given length.
    """
    key = ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(length))
    return key
#}}}
 
#{{{ Gen base64 passwd
def gen_base64_passwd(length):
    """
    Generates a base64 encoded password with given length.
    """
    return base64.b64encode(gen_passwd(length))
#}}}
