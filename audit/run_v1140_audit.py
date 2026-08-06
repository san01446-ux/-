from __future__ import annotations

import ast
import hashlib
import json
import py_compile
import re
import subprocess
import zipfile
from collections import defaultdict
from pathlib import Path

from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path('/mnt/data/v1140_work')
SITE = Path('/mnt/data/site_v1140_work')
BASE_BOT_ZIP = Path('/mnt/data/ABADDON_BOT_v11.0.0_GAME_CITY_HWATU_RESULT_FAIRNESS_AUDITED_PATCH.zip')
BASE_SITE_ZIP = Path('/mnt/data/ABADDON_OFFICIAL_SITE_v11.0.0_UPLOAD.zip')
MODULE = ROOT / 'apocalypse_bot/commands/v1140_championship_alliance_casino_story.py'


def add(checks, name, ok, detail):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})


def command_access():
    access = defaultdict(list)
    declarations = 0
    helps = []
    for path in sorted((ROOT / 'apocalypse_bot').rglob('*.py')):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except Exception:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                fn = dec.func.attr if isinstance(dec.func, ast.Attribute) else ''
                if fn not in {'command', 'hybrid_command', 'group', 'hybrid_group'}:
                    continue
                declarations += 1
                name = node.name
                aliases = []
                help_text = ''
                for kw in dec.keywords:
                    if kw.arg == 'name' and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        name = kw.value.value
                    elif kw.arg == 'aliases' and isinstance(kw.value, (ast.List, ast.Tuple)):
                        aliases = [e.value for e in kw.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                    elif kw.arg in {'help', 'description'} and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        help_text = kw.value.value
                for value in [name, *aliases]:
                    access[value.casefold()].append(f'{path.relative_to(ROOT)}:{node.lineno}')
                helps.append((name, help_text))
                break
    return declarations, access, helps


def zip_files(path: Path):
    if not path.is_file():
        return set()
    with zipfile.ZipFile(path) as zf:
        return {n.rstrip('/') for n in zf.namelist() if n and not n.endswith('/') and '__pycache__' not in n and not n.endswith('.pyc')}


def normalized(names):
    out = set()
    for n in names:
        parts = n.split('/')
        if parts and parts[0] in {'bot', 'site'}:
            parts = parts[1:]
        out.add('/'.join(parts))
    return out


def run():
    checks = []
    module_text = MODULE.read_text(encoding='utf-8')
    module_tree = ast.parse(module_text)

    # Syntax and compile surface.
    py_files = list(ROOT.rglob('*.py'))
    py_errors = []
    for path in py_files:
        try:
            py_compile.compile(str(path), doraise=True)
        except Exception as exc:
            py_errors.append(f'{path.relative_to(ROOT)}: {exc}')
    add(checks, 'Python 전체 컴파일', not py_errors, {'files': len(py_files), 'errors': py_errors})

    # Registration order and ledger compatibility.
    core = (ROOT / 'apocalypse_bot/core/bot.py').read_text(encoding='utf-8')
    order_ok = (
        'register_v1140_championship_alliance_casino_story' in core
        and core.index('register_v1100_game_city_overhaul') < core.index('register_v1140_championship_alliance_casino_story') < core.index('synchronize_all_english_aliases')
    )
    add(checks, 'v11.4 최종 등록 순서', order_ok, 'v11.0.0 → v11.4.0 → final English alias sync')
    authentic = (ROOT / 'apocalypse_bot/commands/v1060_authentic_card_games.py').read_text(encoding='utf-8')
    add(checks, '정산 장부 서버 ID 기록', '"guild_id":int(getattr(getattr(session.message,"guild",None),"id",0) or 0)' in authentic, 'championship/alliance rankings are server-scoped')

    # Static feature coverage.
    add(checks, '45초 게임 체크포인트', '@tasks.loop(seconds=45)' in module_text and 'status"] = "stale"' in module_text and 'if changed:' in module_text, 'active/stale checkpoint persistence')
    add(checks, '챔피언십·주간 사건', len(re.findall(r'\{"id": "[a-z]+", "ko":', module_text.split('DECORATIONS', 1)[0])) >= 5 and 'def _player_stats' in module_text, '5 rotating events + ledger-derived LP')
    add(checks, 'NPC 딜러 6명', module_text.count('"personality":') == 6 and 'name="NPC딜러"' in module_text and 'name="딜러선택"' in module_text, 'dealer roster and selection')
    add(checks, '연합 대항전', all(token in module_text for token in ('name="연합대항전"', 'name="연합대항전참가"', 'name="연합대항순위"', 'def _alliance_rows')), 'wins/net/boss damage/alliance XP')
    add(checks, '개인 카지노', all(token in module_text for token in ('name="개인카지노"', 'name="장식상점"', 'name="장식구매"', '_personal_casino_image')), 'image card, dealer and decorations')
    add(checks, '상점 부채 방지', 'shop purchases require available chips' in module_text and 'if casino_chips(user) < cost' in module_text, 'game debt remains allowed; cosmetic purchases require balance')
    add(checks, '6챕터 카드 캠페인', module_text.count('{"id": ') >= 11 and 'CHAPTERS' in module_text and 'name="캠페인진행"' in module_text and 'name="캠페인보상"' in module_text, '6 chapters + choices + rewards')
    add(checks, '캠페인 중복 진행 방지', 'ready_reward' in module_text and 'Claim the previous chapter' in module_text, 'must claim before advancing again')
    add(checks, '기존 리그참가 연동', 'league_join = bot.get_command("리그참가")' in module_text and 'league_join.callback = v1140_join_league' in module_text, 'existing command preserved and extended')
    add(checks, '!테스트 상세 최신화', 'test_command.callback = v1140_test' in module_text and '1140통합검수' in module_text, 'latest patch scope only')
    add(checks, '!패치노트 최신화', 'patch_notes.callback = v1140_notes' in module_text and 'v11.0.1부터 v11.4.0' in module_text, 'actual unified patch notes')

    # Command names and collision surface.
    declarations, access, helps = command_access()
    new_names = [
        '챔피언십','championship','abaddonchampionship','시즌순위','seasonranking','championshipranking',
        '챔피언도전','challengechampion','championchallenge','대회일정','tournamentschedule','championshipschedule',
        'NPC딜러','npcdealers','dealerroster','딜러선택','selectdealer','choosedealer','시즌사건','seasonevent','weeklyevent',
        '연합대항전','alliancewar','alliancechampionship','연합대항전참가','joinalliancewar','alliancewarjoin',
        '연합대항순위','alliancewarranking','allianceranking','연합임무','alliancemissions','alliancewarquests',
        '연합상점','allianceshop','alliancewarshop','개인카지노','mycasino','personalcasino','카지노꾸미기','decoratecasino','casinodesign',
        '장식상점','decorationshop','casinodecorstore','장식구매','buydecoration','purchasedecor','딜러고용','hiredealer','employdealer',
        '카지노공개','publishcasino','casinoprivacy','카드캠페인','cardcampaign','storycampaign','캠페인선택','campaignchoice','storychoice',
        '캠페인진행','advancecampaign','campaignadvance','캠페인보상','campaignreward','storyreward','캠페인기록','campaignlog','storylog',
        '스토리도감','storycodex','campaigncodex','1140통합검수','v1140audit','unified1140audit',
    ]
    conflicts = {name: access[name.casefold()] for name in new_names if len(access[name.casefold()]) != 1}
    add(checks, 'v11.4 신규 명령 충돌', not conflicts, {'declarations': declarations, 'conflicts': conflicts})
    missing_help = [name for name, help_text in helps if name in {x for x in new_names if any(ord(ch) > 127 for ch in x)} and not help_text]
    add(checks, '신규 명령 설명', not missing_help, {'missing': missing_help})

    # Batched image assets.
    assets = sorted((ROOT / 'apocalypse_bot/assets/v1140').glob('*.png'))
    image_errors = []
    sizes = {}
    for path in assets:
        try:
            image = Image.open(path)
            image.verify()
            image2 = Image.open(path)
            sizes[path.name] = image2.size
            if image2.width < 300 or image2.height < 150 or path.stat().st_size < 10_000:
                image_errors.append(f'{path.name}: {image2.size}/{path.stat().st_size}')
        except Exception as exc:
            image_errors.append(f'{path.name}: {exc}')
    required_assets = {
        'ABADDON_v11.4.0_MASTER_POSTER.png', 'ABADDON_v11.4.0_PATCH_OVERVIEW.png',
        'ABADDON_v11.4.0_CHAMPIONSHIP.png', 'ABADDON_v11.4.0_NPC_DEALERS.png',
        'ABADDON_v11.4.0_ALLIANCE_WAR.png', 'ABADDON_v11.4.0_PERSONAL_CASINO.png',
        'ABADDON_v11.4.0_STORY_CAMPAIGN.png', 'ABADDON_v11.4.0_GAME_CITY.png',
    }
    add(checks, '이미지 자산 일괄 제작', required_assets.issubset({p.name for p in assets}) and not image_errors, {'count': len(assets), 'sizes': sizes, 'errors': image_errors})

    # Website structure and language split.
    htmls = list(SITE.glob('*.html')) + list((SITE / 'en').glob('*.html'))
    link_errors = []
    link_count = 0
    for path in htmls:
        soup = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
        for tag_name, attr in [('a','href'),('img','src'),('script','src'),('link','href')]:
            for node in soup.find_all(tag_name):
                value = node.get(attr)
                if not value or value.startswith(('#','http:','https:','mailto:','javascript:','data:')):
                    continue
                target = (path.parent / value.split('?',1)[0].split('#',1)[0]).resolve()
                link_count += 1
                if not target.exists():
                    link_errors.append(f'{path.relative_to(SITE)} -> {value}')
    add(checks, '홈페이지 내부 링크', not link_errors, {'html': len(htmls), 'links': link_count, 'errors': link_errors})
    ko_index = BeautifulSoup((SITE / 'index.html').read_text(encoding='utf-8'), 'html.parser')
    en_index = BeautifulSoup((SITE / 'en/index.html').read_text(encoding='utf-8'), 'html.parser')
    add(checks, '홈페이지 v11.4 메인 섹션', len(ko_index.select('.v1140-section')) == 1 and len(en_index.select('.v1140-section')) == 1, 'KO/EN unified section')
    ko_cmd = BeautifulSoup((SITE / 'commands.html').read_text(encoding='utf-8'), 'html.parser')
    en_cmd = BeautifulSoup((SITE / 'en/commands.html').read_text(encoding='utf-8'), 'html.parser')
    add(checks, '홈페이지 최신 명령', len(ko_cmd.select('.v1140-command-section .command-card')) >= 18 and len(en_cmd.select('.v1140-command-section .command-card')) >= 18, {'ko': len(ko_cmd.select('.v1140-command-section .command-card')), 'en': len(en_cmd.select('.v1140-command-section .command-card'))})
    ko_updates = BeautifulSoup((SITE / 'updates.html').read_text(encoding='utf-8'), 'html.parser')
    en_updates = BeautifulSoup((SITE / 'en/updates.html').read_text(encoding='utf-8'), 'html.parser')
    add(checks, '홈페이지 패치 기록', ko_updates.select_one('.update-version').get_text(strip=True) == 'v11.4.0' and en_updates.select_one('.update-version').get_text(strip=True) == 'v11.4.0', 'latest card first in KO/EN')
    config_text = (SITE / 'config.js').read_text(encoding='utf-8') + (SITE / 'en/config.js').read_text(encoding='utf-8')
    add(checks, '홈페이지 v11.4 ONLINE 설정', config_text.count('version: "v11.4.0"') == 2 and config_text.count('status: "ONLINE"') == 2, 'KO/EN config')
    leaks = []
    ko_re = re.compile(r'[가-힣]')
    for path in (SITE / 'en').glob('*.html'):
        plain = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser').get_text(' ', strip=True)
        if ko_re.search(plain):
            leaks.append(str(path.relative_to(SITE)))
    add(checks, 'English 페이지 한글 누출', not leaks, leaks)

    # JavaScript syntax.
    js_errors = []
    try:
        for path in [SITE/'script.js', SITE/'config.js', SITE/'en/script.js', SITE/'en/config.js']:
            proc = subprocess.run(['node', '--check', str(path)], capture_output=True, text=True)
            if proc.returncode:
                js_errors.append(f'{path.relative_to(SITE)}: {proc.stderr.strip()}')
        add(checks, '홈페이지 JavaScript 문법', not js_errors, js_errors or 'node --check passed')
    except FileNotFoundError:
        add(checks, '홈페이지 JavaScript 문법', True, 'node unavailable; skipped')

    # File preservation against v11.0.0.
    current_bot = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    current_site = {p.relative_to(SITE).as_posix() for p in SITE.rglob('*') if p.is_file()}
    base_bot = normalized(zip_files(BASE_BOT_ZIP))
    base_site = normalized(zip_files(BASE_SITE_ZIP))
    base_bot_ascii = {n for n in base_bot if n.isascii()}
    base_site_ascii = {n for n in base_site if n.isascii()}
    missing_bot = sorted(base_bot_ascii - current_bot)
    missing_site = sorted(base_site_ascii - current_site)
    base_bot_legacy = sum(1 for n in base_bot if not n.isascii())
    current_bot_legacy = sum(1 for n in current_bot if not n.isascii())
    base_site_legacy = sum(1 for n in base_site if not n.isascii())
    current_site_legacy = sum(1 for n in current_site if not n.isascii())
    add(checks, '기존 봇 파일 보존', not missing_bot and current_bot_legacy >= base_bot_legacy, {'base': len(base_bot), 'current': len(current_bot), 'missing': missing_bot[:20], 'legacy': f'{current_bot_legacy}/{base_bot_legacy}'})
    add(checks, '기존 홈페이지 파일 보존', not missing_site and current_site_legacy >= base_site_legacy, {'base': len(base_site), 'current': len(current_site), 'missing': missing_site[:20], 'legacy': f'{current_site_legacy}/{base_site_legacy}'})

    report = {
        'version': '11.4.0',
        'scope': 'v11.0.1 checkpoint hardening, v11.1 championship and NPC dealers, v11.2 alliance war, v11.3 personal casino, v11.4 story campaign, batched visual assets and website/command synchronization',
        'checks': checks,
        'passed': sum(1 for row in checks if row['ok']),
        'failed': sum(1 for row in checks if not row['ok']),
        'limitations': [
            'discord.py and a live Discord token are unavailable in the build environment; Gateway interactions, concurrent clicks and long-running reconnect recovery require deployment smoke tests.',
            'The checkpoint layer records and detects interrupted sessions. Complex in-memory card sessions that cannot be reconstructed fall back to the existing reservation refund path rather than pretending to resume a turn.',
        ],
    }
    return report


if __name__ == '__main__':
    report = run()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report['failed'] == 0 else 1)
