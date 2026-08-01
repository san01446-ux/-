from __future__ import annotations

import ast
import copy
import json
import os
import py_compile
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import discord
from discord.ext import commands

VERSION = "6.4.1"
KST = timezone(timedelta(hours=9))

THEMES: Dict[str, Dict[str, Any]] = {
    "검은성당": {
        "emoji": "🕯️", "title": "검은 성당", "color": 0x6C3B73,
        "tagline": "침묵 속에서 신호를 지키는 생존 성역",
        "briefing": "낮은 조명과 차분한 경보 문구를 사용하는 정통 ABADDON 테마입니다.",
    },
    "폐허도시": {
        "emoji": "🏙️", "title": "폐허 도시", "color": 0x7A5943,
        "tagline": "무너진 도심을 거점으로 삼은 전투 생존 테마",
        "briefing": "작전·탐색·거래 안내를 거칠고 실용적인 문구로 정리합니다.",
    },
    "격리연구소": {
        "emoji": "🧪", "title": "격리 연구소", "color": 0x2A7F78,
        "tagline": "감염 수치와 표본을 추적하는 연구 거점",
        "briefing": "날씨·감염·무전·장비 상태를 계측 보고서처럼 표시합니다.",
    },
    "황혼전초기지": {
        "emoji": "🏕️", "title": "황혼 전초기지", "color": 0xB0783C,
        "tagline": "생활과 기지 성장을 중심으로 한 개척 테마",
        "briefing": "채집·기지·보급선·시장 정보를 한눈에 확인하기 좋습니다.",
    },
    "종말방송국": {
        "emoji": "📻", "title": "종말 방송국", "color": 0x425D8C,
        "tagline": "끊어진 통신망을 다시 잇는 서버 이벤트 테마",
        "briefing": "SOS·날씨·공개 작전·서버 알림을 방송 속보 형식으로 정리합니다.",
    },
}
DEFAULT_THEME = "검은성당"

STABILITY_GUIDE = {
    "id": "stability_theme",
    "emoji": "🧰",
    "title": "안정화 / 서버 테마",
    "hint": "통합 점검, 오늘 할 일, 서버 브리핑, 텍스트형 테마",
    "commands": [
        "!안정화상태 — 현재 버전·데이터·명령어·텍스트 우선 정책 확인",
        "!오늘할일 — 출석·운세·퀴즈·생활·전투 추천 체크리스트",
        "!서버브리핑 — 날씨·위험구역·보급선·기지방어를 한 화면에 요약",
        "!서버테마 — 서버 테마 목록과 현재 설정 확인",
        "!서버테마미리보기 [테마명] — 텍스트형 테마를 적용 전 확인",
        "!서버테마설정 테마명 — 관리자가 서버 브리핑 테마 변경",
        "!데이터백업 — 관리자가 현재 생존 데이터를 수동 백업",
        "!테스트 상세 — 명령어·가이드·데이터·이미지 정책 통합 진단",
    ],
}

EXPECTED_RECENT_COMMANDS: Tuple[str, ...] = (
    # v6.3.7
    "날씨", "무전", "무전해독", "SOS", "내구도", "무기수리", "개조목록", "개조부품제작",
    "무기개조", "개조해제", "까마귀", "까마귀구매", "위험구역", "오늘의운세", "랜덤박스",
    # v6.3.8
    "괴질탈출", "비상주파수", "지뢰찾기", "돌연변이경주", "돌연변이배팅", "오염문",
    "비상보급상자", "선물거래", "괴수투기장", "영혼결투", "벙커개설", "금고개설",
    "하이에나", "생물테러준비",
    # v6.3.9
    "다크존", "다크존진입", "다크존탐색", "다크존탈출", "밀수품운반", "보급선",
    "보급선수색", "고철갈갈이", "장비갈갈이", "우편함", "받기", "알림설정",
    # v6.4.0
    "미니게임", "반응속도", "기억회로", "생존자레이스",
    # v6.4.1
    "안정화상태", "오늘할일", "서버브리핑", "서버테마", "서버테마미리보기", "서버테마설정", "데이터백업",
)

TEXT_FIRST_MODULES: Tuple[str, ...] = (
    "v631_life_visuals.py", "v632_life_visuals.py", "v633_equipment_crafting.py",
    "v634_equipment_menu.py", "v634_pet_visuals.py", "v635_visuals.py",
    "v39_casino.py", "v432_forge_live.py", "v639_frontier_operations.py",
)


def _now_kst() -> datetime:
    return datetime.now(timezone.utc).astimezone(KST)


def _today() -> str:
    return _now_kst().strftime("%Y-%m-%d")


def _guild_id(ctx: commands.Context) -> int:
    return int(ctx.guild.id) if ctx.guild else 0


def _root_state(world_data: Dict[str, Any]) -> Dict[str, Any]:
    root = world_data.setdefault("v641", {})
    if not isinstance(root, dict):
        root = {}
        world_data["v641"] = root
    root.setdefault("schema_version", 1)
    root.setdefault("guilds", {})
    return root


def _guild_state(world_data: Dict[str, Any], guild_id: int) -> Dict[str, Any]:
    root = _root_state(world_data)
    guilds = root.setdefault("guilds", {})
    state = guilds.setdefault(str(guild_id), {})
    if not isinstance(state, dict):
        state = {}
        guilds[str(guild_id)] = state
    state.setdefault("theme", DEFAULT_THEME)
    state.setdefault("text_first", True)
    return state


def _theme_key(raw: str) -> Optional[str]:
    token = str(raw or "").strip().replace(" ", "")
    if token in THEMES:
        return token
    lowered = token.lower()
    for key, info in THEMES.items():
        if lowered in {key.lower(), str(info["title"]).replace(" ", "").lower()}:
            return key
    return None


def _theme(world_data: Dict[str, Any], guild_id: int) -> Tuple[str, Dict[str, Any]]:
    state = _guild_state(world_data, guild_id)
    key = str(state.get("theme", DEFAULT_THEME))
    if key not in THEMES:
        key = DEFAULT_THEME
        state["theme"] = key
    return key, THEMES[key]


def _normalize_guide(text: str) -> str:
    return "".join(ch for ch in str(text).lower() if ch not in " `!/·-—[]()")


def update_command_guide(guide: List[Dict[str, Any]]) -> None:
    guide[:] = [category for category in guide if category.get("id") != STABILITY_GUIDE["id"]]
    server_index = next((i for i, category in enumerate(guide) if category.get("id") == "server"), len(guide))
    guide.insert(server_index, copy.deepcopy(STABILITY_GUIDE))

    # 같은 설명 문구가 여러 최상위 카테고리에 겹치지 않게 정리합니다.
    seen: set[str] = set()
    for category in guide:
        rows: List[str] = []
        for row in category.get("commands", []):
            key = _normalize_guide(row)
            if not key or key in seen:
                continue
            seen.add(key)
            rows.append(str(row))
        category["commands"] = rows


def _guide_tokens(guide: Sequence[Mapping[str, Any]]) -> set[str]:
    tokens: set[str] = set()
    for category in guide:
        for row in category.get("commands", []):
            text = str(row)
            for part in text.replace("/", " ").split():
                if part.startswith("!"):
                    tokens.add(part[1:].split("[")[0].split("—")[0].strip())
    return {token for token in tokens if token}


def _runtime_duplicate_tokens(bot: commands.Bot) -> List[str]:
    seen: Dict[str, str] = {}
    duplicates: List[str] = []
    for command in bot.walk_commands():
        if command.parent is not None:
            continue
        names = [command.name, *getattr(command, "aliases", [])]
        for name in names:
            token = str(name).lower()
            owner = command.qualified_name
            if token in seen and seen[token] != owner:
                duplicates.append(f"{token}: {seen[token]} / {owner}")
            else:
                seen[token] = owner
    return sorted(set(duplicates))


def _format_seconds(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, sec = divmod(rem, 60)
    if hours:
        return f"{hours}시간 {minutes}분"
    if minutes:
        return f"{minutes}분 {sec}초"
    return f"{sec}초"


def _backup_data_file(data_file: str, *, keep: int = 5) -> Path:
    source = Path(data_file)
    if not source.is_file():
        raise FileNotFoundError("아직 저장된 생존 데이터 파일이 없습니다.")
    backup_dir = source.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = _now_kst().strftime("%Y%m%d_%H%M%S")
    target = backup_dir / f"{source.stem}_{stamp}{source.suffix or '.json'}"
    shutil.copy2(source, target)
    backups = sorted(backup_dir.glob(f"{source.stem}_*{source.suffix or '.json'}"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[max(1, int(keep)):]:
        try:
            old.unlink()
        except OSError:
            pass
    return target


def register_v641_stabilization(
    bot: commands.Bot,
    get_user: Callable[[int], Dict[str, Any]],
    check_registered: Callable[[commands.Context], Any],
    save_data: Callable[[], None],
    world_data: Dict[str, Any],
    user_data: Mapping[str, Dict[str, Any]],
    guide: List[Dict[str, Any]],
    *,
    data_file: str,
) -> None:
    _root_state(world_data)
    update_command_guide(guide)

    async def require_admin(ctx: commands.Context) -> bool:
        if ctx.guild is None or not isinstance(ctx.author, discord.Member):
            await ctx.send("⚠️ 서버에서만 사용할 수 있습니다.")
            return False
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("⚠️ 서버 관리자만 사용할 수 있습니다.")
            return False
        return True

    @bot.command(name="안정화상태", aliases=["안정화", "봇상태점검"])
    async def stabilization_status(ctx: commands.Context) -> None:
        key, theme = _theme(world_data, _guild_id(ctx))
        embed = discord.Embed(
            title="🧰 ABADDON v6.4.1 안정화 상태",
            description="신규 이미지 대신 텍스트·이모지 중심으로 동작하며, **월드보스 이미지만 유지**합니다.",
            color=int(theme["color"]),
        )
        embed.add_field(name="서버 테마", value=f"{theme['emoji']} **{theme['title']}** (`{key}`)", inline=True)
        embed.add_field(name="명령어", value=f"등록 **{len(list(bot.walk_commands()))}개** · 가이드 **{len(guide)}/25**", inline=True)
        embed.add_field(name="데이터", value=f"생존자 **{len(user_data):,}명** · 원자적 저장/백업 보호", inline=True)
        embed.add_field(name="빠른 진단", value="`!테스트 상세`", inline=False)
        embed.set_footer(text="이미지 정책: 월드보스 제외 텍스트 우선 · 기존 데이터와 경제 수치는 유지")
        await ctx.send(embed=embed)

    @bot.command(name="오늘할일", aliases=["오늘뭐하지", "일일체크"])
    async def today_tasks(ctx: commands.Context) -> None:
        if not await check_registered(ctx):
            return
        user = get_user(ctx.author.id)
        today = _today()
        legacy_today = datetime.now().strftime("%Y-%m-%d")
        valid_dates = {today, legacy_today}
        attendance_done = str(user.get("last_attendance", "")) in valid_dates
        fortune = user.get("daily_fortune")
        fortune_done = isinstance(fortune, Mapping) and str(fortune.get("date")) in valid_dates
        quiz = user.get("daily_quiz")
        quiz_done = isinstance(quiz, Mapping) and str(quiz.get("date")) in valid_dates and bool(quiz.get("solved"))
        daily_quest = user.get("daily_quest")
        quest_done = isinstance(daily_quest, Mapping) and bool(
            daily_quest.get("claimed") or int(daily_quest.get("progress", 0) or 0) >= int(daily_quest.get("target", 1) or 1)
        )
        rows = [
            f"{'✅' if attendance_done else '⬜'} 출석 — `!출석`",
            f"{'✅' if fortune_done else '⬜'} 오늘의 운세 — `!오늘의 운세`",
            f"{'✅' if quiz_done else '⬜'} 오늘의 퀴즈 — `!오늘의퀴즈`",
            f"{'✅' if quest_done else '⬜'} 일일 퀘스트 — `!일일퀘스트`",
            "🌿 생활 루틴 — `!채집` `!낚시` `!광산` 중 선택",
            "⚔️ 전투 루틴 — `!던전 보통` 또는 `!전투 보통`",
            "📻 세계 확인 — `!서버브리핑`",
        ]
        done = sum((attendance_done, fortune_done, quiz_done, quest_done))
        embed = discord.Embed(
            title=f"📋 {ctx.author.display_name}님의 오늘 할 일",
            description="\n".join(rows),
            color=discord.Color.dark_teal(),
        )
        embed.add_field(name="핵심 일일 진행", value=f"**{done}/4 완료**", inline=True)
        embed.add_field(name="안내", value="체크는 보상을 강제로 수령하지 않고 현재 기록만 읽습니다.", inline=False)
        await ctx.send(embed=embed)

    @bot.command(name="서버브리핑", aliases=["세계브리핑", "오늘의서버"])
    async def server_briefing(ctx: commands.Context) -> None:
        guild_id = _guild_id(ctx)
        key, theme = _theme(world_data, guild_id)
        from apocalypse_bot.commands.v636_world_combat import get_weather_state
        from apocalypse_bot.commands.v637_dynamic_events import get_hazard_zone
        from apocalypse_bot.commands.v639_frontier_operations import active_supply_drop

        weather = get_weather_state(guild_id)
        hazard = get_hazard_zone(guild_id)
        supply = active_supply_drop(world_data, guild_id)
        defense = world_data.get("base_defense_raids", {}).get(str(guild_id), {})
        if isinstance(defense, Mapping) and defense:
            hp = int(defense.get("hp", 0) or 0)
            max_hp = max(1, int(defense.get("max_hp", 1) or 1))
            defense_text = f"{defense.get('name', '미확인 군체')} · {hp:,}/{max_hp:,} ({hp / max_hp * 100:.1f}%)"
        else:
            defense_text = "아직 이번 주 방어전 정보 없음 · `!기지방어`로 확인"

        if supply.get("active"):
            supply_text = f"활성 중 · 종료까지 {_format_seconds(int(supply.get('remaining', 0) or 0))}"
        else:
            supply_state = world_data.get("v639", {}).get("guilds", {}).get(str(guild_id), {}).get("supply", {})
            now_utc = datetime.now(timezone.utc)
            upcoming = []
            if isinstance(supply_state, Mapping):
                for raw_time in supply_state.get("schedule", []):
                    try:
                        point = datetime.fromisoformat(str(raw_time))
                        if point.tzinfo is None:
                            point = point.replace(tzinfo=timezone.utc)
                        if point > now_utc:
                            upcoming.append(point)
                    except (TypeError, ValueError):
                        continue
            if upcoming:
                next_time = min(upcoming).astimezone(KST).strftime("%H:%M")
                supply_text = f"비활성 · 다음 예정 **{next_time} KST**"
            else:
                supply_text = "비활성 · 오늘 남은 예정 없음"
        embed = discord.Embed(
            title=f"{theme['emoji']} {theme['title']} · 서버 브리핑",
            description=f"**{theme['tagline']}**\n{theme['briefing']}",
            color=int(theme["color"]),
        )
        embed.add_field(
            name=f"{weather.get('emoji', '🌦️')} 현재 날씨 · {weather.get('name', '미확인')}",
            value=f"{weather.get('desc', '')}\n변경까지 **{_format_seconds(int(weather.get('remaining', 0)))}**",
            inline=False,
        )
        embed.add_field(name="☣️ 돌연변이 위험구역", value=f"**{hazard.get('region', '미확인')}** · 보상 ×{float(hazard.get('reward_mult', 1.0)):.2f}", inline=True)
        embed.add_field(name="🎁 보급선", value=supply_text, inline=True)
        embed.add_field(name="🛡️ 기지 방어", value=defense_text, inline=False)
        embed.set_footer(text=f"테마 키: {key} · 설정: !서버테마설정 테마명 · 텍스트 우선 브리핑")
        await ctx.send(embed=embed)

    @bot.command(name="서버테마", aliases=["테마목록"])
    async def server_theme(ctx: commands.Context) -> None:
        current_key, current = _theme(world_data, _guild_id(ctx))
        lines = []
        for key, info in THEMES.items():
            marker = "✅" if key == current_key else "▫️"
            lines.append(f"{marker} {info['emoji']} **{info['title']}** — `{key}`\n└ {info['tagline']}")
        embed = discord.Embed(
            title="🎨 ABADDON 텍스트형 서버 테마",
            description="\n\n".join(lines),
            color=int(current["color"]),
        )
        embed.add_field(name="적용 범위", value="`!서버브리핑`·안정화 안내·향후 서버 리뉴얼 메시지의 색상과 문구", inline=False)
        embed.add_field(name="관리자 설정", value="`!서버테마설정 검은성당/폐허도시/격리연구소/황혼전초기지/종말방송국`", inline=False)
        await ctx.send(embed=embed)

    @bot.command(name="서버테마미리보기", aliases=["테마미리보기"])
    async def theme_preview(ctx: commands.Context, *, 테마명: str = "") -> None:
        key = _theme_key(테마명) if 테마명 else _theme(world_data, _guild_id(ctx))[0]
        if key is None:
            await ctx.send("⚠️ 테마를 찾지 못했습니다. `!서버테마`에서 목록을 확인하세요.")
            return
        info = THEMES[key]
        embed = discord.Embed(
            title=f"{info['emoji']} {info['title']} · 미리보기",
            description=f"**{info['tagline']}**\n{info['briefing']}",
            color=int(info["color"]),
        )
        embed.add_field(name="📡 속보", value="전자기 교란이 감지되었습니다. 야외 활동 전 `!날씨`를 확인하세요.", inline=False)
        embed.add_field(name="🧭 추천 행동", value="`!서버브리핑` → `!오늘할일` → 원하는 생활/전투 콘텐츠", inline=False)
        embed.set_footer(text="이미지 없이 색상·이모지·문장 구성만 변경됩니다.")
        await ctx.send(embed=embed)

    @bot.command(name="서버테마설정", aliases=["테마설정"])
    async def theme_set(ctx: commands.Context, *, 테마명: str) -> None:
        if not await require_admin(ctx):
            return
        key = _theme_key(테마명)
        if key is None:
            await ctx.send("⚠️ 지원하지 않는 테마입니다. `!서버테마`에서 목록을 확인하세요.")
            return
        state = _guild_state(world_data, _guild_id(ctx))
        state["theme"] = key
        state["updated_at"] = _now_kst().isoformat()
        state["updated_by"] = int(ctx.author.id)
        save_data()
        info = THEMES[key]
        await ctx.send(f"✅ 서버 테마를 {info['emoji']} **{info['title']}**로 변경했습니다. `!서버브리핑`에서 확인하세요.")

    @bot.command(name="데이터백업", aliases=["수동백업"])
    @commands.cooldown(1, 60, commands.BucketType.guild)
    async def data_backup(ctx: commands.Context) -> None:
        if not await require_admin(ctx):
            return
        try:
            save_data()
            target = _backup_data_file(data_file, keep=5)
        except Exception as exc:
            ctx.command.reset_cooldown(ctx)
            await ctx.send(f"❌ 백업에 실패했습니다: `{type(exc).__name__}`")
            return
        await ctx.send(f"✅ 데이터 백업 완료 · `{target.name}`\n최근 백업은 최대 **5개**까지 유지합니다.")

    @bot.command(name="안정화도움말", aliases=["안정화명령어"])
    async def stabilization_help(ctx: commands.Context) -> None:
        category = next((category for category in guide if category.get("id") == STABILITY_GUIDE["id"]), STABILITY_GUIDE)
        embed = discord.Embed(title="🧰 안정화 / 서버 테마", description=category["hint"], color=discord.Color.dark_teal())
        embed.add_field(name="명령어", value="\n".join(f"• `{row}`" for row in category["commands"])[:1024], inline=False)
        await ctx.send(embed=embed)

    previous_test = bot.get_command("테스트")
    if previous_test is not None:
        async def v641_test(ctx: commands.Context, 모드: str = "기본") -> None:
            checks: List[Tuple[str, bool, str]] = []
            command_names: set[str] = set()
            for command in bot.walk_commands():
                if command.parent is not None:
                    continue
                command_names.add(str(command.name).lower())
                command_names.update(str(alias).lower() for alias in getattr(command, "aliases", []))
            missing_commands = [name for name in EXPECTED_RECENT_COMMANDS if str(name).lower() not in command_names]
            checks.append(("최근 패치 명령 등록", not missing_commands, "누락 없음" if not missing_commands else ", ".join(missing_commands[:20])))

            duplicates = _runtime_duplicate_tokens(bot)
            checks.append(("명령·별칭 중복", not duplicates, "충돌 없음" if not duplicates else " / ".join(duplicates[:10])))

            category_ids = [str(category.get("id", "")) for category in guide]
            checks.append(("최상위 카테고리 제한", len(guide) <= 25 and len(category_ids) == len(set(category_ids)), f"{len(guide)}/25 · ID 중복 {len(category_ids) - len(set(category_ids))}개"))

            guide_tokens = _guide_tokens(guide)
            missing_guide = [name for name in EXPECTED_RECENT_COMMANDS if name not in guide_tokens]
            checks.append(("!명령어 최신화", not missing_guide, "최근 기능 전부 노출" if not missing_guide else ", ".join(missing_guide[:20])))

            project_root = Path(__file__).resolve().parents[2]
            py_files = sorted(project_root.rglob("*.py"))
            compile_errors: List[str] = []
            for path in py_files:
                try:
                    py_compile.compile(str(path), doraise=True)
                except Exception as exc:
                    compile_errors.append(f"{path.name}: {type(exc).__name__}")
            checks.append(("Python 전체 컴파일", not compile_errors, f"{len(py_files)}개 통과" if not compile_errors else ", ".join(compile_errors[:8])))

            suspicious: List[str] = []
            for path in py_files:
                try:
                    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                except Exception:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "ebp":
                        suspicious.append(f"{path.name}:{getattr(node, 'lineno', '?')}")
            checks.append(("장비 시작 오류 재발 방지", not suspicious, "ebp(...) 호출 0개" if not suspicious else ", ".join(suspicious)))

            try:
                json.dumps({"users": user_data, "world": world_data}, ensure_ascii=False)
                serializable = True
                serial_detail = "현재 데이터 JSON 직렬화 가능"
            except Exception as exc:
                serializable = False
                serial_detail = f"{type(exc).__name__}: {exc}"
            checks.append(("저장 데이터 구조", serializable, serial_detail))

            parent = Path(data_file).expanduser().resolve().parent
            writable = parent.exists() and os.access(parent, os.W_OK)
            checks.append(("영구 저장 경로", writable, f"{parent} · {'쓰기 가능' if writable else '쓰기 불가/미생성'}"))

            modules_dir = Path(__file__).resolve().parent
            policy_failures: List[str] = []
            for filename in TEXT_FIRST_MODULES:
                path = modules_dir / filename
                if not path.is_file():
                    policy_failures.append(f"{filename}: 없음")
                    continue
                text = path.read_text(encoding="utf-8")
                if "ABADDON_TEXT_FIRST_DISABLED" not in text:
                    policy_failures.append(filename)
            checks.append(("텍스트 우선 연출 정책", not policy_failures, "월드보스 외 게임 이미지 비활성" if not policy_failures else ", ".join(policy_failures)))

            world_boss_root = project_root / "apocalypse_bot" / "assets" / "world_boss"
            boss_images = list(world_boss_root.glob("*.png")) + list(world_boss_root.glob("*.jpg")) + list(world_boss_root.glob("*.webp"))
            checks.append(("월드보스 이미지 예외", bool(boss_images), f"{len(boss_images)}개 유지" if boss_images else "월드보스 이미지 없음"))

            theme_ok = _guild_state(world_data, _guild_id(ctx)).get("theme") in THEMES
            checks.append(("서버 테마 상태", theme_ok, str(_guild_state(world_data, _guild_id(ctx)).get("theme"))))

            failed = sum(1 for _, ok, _ in checks if not ok)
            passed = len(checks) - failed
            embed = discord.Embed(
                title=f"🧪 ABADDON v6.4.1 통합 안정화 테스트 · {passed}/{len(checks)} 통과",
                description="재화·전투·인벤토리를 변경하지 않는 읽기 전용 검사입니다.",
                color=discord.Color.green() if failed == 0 else discord.Color.orange(),
            )
            detailed = str(모드).lower() in {"상세", "전체", "detail", "full"} or failed > 0
            if detailed:
                for name, ok, detail in checks:
                    embed.add_field(name=f"{'✅' if ok else '❌'} {name}", value=str(detail)[:1024], inline=False)
            else:
                embed.add_field(name="결과", value=f"✅ {passed} · ❌ {failed}\n상세: `!테스트 상세`", inline=False)
            embed.set_footer(text="실제 Discord 버튼 동시성·권한·DM 전달은 배포 서버 스모크 테스트가 필요합니다.")
            await ctx.send(embed=embed)

        previous_test.callback = v641_test
        previous_test.help = "v6.4.1 명령어·가이드·데이터·텍스트 우선 정책을 읽기 전용으로 통합 검사합니다."
        previous_test.description = previous_test.help

    patch = bot.get_command("패치노트")
    if patch is not None:
        async def v641_patch_notes(ctx: commands.Context) -> None:
            embed = discord.Embed(
                title="🧰 ABADDON v6.4.1 — 안정화·텍스트 퍼스트",
                description="기존 기능을 전수 점검하고 데이터 저장, 명령어 안내, 오류 추적과 서버 브리핑을 정리했습니다.",
                color=discord.Color.dark_teal(),
            )
            embed.add_field(name="🛡️ 안정화", value="원자적 저장 검증·최근 백업·명령/별칭 충돌 검사·가이드 누락 검사·오류 사건 ID", inline=False)
            embed.add_field(name="📚 명령어 드롭다운", value="신규 **안정화 / 서버 테마** 최상위 카테고리 추가 · v6.3.7~v6.4.1 기능 노출 전수 검사", inline=False)
            embed.add_field(name="🎨 서버 리뉴얼 테마", value="검은 성당·폐허 도시·격리 연구소·황혼 전초기지·종말 방송국 · 이미지 없이 색상과 문구만 변경", inline=False)
            embed.add_field(name="📻 접근성", value="`!오늘할일`·`!서버브리핑`·개선된 오류 사용법 안내로 처음 온 생존자도 다음 행동을 확인", inline=False)
            embed.add_field(name="📝 이미지 정책", value="월드보스 전용 이미지만 유지하고 생활·장비·펫·기지·카지노·재활용은 텍스트·이모지 중심으로 전환", inline=False)
            embed.set_footer(text="최신 버전 v6.4.1 · 월드 시즌 v6.5.0 전 안정화 기반")
            await ctx.send(embed=embed)

        patch.callback = v641_patch_notes
        patch.help = "ABADDON v6.4.1 안정화·텍스트 퍼스트·서버 테마 패치 내용을 확인합니다."
        patch.description = patch.help

    bot.v641_version = VERSION
    bot.v641_themes = THEMES
    bot.v641_text_first = True
    bot.v641_backup_data_file = lambda: _backup_data_file(data_file, keep=5)
