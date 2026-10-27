"""Execute the selector with actual native UI construction/parsing; GPU endpoints are fixtures."""
import json
from build_native_font_mode import compose, MODE, TITLE_HOOK, TITLE_RANGE, FRAME_CALLEE
from build_bitmap_font import digest
from test_library_layout import fresh, LibraryCPU, run


class TitleCPU(LibraryCPU):
    def execute(self,pc,delay=False):
        # Native resource teardown is tested separately from font selection;
        # no real GPU texture exists in this integer interpreter.
        if pc in (0x8c078cf0,0x8c0784c2):
            self.calls.append(('delete',pc,self.reg[4]));return self.pr
        return super().execute(pc,delay)


def check(*,compose_fn=compose):
    exe,archive,font,_,report=compose_fn()
    cpu=fresh(exe,font);cpu.__class__=TitleCPU
    cpu.write(0x8c169bac,0x8c401000,4)
    steps=0;results=[]
    def frame(pc,buttons):
        nonlocal steps
        cpu.write(0x8c1dbe24,pc,4);cpu.write(0x8c401008,buttons,4)
        cpu.reg[15]=0x8c701800;cpu.pr=0xdead0000
        saved=cpu.reg[1:];calls=len(cpu.calls);glyphs=len(cpu.glyphs)
        steps+=run(cpu,TITLE_HOOK,FRAME_CALLEE)
        assert cpu.reg[1:]==saved
        assert cpu.pr==0xdead0000
        assert cpu.read(0x8c1dbe24,4)==pc
        mode=cpu.read(MODE,1)
        result={'VM':hex(pc),'buttons':hex(buttons),'mode':mode,'active':cpu.read(MODE+1,1),
                'new_calls':len(cpu.calls)-calls,'text':''.join(g[0] for g in cpu.glyphs[glyphs:])}
        results.append(result);return result
    assert frame(0x8c0191f2,0x200)['active']==0
    r=frame(TITLE_RANGE[0],0);assert r['active']==1 and r['mode']==0 and 'Native (1x)' in r['text'],(r,cpu.calls)
    slot=cpu.read(0x8c1f24d7,1);ctx=0x8c1f0cf8+slot*92
    assert [cpu.read(ctx+i,2) for i in (0x30,0x32,0x4e,0x50)]==[80,224,256,32]
    mallocs=sum(c[0]=='malloc' for c in cpu.calls)
    for mode,button in [(1,0x200),(0,0x400),(1,0x200)]:
        frame(TITLE_RANGE[0]+16,0)
        r=frame(TITLE_RANGE[0]+16,button);assert r['mode']==mode and r['text']
        r=frame(TITLE_RANGE[0]+16,button);assert not r['text']
    assert sum(c[0]=='malloc' for c in cpu.calls)==mallocs,'Switching leaked a surface'
    r=frame(TITLE_RANGE[1],0);assert r['active']==0 and r['mode']==1
    assert cpu.read(0x8c1f24d7,1)==255
    assert frame(0x8c01ef45,0x400)['mode']==1,'Gameplay changed the font'
    return {'version':report['version'],'executable_sha256':digest(exe),
            'native_instructions':steps,'frames':results,'VM_PC_PR_ABI':'pass',
            'context_geometry':[80,224,256,32],'switching_extra_allocations':0,
            'GPU_and_teardown':'Bounded fixtures; separate emulator check required'}


if __name__=='__main__':print(json.dumps(check(),indent=2))
