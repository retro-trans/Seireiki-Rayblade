"""Author source-linked credit roles and supported name readings. Dry run first."""
import argparse
import json

from build_bitmap_font import ROOT, ATLAS, digest
from extract_staff_credits import analyze

DEST = ROOT / 'work/translation/en/ui/staff-credits.en.json'
GLOSSARY = ROOT / 'work/glossary/staff-credits.json'
READINGS = 'https://www.mobygames.com/game/142698/seireiki-rayblade/credits/dreamcast/'
TRANSCRIPT = 'https://raido.moe/staff/dc/dc_seireiki_rayblade.html'

ROLES = [
    ('総指揮', 'Executive Producer'), ('チーフディレクター', 'Chief Director'),
    ('ディレクター', 'Director'), ('サブディレクター', 'Co-Director'),
    ('脚本', 'Script'), ('キャラクターデザイン・原画', 'Character Design & Original Art'),
    ('メカニックデザイン', 'Mechanical Design'), ('サウンド', 'Sound'),
    ('プログラム', 'Programming'), ('シナリオデータ', 'Scenario Data'),
    ('アニメーションデータ', 'Animation Data'), ('キャラクターグラフィック', 'Character Graphics'),
    ('ユニットグラフィック', 'Unit Graphics'), ('エフェクトグラフィック', 'Effect Graphics'),
    ('背景', 'Background Art'), ('戦術背景', 'Tactical Map Backgrounds'),
    ('CGムービー', 'CG Movies'), ('メインメカデザイン', 'Lead Mech Design'),
    ('スペシャルサンクス', 'Special Thanks'), ('企画・制作', 'Planning & Production'),
    ('（株）ウィンキーソフト', 'Winky Soft Co., Ltd.'),
]
PEOPLE = [
    ('高宮 成光', 'Shigemitsu Takamiya'), ('松本 健一郎', 'Kenichiro Matsumoto'),
    ('鎌田 篤志', 'Atsushi Kamata'), ('庄 真宏', 'Masahiro Sho'),
    ('阿部 徹', 'Toru Abe'), ('堀川 和良', 'Kazuyoshi Horikawa'),
    ('下山 剛史', 'Takeshi Shimoyama'), ('黒住 幸司', 'Koji Kurosumi'),
    ('藤原 達也', 'Tatsuya Fujiwara'), ('稲田 義広', 'Yoshihiro Inada'),
    ('草開 一也', None), ('徳村 義則', 'Yoshinori Tokumura'),
    ('稲岡 良平', 'Ryohei Inaoka'), ('吉岡 昭典', 'Akinori Yoshioka'),
    ('岩鶴 素義', 'Motoyoshi Iwatsuru'), ('武馬 功治', 'Yoshiharu Buma'),
    ('菊池 耕二', 'Koji Kikuchi'), ('宮下 加代子', 'Kayoko Miyashita'),
    ('中田 貴子', 'Takako Nakata'), ('乾 直也', 'Naoya Inui'),
    ('伊藤 健', None), ('戸田 篤樹', 'Atsuki Toda'),
    ('福田 博之', 'Hiroyuki Fukuda'), ('奥田 浩貴', 'Hirotaka Okuda'),
    ('森重 浩正', 'Hiromasa Morishige'), ('中村 真人', 'Masato Nakamura'),
    ('中出 秀二郎', 'Shujiro Nakade'), ('吉田 渉', 'Wataru Yoshida'),
    ('中柴 直樹', 'Naoki Nakashiba'), ('糸洲 文恵', 'Fumie Itosu'),
    ('須磨 敦史', None), ('中田 吉保', 'Yoshiyasu Nakata'),
    ('市川 裕文', 'Hirofumi Ichikawa'), ('武馬 佳代', 'Kayo Buma'),
    ('内方 智士', None), ('穂多田 佳子', 'Yoshiko Hotada'),
    ('鈴木 桃子', 'Momoko Suzuki'), ('岩崎 昌彦', 'Masahiko Iwasaki'),
    ('田畑 全啓', None), ('宮崎 匡史', None),
    ('水野 賢哉', 'Kenya Mizuno'), ('聖川 尚志', None),
]


def prepare():
    info, *_ = analyze()
    rows, unresolved, names = [], [], []
    assert len(ROLES) == 21 and len(PEOPLE) == 42
    for index, (ja, en) in enumerate(ROLES + PEOPLE, 21):
        source = info['rectangles'][index]
        kind = 'role_or_company' if index < 42 else 'person'
        entry = {'id': source['id'], 'kind': kind, 'ja': ja, 'en': en,
                 'source_pixels_sha256': source['source_pixels_sha256'],
                 'source_box': source['source_box'],
                 'status': 'authored_role_translation' if kind == 'role_or_company' else
                           ('secondary_reference_reading' if en else 'needs_reading_research')}
        if kind == 'person':
            entry['reading_reference'] = READINGS if en else None
            if en:
                entry['reading_note'] = 'Secondary credits reference; not claimed official self-romanization. ASCII long-vowel spelling for the native Latin repertoire.'
            else:
                entry['reading_note'] = 'Targeted searches did not establish this exact person\'s reading. Preserve original image; do not guess from common kanji readings.'
            if index == 52:
                entry['source_note'] = 'Present in the atlas, absent from the consulted Rayblade credit transcript; actual display/reachability not established.'
            if index == 68:
                entry['reading_note'] += ' Reference Shuujirou shortened consistently to Shujiro; source atlas has 秀二郎.'
            names.append(entry)
        if en:
            assert all(' ' <= c <= '~' for c in en)
            rows.append({**source, 'kind': kind, 'en': en, 'reading_status': entry['status']})
        else:
            unresolved.append(entry)
    glossary = {'scope': 'Credits name readings, separate from fictional character/term glossary',
                'source_archive_sha256': info['source_archive_sha256'],
                'sources': [{'url': READINGS, 'role': 'Secondary name-reading reference; direct fetch returned 403, indexed credits text was available'},
                            {'url': TRANSCRIPT, 'role': 'Japanese credit transcript cross-check; atlas is authoritative for printed glyphs'}],
                'people': names, 'role_translations': [dict(ja=ja, en=en, id=f'staff.19.{i:03d}') for i, (ja, en) in enumerate(ROLES, 21)],
                'limits': ['No name reading inferred from unrelated people with the same kanji.',
                           'Seven personal names remain unresolved; 35 reference readings need independent confirmation.',
                           'Sprite roster does not establish complete native credit timing, order or actual use.']}
    recipe = {'source': 'Original STAFF.AFS members 19/20',
              'source_archive_sha256': info['source_archive_sha256'],
              'font': str(ATLAS.relative_to(ROOT)).replace('\\', '/'), 'font_sha256': digest(ATLAS.read_bytes()),
              'font_scale': 'Uniform 1/2 source scale, 12-pixel cell height, common baseline',
              'rows': rows, 'unresolved_name_ids': [r['id'] for r in unresolved],
              'original_English_sprite_ids': list(range(21)),
              'pending': ['Seven unresolved name readings', 'Independent confirmation of secondary-reference readings',
                          'Native credit order/timing, live layout and appearance']}
    assert len(rows) == 56 and len(unresolved) == 7
    return recipe, glossary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    recipe, glossary = prepare()
    print('Plan: 21 translated roles/company labels, 35 supported name readings, seven unchanged unresolved names.')
    for row in recipe['rows']:
        print(row['id'], row['en'], '(' + row['reading_status'] + ')')
    print('Unresolved:', recipe['unresolved_name_ids'])
    if not args.write:
        print('DRY RUN: no translation or name glossary written')
        return
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(recipe, indent=2) + '\n', 'utf-8')
    GLOSSARY.write_text(json.dumps(glossary, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print('Wrote', DEST, 'and', GLOSSARY)


if __name__ == '__main__':
    main()
