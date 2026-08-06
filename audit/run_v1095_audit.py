from __future__ import annotations

import ast
import json
import py_compile
import re
from collections import defaultdict
from io import BytesIO
from pathlib import Path

from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT.parent / 'site'


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
                for kw in dec.keywords:
                    if kw.arg == 'name' and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        name = kw.value.value
                    elif kw.arg == 'aliases' and isinstance(kw.value, (ast.List, ast.Tuple)):
                        aliases = [e.value for e in kw.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                for value in [name, *aliases]:
                    access[value.casefold()].append(f'{path.relative_to(ROOT)}:{node.lineno}')
                break
    return declarations, access


def run():
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from apocalypse_bot.commands.v1095_visual_polish import render_live_board, render_replay_timeline, render_session_media

    class PokerSession:
        locale='ko'; variant='텍사스홀덤'; game_id='audit'; player_ids=[1,-1]
        names={1:'긴 닉네임 생존자',-1:'ABADDON'}; current_uid=1; pot=180000
        board=[(14,'♠'),(10,'♥'),(7,'♣'),(4,'♦')]
        hands={1:[(13,'♠'),(12,'♠')],-1:[(2,'♦'),(3,'♦')]}
        stage_label='리버 대기'; last_action='ABADDON이 40,000칩 레이즈'; replay=['START','RAISE']; done=False
        class Betting:
            folded=set(); round_bets={1:40000,-1:40000}; current_bet=40000
        betting=Betting()

    checks=[]
    media, ext = render_session_media(PokerSession(), None)
    image = Image.open(media) if media else None
    add(checks, '진행 중 테이블 미디어', media is not None and ext in {'gif','png'}, {'extension': ext, 'size': image.size if image else None})
    add(checks, '턴 GIF 프레임', ext != 'gif' or getattr(image, 'n_frames', 1) >= 3, getattr(image, 'n_frames', 1) if image else 0)

    finished=PokerSession(); finished.done=True
    final_media, final_ext=render_session_media(finished,None)
    final_img=Image.open(final_media) if final_media else None
    add(checks,'종료 화면 PNG',final_ext=='png' and final_img and final_img.format=='PNG',final_img.size if final_img else None)

    replay_row={
        'id':'audit-1','game':'고스톱','stake':10**30,
        'players':{'1':'아주 긴 생존자 이름','-1':'ABADDON'},
        'events':[f'[{i:02d}:00] 긴 공개 행동 기록 {i} · 비공개 손패 없음' for i in range(20)],
        'result':'생존자 승리 · 광박 · 피박 · 128배 · +1,000,000칩',
    }
    replay=render_replay_timeline(replay_row,'ko'); replay_img=Image.open(replay)
    add(checks,'리플레이 타임라인 PNG',replay_img.format=='PNG' and replay_img.size==(1280,720),replay_img.size)
    add(checks,'긴 한글 리플레이',len(replay.getvalue())>10000,{'bytes':len(replay.getvalue())})

    live=render_live_board(locale='ko',active_games={123:PokerSession()},live_races={1:{'selected_name':'검은 성가','leader_name':'재의 질주','tick':8}},recent_races=[{'winner':'붉은 안개','net':-10000}])
    live_img=Image.open(live)
    add(checks,'카드·경마 실시간 보드',live_img.format=='PNG' and live_img.size==(1280,720),live_img.size)

    safe=(ROOT/'apocalypse_bot/commands/v651_card_games.py').read_text(encoding='utf-8')
    authentic=(ROOT/'apocalypse_bot/commands/v1060_authentic_card_games.py').read_text(encoding='utf-8')
    race=(ROOT/'apocalypse_bot/commands/v1092_visual_status_horserace.py').read_text(encoding='utf-8')
    patch=(ROOT/'apocalypse_bot/commands/v1095_gameplay_polish_patch.py').read_text(encoding='utf-8')
    visual=(ROOT/'apocalypse_bot/commands/v1095_visual_polish.py').read_text(encoding='utf-8')
    core=(ROOT/'apocalypse_bot/core/bot.py').read_text(encoding='utf-8')

    add(checks,'미디어 재시도', 'for delay in (0.0, 0.65)' in safe, '2 attempts')
    add(checks,'임베드 자동 복구','Final recovery path' in safe and '_v1095_embed_fallbacks' in safe,'media failure → embed-only')
    add(checks,'최종 결과 새 메시지 복구','render_session_media' in authentic and 'channel.send(embed=embed' in authentic,'final result fallback')
    add(checks,'공개 행동 기록','_v1095_visual_history' in safe,'private cards excluded')
    add(checks,'리플레이 비공개 패 차단','getattr(session, "hands"' not in visual.split('def render_replay_timeline',1)[1].split('def render_live_board',1)[0],'replay renderer does not access hands')
    add(checks,'경마 상태 시작','LIVE_RACE_STATES[self.owner_id]' in race and '"status": "starting"' in race,'starting state')
    add(checks,'경마 상태 틱','"leader_name"' in race and '"status": "racing"' in race,'tick/leader')
    add(checks,'경마 상태 정리','LIVE_RACE_STATES.pop(self.owner_id, None)' in race,'finally cleanup')
    add(checks,'이미지 관전 콜백','send_spectator_image' in patch and 'render_session_media(session, embed)' in patch,'public table media')
    add(checks,'최신 테스트 범위','v10.9.5에서 바꾼 턴 연출' in patch and 'test_command.callback = v1095_test' in patch,'latest patch only')
    add(checks,'최신 패치노트','v1095_patch_notes' in patch and 'patch_notes.callback = v1095_patch_notes' in patch,'v10.9.5')
    add(checks,'최종 등록 순서',core.index('register_v1095_gameplay_polish_patch') < core.index('synchronize_all_english_aliases'),'before English alias sync')

    py_errors=[]
    py_files=list(ROOT.rglob('*.py'))
    for path in py_files:
        try: py_compile.compile(str(path),doraise=True)
        except Exception as exc: py_errors.append(f'{path.relative_to(ROOT)}: {exc}')
    add(checks,'Python 전체 컴파일',not py_errors,{'files':len(py_files),'errors':py_errors})

    declarations, access=command_access()
    new_names=['실시간보드','liveboard','gameliveboard','livestatusboard','리플레이이미지','replayimage','visualreplay','연출검수','polishaudit','visualpolishaudit','gamefxaudit']
    conflicts={name:access[name.casefold()] for name in new_names if len(access[name.casefold()])!=1}
    add(checks,'신규 명령 접근 이름',not conflicts,{'declarations':declarations,'conflicts':conflicts})

    htmls=list(SITE.glob('*.html'))+list((SITE/'en').glob('*.html'))
    link_errors=[]; link_count=0
    for path in htmls:
        soup=BeautifulSoup(path.read_text(encoding='utf-8'),'html.parser')
        for tag, attr in [('a','href'),('img','src'),('script','src'),('link','href')]:
            for node in soup.find_all(tag):
                value=node.get(attr)
                if not value or value.startswith(('#','http:','https:','mailto:','javascript:','data:')): continue
                target=(path.parent/value.split('?',1)[0].split('#',1)[0]).resolve(); link_count+=1
                if not target.exists(): link_errors.append(f'{path.relative_to(SITE)} -> {value}')
    add(checks,'홈페이지 내부 링크',not link_errors,{'html':len(htmls),'links':link_count,'errors':link_errors})

    ko_re=re.compile(r'[가-힣]')
    leaks=[]
    for path in (SITE/'en').glob('*.html'):
        plain=BeautifulSoup(path.read_text(encoding='utf-8'),'html.parser').get_text(' ',strip=True)
        if ko_re.search(plain): leaks.append(str(path.relative_to(SITE)))
    add(checks,'English 페이지 한글 누출',not leaks,leaks)

    previews=list((SITE/'assets/v1095').glob('*'))
    add(checks,'홈페이지 미리보기 3종',len(previews)==3 and all(p.stat().st_size>10000 for p in previews),[p.name for p in previews])
    configs=(SITE/'config.js').read_text(encoding='utf-8')+(SITE/'en/config.js').read_text(encoding='utf-8')
    add(checks,'홈페이지 버전 동기화',configs.count('v10.9.5')>=2,'ko/en config')

    old_bot=ROOT.parent.parent/'v1094_work'/'bot'
    old_site=ROOT.parent.parent/'v1094_work'/'site'
    # The audit also works after the work folder is relocated; only check when sources are present.
    if old_bot.exists() and old_site.exists():
        for label, old, new in [('봇',old_bot,ROOT),('홈페이지',old_site,SITE)]:
            old_files={p.relative_to(old).as_posix() for p in old.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
            new_files={p.relative_to(new).as_posix() for p in new.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
            missing=sorted(old_files-new_files)
            add(checks,f'기존 {label} 파일 보존',not missing,{'old':len(old_files),'new':len(new_files),'missing':missing})

    report={
        'version':'10.9.5',
        'scope':'active-turn media, media fallback, replay PNG, image spectating, card/racing live board, website sync',
        'checks':checks,
        'passed':sum(1 for row in checks if row['ok']),
        'failed':sum(1 for row in checks if not row['ok']),
    }
    return report


if __name__=='__main__':
    report=run()
    print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(0 if report['failed']==0 else 1)
