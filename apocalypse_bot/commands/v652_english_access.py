from __future__ import annotations

import copy
from typing import Any, Dict, List, Tuple

import discord
from discord.ext import commands

VERSION = "6.5.4"
PATCH_DATE = "2026-08-02"

# English prefix aliases reuse the existing Korean command callbacks. Therefore
# cooldowns, balances, permissions, and saved data remain shared and unchanged.
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

# This small category remains visible in the Korean !명령어 browser, but its
# wording is Korean because it belongs to the Korean interface.
ENGLISH_GUIDE = {
    "id": "english_commands",
    "emoji": "🌐",
    "title": "영문 명령어",
    "hint": "!help 또는 !english로 영어 전용 도움말 열기",
    "commands": [
        "!help / !commands / !english / !enhelp — 영어 전용 도움말",
        "!help base / !help pet / !help equipment — 영어 명령 검색",
        "기존 한국어 명령어는 그대로 유지됩니다.",
    ],
}

ENGLISH_GUIDE_CATEGORIES: List[Dict[str, Any]] = [
    {
        "id": "overview",
        "emoji": "📚",
        "title": "Overview",
        "hint": "English command guide and search instructions",
        "commands": [],
    },
    {
        "id": "account",
        "emoji": "🧾",
        "title": "Account & Profile",
        "hint": "Registration, profile, wallet, ranking, and daily progress",
        "commands": [
            "!register survivor", "!tutorial", "!profile", "!wallet", "!status",
            "!ranking", "!daily", "!today", "!fortune", "!train", "!rest",
        ],
    },
    {
        "id": "life",
        "emoji": "🌿",
        "title": "Life & Exploration",
        "hint": "Work, gathering, fishing, mining, digging, weather, and radio",
        "commands": [
            "!work", "!gather", "!fish", "!woodcut", "!mine", "!dig",
            "!coinsearch", "!weather", "!hazardzone", "!radio", "!decoderadio",
            "!lootbox 1", "!aid",
        ],
    },
    {
        "id": "equipment",
        "emoji": "🛠️",
        "title": "Equipment & Crafting",
        "hint": "Inventory, enhancement, durability, crafting, repair, and scrap",
        "commands": [
            "!shop", "!equipment", "!gearlist", "!inventory", "!buy item-name",
            "!enhance item-name", "!enhanceinfo item-name", "!safeenhance item-name",
            "!gearvisual item-name", "!materials", "!craftlist", "!craft item-name",
            "!durability", "!repair item-name", "!mods", "!modweapon", "!scrap",
        ],
    },
    {
        "id": "relics",
        "emoji": "🏺",
        "title": "Relics & Appraisal",
        "hint": "Appraise treasures and review relic collections",
        "commands": ["!appraise", "!treasures", "!appraisers"],
    },
    {
        "id": "combat",
        "emoji": "⚔️",
        "title": "Combat & Dungeons",
        "hint": "Monsters, tactical combat, regions, raids, and world bosses",
        "commands": [
            "!monsters", "!dungeon weak", "!dungeon normal", "!dungeon hard",
            "!dungeon hell", "!tacticaldungeon weak", "!battle", "!battlestatus",
            "!surrender", "!regions", "!regioninfo", "!travel region-name",
            "!explore", "!raid", "!worldboss", "!worldbossattack",
        ],
    },
    {
        "id": "economy",
        "emoji": "💰",
        "title": "Economy & Trading",
        "hint": "Market, bank, loans, and dynamic resource trading",
        "commands": [
            "!market", "!marketsearch keyword", "!sell item-name price", "!bank",
            "!deposit amount", "!withdraw amount", "!loan amount", "!repay amount",
            "!resourcemarket", "!buyresource wood 10", "!sellresource ore 5",
        ],
    },
    {
        "id": "games",
        "emoji": "🎮",
        "title": "Minigames & Casino",
        "hint": "Casino games, reaction games, mines, and races",
        "commands": [
            "!casino", "!blackjack amount", "!slots amount", "!roulette amount",
            "!minigames", "!minesweeper", "!reactiongame", "!memorygame",
            "!survivorrace",
        ],
    },
    {
        "id": "cards",
        "emoji": "🃏",
        "title": "Card Games",
        "hint": "Player lobbies for poker, One Card, and Joker Catch",
        "commands": ["!cardgames", "!poker 10000", "!onecard 10000", "!jokercatch 10000"],
    },
    {
        "id": "story",
        "emoji": "📖",
        "title": "Story & Expeditions",
        "hint": "Story progression and expedition content",
        "commands": ["!story", "!expedition"],
    },
    {
        "id": "pets",
        "emoji": "🐾",
        "title": "Pets",
        "hint": "Pet collection, information, training, and evolution",
        "commands": ["!pet", "!petinfo", "!pettrain", "!petevolve"],
    },
    {
        "id": "base",
        "emoji": "🏕️",
        "title": "Base & Survival",
        "hint": "Base construction, upgrades, production, and defense",
        "commands": [
            "!base", "!buildbase", "!upgradebase", "!baseharvest", "!basedefense",
            "!resourcemarket",
        ],
    },
    {
        "id": "server",
        "emoji": "🏰",
        "title": "Server Tools & Themes",
        "hint": "Server renewal, themes, briefings, stability, and diagnostics",
        "commands": [
            "!themes", "!briefing", "!serverrenewal", "!stability", "!diagnostics",
            "!patchnotes", "!botinfo",
        ],
    },
]


def _add_alias(bot: commands.Bot, command_name: str, alias: str) -> Tuple[bool, str]:
    command = bot.get_command(command_name)
    if command is None:
        return False, "missing-target"
    current = bot.get_command(alias)
    if current is not None and current is not command:
        return False, f"collision:{current.qualified_name}"
    if alias not in command.aliases:
        command.aliases.append(alias)
    if command.parent is None:
        bot.all_commands[alias] = command
    else:
        command.parent.all_commands[alias] = command
    return True, "registered"


def _release_top_level_name(bot: commands.Bot, name: str) -> None:
    """Release an alias so it can be used by the dedicated English help command."""
    current = bot.all_commands.get(name)
    if current is None:
        return
    if current.name == name:
        bot.remove_command(name)
        return
    if name in current.aliases:
        current.aliases.remove(name)
    bot.all_commands.pop(name, None)


def _update_korean_guide(guide: List[Dict[str, Any]]) -> None:
    guide[:] = [row for row in guide if row.get("id") != ENGLISH_GUIDE["id"]]
    guide.insert(min(1, len(guide)), copy.deepcopy(ENGLISH_GUIDE))


def _normalize(text: str) -> str:
    return "".join(ch for ch in str(text or "").lower() if ch.isalnum())


def _command_chunks(command_list: List[str], max_len: int = 900) -> List[str]:
    chunks: List[str] = []
    current: List[str] = []
    length = 0
    for command in command_list:
        line = f"• `{command}`"
        if current and length + len(line) + 1 > max_len:
            chunks.append("\n".join(current))
            current = [line]
            length = len(line)
        else:
            current.append(line)
            length += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks


def _english_overview_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🌐 ABADDON English Command Guide",
        description=(
            "This interface is fully displayed in English. Select a category below or search by keyword.\n\n"
            "Examples: `!help base`, `!help pet`, `!help equipment`, `!help dungeon`\n"
            "The original Korean command guide remains available separately."
        ),
        color=0x4C8FD4,
    )
    for category in ENGLISH_GUIDE_CATEGORIES[1:]:
        embed.add_field(
            name=f"{category['emoji']} {category['title']}",
            value=category["hint"],
            inline=True,
        )
    embed.set_footer(text=f"ABADDON v{VERSION} · English help interface · {PATCH_DATE}")
    return embed


def _english_category_embed(category: Dict[str, Any]) -> discord.Embed:
    if category["id"] == "overview":
        return _english_overview_embed()
    embed = discord.Embed(
        title=f"{category['emoji']} {category['title']}",
        description=category["hint"],
        color=0x4C8FD4,
    )
    for index, chunk in enumerate(_command_chunks(category["commands"]), start=1):
        field_name = "Commands" if index == 1 else f"Commands {index}"
        embed.add_field(name=field_name, value=chunk, inline=False)
    embed.set_footer(text="Search: !help keyword · Use the dropdown to open another category")
    return embed


def _search_english_commands(query: str, limit: int = 25) -> List[Tuple[str, str]]:
    token = _normalize(query)
    if not token:
        return []
    matches: List[Tuple[int, int, str, str]] = []
    for category in ENGLISH_GUIDE_CATEGORIES[1:]:
        category_text = _normalize(category["title"] + category["hint"])
        for command in category["commands"]:
            command_text = _normalize(command)
            if command_text.startswith(token):
                score = 0
            elif token in command_text:
                score = 1
            elif token in category_text:
                score = 2
            else:
                continue
            matches.append((score, len(command), category["title"], command))
    matches.sort(key=lambda row: (row[0], row[1], row[2], row[3]))
    result: List[Tuple[str, str]] = []
    seen = set()
    for _, _, category_title, command in matches:
        key = (category_title, command)
        if key in seen:
            continue
        seen.add(key)
        result.append(key)
        if len(result) >= limit:
            break
    return result


def _english_search_embed(query: str, results: List[Tuple[str, str]]) -> discord.Embed:
    embed = discord.Embed(title=f"🔎 Command Search: {query}", color=0x4C8FD4)
    if not results:
        embed.description = "No matching English command was found. Try a broader keyword or select a category below."
    else:
        embed.description = "\n".join(
            f"• **{category}** — `{command}`" for category, command in results[:20]
        )
        if len(results) > 20:
            embed.add_field(
                name="More results",
                value=f"{len(results) - 20} additional matches were omitted. Use a more specific keyword.",
                inline=False,
            )
    embed.set_footer(text="Examples: !help base · !help pet · !help equipment · !help server")
    return embed


class EnglishCategorySelect(discord.ui.Select):
    def __init__(self) -> None:
        options = [
            discord.SelectOption(
                label=category["title"][:100],
                value=category["id"],
                description=category["hint"][:100],
                emoji=category["emoji"],
            )
            for category in ENGLISH_GUIDE_CATEGORIES
        ]
        super().__init__(
            placeholder="Select a command category",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        selected = next(
            (category for category in ENGLISH_GUIDE_CATEGORIES if category["id"] == self.values[0]),
            None,
        )
        if selected is None:
            await interaction.response.send_message("The selected category could not be found.", ephemeral=True)
            return
        await interaction.response.edit_message(embed=_english_category_embed(selected), view=self.view)


class EnglishSearchModal(discord.ui.Modal, title="Search English Commands"):
    query = discord.ui.TextInput(
        label="Command or keyword",
        placeholder="Examples: base, pet, equipment, dungeon",
        min_length=1,
        max_length=40,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        query = str(self.query.value).strip()
        await interaction.response.send_message(
            embed=_english_search_embed(query, _search_english_commands(query)),
            ephemeral=True,
        )


class EnglishHelpView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=300)
        self.add_item(EnglishCategorySelect())

    @discord.ui.button(label="Search Commands", emoji="🔎", style=discord.ButtonStyle.primary, row=1)
    async def search_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_modal(EnglishSearchModal())


def register_v652_english_access(bot: commands.Bot, guide: List[Dict[str, Any]]) -> None:
    _update_korean_guide(guide)

    # Keep the Korean browsers untouched, but reserve these names for the fully
    # English interface. This removes the old Korean !help alias safely.
    for reserved_name in ("help", "commands", "english", "enhelp", "englishhelp", "guide"):
        _release_top_level_name(bot, reserved_name)

    registered: Dict[str, List[str]] = {}
    skipped: Dict[str, str] = {}
    for korean, aliases in ENGLISH_ALIASES.items():
        for alias in aliases:
            ok, reason = _add_alias(bot, korean, alias)
            if ok:
                registered.setdefault(korean, []).append(alias)
            else:
                skipped[f"{korean}:{alias}"] = reason

    @bot.command(
        name="help",
        aliases=["commands", "english", "enhelp", "englishhelp", "guide"],
        help="Open the fully English ABADDON command guide.",
    )
    async def english_help(ctx: commands.Context, *, keyword: str = "") -> None:
        keyword = keyword.strip()
        if keyword:
            embed = _english_search_embed(keyword, _search_english_commands(keyword))
        else:
            embed = _english_overview_embed()
        await ctx.send(embed=embed, view=EnglishHelpView())

    intro = bot.get_command("봇소개")
    if intro is not None:
        async def v654_bot_intro(ctx: commands.Context) -> None:
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
            embed.add_field(name="🌐 Help Interfaces", value="한국어: `!명령어` · English: `!help`, `!commands`, `!english`", inline=False)
            embed.add_field(name="🚀 Quick Start", value="`!help` → `!register survivor` 또는 `!가입 생존자` → `!today` → `!story` / `!dungeon weak`", inline=False)
            embed.set_footer(text=f"ABADDON v{VERSION} · Patch {PATCH_DATE}")
            await ctx.send(embed=embed)
        intro.callback = v654_bot_intro
        intro.help = "ABADDON 소개와 한국어·영어 명령어 빠른 시작을 확인합니다."
        intro.description = intro.help

    patch = bot.get_command("패치노트")
    if patch is not None:
        async def v654_patch_notes(ctx: commands.Context) -> None:
            embed = discord.Embed(
                title="🌐 ABADDON v6.5.4 — English Help Localization",
                description=(
                    "기존 한국어 명령어와 `!명령어` 화면은 그대로 유지하면서, "
                    "`!help`, `!commands`, `!english`, `!enhelp`를 완전한 영어 전용 도움말로 분리했습니다."
                ),
                color=0x4C8FD4,
            )
            embed.add_field(
                name="🇬🇧 English-only interface",
                value="제목·설명·드롭다운·선택지·검색 버튼·검색 모달·오류 문구·푸터를 모두 영어로 표시합니다.",
                inline=False,
            )
            embed.add_field(
                name="🇰🇷 Korean interface preserved",
                value="`!명령어`와 `!도움말`은 기존 한국어 화면과 명령 목록을 그대로 유지합니다.",
                inline=False,
            )
            embed.add_field(
                name="🔎 English search",
                value="`!help base`, `!help pet`, `!help equipment`, `!help dungeon`처럼 영어 키워드 검색을 지원합니다.",
                inline=False,
            )
            embed.add_field(
                name="🧩 Compatibility",
                value="게임 밸런스·경제·쿨타임·저장 데이터·기존 영문 별칭에는 변경이 없습니다.",
                inline=False,
            )
            embed.add_field(name="📅 Patch Date", value=f"**{PATCH_DATE}**", inline=False)
            await ctx.send(embed=embed)
        patch.callback = v654_patch_notes
        patch.help = "ABADDON v6.5.4 영어 도움말 완전 분리 패치를 확인합니다."
        patch.description = patch.help

    bot.v652_version = VERSION
    bot.v652_english_aliases = registered
    bot.v652_english_alias_skipped = skipped
    bot.v654_english_help_categories = len(ENGLISH_GUIDE_CATEGORIES)
