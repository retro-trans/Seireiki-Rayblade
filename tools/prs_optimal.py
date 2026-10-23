"""Bit-cost dynamic PRS parse with bounded back-reference candidate search.

Uses the same Rayblade stream grammar as rayblade_codec. Unlike its greedy
encoder, considers future token costs at every source position. All possible
lengths up to each discovered match are considered. Matching is bounded to
128 long candidates, so this is not an unrestricted optimal-match claim.
"""
from rayblade_codec import decompress


def compress_dynamic(data):
    data=bytes(data);n=len(data);cost=[0]*(n+1);cost[n]=26;choice=[None]*n
    for pos in range(n-1,-1,-1):
        limit=min(256,n-pos);short_len=0;short_dist=0;long_len=0;long_dist=0
        if limit>=2 and pos:
            key=data[pos:pos+2];upper=pos+1;low=max(0,pos-256)
            while True:
                candidate=data.rfind(key,low,upper)
                if candidate<0:break
                length=2
                while length<min(5,limit) and data[candidate+length]==data[pos+length]:length+=1
                if length>short_len:short_len=length;short_dist=pos-candidate
                if length==min(5,limit):break
                upper=candidate+1
        if limit>=3 and pos:
            key=data[pos:pos+3];upper=pos+2;low=max(0,pos-8192)
            for _ in range(128):
                candidate=data.rfind(key,low,upper)
                if candidate<0:break
                length=3
                while length<limit and data[candidate+length]==data[pos+length]:length+=1
                if length>long_len:long_len=length;long_dist=pos-candidate
                if length==limit:break
                upper=candidate+2
        best=9+cost[pos+1];selected=(1,1,0)
        for length in range(2,short_len+1):
            total=12+cost[pos+length]
            if total<best:best=total;selected=(0,length,short_dist)
        for length in range(3,min(long_len,9)+1):
            total=18+cost[pos+length]
            if total<best:best=total;selected=(2,length,long_dist)
        if long_len>=10:
            score=min(cost[pos+10:pos+long_len+1]);length=cost.index(score,pos+10,pos+long_len+1)-pos
            total=26+score
            if total<best:best=total;selected=(2,length,long_dist)
        cost[pos]=best;choice[pos]=selected
    out=bytearray();remaining=0;flag_pos=0
    def bit(value):
        nonlocal remaining,flag_pos
        if not remaining:flag_pos=len(out);out.append(0);remaining=8
        remaining-=1
        if value:out[flag_pos]|=1<<remaining
    pos=0
    while pos<n:
        kind,length,distance=choice[pos]
        if kind==1:bit(1);out.append(data[pos])
        elif kind==0:
            bit(0);bit(0);bit((length-2)>>1);bit((length-2)&1);out.append(256-distance)
        else:
            bit(0);bit(1);token=(8192-distance)<<3
            if length<=9:token|=length-2
            out.extend((token>>8,token&255))
            if length>9:out.append(length-1)
        pos+=length
    bit(0);bit(1);out.extend((0,0,0))
    result=bytes(out)
    assert len(result)==(cost[0]+7)//8
    assert decompress(result)==(data,len(result))
    return result
