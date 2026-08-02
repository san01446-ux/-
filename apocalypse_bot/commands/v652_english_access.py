from __future__ import annotations

import copy
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import discord
from discord.ext import commands

VERSION = "6.5.3"
PATCH_DATE = "2026-08-02"

# Prefix-command aliases only. Existing Korean command objects and callbacks are reused,
# so balances, cooldowns, permissions, and save behavior stay exactly the same.
ENGLISH_ALIASES: Dict[str, Tuple[str, ...]] = {
    # start / profile
    "가입": ("register", "signup"),
    "튜토리얼": ("tutorial",),
    "정보": ("profile", "userinfo"),
    "지갑": ("wallet",),
    "상태": ("status",),
    "랭킹": ("ranking", "rankings"),
    "출석": ("daily", "checkin"),
    "돈주세요": ("aid", "support"),
    "훈련": ("train",),
    "휴식": ("rest",),
    "오늘할일": ("today", "dailytasks"),
    "오늘의운세": ("fortune",),
    "봇소개": ("botinfo", "aboutbot"),
    "패치노트": ("patchnotes", "updates"),
    "명령어": ("commands", "help", "guide"),
    "테스트": ("test", "diagnostics"),

    # life / exploration
    "알바": ("work", "job"),
    "채집": ("gather",),
    "낚시": ("fish", "fishing"),
    "벌목": ("woodcut", "logging"),
    "광산": ("mine", "mining"),
    "땅파기": ("dig",),
    "코인탐색": ("coinsearch",),
    "보물감정": ("appraise",),
    "보물함": ("treasures",),
    "감정사": ("appraisers",),
    "무전": ("radio",),
    "무전해독": ("decoderadio",),
    "날씨": ("weather",),
    "위험구역": ("hazardzone",),
    "랜덤박스": ("lootbox",),

    # equipment / crafting
    "상점": ("shop",),
    "장비": ("equipment", "gear"),
    "장비목록": ("gearlist",),
    "인벤토리": ("inventory", "inv"),
    "구매": ("buy",),
    "강화": ("enhance", "upgradegear"),
    "강화정보": ("enhanceinfo",),
    "보호강화": ("safeenhance",),
    "강화기록": ("enhancelog",),
    "장비외형": ("gearvisual", "equipmentvisual"),
    "재료": ("materials",),
    "제작목록": ("craftlist",),
    "제작": ("craft",),
    "내구도": ("durability",),
    "무기수리": ("repairweapon", "repair"),
    "개조목록": ("mods", "modlist"),
    "무기개조": ("modweapon",),
    "개조해제": ("unmod",),
    "고철갈갈이": ("scrap", "scrapmaterials"),
    "장비갈갈이": ("scrapgear",),

    # combat
    "괴물목록": ("monsters",),
    "던전": ("dungeon",),
    "던전전술": ("tacticaldungeon",),
    "전투": ("battle", "combat"),
    "전투상태": ("battlestatus",),
    "전투포기": ("surrender",),
    "지역목록": ("regions",),
    "지역정보": ("regioninfo",),
    "지역이동": ("travel",),
    "지역탐색": ("explore",),
    "레이드": ("raid",),
    "월드보스": ("worldboss",),
    "월드보스공격": ("worldbossattack",),
    "월드보스기여도": ("worldbosscontribution",),

    # economy
    "거래소": ("market", "exchange"),
    "거래검색": ("marketsearch",),
    "판매": ("sell",),
    "은행": ("bank",),
    "입금": ("deposit",),
    "출금": ("withdraw",),
    "대출": ("loan",),
    "상환": ("repay",),
    "자원시장": ("resourcemarket",),
    "자원구매": ("buyresource",),
    "자원판매": ("sellresource",),

    # casino / minigames / cards
    "카지노": ("casino",),
    "블랙잭": ("blackjack",),
    "슬롯": ("slots",),
    "룰렛": ("roulette",),
    "미니게임": ("minigames",),
    "지뢰찾기": ("minesweeper",),
    "반응속도": ("reactiongame",),
    "기억회로": ("memorygame",),
    "생존자레이스": ("survivorrace", "racing"),
    "카드게임": ("cardgames", "cards"),
    "포커": ("poker",),
    "원카드": ("onecard",),
    "조커잡기": ("jokercatch",),

    # story / pets / base / server
    "스토리": ("story",),
    "원정": ("expedition",),
    "펫": ("pet", "pets"),
    "펫정보": ("petinfo",),
    "펫훈련": ("pettrain",),
    "펫진화": ("petevolve",),
    "기지": ("base", "basestatus"),
    "기지건설": ("buildbase",),
    "기지강화": ("upgradebase",),
    "기지수확": ("baseharvest",),
    "기지방어": ("basedefense",),
    "서버테마": ("themes", "serverthemes"),
    "서버브리핑": ("briefing", "serverbriefing"),
    "서버리뉴얼": ("serverrenewal",),
    "안정화상태": ("stability",),
}

ENGLISH_GUIDE = {
    "id": "english_commands",
    "emoji": "🌐",
    "title": "English Commands / 영문 명령어",
    "hint": "기존 한국어 명령은 유지되며 동일 기능의 영문 별칭을 제공합니다.",
    "commands": [
        "!english / !enhelp — 영문 명령어 카테고리 안내",
        "기본: !help · !commands · !botinfo · !today · !profile · !wallet",
        "생활: !work · !gather · !fish · !woodcut · !mine · !dig · !appraise",
        "장비: !equipment · !inventory · !enhance · !craft · !repair · !scrap",
        "전투: !dungeon · !battle · !regions · !explore · !raid · !worldboss",
        "경제: !market · !sell · !bank · !deposit · !withdraw · !resourcemarket",
        "펫/기지: !pet · !petinfo · !petevolve · !base · !buildbase · !upgradebase",
        "게임: !minigames · !minesweeper · !cardgames · !poker · !onecard · !jokercatch",
        "서버: !themes · !briefing · !serverrenewal · !stability · !diagnostics",
    ],
}

ENGLISH_SECTIONS: Dict[str, Tuple[str, ...]] = {
    "General / 기본": ("help", "commands", "botinfo", "today", "profile", "wallet", "daily"),
    "Life / 생활": ("work", "gather", "fish", "woodcut", "mine", "dig", "appraise", "weather"),
    "Equipment / 장비": ("equipment", "inventory", "enhance", "craft", "durability", "repair", "scrap"),
    "Combat / 전투": ("dungeon", "tacticaldungeon", "battle", "regions", "explore", "raid", "worldboss"),
    "Pets & Base / 펫·기지": ("pet", "petinfo", "pettrain", "petevolve", "base", "buildbase", "upgradebase"),
    "Games / 게임": ("minigames", "minesweeper", "reactiongame", "cardgames", "poker", "onecard", "jokercatch"),
    "Server / 서버": ("themes", "briefing", "serverrenewal", "stability", "diagnostics"),
}


def _add_alias(bot: commands.Bot, command_name: str, alias: str) -> Tuple[bool, str]:
    command = bot.get_command(command_name)
    if command is None:
        return False, "missing-target"
    current = bot.get_command(alias)
    if current is not None and current is not command:
        return False, f"collision:{current.qualified_name}"
    if alias not in command.aliases:
        command.aliases.append(alias)
    # Prefix parser looks up aliases in the parent's command map.
    if command.parent is None:
        bot.all_commands[alias] = command
    else:
        command.parent.all_commands[alias] = command
    return True, "registered"


def _update_guide(guide: List[Dict[str, Any]]) -> None:
    guide[:] = [row for row in guide if row.get("id") != ENGLISH_GUIDE["id"]]
    # Put English access near the beginning while retaining every existing category.
    insert_at = min(1, len(guide))
    guide.insert(insert_at, copy.deepcopy(ENGLISH_GUIDE))


def register_v652_english_access(
    bot: commands.Bot,
    guide: List[Dict[str, Any]],
) -> None:
    _update_guide(guide)
    registered: Dict[str, List[str]] = {}
    skipped: Dict[str, str] = {}
    for korean, aliases in ENGLISH_ALIASES.items():
        for alias in aliases:
            ok, reason = _add_alias(bot, korean, alias)
            if ok:
                registered.setdefault(korean, []).append(alias)
            else:
                skipped[f"{korean}:{alias}"] = reason

    # The project already had an older !help alias. Route it to the current searchable
    # command browser so English users do not see an outdated menu.
    legacy_help = bot.get_command("help")
    latest_help = bot.get_command("명령어")
    if legacy_help is not None and latest_help is not None and legacy_help is not latest_help:
        async def v652_latest_help(ctx: commands.Context, *, category: str = "") -> None:
            await latest_help.callback(ctx, 검색어=(category or None))
        legacy_help.callback = v652_latest_help
        legacy_help.help = "Open the latest ABADDON command browser. Optional: !help keyword"
        legacy_help.description = legacy_help.help

    @bot.command(name="english", aliases=["enhelp", "englishhelp"])
    async def english_help(ctx: commands.Context) -> None:
        embed = discord.Embed(
            title="🌐 ABADDON English Command Guide",
            description=(
                "All existing Korean commands remain available. English names are prefix aliases, "
                "so they use the same cooldowns, balances, permissions, and save data.\n"
                "Example: `!기지` and `!base` run the same command."
            ),
            color=0x4C8FD4,
        )
        for title, names in ENGLISH_SECTIONS.items():
            embed.add_field(name=title, value=" · ".join(f"`!{name}`" for name in names), inline=False)
        embed.add_field(name="Search / 검색", value="`!commands keyword` 또는 `!명령어 검색어`", inline=False)
        embed.set_footer(text=f"ABADDON v{VERSION} · Korean commands preserved · {PATCH_DATE}")
        await ctx.send(embed=embed)

    # Update official bot introduction without replacing the existing command object.
    intro = bot.get_command("봇소개")
    if intro is not None:
        async def v652_bot_intro(ctx: commands.Context) -> None:
            embed = discord.Embed(
                title="🛰️ ABADDON · Survival RPG",
                description=(
                    "ABADDON은 Discord에서 즐기는 생존 RPG 봇입니다. 성장·스토리·던전·월드보스·장비·보물·펫·기지·생활·거래·카드게임과 "
                    "서버 리뉴얼을 한곳에서 제공합니다. 기존 한국어 명령은 그대로 유지되며 주요 기능은 영어 명령어로도 실행할 수 있습니다."
                ),
                color=0xC8AA62,
            )
            embed.add_field(name="⚔️ Survival RPG", value="스토리 분기 · 자동/전술 던전 · 원정 · 레이드 · 월드보스", inline=False)
            embed.add_field(name="🧰 Progression", value="장비 강화·개조 · 보물 감정 · 펫 성장·진화 · 기지 Lv.0~Lv.5", inline=False)
            embed.add_field(name="🎮 Community", value="생활·거래·미니게임·포커·원카드·조커잡기 · 28종 서버 테마", inline=False)
            embed.add_field(name="🌐 Bilingual Commands", value="`!명령어` / `!commands` · `!english`에서 주요 영문 명령어 확인", inline=False)
            embed.add_field(name="🚀 Quick Start", value="`!help` → `!register survivor` 또는 기존 `!가입 생존자` → `!today` → `!story` / `!dungeon 약함`", inline=False)
            embed.set_footer(text=f"ABADDON v{VERSION} · Patch {PATCH_DATE}")
            await ctx.send(embed=embed)
        intro.callback = v652_bot_intro
        intro.help = "ABADDON 소개와 한국어·영어 명령어 빠른 시작을 확인합니다."
        intro.description = intro.help

    patch = bot.get_command("패치노트")
    if patch is not None:
        async def v652_patch_notes(ctx: commands.Context) -> None:
            embed = discord.Embed(
                title="🖼️ ABADDON v6.5.3 — Activity Gallery & Message Cleanup",
                description="기존 한국어·영어 명령어를 유지하면서 낚시·채집·상인·코인 탐색에 전용 랜덤 이미지 갤러리를 추가하고 안내 문구를 정리했습니다.",
                color=0x365F8D,
            )
            embed.add_field(name="🖼️ 활동 이미지", value="낚시·채집·상인·코인 탐색 각 10장 · 1280×720 안전 프레임 · 행동과 다른 이미지가 섞이지 않도록 갤러리 분리", inline=False)
            embed.add_field(name="🏰 기지 외형 HD", value="Lv.0~Lv.5를 동일한 산악 거점 구도와 성장 순서로 재보정 · 봇과 홈페이지 이미지를 같은 파일로 동기화", inline=False)
            embed.add_field(name="✨ 품질 패널", value="주간 기지 방어·변동 자원 시장·+0/+5/+10/+15/+20 강화 미리보기 신규 고해상도 파일 적용", inline=False)
            embed.add_field(name="🌐 English Commands", value=f"한국어 명령 유지 · 영문 별칭 **{sum(len(v) for v in registered.values())}개** 연결 · `!english`, `!help`, `!commands`, `!base`, `!equipment`, `!cardgames` 지원", inline=False)
            embed.add_field(name="📚 안내 최신화", value="`!명령어`와 영문 도움말 유지 · 봇 소개·홈페이지 명령어 검색·업데이트 기록 동기화", inline=False)
            embed.add_field(name="📅 Patch Date", value=f"**{PATCH_DATE}**", inline=False)
            embed.set_footer(text="카지노만 이미지 미사용 · 기존 경제/확률/쿨타임/데이터 구조 변경 없음")
            await ctx.send(embed=embed)
        patch.callback = v652_patch_notes
        patch.help = "ABADDON v6.5.3 활동 이미지 갤러리·문구 정리 패치를 확인합니다."
        patch.description = patch.help

    bot.v652_version = VERSION
    bot.v652_english_aliases = registered
    bot.v652_english_alias_skipped = skipped
