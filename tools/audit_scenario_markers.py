"""Resolve two signature-review items using native VM dispatch/advance.

BF pointer-table parsing executes directly. D2's unit-value query is a bounded
fixture; operand parsing, condition selection and VM branch/skip execute.
Default dry run. No game components or Japanese script output are written.
"""
import argparse,hashlib,json,struct
from functools import lru_cache
from build_font_patch import ROOT
from test_font_patch import CPU

BASE=0x8c010000;SOURCE=0x8c500000;STOP=0xdead0000
DEST=ROOT/'docs/scenario-marker-review.json'
CASES=[('s_086.bin',0x1d,0x23,14,'six signed callback-pointer operands'),('s_161.bin',0xdc8,0xdcd,7,'signed conditional-branch displacement')]
digest=lambda b:hashlib.sha256(b).hexdigest()


class ReviewCPU(CPU):
    def execute(self,pc,delay=False):
        self.visited.add(pc);op=self.read(pc,2)
        if op&0xff00==0xc700:self.reg[0]=((pc+4)&~3)+(op&255)*4;return pc+2
        if op&0xf0ff==0x0023:
            assert not delay
            target=(pc+4+self.reg[(op>>8)&15])&0xffffffff;self.execute(pc+2,True);return target
        if pc==0x8c086c88:
            self.queries.append(tuple(self.reg[4:6]));self.reg[0]=self.query_value;return self.pr
        return super().execute(pc,delay)


def run(c,start,end):
    c.pc=start
    for n in range(10000):
        if c.pc==end:return n
        c.pc=c.execute(c.pc)
    raise ValueError('Native marker audit instruction limit '+hex(c.pc))


def audit():
    original=(ROOT/'work/source/disc/1ST_READ.BIN').read_bytes();exe=(ROOT/'work/output/0.1.20/1ST_READ.BIN').read_bytes()
    ranges=[(0x2f23e,0x2f4c4),(0x83790,0x83838),(0x7a06c,0x7a174)]
    for lo,hi in ranges:assert exe[lo:hi]==original[lo:hi]
    resolutions=[];steps=0
    for member,start,marker,length,kind in CASES:
        data=(ROOT/'work/source/scenario'/member).read_bytes();opcode=data[start]
        assert data[marker:marker+2]==b'\x8a\x06' and start<marker<marker+2<=start+length
        witnesses=[]
        for query in ([0] if opcode==0xbf else [0,19,20]):
            c=ReviewCPU(exe,b'',0,0);c.regions=[(BASE,bytearray(exe)),(SOURCE,bytearray(data)),(0x8c1d0000,bytearray(0x30000)),(0x8c700000,bytearray(0x2000))]
            c.reg[15]=0x8c701000;c.write(c.reg[15]+4,STOP,4);c.write(0x8c1dbe24,SOURCE+start+1,4);c.write(0x8c1dbe70,opcode,4);c.visited=set();c.queries=[];c.query_value=query
            saved=c.reg[8:];n=run(c,0x8c03f48a,0x8c03f498);ret=c.reg[0]
            assert c.reg[8:]==saved
            c.write(c.reg[15],ret,4);n+=run(c,0x8c03f250,0x8c03f48a);steps+=n
            assert c.reg[8:]==saved and 0x8c07cf3c not in c.visited
            if opcode==0xbf:
                expected=[start+2+2*i+struct.unpack_from('<h',data,start+2+2*i)[0] for i in range(6)]
                actual=[c.read(0x8c1dfdfc+4*i,4)-SOURCE for i in range(6)]
                assert actual==expected and ret==0x600d and not c.queries
                assert c.read(0x8c1dbe24,4)-SOURCE==start+length+1 and c.read(0x8c1dbe70,4)==data[start+length]
            else:
                assert c.queries==[(4,2)]
                branch=marker+struct.unpack_from('<h',data,marker)[0]
                target=branch if query<=19 else start+length
                assert ret==(0x5004 if query<=19 else 0x6006)
                assert c.read(0x8c1dbe24,4)-SOURCE==target+1 and c.read(0x8c1dbe70,4)==data[target]
            witnesses.append({'unit_query_fixture':query if c.queries else None,'return':hex(ret),'next_opcode_offset':hex(c.read(0x8c1dbe24,4)-SOURCE-1),'next_opcode':hex(c.read(0x8c1dbe70,4)),'native_instructions':n})
        resolutions.append({'member':member,'member_sha256':digest(data),'marker_offset':marker,'command_start':start,'command_end':start+length,'command_sha256':digest(data[start:start+length]),'opcode':opcode,'classification':kind,'not_text':'8A 06 occupies native operands; native VM skips or branches without dispatching it as a dialogue opcode','witnesses':witnesses})
    return {'version':'0.1.20','kind':'Native resolution of two source-signature review items; no game changes','source_executable_sha256':digest(original),'tested_executable_sha256':digest(exe),'native_code_ranges':[{'start':hex(lo),'end':hex(hi),'sha256':digest(exe[lo:hi])} for lo,hi in ranges],'native_instructions':steps,'resolutions':resolutions,'limits':['D2 unit-stat query is a controlled fixture; game-state evaluation is not proved','These two marker resolutions do not prove full VM/opcode or runtime text coverage']}


@lru_cache(maxsize=1)
def reviewed_markers():
    if not DEST.exists():return {}
    review=json.loads(DEST.read_text('utf-8'))
    original=(ROOT/'work/source/disc/1ST_READ.BIN').read_bytes();assert digest(original)==review['source_executable_sha256']
    return {(r['member'],r['marker_offset']):r for r in review['resolutions']}


def reviewed_marker(member,data,marker):
    entry=reviewed_markers().get((member,marker))
    if entry:
        assert digest(data)==entry['member_sha256']
        assert digest(data[entry['command_start']:entry['command_end']])==entry['command_sha256']
    return entry


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--verify',action='store_true');ap.add_argument('--write-report',action='store_true');args=ap.parse_args();assert not args.write_report or args.verify
    if not args.verify:print('DRY RUN: native VM marker audit planned; no writes');return
    report=audit();print(json.dumps(report,indent=2))
    if args.write_report:DEST.write_text(json.dumps(report,indent=2)+'\n','utf-8')


if __name__=='__main__':main()
