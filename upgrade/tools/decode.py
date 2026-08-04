A=0x5DEECE6D; B=0x2FABF0B5; AINV=0x6F4E9B65; MOD=2176782336; SALT=0xA7
def dec36(s):
    if len(s)!=6: return -1
    v=0
    for c in s:
        if '0'<=c<='9': d=ord(c)-48
        elif 'A'<=c<='Z': d=ord(c)-65+10
        elif 'a'<=c<='z': d=ord(c)-97+10
        else: return -1
        v=v*36+d
    return v
def decode(s):
    """→ (layer, cycle) or None"""
    if s is None: return None
    s=s.strip()
    if len(s)>6: s=s[-6:]
    v=dec36(s)
    if v<0: return None
    tmp=(v+MOD-B)%MOD
    packed=(tmp*AINV)%MOD
    if (packed & 0xFF)!=SALT: return None
    layer=(packed>>22)&0x0F
    cycle=(packed>>8)&0x3FFF
    if layer<1 or layer>15: return None
    if cycle<1 or cycle>16383: return None
    return layer,cycle
