from __future__ import annotations

import compileall
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = Path('/mnt/data/v1141_site')

sys.path.insert(0, str(ROOT))
from apocalypse_bot.commands.v1092_horse_racing_rules import FINISH, HORSES, render_track_lane, simulate_race


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
    def handle_starttag(self, tag: str, attrs):
        data = dict(attrs)
        for key in ('href', 'src'):
            value = data.get(key)
            if value:
                self.links.append(value)


def internal_link_errors() -> list[str]:
    errors: list[str] = []
    for page in SITE.rglob('*.html'):
        parser = LinkParser()
        parser.feed(page.read_text(encoding='utf-8'))
        for value in parser.links:
            if value.startswith(('#', 'http://', 'https://', 'mailto:', 'javascript:', 'data:')):
                continue
            target = (page.parent / value.split('?', 1)[0].split('#', 1)[0]).resolve()
            if not target.exists():
                errors.append(f'{page.relative_to(SITE)} -> {value}')
    return errors


def main() -> None:
    checks: list[dict[str, object]] = []
    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})

    positions = [0, 5, 12, 20, 29, FINISH]
    lanes = [render_track_lane(pos) for pos in positions]
    add('horse markers visible', all(lane.count('♞') == 1 for lane in lanes), 'one ♞ per lane')
    add('one finish flag per lane', all(lane.count('🏁') == 1 for lane in lanes), 'one 🏁 per lane')
    add('shared finish coordinate', len({lane.index('🏁') for lane in lanes}) == 1, f'flag index={lanes[0].index("🏁")}')
    add('finished horse remains visible', lanes[-1].endswith('♞🏁]'), lanes[-1][-8:])
    add('equal lane length', len({len(lane) for lane in lanes}) == 1, f'length={len(lanes[0])}')
    add('six horse emojis', len(HORSES) == 6 and all(h.get('emoji') for h in HORSES), f'horses={len(HORSES)}')

    winners_valid = True
    for seed in range(5000):
        positions_out, winner, ticks = simulate_race(seed)
        if winner not in range(len(HORSES)) or ticks <= 0 or any(p < 0 or p > FINISH for p in positions_out):
            winners_valid = False
            break
    add('race simulation regression', winners_valid, '5000 deterministic races')

    race_source = (ROOT/'apocalypse_bot/commands/v1092_visual_status_horserace.py').read_text(encoding='utf-8')
    add('horse emoji shown beside name', 'horse_emoji = str(horse.get("emoji") or "🐎")' in race_source, 'name label restored')
    add('moving lane helper connected', 'render_track_lane(marker)' in race_source, 'live embed path')
    add('latest module loaded last', 'register_v1141_horse_marker_hotfix' in (ROOT/'apocalypse_bot/core/bot.py').read_text(encoding='utf-8'), 'after v11.4.0')

    compiled = compileall.compile_dir(ROOT/'apocalypse_bot', quiet=1)
    py_count = sum(1 for _ in (ROOT/'apocalypse_bot').rglob('*.py'))
    add('python compile', compiled, f'files={py_count}')

    manifest = json.loads((ROOT/'ABADDON_COMMAND_MANIFEST_v11.4.1.json').read_text(encoding='utf-8'))
    add('command manifest version', manifest.get('version') == '11.4.1', str(manifest.get('version')))
    add('new command in manifest', any(c.get('name') == '경마표시검수' for c in manifest.get('commands', [])), f"commands={manifest.get('declaration_count')}")
    hotfix_source = (ROOT/'apocalypse_bot/commands/v1141_horse_marker_hotfix.py').read_text(encoding='utf-8')
    aliases_ok = all(token in hotfix_source for token in ['racetrackaudit', 'horsemarkeraudit', 'v1141audit'])
    add('english/ascii aliases', aliases_ok, 'racetrackaudit / horsemarkeraudit / v1141audit')
    add('latest test scope updated', 'v11.4.1에서 수정한 경마 말 표식' in hotfix_source, '!테스트 상세')
    add('latest patch notes updated', '경마 말 표식 복구' in hotfix_source, '!패치노트')

    html_files = list(SITE.rglob('*.html'))
    html_ok = True
    for page in html_files:
        parser = LinkParser()
        try:
            parser.feed(page.read_text(encoding='utf-8'))
        except Exception:
            html_ok = False
    add('html parsing', html_ok, f'files={len(html_files)}')
    link_errors = internal_link_errors()
    add('website internal links', not link_errors, f'errors={len(link_errors)}')

    node_ok = True
    js_files = [SITE/'script.js', SITE/'config.js', SITE/'en/script.js', SITE/'en/config.js']
    for js in js_files:
        proc = subprocess.run(['node', '--check', str(js)], capture_output=True, text=True)
        if proc.returncode != 0:
            node_ok = False
            break
    add('javascript syntax', node_ok, f'files={len(js_files)}')

    en_text = '\n'.join(p.read_text(encoding='utf-8') for p in (SITE/'en').rglob('*.html'))
    hangul = re.findall(r'[가-힣]', en_text)
    add('english page hangul leak', len(hangul) == 0, f'hangul={len(hangul)}')
    config_ok = 'version: "v11.4.1"' in (SITE/'config.js').read_text(encoding='utf-8') and 'version: "v11.4.1"' in (SITE/'en/config.js').read_text(encoding='utf-8')
    add('website version sync', config_ok, 'ko/en v11.4.1')
    preview = SITE/'assets/v1141/ABADDON_v11.4.1_RACE_MARKER_PREVIEW.png'
    add('race preview asset', preview.exists() and preview.stat().st_size > 10_000, f'bytes={preview.stat().st_size if preview.exists() else 0}')

    previous_zip = Path('/mnt/data/ABADDON_BOT_v11.4.0_CHAMPIONSHIP_ALLIANCE_CASINO_STORY_AUDITED_PATCH.zip')
    if previous_zip.exists():
        with zipfile.ZipFile(previous_zip) as z:
            previous = {name.rstrip('/') for name in z.namelist() if not name.endswith('/')}
        current = {str(p.relative_to(ROOT)).replace('\\','/') for p in ROOT.rglob('*') if p.is_file()}
        missing = sorted(previous - current)
        add('existing bot files preserved', not missing, f'missing={len(missing)}')
    else:
        add('existing bot files preserved', False, 'previous zip missing')

    passed = sum(1 for row in checks if row['ok'])
    report = {
        'version': '11.4.1',
        'scope': 'horse marker visibility hotfix',
        'summary': {'passed': passed, 'total': len(checks), 'failed': len(checks)-passed},
        'checks': checks,
        'limitations': ['Discord Gateway login and live multi-user interaction were not executed in the offline build environment.'],
    }
    (ROOT/'ABADDON_v11.4.1_AUDIT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report['summary'], ensure_ascii=False))
    if passed != len(checks):
        for row in checks:
            if not row['ok']:
                print('FAILED:', row)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
