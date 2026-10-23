"""Historical 0.1.20 recipe; preserve for old build/proof reproducibility.

WARNING: sprites 60/61 were misidentified as Resupply/None. The current
source-linked correction is counterattack-orders.en.json, built by
build_order_icons_patch.py (all five order icons, all three atlas copies).
Do not use this historical recipe as the current order-icon translation.
"""
import argparse,json
from extract_ui_atlases import ROOT,analyze,digest

DEST=ROOT/'work/translation/en/ui/image-labels.en.json'


def prepare():
    resources=analyze();names={r['id']:r for r in json.loads((ROOT/'work/translation/en/ui/names.json').read_text('utf-8'))}
    rows=[]
    def add(info,im,index,en,style,meaning=None,name_id=None,parts=None):
        r=info['rectangles'][index];crop=im.crop(r['source_box'])
        item={'id':r['id'],'texture_member':info['texture_member'],'sprite':index,'source_box':r['source_box'],'source_pixels_sha256':digest(crop.tobytes()),
            'en':en,'style':style,'meaning':meaning or en}
        if name_id:item.update(name_source_id=name_id,name_source_sha256=names[name_id]['source_sha256'])
        if parts:item['parts']=parts
        rows.append(item)
    for info,_,_,im in resources:
        if info['dat_member'] in (1,5):
            for index,en,meaning in [(59,'Ctr','Counterattack'),(60,'Sup','Resupply'),(61,'Nil','None'),(62,'Def','Defend')]:
                add(info,im,index,en,'icon',meaning)
            add(info,im,57,'Prana','medium',name_id=None)
            if info['dat_member']==5:
                add(info,im,116,'EVENT','small_red',meaning='Event')
                for index,en,key in [(89,'Critical',None),(90,'Evade',None),(91,'Defend',None),(92,'Plasma Coating','names.g00.028'),(93,'Plasma Barrier','names.g00.025'),(95,'Special Field','names.g00.026'),(107,'Barrier','names.g00.029')]:
                    if key:assert names[key]['en']==en
                    add(info,im,index,en,'medium',name_id=key)
                assert names['names.g00.027']['en']=='Ballistic Barrier'
                add(info,im,94,'Ballistic Barrier','medium',name_id='names.g00.027',parts=[{'text':'Ballistic','box':[0,0,48,16]},{'text':'Barrier','box':[48,0,96,16]}])
        else:
            add(info,im,0,'Trust Gauge','tab')
            short=['Ai','Ymir','Kasumi','Xiujian','Clovis','Fain','Rosalie','Gen','Aurelie','Arthur','Melvi','Leone','Kururu','Melissa','Celica']
            for sprite,text in enumerate(short,2):
                key=f'names.g11.{sprite:03d}';full=names[key]['en']
                assert text in full or (text=='Gen' and full.startswith('Genzbariored'))
                add(info,im,sprite,text,'tab',name_id=key)
    assert len(rows)==35
    return {'version':'0.1.20','source':'Original WIN00.AFS sprite/PVR pairs 1/2, 5/6, 87/88','font':'incoming/fonts/user-bitmap/dialogue-atlas.png',
        'font_scale':{'medium':'uniform 1/2 source scale (12-pixel cell height)','icon_and_tab':'uniform 1/3 source scale (8-pixel cell height)','small_red':'uniform 1/4 source scale (6-pixel cell height), retaining red event-label color'},
        'notes':['Ctr/Sup/Def are compact display labels for Counterattack/Resupply/Defend in 16-pixel icon cells; Nil means None','Small labels retain source stroke coverage per uniformly scaled block and use one-pixel letter gaps; glyphs are padded, never stretched','Gen and Xiujian follow the short labels printed in the original atlas','Sprite 107 reuses the Barrier half of sprite 94; both keep the same translated pixels','Image text does not add story/library draft credit'],
        'rows':rows}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--write',action='store_true');args=ap.parse_args();data=prepare();print(json.dumps(data,indent=2))
    if not args.write:print('DRY RUN: no translation map written');return
    DEST.write_text(json.dumps(data,indent=2)+'\n','utf-8');print('Wrote',DEST)


if __name__=='__main__':main()
