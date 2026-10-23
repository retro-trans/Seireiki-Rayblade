"""Trace the real Hongshenguang attack graphic choice in ANIME 172/173.

Native dispatch, bit-field query, conditional branch, resource-load argument
parsing, join and ABI execute. Actual async file I/O/poll are bounded stubs.
This does not execute the whole attack or prove sprite/GPU appearance.
"""
import argparse
import json
import struct

from audit_animation_payloads import original
from build_bitmap_font import ROOT,digest
from rayblade_codec import decompress
from test_font_patch import CPU

BASE=0x8c010000
SOURCE=0x8c500000
STOP=0xdead0000
OUT=ROOT/'work/ui/asset-audit/EFFECT/attack-lettering'


class AttackCPU(CPU):
    def execute(self,pc,delay=False):
        self.visited.add(pc)
        op=self.read(pc,2)
        if op&0xf00f==0x6008:  # SWAP.B Rm,Rn: upper word is retained
            value=self.reg[(op>>4)&15]
            self.reg[(op>>8)&15]=(value&0xffff0000)|((value&255)<<8)|((value>>8)&255)
            return pc+2
        if op&0xff00==0xc700:
            self.reg[0]=((pc+4)&~3)+(op&255)*4
            return pc+2
        if op&0xf0ff==0x0023:
            assert not delay
            target=(pc+4+self.reg[(op>>8)&15])&0xffffffff
            self.execute(pc+2,True)
            return target
        if pc==0x8c021bc4:
            self.loads.append(list(self.reg[4:8]))
            self.reg[0]=1
            return self.pr
        if pc==0x8c021a3c:
            self.polls+=1
            self.reg[0]=1  # deliberately still pending: no fake PVM load
            return self.pr
        return super().execute(pc,delay)


def fresh(exe,program,actor,direction):
    c=AttackCPU(exe,b'',0,0)
    c.regions=[(BASE,bytearray(exe)),(0x8c160000,bytearray(0x20000)),
               (0x8c1d0000,bytearray(0x40000)),(SOURCE,bytearray(program)),
               (0x8c700000,bytearray(b'\xa5'*0x2000))]
    c.reg[15]=0x8c701000
    c.write(c.reg[15]+4,STOP,4)
    c.write(0x8c1dbfcd,actor,1)
    # Native query 0x802 selects bits 7:6 of this state word. Put the opposite
    # orientation in the other actor to verify the native actor selector.
    selected=0x8c1dc134 if actor else 0x8c1dc124
    other=0x8c1dc124 if actor else 0x8c1dc134
    c.write(selected,direction<<6,2)
    c.write(other,((direction+1)%4)<<6,2)
    c.write(0x8c1dbe24,SOURCE+181,4)
    c.write(0x8c1dbe70,0x85,4)
    c.loads=[]
    c.polls=0
    c.visited=set()
    return c


def run(c,start,end,limit=10000):
    c.pc=start
    for steps in range(limit):
        if c.pc==end:
            return steps
        c.pc=c.execute(c.pc)
    raise ValueError('Native attack selection instruction limit at '+hex(c.pc))


def advance(c,result):
    c.write(c.reg[15],result,4)
    return run(c,0x8c03f250,0x8c03f48a)


def check():
    archive,members=original()
    exe=(ROOT/'work/output/0.1.32/1ST_READ.BIN').read_bytes()
    # The archive filename pointer table agrees with the real file argument
    # recorded below. We do not execute the actual CD/filesystem routine.
    table=0x8c098b08-BASE
    pointer=struct.unpack_from('<I',exe,table+8*4)[0]-BASE
    assert exe[pointer:pointer+11]==b'EFFECT.AFS\0'
    assert struct.unpack_from('<I',exe,0x8c099798-BASE+0x85*4)[0]==0x8c055384
    assert struct.unpack_from('<I',exe,0x8c09a848-BASE+0x24*4)[0]==0x8c056620
    cases=[]
    for member,normal,alternate in [(172,142,455),(173,143,456)]:
        program,used=decompress(members[member])
        assert used==len(members[member])
        assert program[180:184]==bytes.fromhex('85240b00')
        assert program[184:190]==b'\x74\x06\x25\x08'+struct.pack('<H',normal)
        assert program[190:193]==b'\x03\x08\0'
        assert program[193:199]==b'\x74\x06\x25\x08'+struct.pack('<H',alternate)
        assert program[199]==0x61
        for actor in (0,64):
            for direction in range(4):
                c=fresh(exe,program,actor,direction)
                saved=c.reg[8:]
                steps=run(c,0x8c03f48a,0x8c03f498)
                result=c.reg[0]
                assert result==(0x5001 if direction in (1,3) else 0x6003)
                assert c.reg[8:]==saved and 0x8c093914 in c.visited
                steps+=advance(c,result)
                offset=c.read(0x8c1dbe24,4)-SOURCE-1
                wanted_offset=193 if direction in (1,3) else 184
                assert offset==wanted_offset and c.read(0x8c1dbe70,4)==0x74
                # Phase zero parses and calls the actual AFS API endpoint.
                # Stubs stop at pending I/O, retaining native state-machine
                # behavior without fabricating a loaded resource.
                c.write(0x8c1dbe74,0,4)
                steps+=run(c,0x8c03f48a,0x8c03f498)
                wanted=alternate if direction in (1,3) else normal
                assert c.loads==[[8,wanted,0,0x8c1f7220]] and c.polls==1
                assert c.reg[0]==0 and c.read(0x8c1dbe74,4)==1 and c.reg[8:]==saved
                # Enter only the real completed phase after the captured I/O
                # boundary. We do not pretend phases 1/2 loaded anything.
                c.write(0x8c1dbe74,3,4)
                steps+=run(c,0x8c03f48a,0x8c03f498)
                assert c.reg[0]==0x6005 and c.reg[8:]==saved
                steps+=advance(c,c.reg[0])
                if wanted_offset==184:
                    assert c.read(0x8c1dbe70,4)==3
                    steps+=run(c,0x8c03f48a,0x8c03f498)
                    assert c.reg[0]==0xf000
                    steps+=advance(c,c.reg[0])
                assert c.read(0x8c1dbe24,4)-SOURCE-1==199
                assert c.read(0x8c1dbe70,4)==0x61 and c.reg[8:]==saved
                # Stack may use a bounded native frame below the caller.
                stack=c.regions[-1][1]
                assert stack[:0xf00]==b'\xa5'*0xf00 and stack[0x1008:]==b'\xa5'*(0x2000-0x1008)
                cases.append({'ANIME_member':member,'source_decoded_sha256':digest(program),
                              'actor_selector_bit':actor,'native_state_bits_7_6':direction,
                              'branch_return':hex(result),'selected_command_offset':offset,
                              'EFFECT_member':wanted,'load_arguments':c.loads[0],
                              'joined_command_offset':199,'native_instructions':steps})
    assert len(cases)==16
    return {'source_build':'0.1.32','executable_sha256':digest(exe),
            'source_ANIME_archive_sha256':digest(archive),
            'native_cases':16,'native_instructions':sum(c['native_instructions'] for c in cases),'cases':cases,
            'native_dispatch_bit_query_branch_join_and_ABI':'pass',
            'observed_archive_filename_table':{'address':'0x8c098b08','index':8,'name':'EFFECT.AFS'},
            'graphic_variant_pairs':[[142,455],[143,456]],
            'all_branches_select_exactly_one_load':'pass',
            'fixtures':['AFS call at 0x8c021bc4 records native arguments and returns a token',
                        'Async poll at 0x8c021a3c stays pending; phases 1/2 file/PVM work are not executed',
                        'Completed phase 3 is entered separately to test native continuation/join'],
            'limits':['Actor state words are controlled fixtures; native actor selection and bit extraction execute',
                      'Only the real source branch/load/join region is tested, not whole ANIME control-flow reachability',
                      'No attack frames, palette animation, sprite transforms, file I/O or GPU appearance executed',
                      'This does not resolve the smeared glyph frame or establish a full English artwork treatment'],
            'game_build_changed':False}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify',action='store_true')
    ap.add_argument('--write-report',action='store_true')
    args=ap.parse_args()
    assert not args.write_report or args.verify
    print('Plan: native source 85/24 branch, real SDK bit query, parsed AFS arguments and continuation join for 16 actor/orientation cases.',flush=True)
    if not args.verify:
        print('DRY RUN: no native execution or report')
        return
    result=check()
    print('PASS:',result['native_cases'],'source cases;',result['native_instructions'],'native instructions; graphic pairs 142/455 and 143/456.',flush=True)
    if args.write_report:
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/'native-variant-selection.json').write_text(json.dumps(result,indent=2)+'\n','utf-8')


if __name__=='__main__':
    main()
