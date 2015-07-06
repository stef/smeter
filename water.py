#!/usr/bin/env python

import sys, math, binascii, struct
from bitarray import bitarray
from crcmod import Crc
from collections import defaultdict
from hamm import hamming

# poly: x16+x13+x12+x11+x10+x8+x6+x5+x2+1
poly=(1<<16)+(1<<13)+(1<<12)+(1<<11)+(1<<10)+(1<<8)+(1<<6)+(1<<5)+(1<<2)+1
CRC16 = Crc(poly, initCrc=0xffff, rev=False, xorOut=0xffff)

def check(data, crc):
    crc16 = CRC16.copy()
    crc16.update(data)
    return crc == crc16.digest()

def todate(d):
    d=[ord(c) for c in d]
    return '%04d-%02d-%02d' % (
        (d[1] >> 5) + 2014,
        ((d[1]>>1) & 0xf),
        ((d[1] & 1) << 4) | (d[0] >> 4))

def dump(decoded):
    manuf = []
    vendor = struct.unpack("<H", decoded[2:4])[0]
    for i in xrange(3):
        manuf.append(chr(0x40 + (vendor & 0x1f)))
        vendor >>= 5
    manuf = ''.join(reversed(manuf))
    #print "%-3s" % ord(decoded[0]),
    #print CVALS[ord(decoded[1])],
    #print manuf,

    print "%02x%02x" % (ord(decoded[5]),ord(decoded[4])),
    print "%02x%02x" % (ord(decoded[6]),ord(decoded[7])),
    print "%02x%02x" % (ord(decoded[8]),ord(decoded[9])),
    print "%-10s" % todate(decoded[18:20]),
    print "%-5s" % struct.unpack('<H',decoded[20:22])[0],
    print "%-5s" % struct.unpack('<H',decoded[22:24])[0],

    print '\t', ' | '.join((hexdump(t[12:28]), hexdump(t[30:46]), hexdump(t[48:-2])))

    nl=False
    if decoded[0] != '\x2f':
        print >>sys.stderr, '[x] size', binascii.hexlify(decoded[0])
        nl=True
    if decoded[1] != '\x44':
        print >>sys.stderr, '[x] type', binascii.hexlify(decoded[1]), CVALS.get(ord(decoded[1]),'UNKNOWN'),
        nl=True
    if decoded[2:4] != '\x68\x50':
        print >>sys.stderr, '[x] make', manuf
        nl=True
    #if decoded[6:8] not in ['\x16\x03','\x17\x03', '\x86\x02', '\x87\x02']:
    #    print >>sys.stderr, '[x] at', binascii.hexlify(decoded[6:8]),
    #    nl=True
    #if decoded[8:10] != '\x69\x80':
    #    print >>sys.stderr, '[x] a', binascii.hexlify(decoded[8:10]),
    #    nl=True
    #if decoded[12:16] not in ['\xa0\x11\x9f\x1d', '\xa0\x91\x9f\x1d']:
    #    print >>sys.stderr, '[x] 1/1', binascii.hexlify(decoded[12:16]),
    #    nl=True
    if nl: print >>sys.stderr

def split_by_n( seq, n ):
    """A generator to divide a sequence into chunks of n units.
       src: http://stackoverflow.com/questions/9475241/split-python-string-every-nth-character"""
    while seq:
        yield seq[:n]
        seq = seq[n:]

def hexdump(a):
    return ' '.join(split_by_n(binascii.hexlify(a),4))

if __name__ == '__main__':
    pkts=[binascii.unhexlify(''.join(line.split())) for line in sys.stdin]
    pcnt = defaultdict(int)
    amap = defaultdict(list)
    for p  in pkts:
        a = format(ord(p[4]),"02x")+format(ord(p[5]),"02x")
        pcnt[p]+=1
        amap[a].append(p)

    print "details"
    for a in sorted(amap.keys()):
        for t in amap[a]:
            if t not in pcnt: continue
            print "%-3s" % pcnt[t],
            dump(t)
            #print >>sys.stderr, hexdump(t)
            del pcnt[t]
        print
