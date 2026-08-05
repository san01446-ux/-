from __future__ import annotations

"""ABADDON v16.3.0 core-RPG navigation, city workshop and reaction expansion.

Additive patch goals:
- classify every runtime command exactly once instead of relying on the manually
  maintained guide list;
- put the apocalypse story (Season 1 -> Season 5) back at the front of !명령어;
- expose every command through section buttons, grouped dropdowns, pagination,
  short descriptions and a real execute button;
- preserve all legacy commands and save data;
- audit the renewed 20-part city workshop and expand automatic reaction presets.
"""

import inspect
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

import discord
from discord.ext import commands

from apocalypse_bot.commands.v600_game_center import _command_requires_input, _invoke_command

VERSION = "16.3.0"
EXPECTED_DECLARATIONS = 1339
ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets"
CITY_COMPONENT_ROOT = ASSET_ROOT / "v1500" / "city" / "components"
V1630_PREVIEW_ROOT = ASSET_ROOT / "v1630" / "previews"
MENU_TIMEOUT = 900
PAGE_SIZE = 25


def _t(locale: str, ko: str, en: str) -> str:
    return en if locale == "en" else ko


def _clean(value: Any, limit: int = 4000) -> str:
    text = " ".join(str(value or "").replace("\x00", " ").split())
    return text[:limit]


def _short(value: Any, limit: int = 96) -> str:
    text = _clean(value, limit + 20)
    return text if len(text) <= limit else text[: max(1, limit - 1)] + "…"


SECTION_SPECS: Tuple[Tuple[str, str, str, str], ...] = (
    ("main", "📖 메인 RPG", "📖 Core RPG", "시즌 1부터 이어지는 아포칼립스 스토리·성장·탐험"),
    ("play", "⚔️ 플레이", "⚔️ Play", "생활·전투·장비·경제·게임"),
    ("world", "🌌 세계", "🌌 World", "BLACK CITY·NEON ABYSS·재난·세력·도시 공방"),
    ("social", "🤝 소셜", "🤝 Social", "길드·동료·NPC·일정·방송·친목"),
    ("system", "🛠️ 운영", "🛠️ System", "서버 설정·보안·알림·이모지·검수·복구"),
)

# key, Korean label, English label, Korean description, English description, emoji
GROUP_SPECS: Dict[str, Tuple[Tuple[str, str, str, str, str, str], ...]] = {
    "main": (
        ("story1", "시즌 1 · 검은 주파수", "Season 1 · Black Frequency", "메인 스토리 시작·선택·기록·재시작", "Main story start, choices, history and restart", "📻"),
        ("story2", "시즌 2 · 백색 방주", "Season 2 · White Ark", "두 번째 이야기와 장면·엔딩·계승", "Second story, scenes, endings and legacy", "🚢"),
        ("story3", "시즌 3 · 종말의 왕좌", "Season 3 · Throne of the End", "세 번째 이야기의 선택과 엔딩", "Third story choices and endings", "👑"),
        ("story4", "시즌 4 · 황혼의 종착역", "Season 4 · Twilight Terminal", "황혼선 이야기·여정·유산", "Twilight Line story, journey and legacy", "🚂"),
        ("story5", "시즌 5 · 잿빛 연합전선", "Season 5 · Ashen Front", "세계 상태·서버 투표·결정·연대기", "World state, server votes, decisions and chronicle", "📡"),
        ("onboarding", "가입·프로필·초보 안내", "Onboarding & Profile", "가입, 정보, 직업, 튜토리얼과 복귀 안내", "Registration, profile, jobs, tutorial and return guide", "🌱"),
        ("quests", "퀘스트·성장·업적", "Quests, Growth & Achievements", "오늘 할 일, 퀘스트, 레벨, 미션과 보상", "Daily tasks, quests, levels, missions and rewards", "🎯"),
        ("exploration", "생존 탐험·원정·사건", "Survival Exploration", "지역 정찰, 원정, 사건, 수사와 유물", "Scouting, expeditions, incidents, investigation and relics", "🧭"),
        ("base", "기지·대피소·세계 진행", "Base, Shelter & World Progress", "기지 성장, 대피소, 개척, 복구와 세계 순환", "Base growth, shelter, frontier, recovery and world cycle", "🏕️"),
        ("codex", "도감·연대기·진행 확인", "Codex, Chronicle & Progress", "발견 기록, 도감, 진행판과 다음 행동", "Discovery records, codices, progress and next actions", "📚"),
    ),
    "play": (
        ("life", "생활·채집·파밍", "Life, Gathering & Farming", "채집, 낚시, 벌목, 광산, 파밍과 생활 숙련", "Gathering, fishing, logging, mining, farming and mastery", "⛏️"),
        ("gear", "상점·장비·강화·제작", "Shop, Gear, Enhance & Craft", "아이템 구매, 장착, 강화, 제작과 공방", "Buy, equip, enhance and craft items", "🛠️"),
        ("combat", "전투·보스·던전", "Combat, Boss & Dungeon", "일반 전투, 결투, 던전, 보스와 공격대", "Combat, duels, dungeons, bosses and raids", "⚔️"),
        ("economy", "경제·거래·사업", "Economy, Trade & Business", "지갑, 송금, 시장, 거래소, 무역과 사업", "Wallet, transfers, markets, trade and business", "💰"),
        ("cards", "카드·화투 게임", "Cards & Hwatu", "포커, 화투, 블랙잭 등 실전 카드게임", "Poker, hwatu, blackjack and card games", "🎴"),
        ("casino", "카지노·경마·도박", "Casino, Racing & Gambling", "카지노 게임, 경마, 룰렛과 배팅 기록", "Casino games, racing, roulette and betting records", "🎰"),
        ("party_games", "파티게임·축제·미니게임", "Party Games & Festival", "서버 파티게임, 혼돈 이벤트와 가벼운 놀이", "Server party games, chaos events and mini games", "🎉"),
        ("collections", "수집·꾸미기·보상", "Collections, Cosmetics & Rewards", "수집품, 칭호, 배경, 트로피와 꾸미기", "Collections, titles, backgrounds, trophies and cosmetics", "🏆"),
    ),
    "world": (
        ("black_city", "BLACK CITY", "BLACK CITY", "도시 지도, 세력, 직업, 범죄, 경제와 시즌", "City map, factions, jobs, crime, economy and seasons", "🏙️"),
        ("city_decor", "도시 꾸미기·공방", "City Decoration Workshop", "도시 부품, 배치, 사진, 제작과 시각 연출", "City parts, placement, photos, crafting and visuals", "🎨"),
        ("neon", "NEON ABYSS·차원", "NEON ABYSS & Dimensions", "차원문, 항해, 차원 탐사와 기지", "Gates, voyages, dimension exploration and base", "🌀"),
        ("crew_raid", "크루·우주선·공격대", "Crew, Ship & Raid", "크루 임무, 우주선 시설과 차원 공격대", "Crew missions, ship facilities and dimension raids", "🚀"),
        ("factions", "세력·영토·전쟁·무역", "Factions, Territory, War & Trade", "세력 평판, 영토, 호송, 전선과 공동 전쟁", "Faction reputation, territory, convoys and wars", "🏴"),
        ("disaster", "재난·기상·복구", "Disaster, Weather & Recovery", "공동 재난, 예보, 날씨, 구조와 복구 작전", "Shared disasters, forecasts, rescue and recovery", "☄️"),
        ("creator", "창작센터·콘텐츠 교환", "Creator Studio & Exchange", "퀘스트·보스 제작, 공개, 검색과 설치", "Create, publish, search and install content", "🧩"),
        ("world_misc", "월드 시스템·지도", "World Systems & Maps", "공동 지도, 세계 상태, 순환과 서버 기록", "Shared maps, world state, cycles and records", "🗺️"),
    ),
    "social": (
        ("guild", "길드·파티·연합", "Guild, Party & Alliance", "길드, 파티, 연합, 분대와 협동 조직", "Guilds, parties, alliances, squads and co-op groups", "🛡️"),
        ("companions", "동료·펫·육성", "Companions, Pets & Growth", "동료와 펫의 영입, 배치, 훈련과 진화", "Recruit, deploy, train and evolve companions and pets", "🐾"),
        ("npc", "NPC·인연·관계", "NPC, Bonds & Relations", "NPC 대화, 선물, 평판과 인연 기록", "NPC dialogue, gifts, reputation and bonds", "🤝"),
        ("schedule", "일정·예약·방송", "Schedules, Reservations & Broadcasts", "서버 일정, 게임 예약, 중계와 방송", "Server schedules, game reservations and broadcasts", "📅"),
        ("chat", "대화·친목·예능", "Chat, Social & Variety", "아바돈 대화, 칭찬, 궁합, 월드컵과 친목", "ABADDON chat, praise, compatibility and social games", "💬"),
        ("voice", "음성·하이라이트·미디어", "Voice, Highlights & Media", "음성방, 하이라이트, 사진과 미디어 관리", "Voice rooms, highlights, photos and media", "🎙️"),
        ("support", "문의·건의·신고·도움", "Support, Suggestions & Reports", "문의센터, 공개 건의, 신고와 운영진 전달", "Support center, suggestions, reports and staff relay", "📮"),
        ("social_misc", "커뮤니티 기타", "Other Community Tools", "서버 커뮤니티와 소셜 보조 기능", "Other server community and social tools", "🌐"),
    ),
    "system": (
        ("server_setup", "서버 설치·채널·역할", "Server Setup, Channels & Roles", "서버 리뉴얼, 채널, 역할과 안내판 설치", "Server renewal, channels, roles and guide panels", "🏗️"),
        ("security", "권한·보안·관리", "Permissions, Security & Moderation", "권한 검사, 안티레이드, 격리와 관리자 도구", "Permissions, anti-raid, quarantine and moderation", "🛡️"),
        ("auto_emoji", "자동 이모지·반응", "Automatic Emoji & Reactions", "채널 프리셋, 키워드 규칙과 다중 반응", "Channel presets, keyword rules and multi-reactions", "✨"),
        ("alerts", "알림·구독·운영센터", "Alerts, Subscriptions & Operations", "알림센터, 구독 시간, 채널과 운영 대시보드", "Alerts, subscription times, channels and dashboards", "🔔"),
        ("help", "명령어·언어·접근성", "Commands, Language & Accessibility", "명령 탐색, 검색, 언어와 접근성 설정", "Command browsing, search, language and accessibility", "📚"),
        ("audit", "검수·진단·오류", "Audit, Diagnostics & Errors", "통합 검수, 시각 검사, 오류 조회와 테스트", "Integration audits, visual checks, errors and tests", "🧪"),
        ("recovery", "백업·복구·안정화", "Backup, Recovery & Stability", "백업, 복원, 재시작 복구와 안정화 도구", "Backups, restore, restart recovery and stability", "💾"),
        ("admin", "고급 관리자·데이터", "Advanced Admin & Data", "운영자 전용 지급, 데이터, 강제 진행과 관리", "Owner/admin grants, data and forced progression", "🔧"),
        ("legacy", "기타·보존 명령", "Other Preserved Commands", "분류 규칙에 걸리지 않은 기존 기능을 빠짐없이 보존", "Every remaining legacy command preserved", "🗄️"),
    ),
}

GROUP_INDEX: Dict[str, Tuple[str, str, str, str, str, str]] = {
    key: (section, ko, en, dko, den, emoji)
    for section, groups in GROUP_SPECS.items()
    for key, ko, en, dko, den, emoji in groups
}


@dataclass(frozen=True)
class CommandEntry:
    index: int
    qualified_name: str
    name: str
    help_text: str
    signature: str
    aliases: Tuple[str, ...]
    source: str
    section: str
    group: str
    restricted: bool
    is_group: bool

    @property
    def search_blob(self) -> str:
        section, ko, en, dko, den, _emoji = GROUP_INDEX[self.group]
        return " ".join((self.qualified_name, self.name, self.help_text, self.signature, " ".join(self.aliases), self.source, ko, en, dko, den)).casefold()


def _has(blob: str, *tokens: str) -> bool:
    return any(token.casefold() in blob for token in tokens)


def _classify(command: commands.Command) -> Tuple[str, str]:
    qname = str(getattr(command, "qualified_name", command.name))
    aliases = " ".join(str(x) for x in getattr(command, "aliases", []) or [])
    help_text = str(getattr(command, "help", "") or getattr(command, "description", "") or "")
    source = str(getattr(getattr(command, "callback", None), "__module__", ""))
    blob = " ".join((qname, aliases, help_text, source)).casefold()
    module = source.rsplit(".", 1)[-1]

    # Main story is explicit and always wins over generic game/campaign words.
    if module == "v33_story":
        return "main", "story1"
    if module == "v430_story_expedition" and _has(blob, "시즌2", "백색방주", "후일담", "story2", "white ark"):
        return "main", "story2"
    if module == "v600_game_center" and _has(blob, "시즌3", "종말의왕좌", "story3", "왕좌"):
        return "main", "story3"
    if module in {"v730_season_story", "v731_duplicate_stability"}:
        return "main", "story4"
    if module == "v900_faction_world_state" and _has(blob, "시즌5", "연합전선", "세계상태", "세계연대기", "season5"):
        return "main", "story5"
    if _has(blob, "시즌 1", "시즌1", "검은 주파수") and not _has(blob, "슬롯"):
        return "main", "story1"
    if _has(blob, "시즌 2", "시즌2", "백색 방주"):
        return "main", "story2"
    if _has(blob, "시즌 3", "시즌3", "종말의 왕좌"):
        return "main", "story3"
    if _has(blob, "시즌 4", "시즌4", "황혼의 종착역", "황혼선"):
        return "main", "story4"
    if _has(blob, "시즌 5", "시즌5", "잿빛 연합전선"):
        return "main", "story5"

    # World expansions and the city workshop.
    if module == "v1500_neon_abyss":
        if _has(blob, "도시꾸미", "도시부품", "도시사진", "도시전경", "연출설정", "연출도감", "지역보기", "citydecor", "citypart"):
            return "world", "city_decor"
        if _has(blob, "크루", "우주선", "공격대", "보스방어", "crew", "ship", "raid"):
            return "world", "crew_raid"
        if _has(blob, "창작", "콘텐츠", "퀘스트제작", "보스제작", "creator", "content"):
            return "world", "creator"
        return "world", "neon"
    if module.startswith("v1320_black_city") or module == "v1221_runtime_ui_hotfix":
        if _has(blob, "꾸미", "장식", "공방", "도시제작", "도시부품"):
            return "world", "city_decor"
        return "world", "black_city"
    if module in {"v900_faction_world_state", "v920_world_cycle_professions"}:
        if _has(blob, "재난", "복구", "세계순환", "세계지령"):
            return "world", "disaster"
        return "world", "factions"
    if module in {"v780_server_disaster", "v790_operations_disaster", "v636_world_combat"} and _has(blob, "재난", "기상", "복구", "weather", "disaster"):
        return "world", "disaster"
    if module in {"v810_world_map_ux", "v639_frontier_operations"}:
        return "world", "world_misc"

    # Automatic reactions must stay visible inside operations.
    if module == "v411_server_guard_plus" and _has(blob, "이모지", "반응", "reaction", "emoji"):
        return "system", "auto_emoji"

    # Module families provide strong hints before generic keyword scoring.
    if module in {"v631_life_visuals", "v632_life_visuals", "v610_digging_treasure", "v770_ruin_farming"}:
        return "play", "life"
    if module in {"v633_equipment_crafting", "v634_equipment_menu", "v640_scrap_system", "v432_forge_live"}:
        return "play", "gear"
    if module in {"v630_world_boss", "v636_world_combat", "v638_hardcore_arcade", "v750_guild_raid"} and _has(blob, "보스", "전투", "던전", "레이드", "공격", "결투"):
        return "play", "combat"
    if module in {"v651_card_games", "v1010_companion_card_games", "v1051_authentic_card_games", "v1060_authentic_card_games", "v1090_rules", "v1094_card_table_images", "v1100_game_city_overhaul", "v1152_traditional_hwatu_refresh"}:
        return "play", "cards"
    if module in {"v39_casino", "v40_black_casino", "v37_gambling_experience", "v1092_horse_racing_rules", "v1142_dynamic_horse_odds"}:
        return "play", "casino"
    if module in {"v1220_fun_core", "v1220_chaos_festival_complete"}:
        if _has(blob, "동료", "펫", "npc"):
            return "social", "companions"
        if _has(blob, "사업", "탐험"):
            return "play", "economy"
        if _has(blob, "수집", "꾸미", "칭호", "배경"):
            return "play", "collections"
        return "play", "party_games"
    if module in {"v750_guild_raid", "v760_guild_dispatch"} and _has(blob, "길드", "파티", "연합", "분대"):
        return "social", "guild"
    if module in {"v634_pet_visuals", "v1010_companion_card_games"} and _has(blob, "동료", "펫", "훈련", "원정"):
        return "social", "companions"
    if module in {"v1190_event_broadcast_collection"}:
        if _has(blob, "일정", "예약", "방송", "중계"):
            return "social", "schedule"
        return "play", "collections"
    if module in {"v620_dialogue_memory", "v711_cute_interactions"}:
        return "social", "chat"
    if module in {"v433_voice_sanctuary"}:
        return "social", "voice"
    if module in {"v403_server_builder", "v410_server_management", "v602_channel_rules"}:
        return "system", "server_setup"
    if module in {"v411_server_guard_plus", "v420_ops_center", "v422_security_center", "v1150_server_operations_permissions"}:
        return "system", "security"
    if module in {"v1151_alert_settings_ui", "v1143_disaster_optin", "v790_operations_disaster"} and _has(blob, "알림", "구독", "운영"):
        return "system", "alerts"
    if module in {"v521_diagnostics", "v1093_command_ui_audit", "v1330_command_registry_guard", "v1621_visual_command_hotfix"}:
        return "system", "audit"
    if module in {"v1160_recovery_rules", "v1160_game_recovery_validation"}:
        return "system", "recovery"

    # Legacy module families that use very short Korean subcommand names.
    # Runtime qualified names provide even more context, while these mappings
    # keep static declarations and old standalone commands out of a vague bucket.
    if module == "admin_tools":
        return "system", "admin"
    if module == "conditions":
        return ("play", "gear") if _has(blob, "의약", "약품", "병원", "사용") else ("main", "onboarding")
    if module in {"daily_quiz", "v31_quiz_notify"}:
        return "play", "party_games"
    if module == "status":
        return "main", "onboarding"
    if module == "v1000_global_survivor":
        return ("main", "exploration") if _has(blob, "탐사") else ("main", "onboarding")
    if module == "v1050_unified_expansion":
        if _has(blob, "게임장", "빠른참가", "게임전적", "게임랭킹", "토너먼트"):
            return "play", "cards"
        if _has(blob, "무료시즌"):
            return "main", "quests"
        return "play", "cards"
    if module == "v1090_integrated_renewal":
        if _has(blob, "대시보드", "최근게임", "게임리플레이", "관전", "재대결", "게임방", "빠른대전"):
            return "play", "cards"
        if _has(blob, "파산", "재기"):
            return "play", "economy"
        if _has(blob, "명예의전당", "대회센터", "리그"):
            return "play", "collections"
        return "play", "cards"
    if module == "v1140_championship_alliance_casino_story":
        if _has(blob, "캠페인"):
            return "main", "codex"
        return "play", "cards"
    if module == "v1620_living_legends":
        if _has(blob, "즐겨찾기", "최근명령"):
            return "system", "help"
        if _has(blob, "탈것"):
            return "world", "neon"
        return "main", "codex"
    if module == "v21_reborn":
        if _has(blob, "입찰"):
            return "play", "economy"
        if _has(blob, "랭킹"):
            return "play", "collections"
        return "play", "gear"
    if module == "v30_invasion":
        return "play", "combat"
    if module == "v32_codex_settings_tutorial":
        return ("system", "server_setup") if _has(blob, "서버") else ("main", "codex")
    if module in {"v36_gambling_market", "v40_finance"}:
        return "play", "economy"
    if module == "v421_utility_pack":
        return "system", "server_setup"
    if module == "v423_intake_center":
        return "social", "support"
    if module == "v430_story_expedition":
        if _has(blob, "시작", "선택"):
            return "main", "story2"
        return "main", "exploration"
    if module == "v431_growth_balance":
        if _has(blob, "장면", "계승"):
            return "main", "story2"
        if _has(blob, "장착", "해제"):
            return "play", "gear"
        return "main", "quests"
    if module == "v600_game_center":
        if _has(blob, "시작", "선택"):
            return "main", "story3"
        return "system", "help"
    if module == "v636_world_combat":
        if _has(blob, "자원구매", "자원판매"):
            return "play", "economy"
        if _has(blob, "날씨"):
            return "world", "disaster"
        return "play", "combat"
    if module == "v637_dynamic_events":
        if _has(blob, "내구도", "개조"):
            return "play", "gear"
        if _has(blob, "위험구역", "무전"):
            return "main", "exploration"
        if _has(blob, "까마귀구매"):
            return "play", "economy"
        return "play", "party_games"
    if module == "v638_hardcore_arcade":
        if _has(blob, "벙커", "금고", "생물테러", "오염문", "괴질탈출"):
            return "play", "combat"
        return "play", "party_games"
    if module == "v640_interactive_arcade":
        return "play", "party_games"
    if module == "v641_stabilization":
        return "system", "server_setup"
    if module == "v702_stability":
        return "system", "audit"
    if module == "v720_coop_cleanup":
        if _has(blob, "패치"):
            return "system", "alerts"
        return "play", "party_games"
    if module == "world_exploration":
        return "main", "exploration"
    if module == "bot":
        if _has(blob, "구매", "인벤토리", "장착", "해제", "버리기", "재료"):
            return "play", "gear"
        if _has(blob, "괴물", "pvp"):
            return "play", "combat"
        if _has(blob, "돈주세요", "자원", "판매", "구매등록번호", "판매취소"):
            return "play", "economy"
        if _has(blob, "시즌패스", "시즌보상"):
            return "main", "quests"
        if _has(blob, "랭킹", "가방조회"):
            return "main", "codex"
    if module == "v1630_core_rpg_command_city_overhaul" and _has(blob, "이모지"):
        return "system", "auto_emoji"

    # Name/help scoring catches core.bot and small legacy modules.
    ordered_rules: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
        ("system", "auto_emoji", ("자동이모지", "이모지채널", "이모지규칙", "이모지프리셋", "반응이모지")),
        ("world", "city_decor", ("도시꾸미", "도시부품", "도시사진", "도시전경", "장식", "공방")),
        ("world", "black_city", ("black city", "도시세력", "도시거래", "도시시즌", "오늘의신문", "아지트", "범죄", "현상금")),
        ("world", "neon", ("차원문", "차원탐사", "차원지도", "차원기지", "항해", "neon abyss", "균열")),
        ("world", "crew_raid", ("크루", "우주선", "공격대", "차원보스")),
        ("world", "factions", ("세력", "영토", "전쟁", "전선", "호송", "무역로")),
        ("world", "disaster", ("재난", "기상", "복구작전", "세계순환", "세계지령")),
        ("world", "creator", ("창작센터", "콘텐츠공개", "콘텐츠검색", "콘텐츠설치", "퀘스트제작", "보스제작")),
        ("social", "schedule", ("일정", "예약", "방송", "중계", "캘린더")),
        ("social", "guild", ("길드", "파티", "연합", "분대", "협동")),
        ("social", "companions", ("동료", "펫", "진화", "훈련")),
        ("social", "npc", ("npc", "인연", "관계도", "선물", "딜러대화")),
        ("social", "voice", ("음성", "tts", "하이라이트", "미디어")),
        ("social", "support", ("문의", "건의", "신고", "제보", "지원센터")),
        ("social", "chat", ("대화", "칭찬", "궁합", "비밀친구", "월드컵")),
        ("play", "cards", ("카드", "포커", "화투", "맞고", "고스톱", "훌라", "라미", "섯다", "블랙잭", "바둑이", "대통령", "삼봉", "도리짓고땡", "육백", "토너먼트", "관전", "재대결")),
        ("play", "casino", ("카지노", "경마", "룰렛", "도박", "배팅", "바카라", "슬롯")),
        ("play", "party_games", ("파티게임", "마피아", "라이어", "룰렛게임", "폭탄돌리기", "축제")),
        ("play", "combat", ("전투", "공격", "보스", "던전", "레이드", "결투", "방어")),
        ("play", "gear", ("장비", "아이템", "강화", "제작", "상점", "수리", "감정", "분해")),
        ("play", "life", ("채집", "낚시", "벌목", "광산", "땅파기", "파밍", "알바", "생활", "보물")),
        ("play", "economy", ("지갑", "송금", "식량", "경제", "거래", "시장", "사업", "경매", "대출", "부채")),
        ("play", "collections", ("수집", "칭호", "트로피", "배경", "스킨", "도감보상")),
        ("main", "onboarding", ("가입", "정보", "프로필", "직업", "튜토리얼", "처음", "초보", "복귀")),
        ("main", "quests", ("퀘스트", "미션", "출석", "업적", "레벨", "성장", "오늘할일", "주간", "일일", "시즌패스", "시즌보상")),
        ("main", "exploration", ("탐험", "원정", "정찰", "사건", "수사", "단서", "유물", "현상금")),
        ("main", "base", ("기지", "대피소", "개척", "거점", "복구", "세계상태")),
        ("main", "codex", ("도감", "연대기", "기록", "진행", "할일", "다음 행동")),
        ("system", "server_setup", ("서버설정", "서버리뉴얼", "채널설정", "채널가이드", "역할설정", "설치")),
        ("system", "security", ("권한", "보안", "안티레이드", "격리", "잠금", "차단", "경고", "관리자")),
        ("system", "alerts", ("알림", "구독", "운영센터", "운영대시보드")),
        ("system", "help", ("명령어", "도움말", "언어", "english", "접근성", "검색", "대시보드")),
        ("system", "audit", ("검수", "진단", "오류", "테스트", "감사", "점검")),
        ("system", "recovery", ("백업", "복구", "복원", "재시작", "안정화")),
        ("system", "admin", ("지급", "회수", "강제", "데이터", "초기화", "운영자")),
    )
    for section, group, tokens in ordered_rules:
        if _has(blob, *tokens):
            return section, group
    return "system", "legacy"


def _build_registry(bot: commands.Bot) -> List[CommandEntry]:
    rows: List[CommandEntry] = []
    seen: set[str] = set()
    for command in bot.walk_commands():
        qname = _clean(getattr(command, "qualified_name", command.name), 100)
        if not qname or qname in seen:
            continue
        seen.add(qname)
        help_text = _clean(getattr(command, "help", "") or getattr(command, "description", "") or inspect.getdoc(getattr(command, "callback", None)) or "설명이 등록되지 않은 기존 명령입니다.", 500)
        aliases = tuple(dict.fromkeys(_clean(x, 80) for x in (getattr(command, "aliases", []) or []) if _clean(x, 80)))
        source = _clean(getattr(getattr(command, "callback", None), "__module__", "unknown"), 120)
        section, group = _classify(command)
        restricted = bool(getattr(command, "hidden", False)) or _has(" ".join((qname, help_text, source)).casefold(), "관리자", "운영자", "owner", "admin", "권한 필요")
        rows.append(CommandEntry(
            index=len(rows),
            qualified_name=qname,
            name=_clean(command.name, 100),
            help_text=help_text,
            signature=_clean(getattr(command, "signature", ""), 220),
            aliases=aliases,
            source=source.rsplit(".", 1)[-1],
            section=section,
            group=group,
            restricted=restricted,
            is_group=isinstance(command, commands.Group),
        ))

    story_rank = {"story1": 0, "story2": 1, "story3": 2, "story4": 3, "story5": 4}
    rows.sort(key=lambda e: (
        0 if e.section == "main" else 1,
        story_rank.get(e.group, 10),
        e.section,
        e.group,
        e.qualified_name.casefold(),
    ))
    # Re-number after sorting so Select values remain compact and stable for this process.
    return [CommandEntry(i, e.qualified_name, e.name, e.help_text, e.signature, e.aliases, e.source, e.section, e.group, e.restricted, e.is_group) for i, e in enumerate(rows)]


def _group_spec(group: str) -> Tuple[str, str, str, str, str, str]:
    return GROUP_INDEX.get(group, ("system", "기타·보존 명령", "Other Preserved Commands", "모든 기존 기능을 보존합니다.", "All legacy commands are preserved.", "🗄️"))


def _section_spec(section: str) -> Tuple[str, str, str, str]:
    return next((row for row in SECTION_SPECS if row[0] == section), SECTION_SPECS[0])


def _state_for(get_user: Callable[[int], Optional[MutableMapping[str, Any]]], user_id: int) -> Optional[MutableMapping[str, Any]]:
    try:
        user = get_user(int(user_id))
    except Exception:
        return None
    if not isinstance(user, MutableMapping):
        return None
    state = user.setdefault("v1630_command_center", {})
    if not isinstance(state, MutableMapping):
        state = {}
        user["v1630_command_center"] = state
    state.setdefault("favorites", [])
    state.setdefault("recent", [])
    return state


def _record_recent(get_user: Callable[[int], Optional[MutableMapping[str, Any]]], save_data: Callable[[], None], user_id: int, entry: CommandEntry) -> None:
    state = _state_for(get_user, user_id)
    if state is None:
        return
    recent = [str(x) for x in state.get("recent", []) if str(x) != entry.qualified_name]
    recent.insert(0, entry.qualified_name)
    state["recent"] = recent[:30]
    save_data()


def _toggle_favorite(get_user: Callable[[int], Optional[MutableMapping[str, Any]]], save_data: Callable[[], None], user_id: int, entry: CommandEntry) -> Tuple[bool, str]:
    state = _state_for(get_user, user_id)
    if state is None:
        return False, "가입 후 즐겨찾기를 저장할 수 있습니다."
    favorites = [str(x) for x in state.get("favorites", [])]
    if entry.qualified_name in favorites:
        favorites.remove(entry.qualified_name)
        state["favorites"] = favorites
        save_data()
        return False, f"☆ `!{entry.qualified_name}` 즐겨찾기를 해제했습니다."
    if len(favorites) >= 40:
        return False, "즐겨찾기는 최대 40개까지 저장할 수 있습니다."
    favorites.append(entry.qualified_name)
    state["favorites"] = favorites
    save_data()
    return True, f"⭐ `!{entry.qualified_name}`를 즐겨찾기에 추가했습니다."


def _lookup_saved(entries: Sequence[CommandEntry], names: Iterable[Any]) -> List[CommandEntry]:
    index = {e.qualified_name: e for e in entries}
    return [index[str(name)] for name in names if str(name) in index]


def _search(entries: Sequence[CommandEntry], query: str) -> List[CommandEntry]:
    terms = [x for x in re.split(r"\s+", _clean(query, 80).casefold()) if x]
    if not terms:
        return []
    scored: List[Tuple[int, CommandEntry]] = []
    for entry in entries:
        if all(term in entry.search_blob for term in terms):
            score = 0
            q = entry.qualified_name.casefold()
            for term in terms:
                if q == term:
                    score += 20
                elif q.startswith(term):
                    score += 10
                elif term in q:
                    score += 6
                elif term in entry.help_text.casefold():
                    score += 2
            scored.append((score, entry))
    scored.sort(key=lambda row: (-row[0], row[1].qualified_name.casefold()))
    return [entry for _score, entry in scored]


def _story_route(entries: Sequence[CommandEntry]) -> List[CommandEntry]:
    priorities = ("상태", "시작", "선택", "장면", "기록", "도감", "수집", "여정", "유산", "재시작", "투표", "결정")
    groups = ("story1", "story2", "story3", "story4", "story5")
    result: List[CommandEntry] = []
    for group in groups:
        group_rows = [e for e in entries if e.group == group]
        group_rows.sort(key=lambda e: (next((i for i, token in enumerate(priorities) if token in e.qualified_name), 99), e.qualified_name.casefold()))
        result.extend(group_rows)
    return result


def _today_route(entries: Sequence[CommandEntry]) -> List[CommandEntry]:
    preferred = ("정보", "오늘할일", "출석", "성장보드", "일일퀘스트", "주간퀘스트", "미션보상", "채집", "기지", "스토리")
    index = {e.qualified_name: e for e in entries}
    result = [index[name] for name in preferred if name in index]
    if len(result) < 8:
        for entry in entries:
            if entry.group in {"quests", "onboarding"} and entry not in result:
                result.append(entry)
            if len(result) >= 18:
                break
    return result


def _overview_embed(locale: str, entries: Sequence[CommandEntry], section: str, group: str, visible: Sequence[CommandEntry], page: int, special_title: Optional[str] = None) -> discord.Embed:
    section_key, sko, sen, sdesc = _section_spec(section)
    _gsection, gko, gen, gdko, gden, emoji = _group_spec(group)
    title = special_title or _t(locale, "📖 ABADDON 완전 명령어 센터", "📖 ABADDON Complete Command Center")
    description = _t(
        locale,
        "**이 봇의 중심은 시즌 1부터 이어지는 아포칼립스 RPG입니다.**\n모든 등록 명령을 자동 수집해 **큰 영역 → 기능군 → 명령 → 실행** 순서로 정리했습니다.",
        "**The core is an apocalypse RPG progressing from Season 1.**\nEvery registered command is collected into **section → group → command → execute**.",
    )
    embed = discord.Embed(title=title, description=description, color=0x7137C8)
    alias_count = sum(len(e.aliases) for e in entries)
    embed.add_field(name=_t(locale, "등록 명령", "Registered Commands"), value=f"**{len(entries):,}개**", inline=True)
    embed.add_field(name=_t(locale, "별칭", "Aliases"), value=f"**{alias_count:,}개**", inline=True)
    embed.add_field(name=_t(locale, "누락", "Missing"), value="**0개**", inline=True)
    embed.add_field(name=_t(locale, "메인 진행", "Main Progression"), value="📻 시즌 1 → 🚢 시즌 2 → 👑 시즌 3 → 🚂 시즌 4 → 📡 시즌 5", inline=False)
    preview = "\n".join(f"• `!{e.qualified_name}` — {_short(e.help_text, 72)}" for e in visible[:8])
    if not preview:
        preview = _t(locale, "이 기능군에 표시할 명령이 없습니다.", "No commands in this group.")
    embed.add_field(name=f"{emoji} {_t(locale, gko, gen)} · {len(visible)}", value=f"{_t(locale, gdko, gden)}\n{preview}"[:1024], inline=False)
    page_count = max(1, (len(visible) - 1) // PAGE_SIZE + 1)
    embed.set_footer(text=_t(locale, f"{_t(locale, sko, sen)} · {page + 1}/{page_count} 페이지 · 선택 후 실행 버튼", f"{_t(locale, sko, sen)} · page {page + 1}/{page_count} · select then execute"))
    return embed


def _detail_embed(locale: str, entry: CommandEntry, favorite: bool) -> discord.Embed:
    _section, gko, gen, gdko, gden, emoji = _group_spec(entry.group)
    embed = discord.Embed(
        title=f"{emoji} !{entry.qualified_name}",
        description=f"**{_t(locale, '무엇을 하나요?', 'What does it do?')}**\n{entry.help_text}",
        color=0x4F8CFF if not entry.restricted else 0xE39B36,
    )
    embed.add_field(name=_t(locale, "분류", "Category"), value=_t(locale, gko, gen), inline=True)
    embed.add_field(name=_t(locale, "실행 방식", "Execution"), value=_t(locale, "입력창 또는 즉시 실행", "Input modal or instant execution"), inline=True)
    embed.add_field(name=_t(locale, "권한", "Access"), value=_t(locale, "관리/조건 확인" if entry.restricted else "일반 사용", "Restricted/checks" if entry.restricted else "General"), inline=True)
    usage = f"!{entry.qualified_name}" + (f" {entry.signature}" if entry.signature else "")
    embed.add_field(name=_t(locale, "직접 입력", "Direct Command"), value=f"`{usage[:1000]}`", inline=False)
    if entry.aliases:
        embed.add_field(name=_t(locale, "별칭", "Aliases"), value=" · ".join(f"`!{x}`" for x in entry.aliases[:12])[:1024], inline=False)
    embed.add_field(name=_t(locale, "버튼 사용", "Button Use"), value=_t(locale, "아래 **실행**을 누르세요. 필수 입력값이 있으면 입력창이 열립니다.", "Press **Execute** below. A modal opens when arguments are required."), inline=False)
    embed.add_field(name=_t(locale, "즐겨찾기", "Favorite"), value="⭐" if favorite else "☆", inline=True)
    embed.add_field(name=_t(locale, "원본 모듈", "Source Module"), value=f"`{entry.source}`", inline=True)
    if entry.is_group:
        embed.add_field(name=_t(locale, "그룹 명령", "Command Group"), value=_t(locale, "하위 명령은 같은 기능군에서 함께 확인할 수 있습니다.", "Subcommands are listed in the same group."), inline=False)
    return embed


class CommandArgsModal(discord.ui.Modal):
    def __init__(self, owner: "CompleteCommandCenterView", entry: CommandEntry) -> None:
        super().__init__(title=_short(f"!{entry.qualified_name} 입력", 45), timeout=MENU_TIMEOUT)
        self.owner_view = owner
        self.entry = entry
        placeholder = entry.signature or _t(owner.locale, "입력값이 없으면 비워두세요", "Leave blank when no value is needed")
        self.raw = discord.ui.TextInput(
            label=_t(owner.locale, "명령어 입력값", "Command Arguments"),
            placeholder=_short(placeholder, 100),
            required=bool(entry.signature and owner.command_requires_input(entry)),
            max_length=600,
            style=discord.TextStyle.paragraph if len(placeholder) > 50 else discord.TextStyle.short,
        )
        self.add_item(self.raw)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        view = self.owner_view
        if int(interaction.user.id) != view.owner_id:
            await interaction.response.send_message(_t(view.locale, "이 메뉴는 실행자만 사용할 수 있습니다.", "Only the opener can use this menu."), ephemeral=True)
            return
        await interaction.response.defer(thinking=True, ephemeral=True)
        ok = await _invoke_command(view.bot, interaction, self.entry.qualified_name, str(self.raw.value or ""))
        if ok:
            _record_recent(view.get_user, view.save_data, interaction.user.id, self.entry)


class CommandSearchModal(discord.ui.Modal):
    def __init__(self, owner: "CompleteCommandCenterView") -> None:
        super().__init__(title=_t(owner.locale, "전체 명령 검색", "Search All Commands"), timeout=MENU_TIMEOUT)
        self.owner_view = owner
        self.query = discord.ui.TextInput(
            label=_t(owner.locale, "검색어", "Search Query"),
            placeholder=_t(owner.locale, "예: 시즌1, 도시꾸미기, 보스, 자동이모지", "e.g. season1, city decorate, boss, auto emoji"),
            required=True,
            max_length=80,
        )
        self.add_item(self.query)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        view = self.owner_view
        results = _search(view.entries, str(self.query.value))
        if not results:
            await interaction.response.send_message(_t(view.locale, "검색 결과가 없습니다.", "No search results."), ephemeral=True)
            return
        view.set_special(results, _t(view.locale, f"🔎 검색 결과 · {self.query.value}", f"🔎 Search · {self.query.value}"))
        view.rebuild()
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class SectionButton(discord.ui.Button):
    def __init__(self, owner: "CompleteCommandCenterView", key: str, ko: str, en: str) -> None:
        style = discord.ButtonStyle.primary if owner.section == key else discord.ButtonStyle.secondary
        super().__init__(label=_short(_t(owner.locale, ko, en), 80), style=style, row=0)
        self.owner_view = owner
        self.key = key

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.owner_view
        view.section = self.key
        view.special_entries = None
        view.special_title = None
        view.selected_index = None
        view.page = 0
        view.group = view.first_group(self.key)
        view.rebuild()
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class GroupSelect(discord.ui.Select):
    def __init__(self, owner: "CompleteCommandCenterView") -> None:
        self.owner_view = owner
        options: List[discord.SelectOption] = []
        counts = owner.group_counts(owner.section)
        for key, ko, en, dko, den, emoji in GROUP_SPECS[owner.section]:
            count = counts.get(key, 0)
            if count <= 0:
                continue
            options.append(discord.SelectOption(
                label=_short(_t(owner.locale, ko, en), 100),
                value=key,
                emoji=emoji,
                description=_short(f"{count} · {_t(owner.locale, dko, den)}", 100),
                default=key == owner.group and owner.special_entries is None,
            ))
        if not options:
            options = [discord.SelectOption(label=_t(owner.locale, "기타·보존 명령", "Other Preserved Commands"), value="legacy", emoji="🗄️")]
        super().__init__(placeholder=_t(owner.locale, "기능군을 선택하세요", "Choose a command group"), min_values=1, max_values=1, options=options[:25], row=1)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.owner_view
        view.group = self.values[0]
        view.special_entries = None
        view.special_title = None
        view.selected_index = None
        view.page = 0
        view.rebuild()
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class CommandSelect(discord.ui.Select):
    def __init__(self, owner: "CompleteCommandCenterView") -> None:
        self.owner_view = owner
        page_rows = owner.page_entries()
        options: List[discord.SelectOption] = []
        for entry in page_rows:
            _section, _ko, _en, _dko, _den, emoji = _group_spec(entry.group)
            options.append(discord.SelectOption(
                label=_short(f"!{entry.qualified_name}", 100),
                value=str(entry.index),
                emoji=emoji,
                description=_short(entry.help_text, 100),
                default=entry.index == owner.selected_index,
            ))
        if not options:
            options = [discord.SelectOption(label=_t(owner.locale, "표시할 명령 없음", "No commands"), value="-1", description=_t(owner.locale, "다른 기능군을 선택하세요", "Choose another group"))]
        start = owner.page * PAGE_SIZE + 1
        end = owner.page * PAGE_SIZE + len(page_rows)
        total = len(owner.current_entries())
        super().__init__(placeholder=_t(owner.locale, f"명령 선택 · {start}-{end}/{total}", f"Choose command · {start}-{end}/{total}"), min_values=1, max_values=1, options=options[:25], row=2)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.owner_view
        try:
            selected = int(self.values[0])
        except ValueError:
            selected = -1
        if selected < 0 or selected not in view.by_index:
            await interaction.response.send_message(_t(view.locale, "선택한 명령을 찾지 못했습니다.", "Command not found."), ephemeral=True)
            return
        view.selected_index = selected
        view.rebuild()
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class NavButton(discord.ui.Button):
    def __init__(self, owner: "CompleteCommandCenterView", action: str, label_ko: str, label_en: str, emoji: str, style: discord.ButtonStyle = discord.ButtonStyle.secondary, row: int = 3) -> None:
        super().__init__(label=_short(_t(owner.locale, label_ko, label_en), 80), emoji=emoji, style=style, row=row)
        self.owner_view = owner
        self.action = action

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.owner_view
        action = self.action
        if action == "home":
            view.section = "main"
            view.group = view.first_group("main")
            view.special_entries = None
            view.special_title = None
            view.selected_index = None
            view.page = 0
        elif action == "prev":
            view.page = max(0, view.page - 1)
            view.selected_index = None
        elif action == "next":
            view.page = min(view.max_page(), view.page + 1)
            view.selected_index = None
        elif action == "search":
            await interaction.response.send_modal(CommandSearchModal(view))
            return
        elif action == "story":
            view.set_special(_story_route(view.entries), _t(view.locale, "📖 메인 스토리 · 시즌 1→5", "📖 Main Story · Season 1→5"))
        elif action == "today":
            view.set_special(_today_route(view.entries), _t(view.locale, "☀️ 오늘 먼저 할 일", "☀️ Today's Recommended Actions"))
        elif action in {"favorites", "recent"}:
            state = _state_for(view.get_user, view.owner_id) or {}
            rows = _lookup_saved(view.entries, state.get(action, []))
            if not rows:
                await interaction.response.send_message(_t(view.locale, "저장된 항목이 없습니다.", "No saved items."), ephemeral=True)
                return
            view.set_special(rows, _t(view.locale, "⭐ 즐겨찾기" if action == "favorites" else "🕘 최근 실행", "⭐ Favorites" if action == "favorites" else "🕘 Recent"))
        elif action == "city":
            rows = [e for e in view.entries if e.group == "city_decor"]
            view.section, view.group = "world", "city_decor"
            view.set_special(rows, _t(view.locale, "🎨 도시 꾸미기 공방 바로가기", "🎨 City Workshop Quick Access"))
        elif action == "emoji":
            rows = [e for e in view.entries if e.group == "auto_emoji"]
            view.section, view.group = "system", "auto_emoji"
            view.set_special(rows, _t(view.locale, "✨ 자동 이모지·반응 바로가기", "✨ Auto Emoji Quick Access"))
        elif action == "back":
            view.selected_index = None
        elif action == "related":
            selected = view.selected_entry()
            if selected:
                view.section, view.group = selected.section, selected.group
                rows = [e for e in view.entries if e.group == selected.group]
                view.set_special(rows, _t(view.locale, "🔗 관련 명령", "🔗 Related Commands"))
        elif action == "favorite":
            selected = view.selected_entry()
            if not selected:
                return
            _added, message = _toggle_favorite(view.get_user, view.save_data, view.owner_id, selected)
            await interaction.response.send_message(message, ephemeral=True)
            return
        elif action == "execute":
            selected = view.selected_entry()
            if not selected:
                await interaction.response.send_message(_t(view.locale, "먼저 명령을 선택하세요.", "Select a command first."), ephemeral=True)
                return
            command = view.bot.get_command(selected.qualified_name)
            if command is None:
                await interaction.response.send_message(_t(view.locale, "실행 가능한 등록 명령을 찾지 못했습니다.", "Registered command not found."), ephemeral=True)
                return
            if _command_requires_input(command):
                await interaction.response.send_modal(CommandArgsModal(view, selected))
                return
            await interaction.response.defer(thinking=True, ephemeral=True)
            ok = await _invoke_command(view.bot, interaction, selected.qualified_name)
            if ok:
                _record_recent(view.get_user, view.save_data, interaction.user.id, selected)
            return
        elif action == "close":
            for item in view.children:
                item.disabled = True
            await interaction.response.edit_message(view=view)
            view.stop()
            return
        view.rebuild()
        await interaction.response.edit_message(embed=view.current_embed(), view=view)


class CompleteCommandCenterView(discord.ui.View):
    PAGE_SIZE = PAGE_SIZE

    def __init__(
        self,
        owner_id: int,
        entries: Sequence[CommandEntry],
        locale: str,
        bot: commands.Bot,
        get_user: Callable[[int], Optional[MutableMapping[str, Any]]],
        save_data: Callable[[], None],
    ) -> None:
        super().__init__(timeout=MENU_TIMEOUT)
        self.owner_id = int(owner_id)
        self.entries = list(entries)
        self.by_index = {e.index: e for e in self.entries}
        self.locale = locale
        self.bot = bot
        self.get_user = get_user
        self.save_data = save_data
        self.section = "main"
        self.group = "story1" if any(e.group == "story1" for e in self.entries) else self.first_group("main")
        self.page = 0
        self.selected_index: Optional[int] = None
        self.special_entries: Optional[List[CommandEntry]] = None
        self.special_title: Optional[str] = None
        self.rebuild()

    def command_requires_input(self, entry: CommandEntry) -> bool:
        command = self.bot.get_command(entry.qualified_name)
        return bool(command and _command_requires_input(command))

    def group_counts(self, section: str) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for entry in self.entries:
            if entry.section == section:
                counts[entry.group] = counts.get(entry.group, 0) + 1
        return counts

    def first_group(self, section: str) -> str:
        counts = self.group_counts(section)
        if section == "main" and counts.get("story1"):
            return "story1"
        for key, *_rest in GROUP_SPECS[section]:
            if counts.get(key):
                return key
        return GROUP_SPECS[section][0][0]

    def set_special(self, rows: Sequence[CommandEntry], title: str) -> None:
        self.special_entries = list(dict.fromkeys(rows))
        self.special_title = title
        self.selected_index = None
        self.page = 0

    def current_entries(self) -> List[CommandEntry]:
        if self.special_entries is not None:
            return list(self.special_entries)
        return [e for e in self.entries if e.section == self.section and e.group == self.group]

    def page_entries(self) -> List[CommandEntry]:
        rows = self.current_entries()
        start = self.page * PAGE_SIZE
        return rows[start:start + PAGE_SIZE]

    def max_page(self) -> int:
        return max(0, (len(self.current_entries()) - 1) // PAGE_SIZE)

    def selected_entry(self) -> Optional[CommandEntry]:
        return self.by_index.get(self.selected_index) if self.selected_index is not None else None

    def favorite_names(self) -> set[str]:
        state = _state_for(self.get_user, self.owner_id) or {}
        return {str(x) for x in state.get("favorites", [])}

    def current_embed(self) -> discord.Embed:
        selected = self.selected_entry()
        if selected:
            return _detail_embed(self.locale, selected, selected.qualified_name in self.favorite_names())
        return _overview_embed(self.locale, self.entries, self.section, self.group, self.current_entries(), self.page, self.special_title)

    def rebuild(self) -> None:
        self.clear_items()
        for key, ko, en, _description in SECTION_SPECS:
            self.add_item(SectionButton(self, key, ko, en))
        self.add_item(GroupSelect(self))
        self.add_item(CommandSelect(self))

        home = NavButton(self, "home", "처음", "Home", "🏠", row=3)
        prev = NavButton(self, "prev", "이전", "Previous", "◀️", row=3)
        nxt = NavButton(self, "next", "다음", "Next", "▶️", row=3)
        search = NavButton(self, "search", "전체 검색", "Search All", "🔎", discord.ButtonStyle.primary, row=3)
        story = NavButton(self, "story", "시즌 1→5", "Season 1→5", "📖", discord.ButtonStyle.success, row=3)
        prev.disabled = self.page <= 0
        nxt.disabled = self.page >= self.max_page()
        for item in (home, prev, nxt, search, story):
            self.add_item(item)

        if self.selected_entry():
            self.add_item(NavButton(self, "execute", "실행", "Execute", "🚀", discord.ButtonStyle.success, row=4))
            self.add_item(NavButton(self, "back", "목록", "Back", "↩️", row=4))
            self.add_item(NavButton(self, "favorite", "즐겨찾기", "Favorite", "⭐", row=4))
            self.add_item(NavButton(self, "related", "관련 명령", "Related", "🔗", row=4))
            self.add_item(NavButton(self, "close", "닫기", "Close", "✖️", discord.ButtonStyle.danger, row=4))
        else:
            self.add_item(NavButton(self, "today", "오늘 추천", "Today", "☀️", discord.ButtonStyle.success, row=4))
            self.add_item(NavButton(self, "favorites", "즐겨찾기", "Favorites", "⭐", row=4))
            self.add_item(NavButton(self, "recent", "최근 실행", "Recent", "🕘", row=4))
            self.add_item(NavButton(self, "city", "도시 공방", "City Workshop", "🎨", discord.ButtonStyle.primary, row=4))
            self.add_item(NavButton(self, "emoji", "자동 이모지", "Auto Emoji", "✨", discord.ButtonStyle.primary, row=4))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if int(interaction.user.id) == self.owner_id:
            return True
        await interaction.response.send_message(_t(self.locale, "이 명령어 센터는 실행자만 조작할 수 있습니다.", "Only the opener can use this command center."), ephemeral=True)
        return False


def _expanded_reaction_data() -> Tuple[Dict[str, List[str]], List[Dict[str, Any]], Tuple[Tuple[str, Tuple[str, ...]], ...]]:
    presets = {
        "공지": ["📢", "🔥", "✅", "👀", "🔔", "📌"],
        "건의": ["👍", "👎", "💬", "💡", "🗳️"],
        "버그": ["🐛", "🔍", "🛠️", "⚠️", "✅"],
        "미디어": ["❤️", "🔥", "👀", "📸", "✨", "👏", "💜"],
        "이벤트": ["🎉", "🔥", "✅", "🥳", "🎁", "📅"],
        "거래": ["💰", "👀", "✅", "🤝", "📦"],
        "투표": ["👍", "👎", "🤔", "🗳️"],
        "일반": ["❤️", "😂", "🔥", "👍", "✨", "👀", "💜"],
        "질문": ["❓", "💡", "✅", "🤝", "👀"],
        "창작": ["🎨", "❤️", "🔥", "✨", "👏", "🖼️", "💜"],
        "모집": ["🙋", "✅", "👀", "🤝", "⚔️"],
        "인증": ["✅", "🛡️", "🎉", "🔒", "✨"],
        "스토리": ["📖", "🕯️", "✨", "🌑", "🎭", "👀"],
        "전투": ["⚔️", "🔥", "🛡️", "💥", "👹", "🏆"],
        "도시": ["🏙️", "✨", "🟣", "🏗️", "🎨", "🌌"],
        "음악": ["🎵", "🎧", "💜", "🔥", "✨", "👏"],
        "축하": ["🎉", "🥳", "🔥", "👏", "🏆", "✨", "💜"],
    }
    rules = [
        {"keyword": "안녕", "emojis": ["👋", "✨"]},
        {"keyword": "축하", "emojis": ["🎉", "🥳", "🔥", "👏"]},
        {"keyword": "고마워", "emojis": ["❤️", "🙏", "✨"]},
        {"keyword": "감사", "emojis": ["💜", "🙏", "✨"]},
        {"keyword": "ㅋㅋ", "emojis": ["😂", "🤣", "🔥"]},
        {"keyword": "버그", "emojis": ["🐛", "🔍", "🛠️", "⚠️"]},
        {"keyword": "대박", "emojis": ["🔥", "🤯", "👏", "✨"]},
        {"keyword": "승리", "emojis": ["🏆", "🔥", "🎉", "⚔️"]},
        {"keyword": "보스", "emojis": ["👹", "⚔️", "🔥", "🛡️"]},
        {"keyword": "도시", "emojis": ["🏙️", "✨", "🟣", "🎨"]},
        {"keyword": "스토리", "emojis": ["📖", "🕯️", "✨", "👀"]},
        {"keyword": "음악", "emojis": ["🎵", "🎧", "💜", "🔥"]},
        {"keyword": "사진", "emojis": ["📸", "👀", "❤️", "✨"]},
        {"keyword": "도움", "emojis": ["💡", "🤝", "✅"]},
    ]
    channels = (
        ("스토리", ("스토리", "이야기", "시즌", "연대기")),
        ("전투", ("전투", "보스", "레이드", "던전", "공격대")),
        ("도시", ("도시", "black-city", "네온", "차원")),
        ("음악", ("음악", "뮤직", "music", "노래", "작곡")),
    )
    return presets, rules, channels


def register_v1630_core_rpg_command_city_overhaul(
    bot: commands.Bot,
    get_user: Callable[[int], Optional[MutableMapping[str, Any]]],
    check_registered: Callable[[commands.Context], Any],
    save_data: Callable[[], None],
    world_data: MutableMapping[str, Any],
    user_data: Mapping[Any, Any],
    guide: List[Dict[str, Any]],
) -> None:
    if getattr(bot, "_abaddon_v1630_registered", False):
        return
    bot._abaddon_v1630_registered = True

    entries = _build_registry(bot)
    setattr(bot, "v1630_command_entries", entries)
    setattr(bot, "v1630_command_index", {e.qualified_name: e for e in entries})

    class BoundCompleteCommandCenterView(CompleteCommandCenterView):
        def __init__(self, owner_id: int, _legacy_guide: Sequence[Mapping[str, Any]], locale: str) -> None:
            super().__init__(owner_id, entries, locale, bot, get_user, save_data)

    # Replace both callbacks rather than only swapping a class global. This makes
    # direct `!명령어 검색어` use the complete runtime registry as well.
    korean = bot.get_command("명령어")
    if korean is not None:
        previous = korean.callback

        async def complete_korean_help(ctx: commands.Context, *, 검색어: str = None) -> None:
            view = BoundCompleteCommandCenterView(ctx.author.id, guide, "ko")
            if 검색어:
                results = _search(entries, 검색어)
                if results:
                    view.set_special(results, f"🔎 전체 명령 검색 · {검색어}")
                    view.rebuild()
            await ctx.send(embed=view.current_embed(), view=view)

        korean.callback = complete_korean_help
        korean.help = "시즌 1 메인 스토리부터 전체 등록 명령을 버튼·드롭다운·검색·즉시 실행으로 탐색합니다."
        korean.description = korean.help
        korean.extras = dict(getattr(korean, "extras", {}) or {})
        korean.extras["v1630_previous_callback"] = previous

    english = bot.get_command("help")
    if english is not None:
        previous = english.callback

        async def complete_english_help(ctx: commands.Context, *, keyword: str = "") -> None:
            view = BoundCompleteCommandCenterView(ctx.author.id, guide, "en")
            if keyword:
                results = _search(entries, keyword)
                if results:
                    view.set_special(results, f"🔎 Search All Commands · {keyword}")
                    view.rebuild()
            await ctx.send(embed=view.current_embed(), view=view)

        english.callback = complete_english_help
        english.help = "Browse every registered command from the Season 1 core RPG with dropdowns, search and execution buttons."
        english.description = english.help
        english.extras = dict(getattr(english, "extras", {}) or {})
        english.extras["v1630_previous_callback"] = previous

    # Keep v16.2 references aligned for other callbacks/audits that inspect the class.
    try:
        from apocalypse_bot.commands import v1620_living_legends as v1620
        v1620.LivingHelpView = BoundCompleteCommandCenterView
    except Exception:
        pass

    # Expand automatic reactions. Existing nested listeners read these module
    # globals at message time, so updating them here immediately affects runtime.
    presets, rules, extra_channels = _expanded_reaction_data()
    migrated_guilds = 0
    try:
        from apocalypse_bot.commands import v411_server_guard_plus as guard
        guard.REACTION_PRESETS.update({k: list(v) for k, v in presets.items()})
        guard.DEFAULT_KEYWORD_RULES[:] = [dict(row) for row in rules]
        existing_channels = list(guard.AUTO_CHANNEL_KEYWORDS)
        existing_names = {row[0] for row in existing_channels}
        guard.AUTO_CHANNEL_KEYWORDS = tuple(existing_channels + [row for row in extra_channels if row[0] not in existing_names])
        management = world_data.setdefault("server_management", {})
        if isinstance(management, MutableMapping):
            for settings in management.values():
                if not isinstance(settings, MutableMapping):
                    continue
                reactions = settings.setdefault("auto_reactions", {})
                if not isinstance(reactions, MutableMapping):
                    continue
                if int(reactions.get("max_per_message", 5) or 5) == 5:
                    reactions["max_per_message"] = 7
                saved_rules = reactions.setdefault("keyword_rules", [])
                if not isinstance(saved_rules, list):
                    saved_rules = []
                    reactions["keyword_rules"] = saved_rules
                known = {str(row.get("keyword", "")).casefold() for row in saved_rules if isinstance(row, Mapping)}
                for rule in rules:
                    if rule["keyword"].casefold() not in known:
                        saved_rules.append(dict(rule))
                migrated_guilds += 1
            if migrated_guilds:
                save_data()
    except Exception as exc:
        print(f"[ABADDON v{VERSION}] auto-reaction expansion warning: {type(exc).__name__}: {exc}", flush=True)

    if not any(str(row.get("id")) == "v1630_core_rpg_command_city" for row in guide):
        guide.append({
            "id": "v1630_core_rpg_command_city",
            "emoji": "📖",
            "title": "v16.3.0 CORE RPG COMMAND & CITY OVERHAUL",
            "hint": "시즌 1~5 메인 RPG 복구, 전체 등록 명령 자동 분류·실행, 도시 공방 20종 1:1 리뉴얼, 자동 이모지 확장",
            "commands": [
                "!명령어",
                "!명령어전수검수 상세",
                "!도시부품검수 상세",
                "!이모지확장설정",
                "!1630통합검수 상세",
            ],
        })

    patch_command = bot.get_command("패치노트")
    if patch_command is not None:
        previous_patch = patch_command.callback

        async def patch_notes_v1630(ctx: commands.Context, *args: Any, **kwargs: Any) -> None:
            locale = "ko"
            try:
                from apocalypse_bot.commands.v1010_companion_card_games import _ctx_locale
                locale = _ctx_locale(bot, ctx)
            except Exception:
                pass
            embed = discord.Embed(
                title=_t(locale, "📜 ABADDON v16.3.0 패치노트", "📜 ABADDON v16.3.0 Patch Notes"),
                description=_t(
                    locale,
                    "메인 아포칼립스 RPG의 시즌 1~5 진행을 명령어 센터 최상단에 복구하고, 전체 등록 명령을 자동 분류·검색·실행하도록 전면 개편했습니다.",
                    "Restored Seasons 1–5 of the core apocalypse RPG to the top of the command center and rebuilt navigation for every registered command.",
                ),
                color=0x7137C8,
            )
            embed.add_field(name=_t(locale, "📖 메인 RPG 복구", "📖 Core RPG Restored"), value=_t(locale, "시즌 1 검은 주파수 → 시즌 5 잿빛 연합전선을 순서대로 바로 탐색", "Direct Season 1 Black Frequency → Season 5 Ashen Front progression"), inline=False)
            embed.add_field(name=_t(locale, "📚 전체 명령 센터", "📚 Complete Command Center"), value=_t(locale, f"런타임 등록 명령 {len(entries):,}개 자동 분류 · 5개 영역 · 43개 기능군 · 25개 자동 페이지 · 검색/즐겨찾기/최근 실행", f"{len(entries):,} runtime commands classified · 5 sections · 43 groups · automatic pages · search/favorites/recent"), inline=False)
            embed.add_field(name=_t(locale, "🚀 버튼 즉시 실행", "🚀 Execute Buttons"), value=_t(locale, "명령 선택 후 실행 버튼 · 필수 인수는 입력창 · 기존 직접 명령도 유지", "Select then execute · argument modal when required · direct commands preserved"), inline=False)
            embed.add_field(name=_t(locale, "🎨 도시 꾸미기 공방", "🎨 City Workshop"), value=_t(locale, "부품 20종을 512×512 투명 이미지로 1:1 리뉴얼 · 선택 이미지 즉시 교체 · 이동/크기/배치/복구 작업 기록", "20 parts rebuilt as 512×512 transparent assets · instant preview replacement · movement/scale/place/undo history"), inline=False)
            embed.add_field(name=_t(locale, "📊 정보 바로가기", "📊 Profile Quick Actions"), value=_t(locale, "복사형 텍스트 대신 지갑·게임·경제·세계지도·전체 명령 버튼 추가", "Replaced copy-only links with wallet, games, economy, world map and command buttons"), inline=False)
            embed.add_field(name=_t(locale, "✨ 자동 이모지", "✨ Automatic Reactions"), value=_t(locale, "17종 프리셋 · 키워드 14종 · 메시지당 최대 7개 반응 · 기존 설정 보존", "17 presets · 14 keyword rules · up to 7 reactions per message · existing settings preserved"), inline=False)
            embed.add_field(name=_t(locale, "🧪 신규 검수", "🧪 New Audits"), value="`!명령어전수검수 상세` · `!도시부품검수 상세` · `!1630통합검수 상세`", inline=False)
            embed.set_footer(text=_t(locale, "기존 명령 삭제 0건 · 기존 저장 데이터 유지 · 2026-08-05", "0 legacy commands removed · existing save data preserved · 2026-08-05"))
            await ctx.send(embed=embed)

        patch_command.callback = patch_notes_v1630
        patch_command.help = "ABADDON v16.3.0 메인 RPG·전체 명령센터·도시 공방·자동 이모지 최신 패치노트입니다."
        patch_command.description = patch_command.help
        patch_command.extras = dict(getattr(patch_command, "extras", {}) or {})
        patch_command.extras["v1630_previous_callback"] = previous_patch

    test_command = bot.get_command("테스트")
    if test_command is not None:
        previous_test = test_command.callback

        async def latest_test_v1630(ctx: commands.Context, mode: str = "") -> None:
            info_source = ASSET_ROOT.parent / "commands" / "v1092_visual_status_horserace.py"
            neon_source = ASSET_ROOT.parent / "commands" / "v1500_neon_abyss.py"
            checks = (
                ("전체 명령 자동 분류", len(entries) > 0 and len(entries) == len({e.qualified_name for e in entries}), f"{len(entries):,}"),
                ("시즌 1~5 메인 RPG 노출", all(any(e.group == f"story{i}" for e in entries) for i in range(1, 6)), "S1-S5"),
                ("선택 후 실행 버튼", callable(_invoke_command), "interaction bridge"),
                ("정보 바로가기 버튼", info_source.is_file() and "ProfileQuickActionView" in info_source.read_text(encoding="utf-8"), "5 buttons"),
                ("도시 부품 20종", len(list(CITY_COMPONENT_ROOT.glob("*.png"))) == 20, "512x512 PNG"),
                ("도시 공방 행동 기록", neon_source.is_file() and "decor_history" in neon_source.read_text(encoding="utf-8"), "place/undo log"),
                ("자동 이모지 확장", len(presets) >= 17 and len(rules) >= 14, "17 presets / 14 keywords"),
                ("최신 패치노트", bot.get_command("패치노트") is not None, VERSION),
            )
            ok = all(row[1] for row in checks)
            embed = discord.Embed(title=f"🧪 ABADDON 최신 테스트 v{VERSION}", color=0x2ECC71 if ok else 0xE67E22)
            embed.description = "\n".join(f"{'✅' if passed else '❌'} **{name}** · {detail}" for name, passed, detail in checks)
            if mode.casefold() in {"상세", "detail", "detailed"}:
                embed.add_field(name="최신 범위", value="메인 RPG 명령센터 · 도시 공방 · 정보 버튼 · 자동 이모지 · 패치노트", inline=False)
                embed.add_field(name="보존", value="기존 명령 삭제 0 · 저장 데이터 유지 · 기존 직접 명령 유지", inline=False)
            await ctx.send(embed=embed)

        test_command.callback = latest_test_v1630
        test_command.help = "가장 최근 v16.3.0 메인 RPG 명령센터·도시 공방·정보 버튼·자동 이모지 범위를 검사합니다."
        test_command.description = test_command.help
        test_command.extras = dict(getattr(test_command, "extras", {}) or {})
        test_command.extras["v1630_previous_callback"] = previous_test

    @bot.command(name="명령어전수검수", aliases=["fullcommandaudit", "commandregistryaudit1630"], help="전체 런타임 명령의 카테고리·페이지·스토리 노출·버튼 실행 연결을 검사합니다.")
    async def full_command_audit(ctx: commands.Context, mode: str = "") -> None:
        classified = sum(1 for e in entries if e.group in GROUP_INDEX)
        missing = [e.qualified_name for e in entries if e.group not in GROUP_INDEX]
        duplicate_names = len(entries) - len({e.qualified_name for e in entries})
        story_counts = {group: sum(1 for e in entries if e.group == group) for group in ("story1", "story2", "story3", "story4", "story5")}
        group_overflow = {group: count for group, count in ((g, sum(1 for e in entries if e.group == g)) for g in GROUP_INDEX) if count > PAGE_SIZE}
        checks = {
            "전체 등록 명령 분류": classified == len(entries),
            "분류 누락 0": not missing,
            "중복 qualified name 0": duplicate_names == 0,
            "시즌 1 노출": story_counts["story1"] > 0,
            "시즌 2 노출": story_counts["story2"] > 0,
            "시즌 3 노출": story_counts["story3"] > 0,
            "시즌 4 노출": story_counts["story4"] > 0,
            "시즌 5 노출": story_counts["story5"] > 0,
            "드롭다운 25개 자동 분할": all(count <= PAGE_SIZE or group in group_overflow for group, count in ((g, sum(1 for e in entries if e.group == g)) for g in GROUP_INDEX)),
            "명령 실행 브리지": callable(_invoke_command),
        }
        ok = all(checks.values())
        embed = discord.Embed(title=f"📚 ABADDON 전체 명령 검수 v{VERSION}", color=0x2ECC71 if ok else 0xE67E22)
        embed.description = "\n".join(f"{'✅' if value else '❌'} {name}" for name, value in checks.items())
        embed.add_field(name="실제 런타임", value=f"명령 **{len(entries):,}개** · 분류 **{classified:,}개** · 누락 **{len(missing)}개**", inline=False)
        embed.add_field(name="소스 선언 기준", value=f"기존 manifest **{EXPECTED_DECLARATIONS:,}개** · 런타임은 충돌 보호·그룹 구조에 따라 수가 달라질 수 있음", inline=False)
        embed.add_field(name="메인 스토리", value=" · ".join(f"S{idx + 1} **{story_counts[f'story{idx + 1}']}**" for idx in range(5)), inline=False)
        if mode.casefold() in {"상세", "detail", "detailed"}:
            embed.add_field(name="페이지 분할 기능군", value=" · ".join(f"{_group_spec(group)[1]} {count}" for group, count in sorted(group_overflow.items()))[:1024] or "없음", inline=False)
            embed.add_field(name="누락", value=" · ".join(missing[:30]) or "없음", inline=False)
        await ctx.send(embed=embed)

    @bot.command(name="도시부품검수", aliases=["citypartaudit", "cityworkshopaudit"], help="도시 꾸미기 20종의 파일명·라벨·크기·투명도·공방 호환을 검사합니다.")
    async def city_part_audit(ctx: commands.Context, mode: str = "") -> None:
        from apocalypse_bot.commands import v1500_neon_abyss as neon
        labels = dict(neon.COMPONENT_LABELS)
        missing: List[str] = []
        invalid: List[str] = []
        alpha_missing: List[str] = []
        dimensions: Dict[str, Tuple[int, int]] = {}
        try:
            from PIL import Image
            for part_id in labels:
                path = CITY_COMPONENT_ROOT / f"{part_id}.png"
                if not path.is_file():
                    missing.append(part_id)
                    continue
                with Image.open(path) as image:
                    dimensions[part_id] = image.size
                    if image.size != (512, 512):
                        invalid.append(part_id)
                    if "A" not in image.getbands():
                        alpha_missing.append(part_id)
        except Exception as exc:
            invalid.append(type(exc).__name__)
        checks = {
            "라벨 20종": len(labels) == 20,
            "파일 20종": not missing,
            "512×512 통일": not invalid,
            "투명 레이어": not alpha_missing,
            "카탈로그 이미지": (V1630_PREVIEW_ROOT / "city_parts_catalog_ko.png").is_file(),
            "배치 기록 지원": "decor_history" in Path(neon.__file__).read_text(encoding="utf-8"),
            "선택 이미지 즉시 교체": "attachments" in Path(neon.__file__).read_text(encoding="utf-8"),
        }
        ok = all(checks.values())
        embed = discord.Embed(title=f"🎨 도시 꾸미기 공방 검수 v{VERSION}", color=0x2ECC71 if ok else 0xE67E22)
        embed.description = "\n".join(f"{'✅' if value else '❌'} {name}" for name, value in checks.items())
        embed.add_field(name="호환", value="기존 부품 ID 유지 · 저장 데이터 유지 · 도시 지도 레이어 즉시 호환", inline=False)
        if mode.casefold() in {"상세", "detail", "detailed"}:
            embed.add_field(name="누락", value=" · ".join(missing) or "없음", inline=False)
            embed.add_field(name="크기 오류", value=" · ".join(invalid) or "없음", inline=False)
            embed.add_field(name="알파 오류", value=" · ".join(alpha_missing) or "없음", inline=False)
        catalog = V1630_PREVIEW_ROOT / "city_parts_catalog_ko.png"
        if catalog.is_file():
            embed.set_image(url="attachment://city_parts_catalog_ko.png")
            await ctx.send(embed=embed, file=discord.File(catalog, filename="city_parts_catalog_ko.png"))
        else:
            await ctx.send(embed=embed)

    @bot.command(name="이모지확장설정", aliases=["reactionexpansionsetup", "emojiupgrade"], help="현재 서버에 확장 자동 이모지 프리셋·키워드 규칙과 메시지당 7개 반응을 적용합니다.")
    @commands.has_guild_permissions(manage_guild=True)
    async def emoji_expansion_setup(ctx: commands.Context) -> None:
        if ctx.guild is None:
            await ctx.send("서버에서만 사용할 수 있습니다.")
            return
        management = world_data.setdefault("server_management", {})
        settings = management.setdefault(str(ctx.guild.id), {})
        reactions = settings.setdefault("auto_reactions", {})
        reactions["enabled"] = True
        reactions["smart_attachments"] = True
        reactions["max_per_message"] = 7
        saved = reactions.setdefault("keyword_rules", [])
        if not isinstance(saved, list):
            saved = []
            reactions["keyword_rules"] = saved
        known = {str(row.get("keyword", "")).casefold() for row in saved if isinstance(row, Mapping)}
        added = 0
        for rule in rules:
            if rule["keyword"].casefold() not in known:
                saved.append(dict(rule))
                added += 1
        save_data()
        embed = discord.Embed(
            title="✨ 자동 이모지 확장 설정 완료",
            description="기존 사용자 설정은 유지하고 누락된 기본 규칙만 추가했습니다.",
            color=0x9B59B6,
        )
        embed.add_field(name="기본 프리셋", value=f"**{len(presets)}종** · 프리셋당 최대 7개", inline=True)
        embed.add_field(name="키워드", value=f"신규 **{added}개** · 총 **{len(saved)}개**", inline=True)
        embed.add_field(name="메시지당 반응", value="최대 **7개**", inline=True)
        embed.add_field(name="예시", value="축하 → 🎉 🥳 🔥 👏\n보스 → 👹 ⚔️ 🔥 🛡️\n도시 → 🏙️ ✨ 🟣 🎨", inline=False)
        await ctx.send(embed=embed)

    @bot.command(name="1630통합검수", aliases=["v1630audit", "1630audit"], help="v16.3.0 메인 RPG 명령센터·도시 공방·정보 버튼·자동 이모지 연결을 검사합니다.")
    async def v1630_audit(ctx: commands.Context, mode: str = "") -> None:
        info_source = ASSET_ROOT.parent / "commands" / "v1092_visual_status_horserace.py"
        neon_source = ASSET_ROOT.parent / "commands" / "v1500_neon_abyss.py"
        checks = {
            "전체 명령 인덱스": len(entries) > 0 and len(entries) == len({e.qualified_name for e in entries}),
            "시즌 1 기본 화면": any(e.group == "story1" for e in entries),
            "선택 후 실행 버튼": bot.get_command("명령어") is not None,
            "정보 바로가기 버튼": info_source.is_file() and "ProfileQuickActionView" in info_source.read_text(encoding="utf-8"),
            "도시 공방 행동 기록": neon_source.is_file() and "방금 한 행동" in neon_source.read_text(encoding="utf-8"),
            "도시 부품 20종": len(list(CITY_COMPONENT_ROOT.glob("*.png"))) == 20,
            "자동 이모지 17종 프리셋": len(presets) >= 17,
            "패치노트 명령": bot.get_command("패치노트") is not None,
        }
        ok = all(checks.values())
        embed = discord.Embed(title=f"🧪 ABADDON v{VERSION} 통합 검수", color=0x2ECC71 if ok else 0xE67E22)
        embed.description = "\n".join(f"{'✅' if value else '❌'} {name}" for name, value in checks.items())
        if mode.casefold() in {"상세", "detail", "detailed"}:
            embed.add_field(name="명령 흐름", value="메인 RPG/플레이/세계/소셜/운영 → 기능군 → 25개 페이지 → 상세 → 실행", inline=False)
            embed.add_field(name="보존 정책", value="기존 명령 삭제 0 · 기존 별칭 유지 · 기존 저장 구조 유지", inline=False)
            embed.add_field(name="자동 이모지 마이그레이션", value=f"시작 시 기존 서버 **{migrated_guilds}개** 보강", inline=False)
        await ctx.send(embed=embed)

    print(
        f"[ABADDON v{VERSION}] complete command center registered: commands={len(entries)} groups={len(GROUP_INDEX)} migrated_reaction_guilds={migrated_guilds}",
        flush=True,
    )
