"""Historical 201-caption recipe, retained for old build/proof reproducibility.

The two old reading holds are resolved separately in album-caption-readings.en.json
and inserted in 0.1.37. Use album-captions-current.en.json for the combined current
203-caption draft map. Do not regenerate this historical map as current status.
"""
import argparse
import json

import numpy as np
from PIL import Image

from build_bitmap_font import ROOT, ATLAS, digest
from extract_album_captions import analyze

DEST = ROOT / 'work/translation/en/ui/album-captions.en.json'


def caption_mask(text):
    """Uniform 1/3 area coverage; no per-letter stretching or max-pool bolding."""
    atlas=Image.open(ATLAS).convert('L');glyphs=[]
    for char in text:
        if char==' ':
            glyphs.append(np.zeros((8,2),np.uint8));continue
        code=ord(char)-32
        assert 0<=code<95
        cell=atlas.crop((code%32*12,code//32*24,code%32*12+12,code//32*24+24))
        box=cell.getbbox();assert box
        crop=cell.crop((box[0],0,box[2],24))
        width=(crop.width+2)//3*3
        padded=Image.new('L',(width,24));padded.paste(crop,(0,0))
        raw=np.asarray(padded,dtype=np.uint16).reshape(8,3,width//3,3)
        glyphs.append(((raw.sum(axis=(1,3))+4)//9).astype(np.uint8))
    result=np.zeros((8,sum(g.shape[1] for g in glyphs)+len(glyphs)+1),np.uint8);x=1
    for glyph in glyphs:
        result[:,x:x+glyph.shape[1]]=glyph;x+=glyph.shape[1]+1
    return result


EN = {
0:'Party Card A', 1:'Party Card B', 2:'Party Card C', 3:'The Debish Family',
4:'Rayblade & Touya', 5:'Vishal & Ai', 6:'Orbest & Kasumi', 7:'Baldock & Clovis',
8:'Drydes & Arthur', 9:'Parikar & Aurelie', 10:'Hongshenguang & Xiujian', 11:'Ahti & Melissa',
12:'Zeifon & Gen', 13:'Selphin & Celica', 14:'New Year Card 1', 15:'New Year Card 2',
16:'Group Photo', 17:'Baresios & Growster', 18:'Leone',
24:'Group Photo', 25:'New Year Card 1', 26:'New Year Card 2',
32:'Meeting Up with Ai', 33:'Ai Hugs Touya', 34:'Kasumi Hugs Touya', 35:"Kasumi Holds Touya's Hand",
36:'A Startled Kasumi', 37:"Touya Holds Kasumi's Hand", 38:'Kasumi Blushes', 39:'Celica Lands on Her Bottom',
40:'Celica Reaches for a Hug', 41:'Smiling with the Children', 42:'Aurelie in the Lobby', 43:'Ymir Stands in Shock',
44:'Ymir Hugs Touya', 45:'Family Photo', 46:'A Photo Together with Leone', 47:"Leone's Face in the Photo",
48:'A Puzzled Look Back', 49:'Wind Blows In', 50:'A Shy Expression', 51:'Melvi at the Front Door',
52:'Sitting Astride Touya', 53:"Melvi's Smile", 54:'Kururu Rests Her Cheek on Her Hand', 55:'A Puzzled Kururu',
56:'Touya Comes to Pick Up Kururu', 57:"Kururu's Smile",
64:'Schoolyard with Cherry Blossoms', 65:'The Teacher Peeks In', 66:'Touya and Koichiro Look Up', 67:'Facing a Mysterious Robot',
68:'A Mysterious Robot Appears!', 69:'A Fallen Robot', 70:'Ai Is Rescued', 71:'Ai Flies Toward Touya!',
72:'The Open Cockpit', 73:'A Mysterious Robot', 74:'A Toppled Robot', 75:'The Mysterious Robot Closes In',
76:'Touya Under Attack', 77:'Looking Up in the Airport Lobby', 78:'Determination!!', 79:'Climbing into the Robot',
80:'Starting Up the Robot', 81:'Held at Gunpoint', 82:None, 83:'A Surprised Kasumi',
84:'In the Living Room', 85:'Family Photo', 86:"Kasumi's Note", 87:'Another Self outside the Window',
88:'Flamuelk Castle', 89:'Kaisar Closes In', 90:'Ai Again Flies Toward Touya!', 91:'Meeting Yamato',
92:'Bathing with Yamato', 93:'Sleeping Beside Yamato', 94:'A Dark Airport Lobby', 95:'Ymir Peeks In',
96:'Yamato with a Ribbon Tied On', 97:'A Black Mech atop a Cliff', 98:'Oswald Goes Mad 1', 99:'Oswald Goes Mad 2',
100:'Alforina Has Fallen', 101:'Ai Gazes at Alforina', 102:None, 103:'Alforina Breathes Her Last',
104:'Alforina Lies Fallen', 105:'Alforina Breathes Her Last', 106:'In the Landship Corridor', 107:'Ai Takes a Seat',
108:'Ai Looks Up', 109:'The Pair by the Window', 110:'Two Silhouettes', 111:"Ai Cries Out against Touya's Back",
112:'Shall I Remind You?', 113:'The Landship Heads out to Sea 1', 114:'The Landship Heads out to Sea 2', 115:'Liebhofen Dock',
116:'The Capital, Brandenkrois', 117:'Rayblade in the Hangar', 118:'Belnea Fort', 119:'Veil Astin',
120:'Celica Sleeps', 121:'Putting a Blanket over Celica', 122:'A Close-Up of Cain', 123:'An Angry Oswald',
124:'Bernst by the Lake', 125:'Cain Appears', 126:'Ai Dives', 127:'Touya Catches Ai',
128:'Ahti with a Sniper Rifle', 129:'A Scope Image', 130:'A Close-Up Scope View', 131:'Touya Readies His Sword',
132:'Touya Readies His Blade', 133:'A Close-Up of Doris', 134:"Alforina's Gravestone", 135:'Something Approaches behind Kasumi',
136:'Kasumi Looks Up', 137:'Baresios Looks Down', 138:'Garyud Appears', 139:'Garyud Cuts It in Two with One Stroke',
140:'Touya and Kasumi in the Cockpit', 141:'The Agarthian Palace', 142:'Zeifon in the Hangar', 143:'Rayblade in the Hangar 1',
144:'Rayblade in the Hangar 2', 145:'Orbest in the Hangar', 146:'Shaking Hands with Garyud', 147:'A Speeding Aircar',
148:'Collapsed onto the Bed', 149:'Ai Is Shocked!', 150:'Clovis Impact!', 151:'Meeting Up with Leone!',
152:'Spilling Tea', 153:'Breaking Through the Center 1', 154:'Breaking Through the Center 2', 155:'Breaking Through the Center 3',
156:'Forstin in the Hangar', 157:'Touya Teaches Kururu', 158:'Reduce Catches the Blade', 159:'Tyron Swings His Blade Down',
160:'Reduce Thrusts His Blade Up', 161:'Two Knights in Combat', 162:'A Broken Sword Tip', 163:'A Blade at the Throat',
164:'Xiujian and Melissa', 165:"Sharl Stands on the Sea's Surface", 166:'Parthenos Appears', 167:'Sharl Looks Down',
168:'Touya Falls from the Boat', 169:'Ai Under Attack!', 170:'People Stand Rooted', 171:"Render's Group Rushes into the Room",
172:'Ioannis Demands Answers', 173:'Ai Stands Up', 174:'Becoming Debish 1', 175:'Becoming Debish 2',
176:'Debish before Goderius', 177:"Aurelie's Home Cooking", 178:'The Lunar Surface', 179:'A Loving Couple',
180:'In the Kitchen with Melvi', 181:"Miyasco's Mark", 182:"Ricara's Portrait", 183:'Kururu Taken Hostage',
184:'The Entryway', 185:"Xiujian and Melissa's World", 186:'Wenimas Receives a Confession', 187:'Rayblade Splashes Down',
188:'At the Beach at Night', 189:'Holding an Injured Maki', 190:'Ymir Sits on the Bed', 191:'Leone Links Arms for the Camera',
192:'Captive Lodis', 193:'Leone Inside the Capsule', 194:'Peering from the Broken Capsule', 195:"Ymir Buries Her Face against His Chest 1",
196:"Ymir Buries Her Face against His Chest 2", 197:'Ymir Weeps Quietly', 198:'Kissing Leone in the Infirmary', 199:'Holding Leone Close',
200:'Rayblade before the Final Battle', 201:'Before the Final Battle: Ai', 202:'Before the Final Battle: Kasumi', 203:'Before the Final Battle: Celica',
204:'Before the Final Battle: Aurelie', 205:'Before the Final Battle: Melvi', 206:'Before the Final Battle: Kururu', 207:'Before the Final Battle: Leone',
208:'A Scope in Flight', 209:'A Floating Core', 210:'Vorlia Appears', 211:'Vorlia Approaches the Holy Land',
212:'Kissing Rishuna at the Party', 213:'Vorlia and Liebhofen', 214:'Yamato Got Here First', 215:'A "Voice" Can Be Heard',
216:'Teacher Peeking In (Monochrome Background)', 217:'Wenimas Peeks In', 218:'Wenimas Ascends',
}
BLANKS = {*range(19, 24), *range(27, 32), *range(58, 64), *range(219, 224)}
NOTES = {
52:'Literal physical posture caption; do not add erotic language or unsupported clothing/body details.',
64:'Cherry-blossom reading supported by the schoolyard thumbnail; no windows/tower detail invented.',
82:'First character before Touya remains unclear in the low-resolution bitmap; retain the entire original caption until resolved.',
102:'Adjective describing Alforina\'s eyes/gaze remains unclear; retain the original caption rather than guess a disposition.',
39:'Physical fall onto the bottom, not making a face; no erotic detail added.',
87:'The source places the other self outside the window; do not invent a mirror/reflection.',
93:'Literal ordinary sleep beside Yamato; avoid the sexual English idiom sleeping with.',
124:'Lake-side location, not a window-side location.',
139:'A single-stroke cut in two, not merely a sword flash or an invented attack name.',
174:'Directional caption and face close-up interpreted as becoming Debish; this interpretation needs independent story/context review.',
175:'Companion directional face close-up caption; same provisional interpretation as 174, retained sequence number.',
185:'World is the printed noun; do not silently change it to a generic scene or expression.',
191:'Thumbnail shows Leone linking arms with Touya; not crossing her own arms. Camera context retained.',
195:'Source omits the chest owner; thumbnail shows Touya. Keep the established visible male referent, with no erotic detail.',
196:'Companion view of the same nonexplicit embrace; retain number and gesture.',
}


def wrap(text):
    lines, current = [], ''
    for word in text.split(' '):
        assert caption_mask(word).shape[1] <= 62, ('Word exceeds cell', word)
        trial = current + (' ' if current else '') + word
        if current and caption_mask(trial).shape[1] > 62:
            lines.append(current); current = word
        else:
            current = trial
    if current:
        lines.append(current)
    assert ' '.join(lines) == text
    return lines


def prepare():
    info, _, _, textures = analyze()
    glossary = json.loads((ROOT / 'work/glossary/glossary.json').read_text('utf-8'))
    terms = {r['id']: r for r in glossary['entries']}
    # Caption forms use the existing project spellings, including their short
    # person labels. No new speculative romanizations are introduced here.
    checks = {'mech.001':'Rayblade','mech.003':'Hongshenguang','mech.004':'Ahti','mech.005':'Zeifon',
              'mech.007':'Parikar','mech.008':'Baldock','mech.009':'Forstin','mech.010':'Vishal',
              'mech.011':'Drydes','mech.012':'Orbest','mech.013':'Selphin','mech.035':'Goderius',
              'mech.036':'Parthenos','mech.055':'Baresios','mech.056':'Veil Astin','mech.058':'Kaisar',
              'character.050':'Render','character.049':'Ioannis','character.084':'Miyasco','character.090':'Alforina'}
    for key, value in checks.items():
        assert terms[key]['en'] == value, (key, terms[key]['en'], value)
    rows, overflows = [], []
    for row in info['rectangles']:
        index = row['sprite']
        image = textures[row['texture_member']][1].crop(row['caption_box']).convert('RGB')
        has_caption = np.ptp(np.asarray(image), axis=(0,1)).max() > 30
        assert bool(has_caption) == (index in EN), index
        assert (index in EN) != (index in BLANKS)
        if index in BLANKS:
            continue
        text = EN[index]
        lines = wrap(text) if text else []
        if len(lines) > 3:
            overflows.append({'id': row['id'], 'en': text, 'lines': lines})
        rows.append({**row, 'en': text, 'wrapped_lines': lines,
                     'status': 'authored_image_caption_draft' if text else 'needs_source_reading',
                     'decision': NOTES.get(index, 'Translate the printed caption in full; use established glossary names and preserve scene/sequence distinctions.')})
    assert len(EN) == 203 and len(BLANKS) == 21 and len(rows) == 203
    assert {r['sprite'] for r in rows if r['en'] is None} == {82, 102}
    return {'source': 'ALBUM.AFS DAT 214 and 28 native thumbnail atlases',
            'source_archive_sha256': info['source_archive_sha256'], 'source_dat_sha256': info['dat_sha256'],
            'font': str(ATLAS.relative_to(ROOT)).replace('\\', '/'), 'font_sha256': digest(ATLAS.read_bytes()),
            'font_source_scale': 'Uniform 1/3 source scale, eight-pixel cells, at most three lines in each 64x24 caption area',
            'font_sampling':'Area-averaged coverage per source 3x3 block, rounded glyph advances; grayscale RGB over the original opaque caption background',
            'rows': rows, 'preserved_blank_Coming_Soon_cells': sorted(BLANKS), 'overflows': overflows,
            'glossary_checks': checks, 'pending': ['Two source-caption readings', 'Independent meaning/context review',
                                                  'Native album unlock/selection/navigation and live caption appearance'],
            'story_library_draft_credit': 0}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    data = prepare()
    print('Plan: 201 authored captions, two original-caption reading holds, 21 original Coming Soon cells.')
    print('First page:', [(r['id'], r['en'], r['wrapped_lines']) for r in data['rows'][:16]])
    print('Overflow:', json.dumps(data['overflows'], indent=2))
    print('Pending source readings:', [r['id'] for r in data['rows'] if r['en'] is None])
    if not args.write:
        print('DRY RUN: no caption map written')
        return
    assert not data['overflows'], 'Resolve all full-meaning fit issues before writing an insertion map'
    DEST.write_text(json.dumps(data, indent=2) + '\n', 'utf-8')
    print('Wrote', DEST)


if __name__ == '__main__':
    main()
