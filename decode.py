#!/usr/bin/env python

import sys, math, binascii, struct
from bitarray import bitarray
from crcmod import Crc
from collections import defaultdict
from hamm import hamming

PREAMBLE_N = 8 # minimum preamble repeats of 01
T1_METER_SYNC = ('01'* 4) + '0000111101'
T2_OTHER_SYNC = ('01'* 4) + '000111011010010110'

_326 = {"010110": "0000",
        "001101": "0001",
        "001110": "0010",
        "001011": "0011",
        "011100": "0100",
        "011001": "0101",
        "011010": "0110",
        "010011": "0111",
        "101100": "1000",
        "100101": "1001",
        "100110": "1010",
        "100011": "1011",
        "110100": "1100",
        "110001": "1101",
        "110010": "1110",
        "101001": "1111"}

CVALS = { 0x44: u'send-no-Reply',
          0x46: u'installation mode',
          0x48: u'Access demand',
          0x00: u'acknowledge'}

# poly: x16+x13+x12+x11+x10+x8+x6+x5+x2+1
poly=(1<<16)+(1<<13)+(1<<12)+(1<<11)+(1<<10)+(1<<8)+(1<<6)+(1<<5)+(1<<2)+1
CRC16 = Crc(poly, initCrc=0xffff, rev=False, xorOut=0xffff)

def check(data, crc):
    crc16 = CRC16.copy()
    crc16.update(data)
    return crc == crc16.digest()

def decode():
    pkts = []
    bad = []
    BSIZE = 1 << 16
    bit = 0
    idx = 0
    pkt = bitarray()
    #badbits = 0
    mm = sys.stdin.read(BSIZE)
    total = 0
    while(True):
        # buffered find(bit,idx) from stdin
        pos = mm.find(chr(bit), idx - total if idx>total else 0)
        while pos == -1:
            total += len(mm)
            mm = sys.stdin.read(BSIZE)
            if not mm:
                #print sizes
                return pkts, bad
            pos = mm.find(chr(bit), idx - total if idx>total else 0)
        pos += total

        size = pos - idx
        idx = pos
        bit ^= 1
        if bit==1 and size > 100:
            # end of packet
            if idx == size: continue
            if len(pkt)>160:
                _pkt = pkt
                found = False
                while len(pkt)>160:
                    msg = parse(pkt)
                    if msg:
                        pkts.append(msg)
                        pkt = pkt[len(msg[0])*12:]
                        found=True
                    else:
                        pkt = pkt[140:]
                if not found:
                    bad.append(_pkt.to01())
            pkt = bitarray()
        else:
            bits = int(round(size / 10.0)) or 1
            pkt.extend([bit]*bits)

def parse(bits):
    pos = bits.to01().find(T1_METER_SYNC)
    if pos < 50 or pos > 140:
        # check for T2 other
        #pos = bits.to01().find(T2_OTHER_SYNC, spos)
        pos = bits.to01().find(T2_OTHER_SYNC)
        if pos < 50 or pos > 140:
            #"no sync byte found %s" % pos
            return
        print "T2 zomg!!!!"
        #sync_size=len(T2_OTHER_SYNC)
        return
    else:
        sync_size=len(T1_METER_SYNC)
    #print bits[:pos+sync_size]
    decoded = bitarray()
    for six in split_by_n(bits[pos+sync_size:].to01(),6):
        if len(six)!=6:
            #print 'trailing', six
            break
        try:
            decoded += _326[six]
        except:
            return
            #print 'decoding error', six, decoded
            #raise
    decoded = decoded.tobytes()
    #if not check(decoded[:10], decoded[10:12]): return
    return decoded, binascii.hexlify(decoded[4:10])

def todate(d):
    d=[ord(c) for c in d]
    return '%02d-%02d-%04d' % (
        ((d[1] & 1) << 4) | (d[0] >> 4),
        ((d[1]>>1) & 0xf),
        (d[1] >> 5) + 2014)

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
    print "%-10s" % todate(decoded[18:20]),
    print "%-3s" % ord(decoded[26]),
    print "%-3s" % ord(decoded[27]),
    print "%-5s" % struct.unpack('<H',decoded[20:22])[0],
    print "%-5s" % struct.unpack('<H',decoded[22:24])[0],
    print "%-5s" % struct.unpack('<H',decoded[24:26])[0],
    print "%-5s" % (struct.unpack('<H',decoded[22:24])[0] - struct.unpack('<H',decoded[24:26])[0]),
    #print "%-5s" % struct.unpack('<H',decoded[26:28])[0],
    #print '+',
    #print "%-5s" % struct.unpack('<H',decoded[30:32])[0],
    #print "%-5s" % struct.unpack('<H',decoded[32:34])[0],
    #print "%-5s" % struct.unpack('<H',decoded[34:36])[0],
    #print '|',
    #print "%-5s" % struct.unpack('<H',decoded[48]+decoded[49])[0],
    #print "%-5s" % struct.unpack('<H',decoded[50:52])[0],
    #print "%-5s" % struct.unpack('<H',decoded[52:54])[0],
    #print "%-5s" % struct.unpack('<H',decoded[54:56])[0],
    #print "+",
    print '\t', ' | '.join((hexdump(t[12:28]), hexdump(t[30:46]), hexdump(t[48:-2])))
    nl=False
    if decoded[0] != '\x32':
        print >>sys.stderr, '[x] size', binascii.hexlify(decoded[0])
        nl=True
    if decoded[1] != '\x44':
        print >>sys.stderr, '[x] type', binascii.hexlify(decoded[1]), CVALS.get(ord(decoded[1]),'UNKNOWN'),
        nl=True
    if decoded[2:4] != '\x68\x50':
        print >>sys.stderr, '[x] make', manuf
        nl=True
    if decoded[6:8] not in ['\x16\x03','\x17\x03', '\x86\x02', '\x87\x02']:
        print >>sys.stderr, '[x] at', binascii.hexlify(decoded[6:8]),
        nl=True
    if decoded[8:10] != '\x69\x80':
        print >>sys.stderr, '[x] a', binascii.hexlify(decoded[8:10]),
        nl=True
    if decoded[12:16] not in ['\xa0\x11\x9f\x1d', '\xa0\x91\x9f\x1d']:
        print >>sys.stderr, '[x] 1/1', binascii.hexlify(decoded[12:16]),
        nl=True
    if nl: print >>sys.stderr

def split_by_n( seq, n ):
    """A generator to divide a sequence into chunks of n units.
       src: http://stackoverflow.com/questions/9475241/split-python-string-every-nth-character"""
    while seq:
        yield seq[:n]
        seq = seq[n:]

def hexdump(a):
    return ' '.join(split_by_n(binascii.hexlify(a),4))

def bindump(a):
    a = format(int(binascii.hexlify(a)[2:],16),"0%db" % (len(a)*8))
    return '\n'.join(' '.join(split_by_n(line,4)) for line in split_by_n(a, 64))

def display(decoded):
    #date='/'.join((str(x) for x in (ord(decoded[18]) & 0x1F,
    #                               (ord(decoded[19]) & 0x0F) - 1,
    #                               ((ord(decoded[18]) & 0xE0) >> 5) | ((ord(decoded[17]) & 0xF0) >> 1))))
    return ' '.join(("%02x%02x" % (ord(decoded[5]),ord(decoded[4])),
                     "%04x" % struct.unpack('<H',decoded[6:8])[0],
                     #"%5s" % struct.unpack('<H',decoded[18:20])[0],
                     "%-10s" % todate(decoded[18:20]),
                     #"%5s" % struct.unpack('<H',decoded[16:18])[0], no clue what this is
                     "%5s" % ord(decoded[26]),
                     "%5s" % ord(decoded[27]),
                     "%5s" % struct.unpack('<H',decoded[20:22])[0],
                     #"%5s" % struct.unpack('<H',decoded[26:28])[0],
                     "%5s" % struct.unpack('<H',decoded[22:24])[0],
                     "%5s" % struct.unpack('<H',decoded[24:26])[0],
                     "%6s" % (struct.unpack('<H',decoded[24:26])[0] - struct.unpack('<H',decoded[22:24])[0]),

                     #'+',
                     #"%-10s" % todate(decoded[31:33]),
                     #"%-10s" % todate(decoded[33:35]),
                     #"%-10s" % todate(decoded[35:37]),
                     #'|',
                     #"%-10s" % todate(decoded[47]+decoded[50]),
                     #"%-10s" % todate(decoded[51:53]),
                     #"%-10s" % todate(decoded[53:55]),
                     #"%-10s" % todate(decoded[55:57]),
                     #"+",

                     ))

if __name__ == '__main__':
    pkts, bad = decode()
    pcnt = defaultdict(int)
    amap = defaultdict(list)
    for p,a  in pkts:
        pcnt[p]+=1
        amap[a].append(p)
    print 'total meters:', len(amap.keys()), 'total messages:', len(pcnt.keys()), 'total pkts:', len(pkts), 'dropped', len(bad)

    print 'latest'
    print "%4s %4s %10s %5s %5s %5s %5s %5s %6s %6s %5s" % ("id", "foo", "time", "cur", "last", "total", "in", "out", "diff", "avg", "seen")
    for k, a, b in sorted([(a, display(amap[a][-1]), "%5s" % len(amap[a])) for a in amap.keys()]):
        avg = "%6s" % (sum((struct.unpack('<H',decoded[24:26])[0] - struct.unpack('<H',decoded[22:24])[0]) for decoded in amap[k]) / len(amap[k]))
        print a, avg, b, '\t', ' | '.join((hexdump(amap[k][-1][30:46]), hexdump(amap[k][-1][48:-2])))
    print

    print "details"
    for a in sorted(amap.keys()):
        for t in amap[a]:
            if t not in pcnt: continue
            print "%-3s" % pcnt[t],
            dump(t)
            #print >>sys.stderr, hexdump(t)
            del pcnt[t]
        print

    print 'dropped'
    for b in bad:
        if not b: continue
        print b
