#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define RING_SIZE (1024*1024)

typedef enum {LISTEN = 0, PREAMBLE, SYNC, PACKET, QUIT = 128 } state_t;

uint8_t rbuf[RING_SIZE];
size_t cur=0, end = 0;
float sample_rate, zero_sample_rate, one_sample_rate;
FILE* src;
state_t state = LISTEN;
uint16_t nbuf=0;
int nsize=0;

// T1_meter_sync '1111000010'
const uint8_t T1_meter_sync[] = {4,4,1,1,0};
// T2_other_sync '111000100101101001'
const uint8_t T2_other_sync[] = { 3,3,1,2,1,1,2,1,1,2,1,0};

static size_t load() {
  size_t len=0;

  if(cur>RING_SIZE) {
    //printf("meh\n");
    return -1;
  }
  if(end>RING_SIZE) {
    //printf("wtf\n");
    return -1;
  }
  if(cur>0) {
    // shift cur to start
    if(end<cur) return -1;
    memmove(rbuf,rbuf+cur, end - cur);
    end = end - cur;
    cur = 0;
  }

  if(RING_SIZE>end) {
    // fill up after the end
    //printf("read %d\n",RING_SIZE - end -1);
    if((len=fread(rbuf+end,1, RING_SIZE - end -1,src))==0) {
      if(feof(src)) {
        //printf("1wtf\n");
        return -1;
      } else {
        //printf("2wtf %s\n", strerror(ferror(src)));
        return -1;
      }
    }
    end+=len;
    //printf("b %ld %ld %ld\n", cur, end, len);
  }
  return len;
}

// listen
static void listen() {
  uint8_t *pre = NULL;
  size_t len;

  sample_rate=0;

  if(cur<end)
    pre = memchr(rbuf+cur, 0, len);

  while(pre==NULL) {
    cur = end;
    len = load();
    if(len==0 || len==-1) {
      state = QUIT;
      return;
    }
    pre = memchr(rbuf+cur, 0, len);
  }
  cur = pre - rbuf;
  len = load();
  if(len==0 || len==-1) {
    state = QUIT;
    return;
  }
  state = PREAMBLE;
}

// match preamble
static void preamble() {
  uint8_t *pre = NULL;
  int dist;

  pre = memchr(rbuf+cur, 1, end-cur);
  if(pre==NULL) {
    printf("found \"endless\" 0 instead of preamble :/\n");
    exit(1);
  }
  dist = pre - (rbuf+cur);
  if(dist<5) {
    cur+=dist;
    state=LISTEN;
    return;
  }
  // adjust cur
  cur+=dist;
  // try to recover clock-rate
  size_t samples[50*2];
  int i;
  uint8_t bit = 0;
  // take five samples of pairs
  for(i=0;i<10;i++) {
    pre = memchr(rbuf+cur, bit, end-cur);
    if(pre==NULL) {
      cur=end;
      state=LISTEN;
      return;
      //printf("found \"endless\" 0 instead of preamble :/\n");
      //exit(1);
    }
    dist = pre - (rbuf+cur);
    cur+=dist;
    samples[i]=dist;
    bit ^=1;
  }
  float avg = 0, deviation=0;
  for(i=0;i<10;i++) avg+=samples[i];
  avg/=10;
  //calculate std deviation
  for(i=0;i<10;i++) deviation+=(samples[i]-avg)*(samples[i]-avg);
  deviation=sqrt(deviation/9);
  //printf("avg: %f, dev: %f\n", avg, deviation);

  if(deviation/avg>0.2) {
    state=LISTEN;
    return;
  }
  for(i=10;i<100;i++) {
    pre = memchr(rbuf+cur, bit, end-cur);
    if(pre==NULL) {
      printf("found \"endless\" bit :/\n");
      exit(1);
    }
    dist = pre - (rbuf+cur);
    if(dist>avg*2) {
      break;
    }
    cur+=dist;
    samples[i]=dist;
    bit ^=1;
  }

  if(dist<=avg*2 || i==100) {
    printf("can't find end of preamble\n");
    return;
  }

  // refine sample_rate
  int j=i;
  zero_sample_rate = 0;
  for(i=0;i<j;i+=2) zero_sample_rate+=samples[i];
  zero_sample_rate/=j/2;
  //printf("zero sample_rate: %f\n", zero_sample_rate);
  one_sample_rate = 0;
  for(i=1;i<j;i+=2) one_sample_rate+=samples[i];
  one_sample_rate/=j/2;
  //printf("one sample_rate: %f\n", one_sample_rate);

  sample_rate = 0;
  //int j=i;
  for(i=0;i<j;i++) sample_rate+=samples[i];
  sample_rate/=j;
  //printf("sample_rate: %f\n", sample_rate);

  state = SYNC;
}

static void sync() {
  uint8_t *sync = NULL, bit = 1;
  const uint8_t *sig;
  int dist, i;
  sync = memchr(rbuf+cur, bit, end-cur);
  if(sync==NULL) {
    printf("found \"endless\" bit :/\n");
    exit(1);
  }
  dist = sync - (rbuf+cur);
  cur+=dist;
  if(dist>5*sample_rate) {
    state=LISTEN;
    return;
  }
  dist = lround(dist/sample_rate);
  //printf("dist: %d\n",dist);

  if(dist==4) { // T1 packet
    sig=T1_meter_sync;
  } else if(dist==3) { // \o/ T2 pkt
    printf("\\o/ T2 syncbyte\n");
    sig=T2_other_sync;
  } else {
    state = LISTEN;
    return;
  }
  i=1;
  while(sig[i]) {
    bit^=1;
    sync = memchr(rbuf+cur, bit, end-cur);
    if(sync==NULL) {
      printf("found \"endless\" bit :/\n");
      exit(1);
    }
    dist=(sync - (rbuf+cur));
    cur+=dist;
    dist = lround(dist/sample_rate);
    //printf("dist: %d\n",dist);
    if(dist!=sig[i]) {
      printf("meh no syncbyte\n");
      state = LISTEN;
      return;
    }
    i++;
  }
  //printf("\\o/ syncbyte\n");
  state = PACKET;
}

static int _4to6(const uint8_t six){
  switch(six) {
  case '\x32': return '\x0e';
  case '\x31': return '\x0d';
  case '\x2c': return '\x08';
  case '\x13': return '\x07';
  case '\x29': return '\x0f';
  case '\x26': return '\x0a';
  case '\x16': return '\x00';
  case '\x25': return '\x09';
  case '\x19': return '\x05';
  case '\x0e': return '\x02';
  case '\x0d': return '\x01';
  case '\x23': return '\x0b';
  case '\x34': return '\x0c';
  case '\x1c': return '\x04';
  case '\x1a': return '\x06';
  case '\x0b': return '\x03';
  default: return -1;
  }
}

#define MIN(a,b) (a<b?a:b)

static int get_nibble() {
  uint8_t *edge = NULL, *edge2 = NULL;
  int dist, bit = rbuf[cur], i, ret;
  size_t pcur=cur;
  double _t;
  while(nsize<6) {
    edge = memchr(rbuf+cur, bit ^ 1, end-cur);
    if(edge==NULL) {
      printf("found \"endless\" bit :/\n");
      exit(1);
    }
    dist=edge - (rbuf+cur);
    if(fabs(modf(dist / (bit?zero_sample_rate:one_sample_rate), &_t) - 0.5)<0.1 ) {
      edge2 = memchr(edge, bit, end-(edge-rbuf));
      if(edge2==NULL) {
        printf("found \"endless\" bit :/\n");
        exit(1);
      }
      edge2 = memchr(edge2, bit ^ 1,  end-(edge2-rbuf));
      if(edge2==NULL) {
        printf("found \"endless\" bit :/\n");
        exit(1);
      }
      if(dist + (edge2 - edge)<40) {
        //printf("extended: %d -> %d ", dist, dist + (edge2 - edge));
        //int kk, kks = dist + (edge2 - edge);
        //uint8_t xxbu[kks];
        //for(kk=0;kk<kks;kk++) xxbu[kk]=rbuf[cur+kk]+'0';
        //xxbu[kks]=0;
        //printf("%.150s\n", xxbu);
        edge=edge2;
      }
    }
    dist = (edge - (rbuf+cur));
    cur += dist;
    //printf("dist: %d %d ", dist, bit);
    dist = lround(dist / (bit?zero_sample_rate:one_sample_rate));
    //printf("%d ", dist);
    if(bit) {
      nbuf = (nbuf << dist) | ((1<<dist)-1);
    } else {
      nbuf <<= dist;
    }
    //printf("%02x\n", nbuf & 0x3f);
    nsize+=dist;
    bit ^= 1;
  }
  ret = _4to6((nbuf >> (nsize-6) ) & 0x3f);
  if (ret==-1) {
    // todo debug remove
    /* uint8_t pkt[256]; */
    /* int k; */
    /* for(k=0;k<MIN((cur-pcur)+120,255);k++) { */
    /*   if(k==70 || k==(cur-pcur)+70) pkt[k++]=' '; */
    /*   pkt[k]=rbuf[pcur+k-70]+'0'; */
    /* } */
    /* pkt[k]=0; */
    /* printf("%02x %s\n", nbuf & 0x3f, pkt); */
    cur=pcur;
  }
  //printf("ret: %02x\n", ret);
  nbuf &= (1<<(nbuf - 5)) -1;
  nsize-=6;
  return ret;
}

static int get_byte() {
  int hi, lo;
  hi = get_nibble();
  if(hi == -1) {
    return -1;
  }
  lo = get_nibble();
  if(lo == -1) {
    return -1;
  }
  return (hi<<4) | lo;
}

static void packet() {
  uint8_t pkt[256]; // todo debug remove
  int b;
  int i,j, size;

  //reset nibble buffer
  nbuf=0; nsize=0;

  pkt[0] = get_byte();
  size = pkt[0] + 1 + ceil(((float)(pkt[0] - 9))/16.0)*2;
  //printf("%02x, %d\n",pkt[0], size);
  for(i=1;i<size;i++) {
    b=get_byte();
    if(b==-1) {
      //printf("meeeh: read pkt error\n");
      break;
    }
    pkt[i]=b;
  }
  //printf("[%03d/%03d] ", i, size);
  //if(size!=i) {
    for(j=0;j<i;j++) {
      printf("%02x",pkt[j]);
      if(j%2==1) printf(" ");
    }
    printf("\n");
  //}
  // todo handle outro
  cur+=80;
  state=LISTEN;
}

void decode() {
  while(1) {
    switch(state) {
    case LISTEN:   listen(); break;
    case PREAMBLE: preamble(); break;
    case SYNC:     sync(); break;
    case PACKET:   packet(); break;
    case QUIT:     exit(1); break;
    default:       listen(); break;
    }
    //uint8_t buf[2] = "\x00\x00";
    //pop(src, buf, 8);
    //fprintf(stdout, "%02x\n", buf[0]);
  }
}

int main(int argc, char** argv) {
  src = stdin;
  decode();
}
