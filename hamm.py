#!/usr/bin/env python

import sys
from itertools import izip_longest
#from bitarray import bitarray
#def hamming(a, b):
#    return (a ^ b).count()
#pkts = [bitarray(p.strip()) for p in sys.stdin.readlines()]

def hamming(a,b):
    dist=0
    for b1,b2 in izip_longest(a,b,fillvalue=None):
        if b1!=b2: dist+=1
    return dist

def descartes(items, fn):
    if len(items)<2: return []
    res = [(fn(items[0],item), items[0], item) for item in items[1:]]
    res.extend(descartes(items[1:],fn))
    return res

def diff(a,b):
    for i, (c, p) in enumerate(zip(a, b)):
        if c == p:
            sys.stdout.write(c)
        else:
            vbits[i] = 1
            sys.stdout.write("\x1b[31m%s\x1b[0m" % c)
    print

def split_by_n( seq, n ):
    """A generator to divide a sequence into chunks of n units.
       src: http://stackoverflow.com/questions/9475241/split-python-string-every-nth-character"""
    while seq:
        yield seq[:n]
        seq = seq[n:]

def tobin(h):
    return ''.join((format(int(n,16),"04b") for n in h if n!=' '))

if __name__ == '__main__':
    pkts=[tobin(sys.stdin.readline().strip())]
    vbits=[0] * len(pkts[0])
    print ''.join(["%-8s" % i for i in xrange(len(vbits)/8)])
    print pkts[-1]
    while True:
        cur = sys.stdin.readline().strip()
        if not cur: break
        cur = tobin(cur)
        diff(cur,pkts[-1])
        pkts.append(cur)

    for c in vbits:
        if c:
            sys.stdout.write("\x1b[31m%s\x1b[0m" % 1)
        else:
            sys.stdout.write(' ')
    print

    for i, byte in enumerate(split_by_n(vbits,8)):
        if sum(byte) == 0:
            n = int(pkts[-1][i*8:i*8+8],2)
            sys.stdout.write("%8s" % ("%03d %02x" % (n, n)))
        else:
            sys.stdout.write(' '*8)
    print

    for dist, a, b in sorted(descartes(pkts, hamming)):
        print dist, pkts.index(a), pkts.index(b)
        print ''.join(["%-8s" % i for i in xrange(len(vbits)/8)])
        print a
        diff(b,a)
        for i, byte in enumerate(split_by_n(a,8)):
            n = int(byte,2)
            sys.stdout.write("%8s" % ("%03d %02x" % (n, n)))
        print
