"""Read SDK video-memory lists from a saved, ignored game-RAM snapshot."""
import argparse,json,struct
from pathlib import Path


def inspect(raw):
    assert len(raw)==0x1000000
    def u(p):return struct.unpack_from('<I',raw,p&0xffffff)[0]
    banks=[]
    for bank in range(2):
        root=0x8c11d0b4+bank*20
        groups={}
        for name,offset in [('allocated',4),('free',12)]:
            ptr=u(root+offset);seen=set();rows=[]
            while ptr:
                assert 0x8c000000<=ptr<0x8d000000 and ptr not in seen
                seen.add(ptr)
                flags,nxt,prev,addr,size,owner=struct.unpack_from('<6I',raw,ptr&0xffffff)
                row={'node':hex(ptr),'flags':hex(flags),'VRAM_offset':hex(addr),'bytes':size,'owner':hex(owner)}
                if name=='allocated' and 0x8c000018<=owner<0x8cffffc0 and not flags&0x2000:
                    row.update(gbix=hex(u(owner-24)),width=u(owner+12),height=u(owner+16))
                rows.append(row);ptr=nxt
            groups[name]=rows
        groups.update(bank=bank,total_free=u(root+16),largest_free=max([r['bytes'] for r in groups['free']],default=0))
        assert sum(r['bytes'] for r in groups['free'])==groups['total_free']
        banks.append(groups)
    return {'VM':hex(u(0x8c1dbe24)),'native_texture_error':u(0x8c419530),'TA_allocator_units':u(0x8c4621a4),'banks':banks}


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('ram',type=Path);ap.add_argument('--report',type=Path);a=ap.parse_args()
    r=inspect(a.ram.read_bytes());text=json.dumps(r,indent=2)+'\n'
    if a.report:a.report.write_text(text,'utf-8')
    print(text)
