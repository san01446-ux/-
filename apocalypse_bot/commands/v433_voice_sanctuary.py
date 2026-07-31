from __future__ import annotations

import asyncio
import contextlib
import importlib.metadata
import importlib.util
import os
import shutil
import sys
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlencode

import aiohttp
import discord
from discord.ext import commands


VERSION = "4.3.3.2"
TTS_MAX_TEXT = 180
TTS_QUEUE_LIMIT = 20
TTS_USER_COOLDOWN = 4.0
DEFAULT_IDLE_SECONDS = 600
RENEWAL_EDIT_DELAY = 0.8

VOICE_PRESETS: Dict[str, Dict[str, str]] = {
    "서현": {"edge": "ko-KR-SunHiNeural", "label": "차분한 여성 음성"},
    "인준": {"edge": "ko-KR-InJoonNeural", "label": "차분한 남성 음성"},
    "봉진": {"edge": "ko-KR-BongJinNeural", "label": "낮고 안정적인 남성 음성"},
    "국민": {"edge": "ko-KR-GookMinNeural", "label": "또렷한 남성 음성"},
}


def _text_channel_specs(style: str) -> List[Dict[str, Any]]:
    if style == "고딕":
        return [
            {"key": "notice", "category": "╭─〔 ☩ 성역의 문 〕─╮", "name": "📜・성역-공지", "keywords": ("공지", "announcement", "notice")},
            {"key": "rules", "category": "╭─〔 ☩ 성역의 문 〕─╮", "name": "📕・성역-규율", "keywords": ("규칙", "룰", "이용규칙", "rule")},
            {"key": "roles", "category": "╭─〔 ☩ 성역의 문 〕─╮", "name": "🎭・서약-선택", "keywords": ("역할", "role", "인증")},
            {"key": "help", "category": "╭─〔 ☩ 성역의 문 〕─╮", "name": "🕯・길잡이", "keywords": ("도움", "가이드", "guide", "help")},
            {"key": "general", "category": "╭─〔 🕯 순례자 광장 〕─╮", "name": "💬・순례자-광장", "keywords": ("일반", "자유", "잡담", "광장", "general", "chat")},
            {"key": "game", "category": "╭─〔 🕯 순례자 광장 〕─╮", "name": "🎮・게임-회랑", "keywords": ("게임", "game")},
            {"key": "bot", "category": "╭─〔 ⚙ 검은 장치실 〕─╮", "name": "🤖・봇-명령실", "keywords": ("봇", "명령어", "command")},
            {"key": "media", "category": "╭─〔 🖼 기억의 전당 〕─╮", "name": "🖼・사진과-기록", "keywords": ("사진", "미디어", "이미지", "스크린샷", "media")},
            {"key": "clips", "category": "╭─〔 🖼 기억의 전당 〕─╮", "name": "🎞・영상과-클립", "keywords": ("영상", "클립", "동영상", "clip", "video")},
            {"key": "ticket", "category": "╭─〔 🎫 고해의 방 〕─╮", "name": "🎫・문의-접수", "keywords": ("문의", "신고", "건의", "ticket")},
            {"key": "admin", "category": "╭─〔 🛡 검은 의회 〕─╮", "name": "🔒・의회-회의실", "keywords": ("관리자", "운영진", "스태프", "admin")},
            {"key": "logs", "category": "╭─〔 🛡 검은 의회 〕─╮", "name": "📋・감시-기록", "keywords": ("로그", "기록", "log")},
        ]
    if style == "커뮤니티":
        return [
            {"key": "notice", "category": "━━━ 시작하기 ━━━", "name": "📢・공지사항", "keywords": ("공지", "announcement", "notice")},
            {"key": "rules", "category": "━━━ 시작하기 ━━━", "name": "📕・이용규칙", "keywords": ("규칙", "룰", "이용규칙", "rule")},
            {"key": "roles", "category": "━━━ 시작하기 ━━━", "name": "🎭・역할선택", "keywords": ("역할", "role", "인증")},
            {"key": "help", "category": "━━━ 시작하기 ━━━", "name": "❓・도움말", "keywords": ("도움", "가이드", "guide", "help")},
            {"key": "general", "category": "━━━ 커뮤니티 ━━━", "name": "💬・자유채팅", "keywords": ("일반", "자유", "잡담", "광장", "general", "chat")},
            {"key": "game", "category": "━━━ 커뮤니티 ━━━", "name": "🎮・게임이야기", "keywords": ("게임", "game")},
            {"key": "bot", "category": "━━━ 커뮤니티 ━━━", "name": "🤖・봇명령어", "keywords": ("봇", "명령어", "command")},
            {"key": "media", "category": "━━━ 미디어 ━━━", "name": "🖼・사진공유", "keywords": ("사진", "미디어", "이미지", "스크린샷", "media")},
            {"key": "clips", "category": "━━━ 미디어 ━━━", "name": "🎞・영상클립", "keywords": ("영상", "클립", "동영상", "clip", "video")},
            {"key": "ticket", "category": "━━━ 문의지원 ━━━", "name": "🎫・문의접수", "keywords": ("문의", "신고", "건의", "ticket")},
            {"key": "admin", "category": "━━━ 운영지원 ━━━", "name": "🔒・운영진채팅", "keywords": ("관리자", "운영진", "스태프", "admin")},
            {"key": "logs", "category": "━━━ 운영지원 ━━━", "name": "📋・운영로그", "keywords": ("로그", "기록", "log")},
        ]
    return [
        {"key": "notice", "category": "〔 시작 〕", "name": "📢・공지", "keywords": ("공지", "announcement", "notice")},
        {"key": "rules", "category": "〔 시작 〕", "name": "📕・규칙", "keywords": ("규칙", "룰", "이용규칙", "rule")},
        {"key": "roles", "category": "〔 시작 〕", "name": "🎭・역할", "keywords": ("역할", "role", "인증")},
        {"key": "help", "category": "〔 시작 〕", "name": "❓・도움", "keywords": ("도움", "가이드", "guide", "help")},
        {"key": "general", "category": "〔 대화 〕", "name": "💬・일반", "keywords": ("일반", "자유", "잡담", "광장", "general", "chat")},
        {"key": "game", "category": "〔 대화 〕", "name": "🎮・게임", "keywords": ("게임", "game")},
        {"key": "bot", "category": "〔 대화 〕", "name": "🤖・봇", "keywords": ("봇", "명령어", "command")},
        {"key": "media", "category": "〔 미디어 〕", "name": "🖼・사진", "keywords": ("사진", "미디어", "이미지", "스크린샷", "media")},
        {"key": "clips", "category": "〔 미디어 〕", "name": "🎞・영상", "keywords": ("영상", "클립", "동영상", "clip", "video")},
        {"key": "ticket", "category": "〔 문의 〕", "name": "🎫・문의", "keywords": ("문의", "신고", "건의", "ticket")},
        {"key": "admin", "category": "〔 운영 〕", "name": "🔒・관리", "keywords": ("관리자", "운영진", "스태프", "admin")},
        {"key": "logs", "category": "〔 운영 〕", "name": "📋・로그", "keywords": ("로그", "기록", "log")},
    ]


def _voice_channel_specs(style: str) -> List[Dict[str, Any]]:
    category = {
        "고딕": "╭─〔 🔊 메아리의 회랑 〕─╮",
        "커뮤니티": "━━━ 음성채널 ━━━",
        "깔끔": "〔 음성 〕",
    }[style]
    names = {
        "고딕": ("🔊・메아리-대기실", "🎮・전장의-방", "🌙・침묵의-방"),
        "커뮤니티": ("🔊・음성로비", "🎮・게임방", "🌙・잠수방"),
        "깔끔": ("🔊・로비", "🎮・게임", "🌙・잠수"),
    }[style]
    return [
        {"key": "voice_lobby", "category": category, "name": names[0], "keywords": ("로비", "대기", "일반", "lobby")},
        {"key": "voice_game", "category": category, "name": names[1], "keywords": ("게임", "game")},
        {"key": "voice_afk", "category": category, "name": names[2], "keywords": ("잠수", "afk")},
    ]


def _game_zone_specs(style: str) -> List[Dict[str, Any]]:
    categories = {
        "깔끔": {
            "growth": "〔 RPG · 성장 〕",
            "game": "〔 게임 · 도박 〕",
            "media": "〔 음악 · 미디어 〕",
            "test": "〔 테스트 〕",
            "voice": "〔 음성 라운지 〕",
        },
        "고딕": {
            "growth": "╭─〔 ⚔ 종말 전장 〕─╮",
            "game": "╭─〔 🎲 운명의 방 〕─╮",
            "media": "╭─〔 🎵 망자의 선율 〕─╮",
            "test": "╭─〔 🧪 봉인 실험실 〕─╮",
            "voice": "╭─〔 🔊 메아리의 방 〕─╮",
        },
        "커뮤니티": {
            "growth": "━━━ RPG · 성장 ━━━",
            "game": "━━━ 게임 · 도박 ━━━",
            "media": "━━━ 음악 · 미디어 ━━━",
            "test": "━━━ 테스트 ━━━",
            "voice": "━━━ 음성 라운지 ━━━",
        },
    }[style]
    return [
        {
            "key": "rpg",
            "category": categories["growth"],
            "name": "⚔️・아포칼립스-rpg",
            "keywords": ("아포칼립스rpg", "아포칼립스", "rpg"),
        },
        {
            "key": "level_notice",
            "category": categories["growth"],
            "name": "🎉・레벨-알림",
            "keywords": ("레벨알림", "레벨", "levelnotify", "levelup"),
        },
        {
            "key": "daily_quiz",
            "category": categories["growth"],
            "name": "🧭・오늘의-퀴즈방",
            "keywords": ("오늘의퀴즈방", "오늘의퀴즈", "퀴즈방", "퀴즈", "quiz"),
        },
        {
            "key": "gambling",
            "category": categories["game"],
            "name": "🎲・도박장",
            "keywords": ("도박장", "도박", "카지노", "casino", "gambling"),
        },
        {
            "key": "ksi",
            "category": categories["game"],
            "name": "🤖・크시",
            "keywords": ("크시", "kshi", "ksi"),
        },
        {
            "key": "tiktok",
            "category": categories["media"],
            "name": "📱・틱톡",
            "keywords": ("틱톡", "tiktok", "shorts"),
        },
        {
            "key": "karaoke",
            "category": categories["media"],
            "name": "🎵・노래방",
            "keywords": ("노래방", "음악", "뮤직", "music", "song"),
        },
        {
            "key": "bot_test",
            "category": categories["test"],
            "name": "🧪・봇-테스트",
            "keywords": ("봇테스트", "테스트", "test"),
        },
    ]


def _game_zone_category_names(style: str) -> Dict[str, str]:
    specs = _game_zone_specs(style)
    result = {"growth": specs[0]["category"], "game": specs[3]["category"], "media": specs[5]["category"], "test": specs[7]["category"]}
    result["voice"] = {
        "깔끔": "〔 음성 라운지 〕",
        "고딕": "╭─〔 🔊 메아리의 방 〕─╮",
        "커뮤니티": "━━━ 음성 라운지 ━━━",
    }[style]
    return result


def _roman_label(index: int) -> str:
    romans = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")
    return romans[index] if 0 <= index < len(romans) else str(index + 1)


async def _renewal_pause() -> None:
    # Discord의 채널 위치/이름 변경 라우트는 짧은 시간에 몰리면 429가 발생할 수 있습니다.
    await asyncio.sleep(RENEWAL_EDIT_DELAY)


def _category_score(category: discord.CategoryChannel, keywords: Iterable[str]) -> int:
    name = _normalise_name(category.name)
    score = 0
    for keyword in keywords:
        norm = _normalise_name(keyword)
        if not norm:
            continue
        if name == norm:
            score = max(score, 100)
        elif norm in name:
            score = max(score, 70)
    return score


def _best_category(guild: discord.Guild, keywords: Iterable[str], excluded: set[int]) -> Optional[discord.CategoryChannel]:
    best = None
    best_score = 0
    for category in guild.categories:
        if category.id in excluded:
            continue
        score = _category_score(category, keywords)
        if score > best_score:
            best = category
            best_score = score
    return best if best_score >= 70 else None


def _detect_game_zone_channels(
    guild: discord.Guild,
    style: str,
) -> Tuple[List[Tuple[Dict[str, Any], Optional[discord.TextChannel]]], List[discord.VoiceChannel], Optional[discord.CategoryChannel], Optional[discord.CategoryChannel], Optional[discord.CategoryChannel]]:
    used: set[int] = set()
    text_matches: List[Tuple[Dict[str, Any], Optional[discord.TextChannel]]] = []
    for spec in _game_zone_specs(style):
        channel = _best_channel(guild.text_channels, spec["keywords"], used)
        if isinstance(channel, discord.TextChannel):
            used.add(channel.id)
        else:
            channel = None
        text_matches.append((spec, channel))

    excluded: set[int] = set()
    bot_game_category = _best_category(guild, ("BOT GAME", "봇게임", "봇 게임", "게임봇"), excluded)
    if bot_game_category is not None:
        excluded.add(bot_game_category.id)
    voice_category = _best_category(guild, ("말해라", "음성", "voice", "보이스"), excluded)
    if voice_category is not None:
        excluded.add(voice_category.id)
    test_category = _best_category(guild, ("테스트", "test"), excluded)

    numbered_names = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"}
    voices: List[discord.VoiceChannel] = []
    if voice_category is not None:
        voices = [channel for channel in voice_category.voice_channels]
    if not voices:
        voices = [
            channel
            for channel in guild.voice_channels
            if _normalise_name(channel.name) in numbered_names
            or any(keyword in _normalise_name(channel.name) for keyword in ("말해라", "음성", "voice", "보이스"))
        ]
    voices.sort(key=lambda channel: (channel.category.position if channel.category else 9999, channel.position, channel.id))
    return text_matches, voices, bot_game_category, voice_category, test_category


def _game_zone_preview_embed(guild: discord.Guild, style: str) -> discord.Embed:
    text_matches, voices, bot_game_category, voice_category, test_category = _detect_game_zone_channels(guild, style)
    categories = _game_zone_category_names(style)
    embed = discord.Embed(
        title=f"🎮 봇 게임·음성 구역 정리 미리보기 · {style}",
        description=(
            "사용 중인 채널을 삭제하지 않고 **RPG·성장 / 게임·도박 / 음악·미디어 / 테스트 / 음성 라운지**로 나눕니다.\n"
            "기존 `BOT GAME`, `말해라`, `테스트` 카테고리는 가능한 경우 새 이름으로 재사용합니다."
        ),
        color=0x6D2335 if style == "고딕" else 0x5865F2,
    )
    detected = [channel for _, channel in text_matches if channel is not None]
    embed.add_field(name="찾은 텍스트 채널", value=f"**{len(detected)}개 / {len(text_matches)}개**", inline=True)
    embed.add_field(name="찾은 음성 채널", value=f"**{len(voices)}개**", inline=True)
    reused = sum(category is not None for category in (bot_game_category, voice_category, test_category))
    embed.add_field(name="재사용할 카테고리", value=f"**{reused}개**", inline=True)

    lines: List[str] = []
    for spec, channel in text_matches:
        if channel is not None:
            lines.append(f"• {channel.mention} → `{spec['category']}` / `{spec['name']}`")
    for index, channel in enumerate(voices):
        lines.append(f"• {channel.mention} → `{categories['voice']}` / `🔊・음성-{_roman_label(index)}`")
    embed.add_field(name="정리 계획", value="\n".join(lines[:20]) or "인식한 대상 채널이 없습니다.", inline=False)
    embed.add_field(
        name="적용 명령",
        value=f"`!서버리뉴얼 게임정리 {style}`\n되돌리기: `!서버리뉴얼 되돌리기`",
        inline=False,
    )
    return embed


STYLE_NAMES = {"깔끔", "고딕", "커뮤니티"}
ESSENTIAL_KEYS = {"notice", "rules", "roles", "general", "bot", "voice_lobby", "voice_afk"}
ADMIN_KEYS = {"admin", "logs"}
READ_ONLY_KEYS = {"notice", "rules", "roles", "help"}


def _normalise_name(value: str) -> str:
    value = re.sub(r"[^0-9A-Za-z가-힣]+", "", value or "").lower()
    return value


def _best_channel(channels: Sequence[Any], keywords: Iterable[str], used: set[int]) -> Optional[Any]:
    best: Optional[Any] = None
    best_score = 0
    normalised_keywords = [_normalise_name(keyword) for keyword in keywords]
    for channel in channels:
        if channel.id in used:
            continue
        name = _normalise_name(channel.name)
        score = 0
        for keyword in normalised_keywords:
            if not keyword:
                continue
            if name == keyword:
                score = max(score, 100)
            elif keyword in name:
                score = max(score, 60 + min(20, len(keyword)))
        if score > best_score:
            best = channel
            best_score = score
    return best if best_score >= 60 else None


def _layout_settings(world_data: Dict[str, Any], guild_id: int) -> Dict[str, Any]:
    root = world_data.setdefault("voice_sanctuary", {})
    settings = root.setdefault(str(guild_id), {})
    settings.setdefault("tts", {})
    tts = settings["tts"]
    tts.setdefault("enabled", False)
    tts.setdefault("text_channel_id", None)
    tts.setdefault("voice_channel_id", None)
    tts.setdefault("voice", "서현")
    tts.setdefault("speed", 1.0)
    tts.setdefault("volume", 1.0)
    tts.setdefault("idle_seconds", DEFAULT_IDLE_SECONDS)
    tts.setdefault("announce_names", True)
    tts.setdefault("auto_join", True)
    tts.setdefault("require_author_in_voice", False)
    settings.setdefault("layout", {})
    settings["layout"].setdefault("style", None)
    settings["layout"].setdefault("backup", None)
    settings["layout"].setdefault("menu_channel_id", None)
    settings["layout"].setdefault("menu_message_id", None)
    return settings


def _snapshot_guild(guild: discord.Guild) -> Dict[str, Any]:
    return {
        "created_at": int(time.time()),
        "categories": [
            {"id": category.id, "name": category.name, "position": category.position}
            for category in guild.categories
        ],
        "channels": [
            {
                "id": channel.id,
                "name": channel.name,
                "category_id": channel.category_id,
                "position": channel.position,
                "type": "voice" if isinstance(channel, discord.VoiceChannel) else "text",
            }
            for channel in [*guild.text_channels, *guild.voice_channels]
        ],
    }


def _admin_category_overwrites(
    guild: discord.Guild,
    author: discord.Member,
    bot_member: discord.Member,
) -> Dict[Any, discord.PermissionOverwrite]:
    return {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        author: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True,
            manage_messages=True,
        ),
        bot_member: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True,
            manage_messages=True,
            embed_links=True,
        ),
    }


def _public_read_only_overwrites(
    guild: discord.Guild,
    author: discord.Member,
    bot_member: discord.Member,
    allow_reactions: bool = False,
) -> Dict[Any, discord.PermissionOverwrite]:
    return {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True,
            read_message_history=True,
            send_messages=False,
            add_reactions=allow_reactions,
        ),
        author: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_messages=True,
            add_reactions=True,
        ),
        bot_member: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_messages=True,
            add_reactions=True,
            embed_links=True,
        ),
    }


def _channel_url(guild_id: int, channel_id: int) -> str:
    return f"https://discord.com/channels/{guild_id}/{channel_id}"


def _detect_layout(guild: discord.Guild, style: str) -> Tuple[List[Tuple[Dict[str, Any], Optional[Any]]], List[Tuple[Dict[str, Any], Optional[Any]]]]:
    used_text: set[int] = set()
    used_voice: set[int] = set()
    text_matches: List[Tuple[Dict[str, Any], Optional[Any]]] = []
    voice_matches: List[Tuple[Dict[str, Any], Optional[Any]]] = []
    for spec in _text_channel_specs(style):
        channel = _best_channel(guild.text_channels, spec["keywords"], used_text)
        if channel is not None:
            used_text.add(channel.id)
        text_matches.append((spec, channel))
    for spec in _voice_channel_specs(style):
        channel = _best_channel(guild.voice_channels, spec["keywords"], used_voice)
        if channel is not None:
            used_voice.add(channel.id)
        voice_matches.append((spec, channel))
    return text_matches, voice_matches


def _layout_preview_embed(guild: discord.Guild, style: str) -> discord.Embed:
    text_matches, voice_matches = _detect_layout(guild, style)
    move_count = sum(1 for _, channel in [*text_matches, *voice_matches] if channel is not None)
    create_count = sum(
        1
        for spec, channel in [*text_matches, *voice_matches]
        if channel is None and spec["key"] in ESSENTIAL_KEYS
    )
    category_names = []
    for spec, _ in [*text_matches, *voice_matches]:
        if spec["category"] not in category_names:
            category_names.append(spec["category"])
    existing_categories = {category.name for category in guild.categories}
    category_create = sum(1 for name in category_names if name not in existing_categories)

    embed = discord.Embed(
        title=f"🕯 서버 리뉴얼 미리보기 · {style}",
        description=(
            "기존 채널을 키워드로 찾아 이름과 위치를 정돈합니다.\n"
            "**채널·역할·메시지는 삭제하지 않으며**, 인식하지 못한 채널은 그대로 둡니다."
        ),
        color=0x6D2335 if style == "고딕" else 0x5865F2,
    )
    embed.add_field(name="찾은 기존 채널", value=f"**{move_count}개**", inline=True)
    embed.add_field(name="새 필수 채널", value=f"**{create_count}개**", inline=True)
    embed.add_field(name="새 카테고리", value=f"**{category_create}개**", inline=True)
    lines = []
    for spec, channel in [*text_matches, *voice_matches]:
        if channel is not None:
            lines.append(f"• {channel.mention} → `{spec['name']}`")
        elif spec["key"] in ESSENTIAL_KEYS:
            lines.append(f"• 새로 생성 → `{spec['name']}`")
    embed.add_field(name="적용 계획", value="\n".join(lines[:16]) or "변경할 필수 항목이 없습니다.", inline=False)
    embed.add_field(
        name="실행",
        value=f"`!서버리뉴얼 적용 {style}`\n되돌리기: `!서버리뉴얼 되돌리기`",
        inline=False,
    )
    return embed


def _menu_destinations(guild: discord.Guild) -> List[Tuple[str, str, discord.TextChannel]]:
    definitions = [
        ("공지", "📢", ("공지", "announcement", "notice")),
        ("규칙", "📕", ("규칙", "이용규칙", "rule")),
        ("역할", "🎭", ("역할", "인증", "role")),
        ("자유채팅", "💬", ("일반", "자유", "잡담", "광장", "chat")),
        ("게임", "🎮", ("게임", "game")),
        ("봇 명령", "🤖", ("봇", "명령어", "command")),
        ("사진", "🖼", ("사진", "미디어", "스크린샷", "media")),
        ("문의", "🎫", ("문의", "신고", "건의", "ticket")),
    ]
    used: set[int] = set()
    result: List[Tuple[str, str, discord.TextChannel]] = []
    for label, emoji, keywords in definitions:
        channel = _best_channel(guild.text_channels, keywords, used)
        if channel is None:
            continue
        used.add(channel.id)
        result.append((label, emoji, channel))
    return result[:10]


def _menu_embed(guild: discord.Guild, destinations: Sequence[Tuple[str, str, discord.TextChannel]]) -> discord.Embed:
    description = [
        "필요한 공간으로 바로 이동하세요. 아래 버튼은 Discord 채널 링크라 봇이 재시작돼도 유지됩니다.",
        "",
    ]
    description.extend(f"{emoji} **{label}** · {channel.mention}" for label, emoji, channel in destinations)
    embed = discord.Embed(
        title="☩ 서버 안내 성역",
        description="\n".join(description),
        color=0x2B1824,
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text=f"{guild.name} · ABADDON 서버 메뉴")
    return embed


def _menu_view(guild: discord.Guild, destinations: Sequence[Tuple[str, str, discord.TextChannel]]) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    for label, emoji, channel in destinations:
        view.add_item(
            discord.ui.Button(
                label=label,
                emoji=emoji,
                style=discord.ButtonStyle.link,
                url=_channel_url(guild.id, channel.id),
            )
        )
    return view


def _dependency_state() -> Tuple[bool, bool]:
    return importlib.util.find_spec("nacl") is not None, importlib.util.find_spec("edge_tts") is not None


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "미설치"
    except Exception:
        return "확인 실패"


def _tts_diagnostic_lines() -> List[str]:
    has_nacl, has_edge = _dependency_state()
    ffmpeg = shutil.which("ffmpeg")
    return [
        f"Python: `{sys.version.split()[0]}`",
        f"discord.py: `{_package_version('discord.py')}`",
        f"PyNaCl: `{'설치됨 ' + _package_version('PyNaCl') if has_nacl else '미설치'}`",
        f"edge-tts: `{'설치됨 ' + _package_version('edge-tts') if has_edge else '미설치'}`",
        f"FFmpeg: `{'확인됨' if ffmpeg else '찾지 못함'}`",
        f"Opus: `{'로드됨' if discord.opus.is_loaded() else '미로드'}`",
    ]


class VoiceRuntime:
    def __init__(self) -> None:
        self.queues: Dict[int, asyncio.Queue[Dict[str, Any]]] = {}
        self.workers: Dict[int, asyncio.Task[None]] = {}
        self.user_cooldowns: Dict[Tuple[int, int], float] = {}

    def queue_for(self, guild_id: int) -> asyncio.Queue[Dict[str, Any]]:
        queue = self.queues.get(guild_id)
        if queue is None:
            queue = asyncio.Queue(maxsize=TTS_QUEUE_LIMIT)
            self.queues[guild_id] = queue
        return queue

    def clear(self, guild_id: int) -> int:
        queue = self.queue_for(guild_id)
        removed = 0
        while True:
            try:
                queue.get_nowait()
                queue.task_done()
                removed += 1
            except asyncio.QueueEmpty:
                return removed


VOICE_RUNTIME = VoiceRuntime()


def _clean_spoken_text(text: str) -> str:
    text = re.sub(r"https?://\S+", " 링크 ", text)
    text = re.sub(r"<a?:\w+:\d+>", "", text)
    text = re.sub(r"[`*_~>|]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:TTS_MAX_TEXT]


async def _synth_edge(text: str, voice: str, speed: float, output_path: str) -> bool:
    try:
        import edge_tts  # type: ignore
    except ImportError:
        return False
    rate = int(round((speed - 1.0) * 100))
    communicator = edge_tts.Communicate(text=text, voice=voice, rate=f"{rate:+d}%")
    await communicator.save(output_path)
    return True


async def _synth_google(text: str, speed: float, output_path: str) -> None:
    params = {
        "ie": "UTF-8",
        "client": "tw-ob",
        "tl": "ko",
        "q": text,
        "ttsspeed": "0.24" if speed < 0.9 else "1",
    }
    url = "https://translate.google.com/translate_tts?" + urlencode(params)
    timeout = aiohttp.ClientTimeout(total=20)
    headers = {"User-Agent": "Mozilla/5.0 ABADDON-TTS/4.3.3.2"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise RuntimeError(f"TTS HTTP {response.status}")
            data = await response.read()
    if not data:
        raise RuntimeError("TTS 음성 데이터가 비어 있습니다.")
    await asyncio.to_thread(Path(output_path).write_bytes, data)


async def _synthesise(text: str, voice_key: str, speed: float, output_path: str) -> str:
    preset = VOICE_PRESETS.get(voice_key, VOICE_PRESETS["서현"])
    if await _synth_edge(text, preset["edge"], speed, output_path):
        return "edge-tts"
    await _synth_google(text, speed, output_path)
    return "google-fallback"


async def _ensure_voice_connection(
    bot: commands.Bot,
    guild: discord.Guild,
    channel_id: Optional[int],
) -> Tuple[Optional[discord.VoiceClient], Optional[str]]:
    if not channel_id:
        return None, "음성 채널이 설정되지 않았습니다. 음성 채널에 들어간 뒤 `!음성입장`을 사용하세요."
    channel = guild.get_channel(int(channel_id))
    if not isinstance(channel, discord.VoiceChannel):
        return None, "설정된 음성 채널을 찾지 못했습니다."
    has_nacl, _ = _dependency_state()
    if not has_nacl:
        return None, (
            "PyNaCl을 실제 실행 환경에서 불러오지 못했습니다. "
            "Render Build Command가 `pip install -r requirements.txt`인지 확인하고 "
            "`Clear build cache & deploy`를 실행한 뒤 `!TTS 진단`으로 재확인하세요."
        )
    me = guild.me
    if me is not None:
        permissions = channel.permissions_for(me)
        if not permissions.connect or not permissions.speak:
            return None, "봇에 해당 음성 채널의 `연결`과 `말하기` 권한이 필요합니다."
    voice = guild.voice_client
    try:
        if voice is None:
            voice = await channel.connect(self_deaf=True)
        elif voice.channel.id != channel.id:
            await voice.move_to(channel)
    except RuntimeError as exc:
        return None, f"음성 런타임 오류: {type(exc).__name__}: {str(exc)[:220]}"
    except (discord.ClientException, discord.Forbidden, discord.HTTPException) as exc:
        return None, f"음성 연결 실패: {type(exc).__name__}: {str(exc)[:180]}"
    return voice, None


async def _play_file(voice: discord.VoiceClient, path: str, volume: float) -> None:
    loop = asyncio.get_running_loop()
    finished: asyncio.Future[None] = loop.create_future()

    def after(error: Optional[Exception]) -> None:
        def resolve() -> None:
            if finished.done():
                return
            if error is not None:
                finished.set_exception(error)
            else:
                finished.set_result(None)
        loop.call_soon_threadsafe(resolve)

    source = discord.FFmpegPCMAudio(path, options="-vn")
    transformed = discord.PCMVolumeTransformer(source, volume=max(0.1, min(2.0, volume)))
    voice.play(transformed, after=after)
    await finished


def register_v433_voice_sanctuary(
    bot: commands.Bot,
    world_data: Dict[str, Any],
    save_data,
) -> None:
    async def require_guild(ctx: commands.Context) -> Optional[discord.Guild]:
        if ctx.guild is None:
            await ctx.send("❌ 서버 안에서만 사용할 수 있습니다.")
            return None
        return ctx.guild

    async def require_admin(ctx: commands.Context) -> Optional[discord.Guild]:
        guild = await require_guild(ctx)
        if guild is None:
            return None
        if not isinstance(ctx.author, discord.Member) or not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ 서버 관리자만 사용할 수 있습니다.")
            return None
        return guild

    async def enqueue_tts(
        guild: discord.Guild,
        author: discord.Member,
        text: str,
        *,
        announce_name: bool,
    ) -> Tuple[bool, str]:
        settings = _layout_settings(world_data, guild.id)["tts"]
        clean = _clean_spoken_text(text)
        if not clean:
            return False, "읽을 수 있는 내용이 없습니다."
        queue = VOICE_RUNTIME.queue_for(guild.id)
        if queue.full():
            return False, f"대기열이 가득 찼습니다. 최대 {TTS_QUEUE_LIMIT}개까지 보관합니다."
        spoken = f"{author.display_name}. {clean}" if announce_name else clean
        await queue.put({"text": spoken, "author_id": author.id, "queued_at": time.time()})
        task = VOICE_RUNTIME.workers.get(guild.id)
        if task is None or task.done():
            VOICE_RUNTIME.workers[guild.id] = asyncio.create_task(tts_worker(guild.id))
        return True, f"대기열 **{queue.qsize()}번째**에 추가했습니다."

    async def tts_worker(guild_id: int) -> None:
        queue = VOICE_RUNTIME.queue_for(guild_id)
        while True:
            guild = bot.get_guild(guild_id)
            if guild is None:
                return
            settings = _layout_settings(world_data, guild_id)["tts"]
            idle_seconds = max(120, min(3600, int(settings.get("idle_seconds", DEFAULT_IDLE_SECONDS))))
            try:
                item = await asyncio.wait_for(queue.get(), timeout=idle_seconds)
            except asyncio.TimeoutError:
                voice = guild.voice_client
                if voice is not None and voice.is_connected():
                    with contextlib.suppress(discord.ClientException, discord.HTTPException):
                        await voice.disconnect(force=False)
                return

            temp_path = ""
            try:
                voice, error = await _ensure_voice_connection(bot, guild, settings.get("voice_channel_id"))
                if voice is None:
                    print(f"[TTS 연결 실패] guild={guild_id} error={error}", flush=True)
                    continue
                fd, temp_path = tempfile.mkstemp(prefix="abaddon_tts_", suffix=".mp3")
                os.close(fd)
                provider = await _synthesise(
                    str(item["text"]),
                    str(settings.get("voice", "서현")),
                    float(settings.get("speed", 1.0)),
                    temp_path,
                )
                await _play_file(voice, temp_path, float(settings.get("volume", 1.0)))
                settings["last_provider"] = provider
                settings["last_played_at"] = int(time.time())
            except Exception as exc:
                print(f"[TTS 재생 오류] guild={guild_id} {type(exc).__name__}: {exc}", flush=True)
            finally:
                queue.task_done()
                if temp_path:
                    with contextlib.suppress(OSError):
                        os.remove(temp_path)

    @bot.group(name="TTS", aliases=["티티에스", "음성성역"], invoke_without_command=True, case_insensitive=True)
    async def tts_group(ctx: commands.Context):
        guild = await require_guild(ctx)
        if guild is None:
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        queue = VOICE_RUNTIME.queue_for(guild.id)
        embed = discord.Embed(
            title="🔊 ABADDON 음성 성역",
            description=(
                "텍스트를 음성 채널에서 읽고, 지정한 채팅 채널의 메시지를 자동 낭독합니다.\n\n"
                "`!음성입장` · `!말해 내용` · `!음성퇴장`\n"
                "`!TTS 채널설정 #텍스트채널 음성채널` · `!TTS 켜기` · `!TTS 끄기`\n"
                "`!TTS 목소리` · `!TTS 속도 1.0` · `!TTS 볼륨 100` · `!TTS 진단`"
            ),
            color=0x6D2335,
        )
        embed.add_field(name="자동 낭독", value="켜짐" if settings.get("enabled") else "꺼짐", inline=True)
        embed.add_field(name="대기열", value=f"{queue.qsize()}/{TTS_QUEUE_LIMIT}", inline=True)
        embed.add_field(name="목소리", value=str(settings.get("voice", "서현")), inline=True)
        await ctx.send(embed=embed)

    @bot.command(name="음성입장", aliases=["보이스입장"])
    async def voice_join(ctx: commands.Context):
        guild = await require_guild(ctx)
        if guild is None or not isinstance(ctx.author, discord.Member):
            return
        if not ctx.author.voice or not isinstance(ctx.author.voice.channel, discord.VoiceChannel):
            await ctx.send("❌ 먼저 음성 채널에 들어가 주세요.")
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        settings["voice_channel_id"] = ctx.author.voice.channel.id
        voice, error = await _ensure_voice_connection(bot, guild, ctx.author.voice.channel.id)
        if voice is None:
            await ctx.send(f"❌ {error}")
            return
        save_data()
        await ctx.send(f"🔊 {ctx.author.voice.channel.mention}에 입장했습니다.")

    @bot.command(name="음성퇴장", aliases=["보이스퇴장"])
    async def voice_leave(ctx: commands.Context):
        guild = await require_guild(ctx)
        if guild is None:
            return
        voice = guild.voice_client
        if voice is None:
            await ctx.send("⚠️ 현재 음성 채널에 연결되어 있지 않습니다.")
            return
        VOICE_RUNTIME.clear(guild.id)
        await voice.disconnect(force=False)
        await ctx.send("🔇 음성 성역에서 퇴장했습니다.")

    @bot.command(name="말해", aliases=["읽어", "say"])
    async def voice_say(ctx: commands.Context, *, text: str):
        guild = await require_guild(ctx)
        if guild is None or not isinstance(ctx.author, discord.Member):
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        voice_channel_id = settings.get("voice_channel_id")
        if not ctx.author.voice or ctx.author.voice.channel.id != voice_channel_id:
            await ctx.send("❌ 설정된 음성 채널에 함께 들어가 있어야 사용할 수 있습니다.")
            return
        now = time.monotonic()
        key = (guild.id, ctx.author.id)
        remaining = TTS_USER_COOLDOWN - (now - VOICE_RUNTIME.user_cooldowns.get(key, 0.0))
        if remaining > 0:
            await ctx.send(f"⏳ TTS 쿨다운 **{remaining:.1f}초**가 남았습니다.", delete_after=5)
            return
        VOICE_RUNTIME.user_cooldowns[key] = now
        ok, message = await enqueue_tts(
            guild,
            ctx.author,
            text,
            announce_name=bool(settings.get("announce_names", True)),
        )
        await ctx.send(("✅ " if ok else "❌ ") + message, delete_after=8)

    async def configure_tts_channels(
        ctx: commands.Context,
        text_channel: discord.TextChannel,
        voice_channel: discord.VoiceChannel,
        *,
        enable: bool = True,
    ) -> None:
        guild = await require_admin(ctx)
        if guild is None:
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        settings["text_channel_id"] = text_channel.id
        settings["voice_channel_id"] = voice_channel.id
        settings["enabled"] = bool(enable)
        settings["auto_join"] = True
        settings["require_author_in_voice"] = False
        save_data()
        state = "켜짐" if enable else "꺼짐"
        await ctx.send(
            "✅ TTS 자동 채널 설정을 저장했습니다.\n"
            f"텍스트: {text_channel.mention}\n"
            f"음성: {voice_channel.mention}\n"
            f"자동 낭독: **{state}**\n\n"
            "이제 지정 텍스트 채널에 일반 메시지가 올라오면, 작성자가 음성방에 없어도 "
            "아바돈이 지정 음성 채널로 자동 입장해 읽습니다."
        )

    @tts_group.command(name="채널설정", aliases=["자동채널", "setchannel"])
    async def tts_channel_setup(
        ctx: commands.Context,
        text_channel: discord.TextChannel,
        voice_channel: discord.VoiceChannel,
    ):
        await configure_tts_channels(ctx, text_channel, voice_channel, enable=True)

    @bot.command(name="채널설정", aliases=["TTS채널설정"])
    async def tts_channel_setup_shortcut(
        ctx: commands.Context,
        text_channel: discord.TextChannel,
        voice_channel: discord.VoiceChannel,
    ):
        await configure_tts_channels(ctx, text_channel, voice_channel, enable=True)

    @tts_group.command(name="켜기", aliases=["on"])
    async def tts_enable(ctx: commands.Context):
        guild = await require_admin(ctx)
        if guild is None or not isinstance(ctx.author, discord.Member):
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        if ctx.author.voice and isinstance(ctx.author.voice.channel, discord.VoiceChannel):
            settings["voice_channel_id"] = ctx.author.voice.channel.id
        if not settings.get("voice_channel_id"):
            await ctx.send(
                "❌ 음성 채널이 설정되지 않았습니다.\n"
                "`!TTS 채널설정 #텍스트채널 음성채널` 또는 `!채널설정 #텍스트채널 음성채널`을 사용하세요."
            )
            return
        if isinstance(ctx.channel, discord.TextChannel) and not settings.get("text_channel_id"):
            settings["text_channel_id"] = ctx.channel.id
        if not settings.get("text_channel_id"):
            await ctx.send("❌ 자동 낭독 텍스트 채널을 먼저 설정해 주세요.")
            return
        settings["enabled"] = True
        settings["auto_join"] = True
        settings["require_author_in_voice"] = False
        save_data()
        text_channel = guild.get_channel(int(settings["text_channel_id"]))
        voice_channel = guild.get_channel(int(settings["voice_channel_id"]))
        await ctx.send(
            "✅ 자동 TTS를 켰습니다.\n"
            f"텍스트: {getattr(text_channel, 'mention', '미설정')}\n"
            f"음성: {getattr(voice_channel, 'mention', '미설정')}\n"
            "지정 텍스트 채널에 메시지가 올라오면 아바돈이 자동 입장해 읽습니다."
        )

    @tts_group.command(name="끄기", aliases=["off"])
    async def tts_disable(ctx: commands.Context):
        guild = await require_admin(ctx)
        if guild is None:
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        settings["enabled"] = False
        removed = VOICE_RUNTIME.clear(guild.id)
        save_data()
        await ctx.send(f"✅ 자동 TTS를 껐습니다. 대기 메시지 **{removed}개**를 비웠습니다.")

    @tts_group.command(name="채널")
    async def tts_channel(ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        guild = await require_admin(ctx)
        if guild is None:
            return
        target = channel or (ctx.channel if isinstance(ctx.channel, discord.TextChannel) else None)
        if target is None:
            await ctx.send("❌ 텍스트 채널을 지정해 주세요.")
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        settings["text_channel_id"] = target.id
        save_data()
        await ctx.send(f"✅ 자동 낭독 채널을 {target.mention}로 지정했습니다.")

    @tts_group.command(name="음성채널", aliases=["보이스채널"])
    async def tts_voice_channel(ctx: commands.Context, channel: discord.VoiceChannel):
        guild = await require_admin(ctx)
        if guild is None:
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        settings["voice_channel_id"] = channel.id
        settings["auto_join"] = True
        save_data()
        await ctx.send(f"✅ 자동 낭독 음성 채널을 {channel.mention}로 지정했습니다.")

    @tts_group.command(name="목소리", aliases=["음성"])
    async def tts_voice(ctx: commands.Context, voice_name: Optional[str] = None):
        guild = await require_guild(ctx)
        if guild is None:
            return
        if voice_name is None:
            lines = [f"• **{name}** — {data['label']}" for name, data in VOICE_PRESETS.items()]
            await ctx.send("🔊 **사용 가능한 한국어 목소리**\n" + "\n".join(lines) + "\n설정: `!TTS 목소리 서현`")
            return
        if not isinstance(ctx.author, discord.Member) or not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ 목소리 설정은 서버 관리자만 변경할 수 있습니다.")
            return
        if voice_name not in VOICE_PRESETS:
            await ctx.send("❌ 목소리는 `서현`, `인준`, `봉진`, `국민` 중에서 선택하세요.")
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        settings["voice"] = voice_name
        save_data()
        await ctx.send(f"✅ TTS 목소리를 **{voice_name}**으로 변경했습니다.")

    @tts_group.command(name="속도")
    async def tts_speed(ctx: commands.Context, speed: float):
        guild = await require_admin(ctx)
        if guild is None:
            return
        if not 0.7 <= speed <= 1.5:
            await ctx.send("❌ 속도는 `0.7`부터 `1.5` 사이로 입력하세요.")
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        settings["speed"] = round(speed, 2)
        save_data()
        await ctx.send(f"✅ TTS 속도를 **{speed:.2f}배**로 설정했습니다.")

    @tts_group.command(name="볼륨")
    async def tts_volume(ctx: commands.Context, volume: int):
        guild = await require_admin(ctx)
        if guild is None:
            return
        if not 10 <= volume <= 200:
            await ctx.send("❌ 볼륨은 `10`부터 `200` 사이로 입력하세요.")
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        settings["volume"] = round(volume / 100, 2)
        save_data()
        await ctx.send(f"✅ TTS 볼륨을 **{volume}%**로 설정했습니다.")

    @tts_group.command(name="대기열", aliases=["queue"])
    async def tts_queue(ctx: commands.Context):
        guild = await require_guild(ctx)
        if guild is None:
            return
        queue = VOICE_RUNTIME.queue_for(guild.id)
        await ctx.send(f"🔊 현재 TTS 대기열: **{queue.qsize()}/{TTS_QUEUE_LIMIT}개**")

    @tts_group.command(name="비우기", aliases=["clear"])
    async def tts_clear(ctx: commands.Context):
        guild = await require_admin(ctx)
        if guild is None:
            return
        removed = VOICE_RUNTIME.clear(guild.id)
        if guild.voice_client and guild.voice_client.is_playing():
            guild.voice_client.stop()
        await ctx.send(f"✅ TTS 대기열 **{removed}개**를 비웠습니다.")

    @tts_group.command(name="진단", aliases=["diagnose", "검사"])
    async def tts_diagnose(ctx: commands.Context):
        guild = await require_guild(ctx)
        if guild is None:
            return
        has_nacl, has_edge = _dependency_state()
        embed = discord.Embed(title="🩺 TTS 실행 환경 진단", color=0x6D2335)
        embed.description = "\n".join(_tts_diagnostic_lines())
        if not has_nacl:
            embed.add_field(
                name="Render 조치",
                value=(
                    "1. Build Command를 `pip install --upgrade pip && pip install -r requirements.txt`로 확인\n"
                    "2. `PyNaCl>=1.6.2`와 `edge-tts>=6.1.0` 확인\n"
                    "3. Manual Deploy → Clear build cache & deploy"
                ),
                inline=False,
            )
        elif not has_edge:
            embed.add_field(name="안내", value="edge-tts가 없어 Google 대체 음성을 사용합니다.", inline=False)
        else:
            embed.add_field(name="결과", value="필수 음성 패키지가 정상적으로 감지됐습니다.", inline=False)
        await ctx.send(embed=embed)

    @tts_group.command(name="상태", aliases=["status"])
    async def tts_status(ctx: commands.Context):
        guild = await require_guild(ctx)
        if guild is None:
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        text_channel = guild.get_channel(settings.get("text_channel_id") or 0)
        voice_channel = guild.get_channel(settings.get("voice_channel_id") or 0)
        has_nacl, has_edge = _dependency_state()
        embed = discord.Embed(title="🔊 TTS 음성 성역 상태", color=0x6D2335)
        embed.add_field(name="자동 낭독", value="켜짐" if settings.get("enabled") else "꺼짐", inline=True)
        embed.add_field(name="음성 연결", value="연결됨" if guild.voice_client else "연결 안 됨", inline=True)
        embed.add_field(name="대기열", value=f"{VOICE_RUNTIME.queue_for(guild.id).qsize()}/{TTS_QUEUE_LIMIT}", inline=True)
        embed.add_field(name="텍스트 채널", value=getattr(text_channel, "mention", "미설정"), inline=True)
        embed.add_field(name="음성 채널", value=getattr(voice_channel, "mention", "미설정"), inline=True)
        embed.add_field(name="자동 입장", value="켜짐" if settings.get("auto_join", True) else "꺼짐", inline=True)
        embed.add_field(name="목소리", value=f"{settings.get('voice', '서현')} · {settings.get('speed', 1.0)}배 · {int(float(settings.get('volume', 1.0))*100)}%", inline=True)
        embed.add_field(
            name="음성 의존성",
            value=f"PyNaCl: {'✅' if has_nacl else '❌'}\nedge-tts: {'✅' if has_edge else '대체 음성 사용'}",
            inline=False,
        )
        await ctx.send(embed=embed)

    @bot.group(name="서버리뉴얼", aliases=["서버정리", "서버디자인"], invoke_without_command=True, case_insensitive=True)
    async def server_renewal(ctx: commands.Context):
        guild = await require_admin(ctx)
        if guild is None:
            return
        embed = discord.Embed(
            title="🕯 ABADDON 서버 리뉴얼",
            description=(
                "현재 채널을 삭제하지 않고 카테고리·채널명·순서를 정돈합니다.\n"
                "사진처럼 길어진 메뉴를 `깔끔`, `고딕`, `커뮤니티` 테마로 정리할 수 있습니다."
            ),
            color=0x6D2335,
        )
        embed.add_field(
            name="사용 순서",
            value=(
                "`!서버리뉴얼 미리보기 고딕`\n"
                "`!서버리뉴얼 적용 고딕`\n"
                "`!서버메뉴 생성`\n"
                "`!서버리뉴얼 되돌리기`"
            ),
            inline=False,
        )
        embed.add_field(name="안전 원칙", value="채널·역할·메시지 삭제 없음 · 미인식 채널 유지 · 적용 전 자동 백업", inline=False)
        await ctx.send(embed=embed)

    @server_renewal.command(name="미리보기", aliases=["preview"])
    async def server_renewal_preview(ctx: commands.Context, style: str = "깔끔"):
        guild = await require_admin(ctx)
        if guild is None:
            return
        if style not in STYLE_NAMES:
            await ctx.send("❌ 테마는 `깔끔`, `고딕`, `커뮤니티` 중에서 선택하세요.")
            return
        await ctx.send(embed=_layout_preview_embed(guild, style))

    @server_renewal.command(name="적용", aliases=["apply"])
    async def server_renewal_apply(ctx: commands.Context, style: str = "깔끔"):
        guild = await require_admin(ctx)
        if guild is None or not isinstance(ctx.author, discord.Member):
            return
        if style not in STYLE_NAMES:
            await ctx.send("❌ 테마는 `깔끔`, `고딕`, `커뮤니티` 중에서 선택하세요.")
            return
        bot_member = guild.me
        if bot_member is None or not bot_member.guild_permissions.manage_channels:
            await ctx.send("❌ 봇에 `채널 관리` 권한이 필요합니다.")
            return

        settings = _layout_settings(world_data, guild.id)["layout"]
        settings["backup"] = _snapshot_guild(guild)
        save_data()
        progress = await ctx.send(f"🕯 **{style} 테마로 서버 메뉴를 정돈하는 중입니다...**")
        text_matches, voice_matches = _detect_layout(guild, style)
        category_names: List[str] = []
        for spec, _ in [*text_matches, *voice_matches]:
            if spec["category"] not in category_names:
                category_names.append(spec["category"])

        categories: Dict[str, discord.CategoryChannel] = {}
        created_categories = 0
        changed_channels = 0
        created_channels = 0
        reason = f"ABADDON v{VERSION} 서버 리뉴얼 / {ctx.author} ({ctx.author.id})"
        try:
            for category_name in category_names:
                category = discord.utils.get(guild.categories, name=category_name)
                if category is None:
                    admin_only = any(
                        spec["category"] == category_name and spec["key"] in ADMIN_KEYS
                        for spec, _ in text_matches
                    )
                    kwargs: Dict[str, Any] = {"reason": reason}
                    if admin_only:
                        kwargs["overwrites"] = _admin_category_overwrites(guild, ctx.author, bot_member)
                    category = await guild.create_category(category_name, **kwargs)
                    await _renewal_pause()
                    created_categories += 1
                categories[category_name] = category

            for index, category_name in enumerate(category_names):
                with contextlib.suppress(discord.Forbidden, discord.HTTPException):
                    await categories[category_name].edit(position=index, reason=reason)
                    await _renewal_pause()

            for spec, channel in text_matches:
                category = categories[spec["category"]]
                if channel is None and spec["key"] in ESSENTIAL_KEYS:
                    kwargs: Dict[str, Any] = {"category": category, "reason": reason}
                    if spec["key"] in READ_ONLY_KEYS:
                        kwargs["overwrites"] = _public_read_only_overwrites(
                            guild,
                            ctx.author,
                            bot_member,
                            allow_reactions=spec["key"] == "roles",
                        )
                    await guild.create_text_channel(spec["name"], **kwargs)
                    await _renewal_pause()
                    created_channels += 1
                elif channel is not None:
                    await channel.edit(name=spec["name"], category=category, reason=reason)
                    await _renewal_pause()
                    changed_channels += 1

            for spec, channel in voice_matches:
                category = categories[spec["category"]]
                if channel is None and spec["key"] in ESSENTIAL_KEYS:
                    await guild.create_voice_channel(spec["name"], category=category, reason=reason)
                    await _renewal_pause()
                    created_channels += 1
                elif channel is not None:
                    await channel.edit(name=spec["name"], category=category, reason=reason)
                    changed_channels += 1

            settings["style"] = style
            settings["applied_at"] = int(time.time())
            settings["applied_by"] = ctx.author.id
            save_data()
            await progress.edit(
                content=(
                    f"✅ **{style} 서버 리뉴얼 완료**\n"
                    f"새 카테고리: **{created_categories}개**\n"
                    f"정돈한 기존 채널: **{changed_channels}개**\n"
                    f"새 필수 채널: **{created_channels}개**\n\n"
                    "인식되지 않은 채널은 그대로 유지했습니다. 메뉴 패널: `!서버메뉴 생성`"
                )
            )
        except discord.Forbidden:
            await progress.edit(content="❌ 권한 부족으로 중단됐습니다. 봇 역할에 `채널 관리` 권한을 확인하세요.")
        except discord.HTTPException as exc:
            await progress.edit(content=f"❌ Discord API 오류로 중단됐습니다: `{type(exc).__name__}: {str(exc)[:250]}`")

    @server_renewal.command(name="게임미리보기", aliases=["봇게임미리보기", "게임프리뷰"])
    async def server_renewal_game_preview(ctx: commands.Context, style: str = "깔끔"):
        guild = await require_admin(ctx)
        if guild is None:
            return
        if style not in STYLE_NAMES:
            await ctx.send("❌ 테마는 `깔끔`, `고딕`, `커뮤니티` 중에서 선택하세요.")
            return
        await ctx.send(embed=_game_zone_preview_embed(guild, style))

    @server_renewal.command(name="게임정리", aliases=["봇게임정리", "게임채널정리"])
    async def server_renewal_game_apply(ctx: commands.Context, style: str = "깔끔"):
        guild = await require_admin(ctx)
        if guild is None or not isinstance(ctx.author, discord.Member):
            return
        if style not in STYLE_NAMES:
            await ctx.send("❌ 테마는 `깔끔`, `고딕`, `커뮤니티` 중에서 선택하세요.")
            return
        bot_member = guild.me
        if bot_member is None or not bot_member.guild_permissions.manage_channels:
            await ctx.send("❌ 봇에 `채널 관리` 권한이 필요합니다.")
            return

        text_matches, voices, bot_game_category, voice_category, test_category = _detect_game_zone_channels(guild, style)
        if not any(channel is not None for _, channel in text_matches) and not voices:
            await ctx.send("❌ 정리할 봇 게임·음성 채널을 찾지 못했습니다. 채널 이름을 확인해 주세요.")
            return

        settings = _layout_settings(world_data, guild.id)["layout"]
        settings["backup"] = _snapshot_guild(guild)
        save_data()
        progress = await ctx.send(f"🎮 **{style} 테마로 봇 게임·음성 구역을 나누는 중입니다...**")
        category_names = _game_zone_category_names(style)
        reason = f"ABADDON v{VERSION} 봇 게임·음성 구역 정리 / {ctx.author} ({ctx.author.id})"
        categories: Dict[str, discord.CategoryChannel] = {}
        created_categories = 0
        changed_channels = 0
        reused_categories = 0

        detected_positions = [
            category.position
            for category in (bot_game_category, voice_category, test_category)
            if category is not None
        ]
        base_position = min(detected_positions) if detected_positions else max(0, len(guild.categories) - 1)

        async def prepare_category(
            key: str,
            preferred: Optional[discord.CategoryChannel] = None,
        ) -> discord.CategoryChannel:
            nonlocal created_categories, reused_categories
            target_name = category_names[key]
            existing = discord.utils.get(guild.categories, name=target_name)
            if existing is not None:
                categories[key] = existing
                return existing
            if preferred is not None and preferred.id not in {category.id for category in categories.values()}:
                await preferred.edit(name=target_name, reason=reason)
                await _renewal_pause()
                categories[key] = preferred
                reused_categories += 1
                return preferred
            created = await guild.create_category(target_name, reason=reason)
            await _renewal_pause()
            categories[key] = created
            created_categories += 1
            return created

        try:
            await prepare_category("growth", bot_game_category)
            await prepare_category("game")
            await prepare_category("media")
            await prepare_category("test", test_category)
            await prepare_category("voice", voice_category)

            for offset, key in enumerate(("growth", "game", "media", "test", "voice")):
                with contextlib.suppress(discord.Forbidden, discord.HTTPException):
                    await categories[key].edit(position=base_position + offset, reason=reason)
                    await _renewal_pause()

            spec_to_key = {
                "rpg": "growth",
                "level_notice": "growth",
                "daily_quiz": "growth",
                "gambling": "game",
                "ksi": "game",
                "tiktok": "media",
                "karaoke": "media",
                "bot_test": "test",
            }
            moved_ids: set[int] = set()
            for spec, channel in text_matches:
                if channel is None:
                    continue
                target_key = spec_to_key[spec["key"]]
                await channel.edit(name=spec["name"], category=categories[target_key], reason=reason)
                await _renewal_pause()
                moved_ids.add(channel.id)
                changed_channels += 1

            # BOT GAME 안에 남은 미인식 텍스트 채널은 삭제하지 않고 게임·도박 구역으로 옮깁니다.
            if bot_game_category is not None:
                leftovers = [
                    channel for channel in list(bot_game_category.text_channels)
                    if channel.id not in moved_ids
                ]
                for channel in leftovers:
                    await channel.edit(category=categories["game"], reason=reason)
                    await _renewal_pause()
                    changed_channels += 1

            for index, channel in enumerate(voices):
                await channel.edit(
                    name=f"🔊・음성-{_roman_label(index)}",
                    category=categories["voice"],
                    reason=reason,
                )
                await _renewal_pause()
                changed_channels += 1

            settings["style"] = style
            settings["game_zone_applied_at"] = int(time.time())
            settings["game_zone_applied_by"] = ctx.author.id
            save_data()
            await progress.edit(
                content=(
                    f"✅ **봇 게임·음성 구역 정리 완료 · {style}**\n"
                    f"정돈한 채널: **{changed_channels}개**\n"
                    f"재사용한 카테고리: **{reused_categories}개**\n"
                    f"새 카테고리: **{created_categories}개**\n\n"
                    "사용 중인 채널·메시지는 삭제하지 않았습니다. 빈 옛 카테고리는 "
                    "`!서버리뉴얼 빈카테고리`로 확인한 뒤 정리하세요."
                )
            )
        except discord.Forbidden:
            await progress.edit(content="❌ 권한 부족으로 중단됐습니다. 봇 역할의 `채널 관리` 권한과 역할 순서를 확인하세요.")
        except discord.HTTPException as exc:
            await progress.edit(content=f"❌ Discord API 오류로 중단됐습니다: `{type(exc).__name__}: {str(exc)[:250]}`")

    @server_renewal.command(name="되돌리기", aliases=["undo", "복원"])
    async def server_renewal_undo(ctx: commands.Context):
        guild = await require_admin(ctx)
        if guild is None:
            return
        settings = _layout_settings(world_data, guild.id)["layout"]
        backup = settings.get("backup")
        if not isinstance(backup, dict):
            await ctx.send("⚠️ 되돌릴 서버 리뉴얼 백업이 없습니다.")
            return
        progress = await ctx.send("↩️ **리뉴얼 전 채널 이름과 위치를 복구하는 중입니다...**")
        restored = 0
        category_map = {category.id: category for category in guild.categories}
        channel_map = {channel.id: channel for channel in [*guild.text_channels, *guild.voice_channels]}
        reason = f"ABADDON v{VERSION} 서버 리뉴얼 되돌리기 / {ctx.author}"
        for row in backup.get("categories", []):
            category = category_map.get(int(row.get("id", 0)))
            if category is None:
                with contextlib.suppress(discord.Forbidden, discord.HTTPException):
                    category = await guild.create_category(str(row.get("name", "복구된 카테고리")), reason=reason)
                    await _renewal_pause()
                    await category.edit(position=int(row.get("position", category.position)), reason=reason)
                    await _renewal_pause()
                    restored += 1
                continue
            with contextlib.suppress(discord.Forbidden, discord.HTTPException):
                await category.edit(name=str(row.get("name", category.name)), position=int(row.get("position", category.position)), reason=reason)
                await _renewal_pause()
                restored += 1
        category_map = {category.id: category for category in guild.categories}
        for row in backup.get("channels", []):
            channel = channel_map.get(int(row.get("id", 0)))
            if channel is None:
                continue
            category_id = row.get("category_id")
            category = category_map.get(int(category_id)) if category_id else None
            with contextlib.suppress(discord.Forbidden, discord.HTTPException):
                await channel.edit(
                    name=str(row.get("name", channel.name)),
                    category=category,
                    position=int(row.get("position", channel.position)),
                    reason=reason,
                )
                await _renewal_pause()
                restored += 1
        settings["style"] = None
        settings["restored_at"] = int(time.time())
        save_data()
        await progress.edit(content=f"✅ 리뉴얼 전 상태로 **{restored}개 항목**을 복구했습니다. 새로 만든 채널은 안전을 위해 삭제하지 않았습니다.")

    @server_renewal.command(name="상태", aliases=["status"])
    async def server_renewal_status(ctx: commands.Context):
        guild = await require_admin(ctx)
        if guild is None:
            return
        settings = _layout_settings(world_data, guild.id)["layout"]
        destinations = _menu_destinations(guild)
        await ctx.send(
            "🕯 **서버 리뉴얼 상태**\n"
            f"현재 테마: **{settings.get('style') or '미적용'}**\n"
            f"복구 백업: **{'있음' if settings.get('backup') else '없음'}**\n"
            f"메뉴에서 찾은 주요 채널: **{len(destinations)}개**\n"
            f"저장된 메뉴 메시지: **{'있음' if settings.get('menu_message_id') else '없음'}**"
        )

    @server_renewal.command(name="빈카테고리", aliases=["empty"])
    async def server_renewal_empty(ctx: commands.Context):
        guild = await require_admin(ctx)
        if guild is None:
            return
        empty = [category for category in guild.categories if not category.channels]
        if not empty:
            await ctx.send("✅ 비어 있는 카테고리가 없습니다.")
            return
        lines = [f"• `{category.name}`" for category in empty[:30]]
        await ctx.send(
            "🧹 **비어 있는 카테고리**\n"
            + "\n".join(lines)
            + "\n\n삭제하려면 `!서버리뉴얼 빈카테고리삭제 확인`을 입력하세요. 채널은 삭제하지 않습니다."
        )

    @server_renewal.command(name="빈카테고리삭제", aliases=["cleanempty"])
    async def server_renewal_delete_empty(ctx: commands.Context, confirm: str = ""):
        guild = await require_admin(ctx)
        if guild is None:
            return
        if confirm != "확인":
            await ctx.send("⚠️ 빈 카테고리만 삭제하려면 `!서버리뉴얼 빈카테고리삭제 확인`을 입력하세요.")
            return
        empty = [category for category in guild.categories if not category.channels]
        if not empty:
            await ctx.send("✅ 삭제할 빈 카테고리가 없습니다.")
            return
        settings = _layout_settings(world_data, guild.id)["layout"]
        if not settings.get("backup"):
            settings["backup"] = _snapshot_guild(guild)
            save_data()
        deleted = 0
        reason = f"ABADDON v{VERSION} 빈 카테고리 정리 / {ctx.author}"
        for category in empty:
            try:
                await category.delete(reason=reason)
                deleted += 1
            except (discord.Forbidden, discord.HTTPException):
                continue
        await ctx.send(f"✅ 채널은 건드리지 않고 빈 카테고리 **{deleted}개**를 정리했습니다.")

    @bot.group(name="서버메뉴", aliases=["채널메뉴", "안내패널"], invoke_without_command=True, case_insensitive=True)
    async def server_menu(ctx: commands.Context):
        guild = await require_admin(ctx)
        if guild is None:
            return
        await ctx.send("사용법: `!서버메뉴 생성 [#채널]` · `!서버메뉴 갱신` · `!서버메뉴 삭제`")

    @server_menu.command(name="생성", aliases=["create"])
    async def server_menu_create(ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        guild = await require_admin(ctx)
        if guild is None:
            return
        target = channel or (ctx.channel if isinstance(ctx.channel, discord.TextChannel) else None)
        if target is None:
            await ctx.send("❌ 메뉴를 올릴 텍스트 채널을 지정하세요.")
            return
        destinations = _menu_destinations(guild)
        if not destinations:
            await ctx.send("❌ 연결할 주요 채널을 찾지 못했습니다. 먼저 `!서버리뉴얼 미리보기 깔끔`을 확인하세요.")
            return
        message = await target.send(embed=_menu_embed(guild, destinations), view=_menu_view(guild, destinations))
        settings = _layout_settings(world_data, guild.id)["layout"]
        settings["menu_channel_id"] = target.id
        settings["menu_message_id"] = message.id
        save_data()
        await ctx.send(f"✅ {target.mention}에 서버 이동 메뉴를 만들었습니다.", delete_after=8)

    @server_menu.command(name="갱신", aliases=["update"])
    async def server_menu_update(ctx: commands.Context):
        guild = await require_admin(ctx)
        if guild is None:
            return
        settings = _layout_settings(world_data, guild.id)["layout"]
        channel = guild.get_channel(settings.get("menu_channel_id") or 0)
        if not isinstance(channel, discord.TextChannel) or not settings.get("menu_message_id"):
            await ctx.send("⚠️ 저장된 서버 메뉴가 없습니다. `!서버메뉴 생성`을 먼저 실행하세요.")
            return
        try:
            message = await channel.fetch_message(int(settings["menu_message_id"]))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            await ctx.send("❌ 저장된 메뉴 메시지를 찾지 못했습니다. 새로 생성하세요.")
            return
        destinations = _menu_destinations(guild)
        await message.edit(embed=_menu_embed(guild, destinations), view=_menu_view(guild, destinations))
        await ctx.send("✅ 현재 채널 구조를 기준으로 서버 메뉴를 갱신했습니다.", delete_after=8)

    @server_menu.command(name="삭제", aliases=["delete"])
    async def server_menu_delete(ctx: commands.Context):
        guild = await require_admin(ctx)
        if guild is None:
            return
        settings = _layout_settings(world_data, guild.id)["layout"]
        channel = guild.get_channel(settings.get("menu_channel_id") or 0)
        if isinstance(channel, discord.TextChannel) and settings.get("menu_message_id"):
            with contextlib.suppress(discord.NotFound, discord.Forbidden, discord.HTTPException):
                message = await channel.fetch_message(int(settings["menu_message_id"]))
                await message.delete()
        settings["menu_channel_id"] = None
        settings["menu_message_id"] = None
        save_data()
        await ctx.send("✅ 저장된 서버 메뉴를 해제했습니다.")

    async def handle_auto_tts(message: discord.Message) -> None:
        if message.guild is None or message.author.bot:
            return
        if message.content.startswith("!"):
            return
        if not isinstance(message.author, discord.Member):
            return
        settings = _layout_settings(world_data, message.guild.id)["tts"]
        if not settings.get("enabled"):
            return
        if message.channel.id != settings.get("text_channel_id"):
            return
        voice_channel_id = settings.get("voice_channel_id")
        if not voice_channel_id:
            return
        if settings.get("require_author_in_voice", False):
            if not message.author.voice or message.author.voice.channel.id != voice_channel_id:
                return
        now = time.monotonic()
        key = (message.guild.id, message.author.id)
        if now - VOICE_RUNTIME.user_cooldowns.get(key, 0.0) < TTS_USER_COOLDOWN:
            return
        VOICE_RUNTIME.user_cooldowns[key] = now
        clean = message.clean_content or ""
        if not clean and message.attachments:
            clean = "파일을 올렸습니다."
        ok, _ = await enqueue_tts(
            message.guild,
            message.author,
            clean,
            announce_name=bool(settings.get("announce_names", True)),
        )
        if not ok:
            with contextlib.suppress(discord.Forbidden, discord.HTTPException):
                await message.add_reaction("⚠️")

    bot.add_listener(handle_auto_tts, "on_message")
