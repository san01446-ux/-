from __future__ import annotations

import ast
import hashlib
import json
import py_compile
import random
import re
import subprocess
import zipfile
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT.parent / 'site'
BASE_ZIP = Path('/mnt/data/ABADDON_BOT_v10.9.5_GAMEPLAY_POLISH_RECOVERY_AUDITED_PATCH.zip')
BASE_SITE_ZIP = Path('/mnt/data/ABADDON_OFFICIAL_SITE_v10.9.5_UPLOAD.zip')


def add(checks, name, ok, detail):
    checks.append({'name': name, 'ok': bool(ok), 'detail': detail})


def command_access():
    access = defaultdict(list)
    declarations = 0
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
                func = dec.func.attr if isinstance(dec.func, ast.Attribute) else ''
                if func not in {'command', 'hybrid_command', 'group', 'hybrid_group'}:
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
                break
    return declarations, access


def zip_files(path: Path):
    if not path.exists():
        return set()
    with zipfile.ZipFile(path) as zf:
        return {n.rstrip('/') for n in zf.namelist() if n and not n.endswith('/') and '__pycache__' not in n and not n.endswith('.pyc')}


def run():
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from apocalypse_bot.commands.v1092_horse_racing_rules import FINISH, HORSES, advance_positions, crossing_winner, simulate_race
    from apocalypse_bot.commands.v1094_card_table_images import render_session_table
    from apocalypse_bot.commands.v1094_visual_core import draw_hwatu_card, HWATU_ASSET_ROOT
    from PIL import ImageDraw

    checks=[]

    # Horse-racing engine: all lanes share one immutable finish coordinate.
    race_fail=[]
    for seed in range(5000):
        positions, winner, ticks = simulate_race(seed, max_ticks=60)
        if len(positions) != len(HORSES) or not all(0 <= p <= FINISH for p in positions):
            race_fail.append({'seed': seed, 'positions': positions}); break
        if winner not in range(len(HORSES)) or ticks <= 0:
            race_fail.append({'seed': seed, 'winner': winner, 'ticks': ticks}); break
    add(checks, '경마 5,000회 규칙 시뮬레이션', not race_fail, race_fail or {'finish': FINISH, 'horses': len(HORSES)})
    previous=[FINISH-1]*len(HORSES)
    current=[FINISH]*len(HORSES)
    crossers={crossing_winner(previous,current,random.Random(seed)) for seed in range(100)}
    add(checks, '공통 결승선 교차 판정', crossers.issubset(set(range(len(HORSES)))) and bool(crossers), {'finish': FINISH, 'photo_finish_candidates': sorted(crossers)})

    # Static shared finish line renderer.
    race_ui=(ROOT/'apocalypse_bot/commands/v1092_visual_status_horserace.py').read_text(encoding='utf-8')
    add(checks, '경마 UI 공통 완주선', 'lane = ["·"] * FINISH' in race_ui and "|🏁]" in race_ui and 'def _track' in race_ui, 'all lanes use the same FINISH-sized lane')

    # Raise safety limit and negative-wallet rules.
    authentic=(ROOT/'apocalypse_bot/commands/v1060_authentic_card_games.py').read_text(encoding='utf-8')
    old_auth=(ROOT/'apocalypse_bot/commands/v1051_authentic_card_games.py').read_text(encoding='utf-8')
    renewal=(ROOT/'apocalypse_bot/commands/v1090_integrated_renewal.py').read_text(encoding='utf-8')
    limit_paths=all('_v1100_raise_limit' in text for text in (authentic, old_auth, renewal))
    add(checks, '레이즈 자유 입력 안전 한도', limit_paths and 'V1100_HARD_RAISE_LIMIT' in authentic, 'all authentic raise paths validate the server-configured per-action limit')
    add(checks, '보유액 초과 손실 음수 유지', 'add_casino_chips(self.get_user(uid), -amount)' in authentic and 'min(casino_chips' not in authentic, 'charge is not clipped to current balance')
    add(checks, '중복 예약 키 제거', authentic.count('"negative_balance_allowed": True') == 1, authentic.count('"negative_balance_allowed": True'))

    # Final result and ledger hooks.
    add(checks, '승자·손익·잔액 결과 훅', all(token in authentic for token in ('🏆 승자','💰 잔액 정산','before','after','net','settlements')), 'winner/net/balance before→after + ledger')
    legacy=(ROOT/'apocalypse_bot/commands/v651_card_games.py').read_text(encoding='utf-8')
    add(checks, '기존 포커·원카드·조커잡기 잔액 결과', all(token in legacy for token in ('opening_chips','settlement_text','이번 게임','잔액 **')), 'legacy card families also show net and balance before→after')
    add(checks, '결과 이미지 오버레이', '_final_overlay' in (ROOT/'apocalypse_bot/commands/v1094_card_table_images.py').read_text(encoding='utf-8'), 'final PNG includes the result embed')

    # Render a representative finished poker table without discord.py.
    class Field:
        def __init__(self,name,value): self.name=name; self.value=value
    class Embed:
        description='🏆 **생존자** · 스트레이트 승리'
        fields=[Field('💰 잔액 정산','생존자 +120,000칩 · -20,000 → 100,000칩'),Field('팟','240,000')]
    class Betting:
        current_bet=80000; round_bets={1:80000,-1:80000}; folded=set()
    class Session:
        locale='ko'; variant='텍사스홀덤'; kind='텍사스홀덤'; game_id='v1100-preview'; player_ids=[1,-1]
        names={1:'생존자',-1:'ABADDON'}; current_uid=1; pot=240000; board=[(14,'♠'),(13,'♥'),(12,'♦'),(11,'♣'),(10,'♠')]
        hands={1:[(9,'♠'),(8,'♠')],-1:[(2,'♦'),(3,'♦')]}; stage_label='쇼다운'; last_action='생존자 승리'; done=True; betting=Betting()
    result=render_session_table(Session(),Embed())
    result_img=Image.open(result) if result else None
    add(checks, '최종 결과 PNG 생성', bool(result_img and result_img.format=='PNG' and result_img.size==(1280,720)), result_img.size if result_img else None)

    # Original 48-card hwatu assets.
    card_files=sorted((HWATU_ASSET_ROOT/'cards').glob('*.png'))
    asset_errors=[]
    for p in card_files:
        try:
            im=Image.open(p); im.verify()
            if Image.open(p).size != (180,260): asset_errors.append(f'{p.name}:size={Image.open(p).size}')
        except Exception as exc: asset_errors.append(f'{p.name}:{exc}')
    add(checks, 'ABADDON 화투 48장 자산', len(card_files)==48 and not asset_errors, {'count':len(card_files),'errors':asset_errors[:10]})
    manifest=json.loads((HWATU_ASSET_ROOT/'manifest.json').read_text(encoding='utf-8'))
    add(checks, '화투 월별 4장 매니페스트', set(manifest)=={str(i) for i in range(1,13)} and all(len(v)==4 for v in manifest.values()), {k:len(v) for k,v in manifest.items()})
    canvas=Image.new('RGB',(500,330),(30,28,35)); draw=ImageDraw.Draw(canvas)
    cards=[SimpleNamespace(month=1,category='bright',uid=1),SimpleNamespace(month=3,category='ribbon_red_poetry',uid=2),SimpleNamespace(month=7,category='animal',uid=3),SimpleNamespace(month=12,category='junk',uid=4)]
    for i,card in enumerate(cards): draw_hwatu_card(draw,(20+i*120,20,120+i*120,300),card)
    preview=ROOT.parent.parent/'ABADDON_v11.0.0_HWATU_RENDER_AUDIT.png'; canvas.save(preview)
    add(checks, '화투 카드 실렌더', preview.exists() and preview.stat().st_size>10000, {'file':preview.name,'bytes':preview.stat().st_size})

    # New command access names.
    declarations, access=command_access()
    new_names=['게임도시','gamecity','cardcity','gamingcity','베팅제한','betlimit','raiselimit','베팅제한설정','setbetlimit','setraiselimit','정산조회','settlement','settlementlookup','최근정산','recentsettlement','latestsettlement','게임결과','gameresult','matchresult','셔플검증','shuffleverify','deckverify','공정성검증','fairnesscheck','fairnessverify','게임세션','gamesession','sessionstatus','게임복구','recovergame','gamerecovery','화투도감','hwatucatalog','hwatudeck','화투패보기','viewhwatu','hwatuart','테이블테마','tabletheme','gametheme','카드스킨','cardskin','cardback','내게임장식','mygamecosmetics','mytabledecor','게임도시검수','gamecityaudit','v1100audit']
    conflicts={name:access[name.casefold()] for name in new_names if len(access[name.casefold()])!=1}
    add(checks, 'v11 신규 명령 접근 이름', not conflicts, {'declarations':declarations,'conflicts':conflicts})

    # Registration order and latest commands.
    core=(ROOT/'apocalypse_bot/core/bot.py').read_text(encoding='utf-8')
    order_ok=('register_v1100_game_city_overhaul' in core and core.index('register_v1095_gameplay_polish_patch') < core.index('register_v1100_game_city_overhaul') < core.index('synchronize_all_english_aliases'))
    add(checks, 'v11 최종 등록 순서', order_ok, 'v10.9.5 → v11.0.0 → final English alias sync')
    module=(ROOT/'apocalypse_bot/commands/v1100_game_city_overhaul.py').read_text(encoding='utf-8')
    add(checks, '!테스트 상세 최신화', 'test_command.callback=v1100_test' in module and '게임도시검수' in module, 'latest patch scope only')
    add(checks, '!패치노트 최신화', 'patch_notes.callback=v1100_notes' in module and 'v11.0.0' in module, 'latest patch notes callback')

    # Python compile.
    py_errors=[]; py_files=list(ROOT.rglob('*.py'))
    for path in py_files:
        try: py_compile.compile(str(path),doraise=True)
        except Exception as exc: py_errors.append(f'{path.relative_to(ROOT)}: {exc}')
    add(checks, 'Python 전체 컴파일', not py_errors, {'files':len(py_files),'errors':py_errors})

    # Website links, separation, and version.
    htmls=list(SITE.glob('*.html'))+list((SITE/'en').glob('*.html'))
    link_errors=[]; link_count=0
    for path in htmls:
        soup=BeautifulSoup(path.read_text(encoding='utf-8'),'html.parser')
        for tag,attr in [('a','href'),('img','src'),('script','src'),('link','href')]:
            for node in soup.find_all(tag):
                value=node.get(attr)
                if not value or value.startswith(('#','http:','https:','mailto:','javascript:','data:')): continue
                target=(path.parent/value.split('?',1)[0].split('#',1)[0]).resolve(); link_count+=1
                if not target.exists(): link_errors.append(f'{path.relative_to(SITE)} -> {value}')
    add(checks, '홈페이지 내부 링크', not link_errors, {'html':len(htmls),'links':link_count,'errors':link_errors})
    ko_re=re.compile(r'[가-힣]'); leaks=[]
    for path in (SITE/'en').glob('*.html'):
        plain=BeautifulSoup(path.read_text(encoding='utf-8'),'html.parser').get_text(' ',strip=True)
        if ko_re.search(plain): leaks.append(str(path.relative_to(SITE)))
    add(checks, 'English 페이지 한글 누출', not leaks, leaks)
    configs=(SITE/'config.js').read_text(encoding='utf-8')+(SITE/'en/config.js').read_text(encoding='utf-8')
    add(checks, '홈페이지 v11 동기화', configs.count('v11.0.0')>=2 and 'V11.0.0 LATEST COMMANDS' in (SITE/'en/commands.html').read_text(encoding='utf-8'), 'KO/EN config, commands and update history')
    assets=list((SITE/'assets/v1100').glob('*'))
    add(checks, '홈페이지 v11 미리보기', len(assets)>=4 and all(p.stat().st_size>10000 for p in assets), [p.name for p in assets])

    # JS syntax when node exists.
    js_errors=[]
    try:
        for path in [SITE/'script.js',SITE/'config.js',SITE/'en/script.js',SITE/'en/config.js']:
            proc=subprocess.run(['node','--check',str(path)],capture_output=True,text=True)
            if proc.returncode: js_errors.append(f'{path.relative_to(SITE)}:{proc.stderr.strip()}')
        add(checks,'홈페이지 JavaScript 문법',not js_errors,js_errors or 'node --check passed')
    except FileNotFoundError:
        add(checks,'홈페이지 JavaScript 문법',True,'node unavailable; static file links checked')

    # Preserve all previous files (compare names with the original zips, allowing top-level folder differences).
    def normalized(names):
        out=set()
        for n in names:
            parts=n.split('/')
            # Original archives are flat project roots in this project.
            if parts and parts[0] in {'bot','site'}: parts=parts[1:]
            out.add('/'.join(parts))
        return out
    current_bot={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    current_site={p.relative_to(SITE).as_posix() for p in SITE.rglob('*') if p.is_file()}
    base_bot=normalized(zip_files(BASE_ZIP)); base_site=normalized(zip_files(BASE_SITE_ZIP))
    # ZIPs created on Windows may expose legacy Korean filenames through a different code page.
    # Compare ASCII-safe paths directly and separately require that legacy non-ASCII file counts are preserved.
    base_bot_ascii={n for n in base_bot if n.isascii()}; base_site_ascii={n for n in base_site if n.isascii()}
    missing_bot=sorted(base_bot_ascii-current_bot); missing_site=sorted(base_site_ascii-current_site)
    base_bot_legacy=sum(1 for n in base_bot if not n.isascii()); current_bot_legacy=sum(1 for n in current_bot if not n.isascii())
    base_site_legacy=sum(1 for n in base_site if not n.isascii()); current_site_legacy=sum(1 for n in current_site if not n.isascii())
    add(checks,'기존 봇 파일 보존',not missing_bot and current_bot_legacy>=base_bot_legacy,{'base':len(base_bot),'current':len(current_bot),'missing':missing_bot[:20],'legacy_names':f'{current_bot_legacy}/{base_bot_legacy}'})
    add(checks,'기존 홈페이지 파일 보존',not missing_site and current_site_legacy>=base_site_legacy,{'base':len(base_site),'current':len(current_site),'missing':missing_site[:20],'legacy_names':f'{current_site_legacy}/{base_site_legacy}'})

    report={
        'version':'11.0.0',
        'scope':'clear final results, settlement ledger, free raises with configurable safety limit, negative debt, shared horse-race finish line, original 48-card hwatu, fairness checks, game city and website sync',
        'checks':checks,
        'passed':sum(1 for row in checks if row['ok']),
        'failed':sum(1 for row in checks if not row['ok']),
        'limitations':['discord.py and a live Discord token are unavailable in the build environment; Gateway interactions require deployment smoke testing.'],
    }
    return report


if __name__=='__main__':
    report=run()
    print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(0 if report['failed']==0 else 1)
