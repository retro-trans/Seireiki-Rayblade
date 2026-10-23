"""Build compressed scenario members with unchanged VM prefixes and EN banks.

Defaults to inspection only. The resulting archive requires the matching new
loader/formatter patch; it is never suitable for the unmodified executable.
"""
import argparse
import hashlib
import json
import struct
from collections import defaultdict
from build_font_patch import ROOT
from audit_scenario_insertion import command_streams
from rayblade_codec import compress, decompress

VERSION='0.1.7'
BANK_MAGIC=b'RBSCEN01'
PACK_MAGIC=b'RBS1'
SCRIPT_CAPACITY=0x20000
SCRATCH_CAPACITY=0x10000
DIALOGUE_CAPACITY=0x2000
BANK_POINTER_OFFSET=SCRIPT_CAPACITY-4


def digest(raw):return hashlib.sha256(raw).hexdigest()
def align(n,a=2048):return (n+a-1)//a*a


def build():
    complete,held,working_hashes,source_hashes=command_streams()
    groups=defaultdict(list)
    for row,payload in complete:groups[row['member']].append((row,payload))
    manifest=json.loads((ROOT/'work/source/scenario/manifest.json').read_text('utf-8'))
    source=(ROOT/'work/source/disc/D_SCE.AFS').read_bytes()
    assert digest(source)==manifest['archive_sha256']
    count=struct.unpack_from('<I',source,4)[0];assert count==448
    # This archive has no standard AFS filename metadata pointer after its
    # index. Its final member is an explicit raw ALS filename list.
    assert source[:4]==b'AFS\0' and source[8+count*8:8+count*8+8]==b'\0'*8
    header_end=align(8+count*8+8)
    archive=bytearray(source[:header_end]);members=[];streams={};packed_streams={}
    for entry in manifest['members']:
        index=entry['index'];name=entry['name'];original=(ROOT/'work/source/scenario'/name).read_bytes()
        off,size=struct.unpack_from('<II',source,8+index*8)
        assert source[off:off+size]==original and digest(original)==entry['sha256']==source_hashes.get(name,entry['sha256'])
        assert len(original)<=0xffff
        translated=sorted(groups[name],key=lambda p:p[0]['command_offset'])
        plain=bytearray(original);plain.extend(b'\0'*(align(len(plain),4)-len(plain)))
        bank_offset=len(plain)
        plain.extend(struct.pack('<8s6I',BANK_MAGIC,len(original),len(translated),0,index,8,0))
        table=len(plain);plain.extend(b'\0'*(8*len(translated)))
        records=[];prior_end=0
        for i,(record,payload) in enumerate(translated):
            source_offset=record['command_offset']+3;source_length=record['source_payload_bytes']
            assert source_offset>=prior_end and source_offset+source_length<=len(original)
            assert source_length+2<0x1000,'Original VM advance count exceeds its 12-bit field'
            assert digest(original[source_offset:source_offset+source_length])==record['source_payload_sha256']
            target=len(plain)
            assert source_offset<=0xffff and source_length<=0xffff
            struct.pack_into('<HHI',plain,table+8*i,source_offset,source_length,target)
            plain.extend(payload)
            prior_end=source_offset+source_length
            records.append({'id':record['id'],'source_offset':source_offset,'source_bytes':source_length,
                'english_offset':target,'english_bytes':len(payload),'english_sha256':digest(payload)})
        plain.extend(b'\0'*(align(len(plain),4)-len(plain)))
        struct.pack_into('<I',plain,bank_offset+16,len(plain))
        assert len(plain)<=BANK_POINTER_OFFSET and plain[:len(original)]==original
        packed=compress(plain)
        assert decompress(packed)==(bytes(plain),len(packed))
        wrapped=struct.pack('<4s4I',PACK_MAGIC,len(plain),len(packed),index,bank_offset)+packed
        assert align(len(wrapped))<=SCRATCH_CAPACITY,(name,len(wrapped),len(plain))
        target=align(len(archive));archive.extend(b'\0'*(target-len(archive)));archive.extend(wrapped)
        struct.pack_into('<II',archive,8+index*8,target,len(wrapped))
        # Re-read every entry using the same self-relative member bank layout
        # that the runtime formatter hook will search.
        for i,record in enumerate(records):
            a,b,c=struct.unpack_from('<HHI',plain,table+8*i)
            assert (a,b,c)==(record['source_offset'],record['source_bytes'],record['english_offset'])
            assert digest(plain[c:c+record['english_bytes']])==record['english_sha256']
        streams[name]=bytes(plain);packed_streams[name]=wrapped
        members.append({'index':index,'name':name,'original_bytes':len(original),
            'original_sha256':digest(original),'decoded_bytes':len(plain),'decoded_sha256':digest(plain),
            'packed_bytes':len(wrapped),'packed_sha256':digest(wrapped),'bank_offset':bank_offset,
            'archive_offset':target,'english_commands':len(records),'commands':records})
        if (index+1)%50==0:print('Compiled scenario members:',index+1,'/447',flush=True)
    last_off,last_size=struct.unpack_from('<II',source,8+447*8)
    listing=source[last_off:last_off+last_size];target=align(len(archive))
    archive.extend(b'\0'*(target-len(archive)));archive.extend(listing)
    struct.pack_into('<II',archive,8+447*8,target,len(listing))
    used=len(archive)
    assert used<=len(source),('Compressed English archive exceeds original ISO extent',used,len(source))
    archive.extend(b'\0'*(len(source)-len(archive)))
    for member in members:
        off,size=struct.unpack_from('<II',archive,8+member['index']*8)
        assert archive[off:off+size]==packed_streams[member['name']]
    assert archive[target:target+len(listing)]==listing and len(archive)==len(source)
    report={'version':VERSION,'kind':'compressed English scenario component; matching loader/hook required',
        'source_archive_sha256':digest(source),'archive_sha256':digest(archive),
        'archive_bytes':len(archive),'used_archive_bytes':used,'spare_archive_bytes':len(source)-used,
        'script_members':len(members),'english_commands':sum(m['english_commands'] for m in members),
        'held_commands':len(held),'held_rows':sum(len(r['held_rows']) for r in held),
        'maximum_decoded_member_bytes':max(m['decoded_bytes'] for m in members),
        'maximum_packed_member_bytes':max(m['packed_bytes'] for m in members),
        'maximum_sector_read_bytes':max(align(m['packed_bytes']) for m in members),
        'script_capacity':SCRIPT_CAPACITY,'scratch_capacity':SCRATCH_CAPACITY,
        'dialogue_capacity':DIALOGUE_CAPACITY,'bank_pointer_offset':BANK_POINTER_OFFSET,
        'index_entry_bytes':8,'packed_header_bytes':20,
        'filename_list_sha256':digest(listing),'working_file_sha256':working_hashes,
        'source_member_sha256':{m['name']:m['original_sha256'] for m in members},'members':members,
        'checks':['Every original script prefix is byte-exact; original VM branches/operands untouched',
                  'All complete English command pages preserved; separate original and English lengths',
                  'All 447 wrapped members pass PRS and bank index round trips',
                  'Original archive byte size/count and raw filename-list bytes retained'],
        'pending':['Native loader/formatter hook verification','Full VM text coverage','Pixel layout and gameplay',
                   'Held passages and independent meaning review']}
    return bytes(archive),streams,packed_streams,report


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args()
    archive,streams,packed,report=build()
    print(json.dumps({k:v for k,v in report.items() if k not in ('members','working_file_sha256','source_member_sha256')},indent=2))
    print('Largest members:',json.dumps(sorted([{k:v for k,v in m.items() if k!='commands'} for m in report['members']],
          key=lambda m:-m['decoded_bytes'])[:3],indent=2))
    if not args.write:print('DRY RUN: no scenario component written.');return
    out=ROOT/'work/output'/VERSION/'text';out.mkdir(parents=True,exist_ok=True)
    (out/'D_SCE.AFS').write_bytes(archive)
    (out/'scenario-component-report.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    print('Wrote scenario component; executable integration still required:',out)


if __name__=='__main__':main()
