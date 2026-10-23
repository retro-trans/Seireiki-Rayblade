"""Catalog all SFD movies and render sampled frames for caption discovery.

Original tracks stay read-only. ffprobe counts decoded video frames; ffmpeg
decodes each full stream and selects eight indexed frames. Sampling locates
text candidates, not proof that no transient caption exists between samples.
Default dry run. No movie is translated/re-encoded or inserted by this tool.
"""
import argparse,hashlib,json,re,shutil,subprocess
from fractions import Fraction
from PIL import Image,ImageDraw
from build_font_patch import ROOT
from disc_inventory import Disc

digest=lambda b:hashlib.sha256(b).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');ap.add_argument('--member',action='append',default=[]);args=ap.parse_args()
    disc=Disc(next(ROOT.glob('*.cue')));movies=[r for r in disc.inventory() if re.fullmatch(r'MOV\d{3}\.SFD',r['path'])]
    if args.member:
        assert all(re.fullmatch(r'MOV\d{3}\.SFD',name) for name in args.member)
        movies=[r for r in movies if r['path'] in args.member];assert len(movies)==len(set(args.member))
    else:assert len(movies)==116
    print(f'Plan: {len(movies)} SFD movies, {sum(r["size"] for r in movies):,} bytes; full decode/frame count and eight indexed frame samples per movie.',flush=True)
    if not args.write:print('DRY RUN: no extraction/decoding/output');return
    ffprobe=shutil.which('ffprobe');ffmpeg=shutil.which('ffmpeg');assert ffprobe and ffmpeg
    source=ROOT/'work/source/movies';dest=ROOT/'work/ui/asset-audit/movies';source.mkdir(parents=True,exist_ok=True);dest.mkdir(parents=True,exist_ok=True)
    entries=[];pages=[];page=None;labels=None
    for number,row in enumerate(movies):
        name=row['path'];raw=disc.read(row['lba'],row['size']);sha=digest(raw);path=source/name
        if path.exists():assert digest(path.read_bytes())==sha
        else:path.write_bytes(raw)
        probe=subprocess.run([ffprobe,'-v','error','-count_frames','-show_streams','-show_format','-of','json',str(path)],capture_output=True,text=True,encoding='utf-8',errors='replace')
        entry={**row,'sha256':sha,'source':'work/source/movies/'+name,'probe_exit':probe.returncode}
        if probe.returncode:
            entry.update(error=probe.stderr[:1200]);entries.append(entry);continue
        metadata=json.loads(probe.stdout);videos=[s for s in metadata['streams'] if s['codec_type']=='video'];assert len(videos)==1
        video=videos[0];w,h=video['width'],video['height'];count=int(video['nb_read_frames']);assert count>0
        rate=Fraction(video['avg_frame_rate'] if video['avg_frame_rate']!='0/0' else video['r_frame_rate'])
        indices=sorted({0,count-1,*[round((count-1)*v) for v in (.1,.25,.4,.55,.7,.85)]})
        select='+'.join(f'eq(n\\,{i})' for i in indices)
        decoded=subprocess.run([ffmpeg,'-v','error','-i',str(path),'-map','0:v:0','-an','-vf','select='+select,'-fps_mode','vfr','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],capture_output=True)
        expected=w*h*3*len(indices);assert decoded.returncode==0 and len(decoded.stdout)==expected,(name,decoded.returncode,len(decoded.stdout),expected,decoded.stderr[:1200])
        frames=[];folder=dest/name[:-4];folder.mkdir(exist_ok=True)
        for i,index in enumerate(indices):
            im=Image.frombytes('RGB',(w,h),decoded.stdout[i*w*h*3:(i+1)*w*h*3]);filename=f'frame-{index:05d}.png';im.save(folder/filename);frames.append(im)
        if number%8==0:
            page=Image.new('RGB',(1280,8*150),'#30333a');labels=ImageDraw.Draw(page);pages.append(page)
        y=number%8*150
        labels.text((4,y+2),name+f'   {w}x{h}, {count} decoded frames, {float(count/rate):.2f}s by frame count',fill='white')
        for col,(index,im) in enumerate(zip(indices,frames)):
            thumb=im.copy();thumb.thumbnail((158,112),Image.Resampling.LANCZOS);page.paste(thumb,(col*160,y+18));labels.text((col*160,y+131),f'f{index} / {float(index/rate):.2f}s',fill='white')
        streams=[{k:s[k] for k in ('index','codec_name','codec_type','width','height','r_frame_rate','sample_rate','channels','duration','nb_read_frames') if k in s} for s in metadata['streams']]
        entry.update(streams=streams,frame_count=count,frame_rate=str(rate),duration_by_frames=float(count/rate),sample_indices=indices,sample_files=[f'work/ui/asset-audit/movies/{name[:-4]}/frame-{i:05d}.png' for i in indices],contact_page=number//8,probe_diagnostics=probe.stderr[:1200],decode_diagnostics=decoded.stderr.decode('utf-8','replace')[:1200],review='pending visual review; samples cannot prove absence of transient captions')
        entries.append(entry)
        print(name,'frames',count,'samples',len(indices),'streams',[(s['codec_type'],s.get('codec_name')) for s in streams],flush=True)
    for i,im in enumerate(pages):im.save(dest/f'contact-{i:02d}.png')
    report={'kind':'SFD movie caption discovery; no game changes','movies':len(entries),'source_bytes':sum(r['size'] for r in entries),'decoded_video_frames':sum(r.get('frame_count',0) for r in entries),'selected_frame_samples':sum(len(r.get('sample_indices',[])) for r in entries),'source_extraction':'Exact ISO payloads read from original tracks; SHA256 for every file','decode_scope':'ffprobe frame count and full ffmpeg decode/select; eight sampled indices per movie','entries':entries,'limits':['Sampled frames locate likely text; they do not prove absence of overlays between samples','Audio dialogue/content, actual movie selection and live game overlays are not reviewed','No translation, encoding or disc modification is performed']}
    target=dest/('movie-index.json' if not args.member else 'movie-subset-index.json');target.write_text(json.dumps(report,indent=2)+'\n','utf-8')
    print('Wrote movie index and',len(pages),'contact sheets.',flush=True)


if __name__=='__main__':main()
