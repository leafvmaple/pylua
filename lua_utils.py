# lua_utils.py

# converts an integer to a "floating point byte", represented as
# (eeeeexxx), where the real value is (1xxx) * 2^(eeeee - 1) if
# eeeee != 0 and (xxx) otherwise.


def int_to_fb(i: int) -> int:
    '''Converts an integer to a "floating point byte".'''
    if i < 8:
        return i
    e = 0
    while i >= 16:
        i = (i + 1) >> 1
        e += 1
    return ((e + 1) << 3) | (i - 8)


def fb_to_int(fb: int) -> int:
    '''Converts a "floating point byte" to an integer.'''
    if fb < 8:
        return fb
    else:
        return ((fb & 0x7) + 8) << ((fb >> 3) - 1)
