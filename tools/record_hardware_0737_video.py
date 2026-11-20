"""Record manually reviewed timed evidence; no hardware success inferred beyond the clip."""
import hashlib
from build_bitmap_font import ROOT
from build_hardware_asset_split import read, save


def main():
    folder = ROOT/'work/ui/hardware-0737-video-20261110'
    video = ROOT/'incoming/hardware-0737-20261110/20261109_235847.mp4'
    with video.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    observations = [
        {'seconds': [0, 5], 'scene': 'Clear 3: A Girl\'s Resolve save selection and intermission',
         'result': 'Visible selection is File 2 Clear 3; this is not a Clear 2 test.'},
        {'seconds': [20, 27], 'scene': 's_004 early battle, Fores/Reamond conversation',
         'result': 'Normal shaped dark unit shadows and readable portrait/text; old white backing rectangles absent in sampled frames.'},
        {'seconds': [30, 34], 'scene': 'Office cutaway with Alforina',
         'result': 'Room background becomes a white rectangle. A second pale rectangle covers dialogue and part of portrait. Large character remains visible. At 34 seconds the lower character is visible again as the scene fades.',
         'likely_dialogue_command': 'scenario.s_004.o004ad',
         'command_basis': 'Alforina Office cutaway between Reamond internal monologue and rock ambush; text itself obscured. Source line is It\'s begun...; identity inferred from sequence.'},
        {'seconds': [40, 45, 70, 80], 'scene': 'Reamond rock warning, aftermath and reply to Fores',
         'result': 'Readable portraits/dialogue, normal shadows in samples; scene continues.'},
        {'seconds': [60], 'scene': 'Ambush effect',
         'result': 'White frame within explosion sequence; not classified as a texture defect without a reference.'},
        {'seconds': [95], 'scene': 'Loading transition',
         'result': 'Small central NOW LOADING remains; historical diagnostic limitation.'},
        {'seconds': [100, 105], 'scene': 'World-map conversation and transition',
         'result': 'Arthur dialogue and labels visible; advances to chapter card.'},
        {'seconds': [115, 116, 120], 'scene': 'Chapter 4 title entrance',
         'result': 'Overlapping title copies at 115 settle to readable title at 116 and remain stable through 120. Entrance animation versus defect unresolved; do not classify as persistent corruption.'},
        {'seconds': [129, 132], 'scene': 'Chapter 4 battle and Ymir dialogue',
         'dialogue_source': 'work/translation/en/scenario/s_085.en.json',
         'result': 'New battle appears and Ymir says Be careful! It\'s that unit from earlier! with visible portrait/text. This confirms progression beyond the preceding scenario in the recording.'},
    ]
    record = {
        'date': '2026-11-10', 'version': '0.7.37', 'version_confirmed': False,
        'version_basis': 'Inferred from feedback following supplied 0.7.37 diagnostic; video does not display a build version.',
        'device': 'Previously established real Dreamcast / GDEMU / VGA',
        'user_report': 'It\u2019s better; the game doesn\u2019t freeze anymore. Graphical glitches appear during some dialogues. I\u2019ve attached a short video to check the locations precisely.',
        'source_url': 'Reporter recording retained locally; sharing URL omitted from public source',
        'local_video': video.relative_to(ROOT).as_posix(), 'bytes': video.stat().st_size,
        'sha256': sha, 'duration_seconds': 132.099489, 'resolution': [1280, 720],
        'codec': 'HEVC', 'nominal_fps': '30/1',
        'review_method': 'Visual review of 28 timed overview samples and 24 exact-time witness frames. No audio transcription or claim of exhaustive every-frame review.',
        'observations': observations,
        'scope_limit': 'Clear 3 selected, scenario advances through Office, world map, Chapter 4 title and Ymir battle dialogue. New Game, Hallway, Clear 2 choice, completion of Chapter 4 and full-game stability are not demonstrated.',
        'interpretation': 'Improvement after reservation change supports further testing of resource pressure; white Office background/dialogue remains. No physical allocator trace and no root cause confirmed.',
        'hardware_root_cause_confirmed': False,
        'frames': [{'path': p.relative_to(ROOT).as_posix(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                   for p in sorted(folder.rglob('*')) if p.suffix.lower() in ('.jpg', '.png')],
    }
    save(folder/'index.json', record)
    save(ROOT/'docs/hardware-0737-video-follow-up.json', record)
    path = ROOT/'docs/hardware-entry-hang-results.json'
    current = read(path)
    current['results']['0.7.37'] = {
        'reported_date': record['date'], 'status': 'Reported no freezes; video crosses into Chapter 4, with Office white rectangles remaining',
        'version_basis': record['version_basis'], 'version_confirmed': False,
        'report': record['user_report'], 'evidence': 'docs/hardware-0737-video-follow-up.json',
        'scope_limit': record['scope_limit'], 'hardware_root_cause_confirmed': False}
    current['interpretation']['latest_report'] = current['results']['0.7.37']['status']
    current['last_updated'] = record['date']
    save(path, current)
    path = ROOT/'docs/hardware-texture-budget-diagnostic.json'
    current = read(path)
    current['hardware_result'] = current_status = 'Reported no freezes; Clear 3 -> Chapter 4 visible; Office background/dialogue remains corrupt. Version inferred as 0.7.37.'
    current['hardware_follow_up'] = 'docs/hardware-0737-video-follow-up.json'
    save(path, current)
    path = ROOT/'docs/hardware-chapter-transition.json'
    current = read(path)
    current['texture_budget_candidate']['status'] = current_status
    current['texture_budget_candidate']['hardware_follow_up'] = 'docs/hardware-0737-video-follow-up.json'
    if current.get('next_compatibility_candidate', {}).get('version') == '0.7.37':
        current['next_compatibility_candidate'] = current['texture_budget_candidate']
    current['last_updated'] = record['date']
    save(path, current)
    print('Recorded video evidence:', sha)


if __name__ == '__main__':
    main()
