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
from discord import app_commands
from discord.ext import commands


VERSION = "4.3.3.4"
TTS_MAX_TEXT = 180
TTS_QUEUE_LIMIT = 20
TTS_USER_COOLDOWN = 4.0
DEFAULT_IDLE_SECONDS = 600
RENEWAL_EDIT_DELAY = 1.0

VOICE_PRESETS: Dict[str, Dict[str, str]] = {
    "선히": {"edge": "ko-KR-SunHiNeural", "label": "밝고 자연스러운 여성 음성", "gender": "여성"},
    "서현": {"edge": "ko-KR-SeoHyeonNeural", "label": "차분하고 선명한 여성 음성", "gender": "여성"},
    "지민": {"edge": "ko-KR-JiMinNeural", "label": "부드럽고 친근한 여성 음성", "gender": "여성"},
    "순복": {"edge": "ko-KR-SoonBokNeural", "label": "편안하고 안정적인 여성 음성", "gender": "여성"},
    "유진": {"edge": "ko-KR-YuJinNeural", "label": "또렷하고 생기 있는 여성 음성", "gender": "여성"},
    "인준": {"edge": "ko-KR-InJoonNeural", "label": "차분하고 부드러운 남성 음성", "gender": "남성"},
    "봉진": {"edge": "ko-KR-BongJinNeural", "label": "낮고 안정적인 남성 음성", "gender": "남성"},
    "국민": {"edge": "ko-KR-GookMinNeural", "label": "또렷하고 힘 있는 남성 음성", "gender": "남성"},
    "현수": {"edge": "ko-KR-HyunsuNeural", "label": "담백하고 자연스러운 남성 음성", "gender": "남성"},
    "현수다국어": {"edge": "ko-KR-HyunsuMultilingualNeural", "label": "외국어 발음도 지원하는 남성 음성", "gender": "남성"},
}

VOICE_CHOICE_LABELS: Dict[str, str] = {
    name: f"{name} · {data['gender']} · {data['label']}"
    for name, data in VOICE_PRESETS.items()
}

VOICE_APP_CHOICES: List[app_commands.Choice[str]] = [
    app_commands.Choice(name=label[:100], value=name)
    for name, label in VOICE_CHOICE_LABELS.items()
]


def _voice_name_or_default(value: Any, default: str = "선히") -> str:
    name = str(value or default)
    return name if name in VOICE_PRESETS else default


def _personal_voice(settings: Dict[str, Any], user_id: int) -> str:
    user_voices = settings.setdefault("user_voices", {})
    return _voice_name_or_default(user_voices.get(str(user_id)), _voice_name_or_default(settings.get("voice")))


THEME_META: Dict[str, Dict[str, Any]] = {
    "깔끔": {"label": "정돈된 기본형", "color": 0x5865F2},
    "고딕": {"label": "검은 성역", "color": 0x6D2335},
    "커뮤니티": {"label": "친근한 커뮤니티", "color": 0x57F287},
    "미니멀": {"label": "짧고 단순한 메뉴", "color": 0x99AAB5},
    "사이버": {"label": "네온·터미널", "color": 0x00D9FF},
    "아포칼립스": {"label": "폐허 생존기지", "color": 0xF47B20},
    "판타지": {"label": "길드·왕국", "color": 0x9B59B6},
}


def _theme_color(style: str) -> int:
    return int(THEME_META.get(style, THEME_META["깔끔"])["color"])


def _text_channel_specs(style: str) -> List[Dict[str, Any]]:
    themes: Dict[str, List[Tuple[str, str, str, Tuple[str, ...]]]] = {
        "깔끔": [
            ("notice", "〔 시작 〕", "📢・공지", ("공지", "announcement", "notice")),
            ("rules", "〔 시작 〕", "📕・규칙", ("규칙", "룰", "이용규칙", "rule")),
            ("roles", "〔 시작 〕", "🎭・역할", ("역할", "role", "인증")),
            ("help", "〔 시작 〕", "❓・도움", ("도움", "가이드", "guide", "help")),
            ("general", "〔 대화 〕", "💬・일반", ("일반", "자유", "잡담", "광장", "general", "chat")),
            ("game", "〔 대화 〕", "🎮・게임", ("게임", "game")),
            ("bot", "〔 대화 〕", "🤖・봇", ("봇", "명령어", "command")),
            ("media", "〔 미디어 〕", "🖼・사진", ("사진", "미디어", "이미지", "스크린샷", "media")),
            ("clips", "〔 미디어 〕", "🎞・영상", ("영상", "클립", "동영상", "clip", "video")),
            ("ticket", "〔 문의 〕", "🎫・문의", ("문의", "신고", "건의", "ticket")),
            ("admin", "〔 운영 〕", "🔒・관리", ("관리자", "운영진", "스태프", "admin")),
            ("logs", "〔 운영 〕", "📋・로그", ("로그", "기록", "log")),
        ],
        "고딕": [
            ("notice", "╭─〔 ☩ 성역의 문 〕─╮", "📜・성역-공지", ("공지", "announcement", "notice")),
            ("rules", "╭─〔 ☩ 성역의 문 〕─╮", "📕・성역-규율", ("규칙", "룰", "이용규칙", "rule")),
            ("roles", "╭─〔 ☩ 성역의 문 〕─╮", "🎭・서약-선택", ("역할", "role", "인증")),
            ("help", "╭─〔 ☩ 성역의 문 〕─╮", "🕯・길잡이", ("도움", "가이드", "guide", "help")),
            ("general", "╭─〔 🕯 순례자 광장 〕─╮", "💬・순례자-광장", ("일반", "자유", "잡담", "광장", "general", "chat")),
            ("game", "╭─〔 🕯 순례자 광장 〕─╮", "🎮・게임-회랑", ("게임", "game")),
            ("bot", "╭─〔 ⚙ 검은 장치실 〕─╮", "🤖・봇-명령실", ("봇", "명령어", "command")),
            ("media", "╭─〔 🖼 기억의 전당 〕─╮", "🖼・사진과-기록", ("사진", "미디어", "이미지", "스크린샷", "media")),
            ("clips", "╭─〔 🖼 기억의 전당 〕─╮", "🎞・영상과-클립", ("영상", "클립", "동영상", "clip", "video")),
            ("ticket", "╭─〔 🎫 고해의 방 〕─╮", "🎫・문의-접수", ("문의", "신고", "건의", "ticket")),
            ("admin", "╭─〔 🛡 검은 의회 〕─╮", "🔒・의회-회의실", ("관리자", "운영진", "스태프", "admin")),
            ("logs", "╭─〔 🛡 검은 의회 〕─╮", "📋・감시-기록", ("로그", "기록", "log")),
        ],
        "커뮤니티": [
            ("notice", "━━━ 시작하기 ━━━", "📢・공지사항", ("공지", "announcement", "notice")),
            ("rules", "━━━ 시작하기 ━━━", "📕・이용규칙", ("규칙", "룰", "이용규칙", "rule")),
            ("roles", "━━━ 시작하기 ━━━", "🎭・역할선택", ("역할", "role", "인증")),
            ("help", "━━━ 시작하기 ━━━", "❓・도움말", ("도움", "가이드", "guide", "help")),
            ("general", "━━━ 커뮤니티 ━━━", "💬・자유채팅", ("일반", "자유", "잡담", "광장", "general", "chat")),
            ("game", "━━━ 커뮤니티 ━━━", "🎮・게임이야기", ("게임", "game")),
            ("bot", "━━━ 커뮤니티 ━━━", "🤖・봇명령어", ("봇", "명령어", "command")),
            ("media", "━━━ 미디어 ━━━", "🖼・사진공유", ("사진", "미디어", "이미지", "스크린샷", "media")),
            ("clips", "━━━ 미디어 ━━━", "🎞・영상클립", ("영상", "클립", "동영상", "clip", "video")),
            ("ticket", "━━━ 문의지원 ━━━", "🎫・문의접수", ("문의", "신고", "건의", "ticket")),
            ("admin", "━━━ 운영지원 ━━━", "🔒・운영진채팅", ("관리자", "운영진", "스태프", "admin")),
            ("logs", "━━━ 운영지원 ━━━", "📋・운영로그", ("로그", "기록", "log")),
        ],
        "미니멀": [
            ("notice", "START", "notice", ("공지", "announcement", "notice")),
            ("rules", "START", "rules", ("규칙", "룰", "이용규칙", "rule")),
            ("roles", "START", "roles", ("역할", "role", "인증")),
            ("help", "START", "guide", ("도움", "가이드", "guide", "help")),
            ("general", "CHAT", "general", ("일반", "자유", "잡담", "광장", "general", "chat")),
            ("game", "CHAT", "games", ("게임", "game")),
            ("bot", "CHAT", "bot", ("봇", "명령어", "command")),
            ("media", "MEDIA", "photos", ("사진", "미디어", "이미지", "스크린샷", "media")),
            ("clips", "MEDIA", "clips", ("영상", "클립", "동영상", "clip", "video")),
            ("ticket", "SUPPORT", "support", ("문의", "신고", "건의", "ticket")),
            ("admin", "STAFF", "staff", ("관리자", "운영진", "스태프", "admin")),
            ("logs", "STAFF", "logs", ("로그", "기록", "log")),
        ],
        "사이버": [
            ("notice", "【 00 · BOOT 】", "📡・system-news", ("공지", "announcement", "notice")),
            ("rules", "【 00 · BOOT 】", "📑・protocol", ("규칙", "룰", "이용규칙", "rule")),
            ("roles", "【 00 · BOOT 】", "🪪・access-role", ("역할", "role", "인증")),
            ("help", "【 00 · BOOT 】", "💾・manual", ("도움", "가이드", "guide", "help")),
            ("general", "【 01 · NETWORK 】", "💬・main-link", ("일반", "자유", "잡담", "광장", "general", "chat")),
            ("game", "【 01 · NETWORK 】", "🎮・game-node", ("게임", "game")),
            ("bot", "【 02 · TERMINAL 】", "⌨️・bot-terminal", ("봇", "명령어", "command")),
            ("media", "【 03 · ARCHIVE 】", "🖼・image-cache", ("사진", "미디어", "이미지", "스크린샷", "media")),
            ("clips", "【 03 · ARCHIVE 】", "🎞・video-cache", ("영상", "클립", "동영상", "clip", "video")),
            ("ticket", "【 04 · SUPPORT 】", "🎫・support-ticket", ("문의", "신고", "건의", "ticket")),
            ("admin", "【 99 · ADMIN 】", "🔒・admin-core", ("관리자", "운영진", "스태프", "admin")),
            ("logs", "【 99 · ADMIN 】", "📋・system-log", ("로그", "기록", "log")),
        ],
        "아포칼립스": [
            ("notice", "╔〔 생존자 전초기지 〕╗", "📻・비상-방송", ("공지", "announcement", "notice")),
            ("rules", "╔〔 생존자 전초기지 〕╗", "📕・생존-수칙", ("규칙", "룰", "이용규칙", "rule")),
            ("roles", "╔〔 생존자 전초기지 〕╗", "🪪・생존자-등록", ("역할", "role", "인증")),
            ("help", "╔〔 생존자 전초기지 〕╗", "🧭・작전-안내", ("도움", "가이드", "guide", "help")),
            ("general", "╠〔 공동 대피소 〕╣", "💬・대피소-광장", ("일반", "자유", "잡담", "광장", "general", "chat")),
            ("game", "╠〔 공동 대피소 〕╣", "🎮・휴식-구역", ("게임", "game")),
            ("bot", "╠〔 통제 장치실 〕╣", "🤖・작전-단말기", ("봇", "명령어", "command")),
            ("media", "╠〔 기록 보관소 〕╣", "📸・현장-사진", ("사진", "미디어", "이미지", "스크린샷", "media")),
            ("clips", "╠〔 기록 보관소 〕╣", "🎞・생존-기록", ("영상", "클립", "동영상", "clip", "video")),
            ("ticket", "╠〔 구조 요청소 〕╣", "🆘・구조-요청", ("문의", "신고", "건의", "ticket")),
            ("admin", "╚〔 지휘 통제실 〕╝", "🔒・지휘관-회의", ("관리자", "운영진", "스태프", "admin")),
            ("logs", "╚〔 지휘 통제실 〕╝", "📋・감시-일지", ("로그", "기록", "log")),
        ],
        "판타지": [
            ("notice", "✦ 왕국의 관문 ✦", "📜・왕국-칙령", ("공지", "announcement", "notice")),
            ("rules", "✦ 왕국의 관문 ✦", "📖・모험가-규율", ("규칙", "룰", "이용규칙", "rule")),
            ("roles", "✦ 왕국의 관문 ✦", "🎭・직업-선택", ("역할", "role", "인증")),
            ("help", "✦ 왕국의 관문 ✦", "🗺・모험-안내", ("도움", "가이드", "guide", "help")),
            ("general", "✦ 모험가 길드 ✦", "💬・길드-홀", ("일반", "자유", "잡담", "광장", "general", "chat")),
            ("game", "✦ 모험가 길드 ✦", "🎮・놀이-광장", ("게임", "game")),
            ("bot", "✦ 마도 공방 ✦", "🔮・마법-명령실", ("봇", "명령어", "command")),
            ("media", "✦ 기억의 수정관 ✦", "🖼・모험-사진", ("사진", "미디어", "이미지", "스크린샷", "media")),
            ("clips", "✦ 기억의 수정관 ✦", "🎞・영웅-연대기", ("영상", "클립", "동영상", "clip", "video")),
            ("ticket", "✦ 의뢰 게시소 ✦", "📨・길드-의뢰", ("문의", "신고", "건의", "ticket")),
            ("admin", "✦ 왕실 회의실 ✦", "🔒・원탁-회의", ("관리자", "운영진", "스태프", "admin")),
            ("logs", "✦ 왕실 회의실 ✦", "📚・왕국-기록", ("로그", "기록", "log")),
        ],
    }
    rows = themes.get(style, themes["깔끔"])
    return [{"key": key, "category": category, "name": name, "keywords": keywords} for key, category, name, keywords in rows]


def _voice_channel_specs(style: str) -> List[Dict[str, Any]]:
    mapping: Dict[str, Tuple[str, Tuple[str, str, str]]] = {
        "깔끔": ("〔 음성 〕", ("🔊・로비", "🎮・게임", "🌙・잠수")),
        "고딕": ("╭─〔 🔊 메아리의 회랑 〕─╮", ("🔊・메아리-대기실", "🎮・전장의-방", "🌙・침묵의-방")),
        "커뮤니티": ("━━━ 음성채널 ━━━", ("🔊・음성로비", "🎮・게임방", "🌙・잠수방")),
        "미니멀": ("VOICE", ("lobby", "game", "afk")),
        "사이버": ("【 05 · VOICE LINK 】", ("🔊・voice-lobby", "🎮・squad-link", "🌙・idle-mode")),
        "아포칼립스": ("╠〔 무전 통신망 〕╣", ("📻・공용-무전", "🎮・분대-통신", "🌙・무전-대기")),
        "판타지": ("✦ 음유시인의 회랑 ✦", ("🔊・모험가-휴게실", "🎮・파티-원정", "🌙・고요한-숲")),
    }
    category, names = mapping.get(style, mapping["깔끔"])
    return [
        {"key": "voice_lobby", "category": category, "name": names[0], "keywords": ("로비", "대기", "일반", "lobby")},
        {"key": "voice_game", "category": category, "name": names[1], "keywords": ("게임", "game")},
        {"key": "voice_afk", "category": category, "name": names[2], "keywords": ("잠수", "afk")},
    ]


def _game_zone_specs(style: str) -> List[Dict[str, Any]]:
    category_sets: Dict[str, Dict[str, str]] = {
        "깔끔": {"growth": "〔 RPG · 성장 〕", "game": "〔 게임 · 도박 〕", "media": "〔 음악 · 미디어 〕", "test": "〔 테스트 〕", "voice": "〔 음성 라운지 〕"},
        "고딕": {"growth": "╭─〔 ⚔ 종말 전장 〕─╮", "game": "╭─〔 🎲 운명의 방 〕─╮", "media": "╭─〔 🎵 망자의 선율 〕─╮", "test": "╭─〔 🧪 봉인 실험실 〕─╮", "voice": "╭─〔 🔊 메아리의 방 〕─╮"},
        "커뮤니티": {"growth": "━━━ RPG · 성장 ━━━", "game": "━━━ 게임 · 도박 ━━━", "media": "━━━ 음악 · 미디어 ━━━", "test": "━━━ 테스트 ━━━", "voice": "━━━ 음성 라운지 ━━━"},
        "미니멀": {"growth": "RPG", "game": "GAMES", "media": "MEDIA", "test": "TEST", "voice": "VOICE ROOMS"},
        "사이버": {"growth": "【 10 · RPG CORE 】", "game": "【 11 · GAME GRID 】", "media": "【 12 · MEDIA CACHE 】", "test": "【 98 · TEST LAB 】", "voice": "【 13 · VOICE LINK 】"},
        "아포칼립스": {"growth": "╠〔 원정 지휘소 〕╣", "game": "╠〔 휴식·도박 구역 〕╣", "media": "╠〔 방송·기록소 〕╣", "test": "╠〔 장비 시험소 〕╣", "voice": "╠〔 무전 통신망 〕╣"},
        "판타지": {"growth": "✦ 모험가 성장관 ✦", "game": "✦ 주사위 선술집 ✦", "media": "✦ 음유시인 무대 ✦", "test": "✦ 마법 실험실 ✦", "voice": "✦ 파티 음성관 ✦"},
    }
    categories = category_sets.get(style, category_sets["깔끔"])
    names: Dict[str, Dict[str, str]] = {
        "깔끔": {"rpg": "⚔️・아포칼립스-rpg", "level": "🎉・레벨-알림", "quiz": "🧭・오늘의-퀴즈방", "gambling": "🎲・도박장", "ksi": "🤖・크시", "tiktok": "📱・틱톡", "karaoke": "🎵・노래방", "test": "🧪・봇-테스트"},
        "고딕": {"rpg": "⚔️・종말-rpg", "level": "🩸・성장-기록", "quiz": "🧭・운명의-문답", "gambling": "🎲・운명의-도박장", "ksi": "🤖・검은-인형", "tiktok": "📱・짧은-기억", "karaoke": "🎵・망자의-노래", "test": "🧪・봉인-실험"},
        "커뮤니티": {"rpg": "⚔️・아포칼립스-rpg", "level": "🎉・레벨업-알림", "quiz": "🧭・오늘의-퀴즈", "gambling": "🎲・도박장", "ksi": "🤖・크시", "tiktok": "📱・틱톡", "karaoke": "🎵・노래방", "test": "🧪・봇-테스트"},
        "미니멀": {"rpg": "rpg", "level": "level-up", "quiz": "daily-quiz", "gambling": "casino", "ksi": "ksi", "tiktok": "shorts", "karaoke": "music", "test": "bot-test"},
        "사이버": {"rpg": "⚔️・rpg-core", "level": "📈・level-signal", "quiz": "🧠・daily-query", "gambling": "🎲・casino-node", "ksi": "🤖・ksi-bot", "tiktok": "📱・short-cache", "karaoke": "🎵・audio-stream", "test": "🧪・sandbox"},
        "아포칼립스": {"rpg": "⚔️・생존-rpg", "level": "📈・생존자-성장", "quiz": "🧭・일일-작전", "gambling": "🎲・암시장-도박", "ksi": "🤖・보조-단말", "tiktok": "📱・현장-숏폼", "karaoke": "🎵・대피소-방송", "test": "🧪・장비-시험"},
        "판타지": {"rpg": "⚔️・모험가-rpg", "level": "✨・성장-축복", "quiz": "🗺・오늘의-의뢰", "gambling": "🎲・선술집-주사위", "ksi": "🤖・마도-골렘", "tiktok": "📱・짧은-연대기", "karaoke": "🎵・음유시인-무대", "test": "🧪・마법-실험"},
    }
    n = names.get(style, names["깔끔"])
    return [
        {"key": "rpg", "category": categories["growth"], "name": n["rpg"], "keywords": ("아포칼립스rpg", "아포칼립스", "rpg")},
        {"key": "level_notice", "category": categories["growth"], "name": n["level"], "keywords": ("레벨알림", "레벨", "levelnotify", "levelup")},
        {"key": "daily_quiz", "category": categories["growth"], "name": n["quiz"], "keywords": ("오늘의퀴즈방", "오늘의퀴즈", "퀴즈방", "퀴즈", "quiz")},
        {"key": "gambling", "category": categories["game"], "name": n["gambling"], "keywords": ("도박장", "도박", "카지노", "casino", "gambling")},
        {"key": "ksi", "category": categories["game"], "name": n["ksi"], "keywords": ("크시", "kshi", "ksi")},
        {"key": "tiktok", "category": categories["media"], "name": n["tiktok"], "keywords": ("틱톡", "tiktok", "shorts")},
        {"key": "karaoke", "category": categories["media"], "name": n["karaoke"], "keywords": ("노래방", "음악", "뮤직", "music", "song")},
        {"key": "bot_test", "category": categories["test"], "name": n["test"], "keywords": ("봇테스트", "테스트", "test")},
    ]


def _game_zone_category_names(style: str) -> Dict[str, str]:
    specs = _game_zone_specs(style)
    result = {"growth": specs[0]["category"], "game": specs[3]["category"], "media": specs[5]["category"], "test": specs[7]["category"]}
    result["voice"] = _voice_channel_specs(style)[0]["category"]
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
        color=_theme_color(style),
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


STYLE_NAMES = set(THEME_META)
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
    # v4.3.3.3부터 실제 Microsoft 음성 이름과 표시 이름을 일치시킵니다.
    # 구버전의 "서현"은 실제로 SunHi 음성을 사용했으므로 선히로 자동 이관합니다.
    if int(tts.get("voice_schema_version", 0) or 0) < 2:
        if tts.get("voice") == "서현":
            tts["voice"] = "선히"
        tts["voice_schema_version"] = 2
    tts.setdefault("voice", "선히")
    tts["voice"] = _voice_name_or_default(tts.get("voice"))
    tts.setdefault("user_voices", {})
    if not isinstance(tts.get("user_voices"), dict):
        tts["user_voices"] = {}
    tts.setdefault("speed", 1.0)
    tts.setdefault("volume", 1.0)
    tts.setdefault("idle_seconds", DEFAULT_IDLE_SECONDS)
    tts.setdefault("announce_names", True)
    tts.setdefault("auto_join", True)
    tts.setdefault("require_author_in_voice", False)
    settings.setdefault("layout", {})
    settings["layout"].setdefault("style", None)
    settings["layout"].setdefault("backup", None)
    settings["layout"].setdefault("backup_history", [])
    if not isinstance(settings["layout"].get("backup_history"), list):
        settings["layout"]["backup_history"] = []
    settings["layout"].setdefault("menu_channel_id", None)
    settings["layout"].setdefault("menu_message_id", None)
    return settings


def _snapshot_guild(
    guild: discord.Guild,
    *,
    operation: str = "renewal",
    style: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "snapshot_version": 2,
        "created_at": int(time.time()),
        "operation": operation,
        "style": style,
        "created_category_ids": [],
        "created_channel_ids": [],
        "reused_category_ids": [],
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


def _store_backup(layout: Dict[str, Any], snapshot: Dict[str, Any]) -> Dict[str, Any]:
    previous = layout.get("backup")
    history = layout.setdefault("backup_history", [])
    if isinstance(previous, dict):
        previous_time = int(previous.get("created_at", 0) or 0)
        if not history or int(history[-1].get("created_at", 0) or 0) != previous_time:
            history.append(previous)
    history[:] = history[-4:]
    layout["backup"] = snapshot
    return snapshot


def _record_created(backup: Dict[str, Any], kind: str, object_id: int) -> None:
    key = "created_category_ids" if kind == "category" else "created_channel_ids"
    values = backup.setdefault(key, [])
    if object_id not in values:
        values.append(object_id)


def _all_theme_category_names() -> set[str]:
    names: set[str] = set()
    for style in STYLE_NAMES:
        for spec in [*_text_channel_specs(style), *_voice_channel_specs(style), *_game_zone_specs(style)]:
            names.add(str(spec["category"]))
        names.update(_game_zone_category_names(style).values())
    return names


def _all_theme_channel_names() -> set[str]:
    names: set[str] = set()
    for style in STYLE_NAMES:
        for spec in [*_text_channel_specs(style), *_voice_channel_specs(style), *_game_zone_specs(style)]:
            names.add(str(spec["name"]))
        for index in range(10):
            names.add(f"🔊・음성-{_roman_label(index)}")
    return names


def _empty_categories(guild: discord.Guild) -> List[discord.CategoryChannel]:
    return sorted(
        [category for category in guild.categories if not category.channels],
        key=lambda category: (category.position, category.id),
    )


def _parse_category_selection(raw: str, empty: Sequence[discord.CategoryChannel]) -> List[discord.CategoryChannel]:
    value = (raw or "").strip().lower()
    if value in {"전체", "all"}:
        return list(empty)
    indices: set[int] = set()
    for token in re.split(r"[,\s]+", value):
        if not token:
            continue
        if "-" in token:
            left, _, right = token.partition("-")
            if left.isdigit() and right.isdigit():
                start_i, end_i = int(left), int(right)
                for number in range(min(start_i, end_i), max(start_i, end_i) + 1):
                    indices.add(number)
        elif token.isdigit():
            indices.add(int(token))
    return [category for index, category in enumerate(empty, start=1) if index in indices]

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
        color=_theme_color(style),
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
    try:
        rate = int(round((speed - 1.0) * 100))
        communicator = edge_tts.Communicate(text=text, voice=voice, rate=f"{rate:+d}%")
        await communicator.save(output_path)
        return Path(output_path).exists() and Path(output_path).stat().st_size > 0
    except Exception as exc:
        print(f"[TTS Edge 합성 실패] voice={voice} {type(exc).__name__}: {exc}", flush=True)
        return False


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
    headers = {"User-Agent": "Mozilla/5.0 ABADDON-TTS/4.3.3.4"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise RuntimeError(f"TTS HTTP {response.status}")
            data = await response.read()
    if not data:
        raise RuntimeError("TTS 음성 데이터가 비어 있습니다.")
    await asyncio.to_thread(Path(output_path).write_bytes, data)


async def _synthesise(text: str, voice_key: str, speed: float, output_path: str) -> str:
    preset = VOICE_PRESETS.get(voice_key, VOICE_PRESETS["선히"])
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
        voice_key: Optional[str] = None,
    ) -> Tuple[bool, str]:
        settings = _layout_settings(world_data, guild.id)["tts"]
        clean = _clean_spoken_text(text)
        if not clean:
            return False, "읽을 수 있는 내용이 없습니다."
        queue = VOICE_RUNTIME.queue_for(guild.id)
        if queue.full():
            return False, f"대기열이 가득 찼습니다. 최대 {TTS_QUEUE_LIMIT}개까지 보관합니다."
        spoken = f"{author.display_name}. {clean}" if announce_name else clean
        resolved_voice = _voice_name_or_default(voice_key, _personal_voice(settings, author.id))
        await queue.put({
            "text": spoken,
            "author_id": author.id,
            "voice": resolved_voice,
            "queued_at": time.time(),
        })
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
                    _voice_name_or_default(item.get("voice"), _voice_name_or_default(settings.get("voice"))),
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
                "`/tts 목소리` · `/tts 내설정` · `!TTS 기본목소리 선히` · `!TTS 진단`"
            ),
            color=0x6D2335,
        )
        embed.add_field(name="자동 낭독", value="켜짐" if settings.get("enabled") else "꺼짐", inline=True)
        embed.add_field(name="대기열", value=f"{queue.qsize()}/{TTS_QUEUE_LIMIT}", inline=True)
        embed.add_field(name="서버 기본 목소리", value=str(settings.get("voice", "선히")), inline=True)
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
        if guild is None or not isinstance(ctx.author, discord.Member):
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        if voice_name is None:
            lines = [f"• **{name}** — {data['label']}" for name, data in VOICE_PRESETS.items()]
            current = _personal_voice(settings, ctx.author.id)
            await ctx.send(
                "🔊 **사용 가능한 한국어 목소리 10종**\n"
                + "\n".join(lines)
                + f"\n\n내 목소리: **{current}**\n설정: `!TTS 목소리 선히` 또는 `/tts 목소리`"
            )
            return
        voice_name = voice_name.strip()
        if voice_name.casefold() in {"기본", "초기화", "default", "reset"}:
            settings.setdefault("user_voices", {}).pop(str(ctx.author.id), None)
            save_data()
            await ctx.send(f"✅ 개인 목소리 설정을 지웠습니다. 이제 서버 기본 **{settings.get('voice', '선히')}**을 사용합니다.")
            return
        if voice_name not in VOICE_PRESETS:
            await ctx.send("❌ 지원하지 않는 목소리입니다. `!TTS 목소리`로 목록을 확인하세요.")
            return
        settings.setdefault("user_voices", {})[str(ctx.author.id)] = voice_name
        save_data()
        await ctx.send(f"✅ 앞으로 {ctx.author.mention}님의 메시지는 **{voice_name}** 목소리로 읽습니다.")

    @tts_group.command(name="기본목소리", aliases=["서버목소리", "defaultvoice"])
    async def tts_default_voice(ctx: commands.Context, voice_name: Optional[str] = None):
        guild = await require_admin(ctx)
        if guild is None:
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        if voice_name is None:
            await ctx.send(
                f"🔊 서버 기본 목소리: **{settings.get('voice', '선히')}**\n"
                "변경: `!TTS 기본목소리 선히`"
            )
            return
        voice_name = voice_name.strip()
        if voice_name not in VOICE_PRESETS:
            await ctx.send("❌ 지원하지 않는 목소리입니다. `!TTS 목소리`로 목록을 확인하세요.")
            return
        settings["voice"] = voice_name
        save_data()
        await ctx.send(f"✅ 개인 설정이 없는 사용자의 기본 목소리를 **{voice_name}**으로 변경했습니다.")

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
        embed.add_field(name="목소리", value=f"{settings.get('voice', '선히')} · {settings.get('speed', 1.0)}배 · {int(float(settings.get('volume', 1.0))*100)}%", inline=True)
        embed.add_field(
            name="음성 의존성",
            value=f"PyNaCl: {'✅' if has_nacl else '❌'}\nedge-tts: {'✅' if has_edge else '대체 음성 사용'}",
            inline=False,
        )
        await ctx.send(embed=embed)

    # Discord 슬래시 명령어: 일반 사용자는 개인 목소리/미리듣기, 관리자는 서버 설정을 변경합니다.
    tts_slash = app_commands.Group(name="tts", description="TTS 목소리와 자동 낭독 설정을 관리합니다.")

    async def slash_guild_member(interaction: discord.Interaction) -> Tuple[Optional[discord.Guild], Optional[discord.Member]]:
        guild = interaction.guild
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if guild is None or member is None:
            if interaction.response.is_done():
                await interaction.followup.send("❌ 서버 안에서만 사용할 수 있습니다.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ 서버 안에서만 사용할 수 있습니다.", ephemeral=True)
            return None, None
        return guild, member

    async def slash_require_admin(interaction: discord.Interaction) -> Tuple[Optional[discord.Guild], Optional[discord.Member]]:
        guild, member = await slash_guild_member(interaction)
        if guild is None or member is None:
            return None, None
        if not (member.guild_permissions.administrator or member.guild_permissions.manage_guild):
            if interaction.response.is_done():
                await interaction.followup.send("❌ 서버 관리자만 사용할 수 있습니다.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ 서버 관리자만 사용할 수 있습니다.", ephemeral=True)
            return None, None
        return guild, member

    @tts_slash.command(name="목소리", description="내 TTS 목소리를 드롭다운에서 선택합니다.")
    @app_commands.describe(voice="내 메시지를 읽을 목소리")
    @app_commands.choices(voice=VOICE_APP_CHOICES)
    async def slash_tts_voice(interaction: discord.Interaction, voice: app_commands.Choice[str]):
        guild, member = await slash_guild_member(interaction)
        if guild is None or member is None:
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        settings.setdefault("user_voices", {})[str(member.id)] = voice.value
        save_data()
        await interaction.response.send_message(
            f"✅ 내 TTS 목소리를 **{voice.value}**으로 저장했습니다.\n{VOICE_PRESETS[voice.value]['label']}",
            ephemeral=True,
        )

    @tts_slash.command(name="내설정", description="내 TTS 목소리와 서버 기본 설정을 확인합니다.")
    async def slash_tts_my_settings(interaction: discord.Interaction):
        guild, member = await slash_guild_member(interaction)
        if guild is None or member is None:
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        personal = _personal_voice(settings, member.id)
        inherited = str(member.id) not in settings.get("user_voices", {})
        await interaction.response.send_message(
            "🔊 **내 TTS 설정**\n"
            f"• 목소리: **{personal}**{' (서버 기본값)' if inherited else ''}\n"
            f"• 설명: {VOICE_PRESETS[personal]['label']}\n"
            f"• 서버 속도: {settings.get('speed', 1.0)}배",
            ephemeral=True,
        )

    @tts_slash.command(name="초기화", description="내 개인 목소리 설정을 지우고 서버 기본값을 사용합니다.")
    async def slash_tts_reset(interaction: discord.Interaction):
        guild, member = await slash_guild_member(interaction)
        if guild is None or member is None:
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        settings.setdefault("user_voices", {}).pop(str(member.id), None)
        save_data()
        await interaction.response.send_message(
            f"✅ 개인 목소리 설정을 초기화했습니다. 서버 기본 **{settings.get('voice', '선히')}**을 사용합니다.",
            ephemeral=True,
        )

    @tts_slash.command(name="미리듣기", description="선택한 목소리를 지정 음성 채널에서 시험 재생합니다.")
    @app_commands.describe(voice="미리 들을 목소리")
    @app_commands.choices(voice=VOICE_APP_CHOICES)
    async def slash_tts_preview(interaction: discord.Interaction, voice: app_commands.Choice[str]):
        guild, member = await slash_guild_member(interaction)
        if guild is None or member is None:
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        if not settings.get("voice_channel_id"):
            await interaction.response.send_message("❌ 관리자가 TTS 음성 채널을 먼저 설정해야 합니다.", ephemeral=True)
            return
        now = time.monotonic()
        key = (guild.id, member.id)
        remaining = TTS_USER_COOLDOWN - (now - VOICE_RUNTIME.user_cooldowns.get(key, 0.0))
        if remaining > 0:
            await interaction.response.send_message(f"⏳ {remaining:.1f}초 뒤에 다시 시도하세요.", ephemeral=True)
            return
        VOICE_RUNTIME.user_cooldowns[key] = now
        ok, message = await enqueue_tts(
            guild,
            member,
            f"{voice.value} 목소리 미리 듣기입니다. 검은 성역에 오신 것을 환영합니다.",
            announce_name=False,
            voice_key=voice.value,
        )
        await interaction.response.send_message(("✅ " if ok else "❌ ") + message, ephemeral=True)

    @tts_slash.command(name="기본목소리", description="개인 설정이 없는 사용자의 서버 기본 목소리를 정합니다.")
    @app_commands.describe(voice="서버 기본 목소리")
    @app_commands.choices(voice=VOICE_APP_CHOICES)
    async def slash_tts_default_voice(interaction: discord.Interaction, voice: app_commands.Choice[str]):
        guild, member = await slash_require_admin(interaction)
        if guild is None or member is None:
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        settings["voice"] = voice.value
        save_data()
        await interaction.response.send_message(f"✅ 서버 기본 TTS 목소리를 **{voice.value}**으로 변경했습니다.", ephemeral=True)

    @tts_slash.command(name="채널설정", description="자동 낭독 텍스트 채널과 음성 채널을 지정합니다.")
    @app_commands.describe(text_channel="메시지를 읽을 텍스트 채널", voice_channel="봇이 입장할 음성 채널")
    async def slash_tts_channels(
        interaction: discord.Interaction,
        text_channel: discord.TextChannel,
        voice_channel: discord.VoiceChannel,
    ):
        guild, member = await slash_require_admin(interaction)
        if guild is None or member is None:
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        settings["text_channel_id"] = text_channel.id
        settings["voice_channel_id"] = voice_channel.id
        settings["enabled"] = True
        settings["auto_join"] = True
        settings["require_author_in_voice"] = False
        save_data()
        await interaction.response.send_message(
            f"✅ 자동 TTS를 설정했습니다.\n텍스트: {text_channel.mention}\n음성: {voice_channel.mention}",
            ephemeral=True,
        )

    @tts_slash.command(name="켜기", description="저장된 채널에서 자동 TTS를 켭니다.")
    async def slash_tts_enable(interaction: discord.Interaction):
        guild, member = await slash_require_admin(interaction)
        if guild is None or member is None:
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        if not settings.get("text_channel_id") or not settings.get("voice_channel_id"):
            await interaction.response.send_message("❌ `/tts 채널설정`을 먼저 실행하세요.", ephemeral=True)
            return
        settings["enabled"] = True
        save_data()
        await interaction.response.send_message("✅ 자동 TTS를 켰습니다.", ephemeral=True)

    @tts_slash.command(name="끄기", description="자동 TTS를 끄고 대기열을 비웁니다.")
    async def slash_tts_disable(interaction: discord.Interaction):
        guild, member = await slash_require_admin(interaction)
        if guild is None or member is None:
            return
        settings = _layout_settings(world_data, guild.id)["tts"]
        settings["enabled"] = False
        removed = VOICE_RUNTIME.clear(guild.id)
        save_data()
        await interaction.response.send_message(f"✅ 자동 TTS를 끄고 대기 메시지 {removed}개를 비웠습니다.", ephemeral=True)

    if bot.tree.get_command("tts") is not None:
        raise RuntimeError("슬래시 명령어 충돌: /tts가 이미 등록되어 있습니다.")
    bot.tree.add_command(tts_slash)

    @bot.group(name="서버리뉴얼", aliases=["서버정리", "서버디자인"], invoke_without_command=True, case_insensitive=True)
    async def server_renewal(ctx: commands.Context):
        guild = await require_admin(ctx)
        if guild is None:
            return
        embed = discord.Embed(
            title="🕯 ABADDON 서버 리뉴얼",
            description=(
                "현재 채널을 삭제하지 않고 카테고리·채널명·순서를 정돈합니다.\n"
                "사진처럼 길어진 메뉴를 7종 테마로 정리하고, 선택형 빈 카테고리 삭제와 복구 기록을 관리합니다."
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
        embed.add_field(name="안전 원칙", value="미인식 채널 유지 · 적용 전 자동 백업 · 생성 항목 추적 · 선택 삭제 지원", inline=False)
        await ctx.send(embed=embed)

    @server_renewal.command(name="테마목록", aliases=["themes", "테마"])
    async def server_renewal_themes(ctx: commands.Context):
        guild = await require_admin(ctx)
        if guild is None:
            return
        lines = [f"• **{name}** · {THEME_META[name]['label']}" for name in THEME_META]
        embed = discord.Embed(
            title="🎨 서버 리뉴얼 테마 7종",
            description="\n".join(lines),
            color=0x6D2335,
        )
        embed.add_field(name="미리보기", value="`!서버리뉴얼 미리보기 테마명`", inline=False)
        embed.add_field(name="게임·음성 구역", value="`!서버리뉴얼 게임미리보기 테마명`", inline=False)
        await ctx.send(embed=embed)

    @server_renewal.command(name="미리보기", aliases=["preview"])
    async def server_renewal_preview(ctx: commands.Context, style: str = "깔끔"):
        guild = await require_admin(ctx)
        if guild is None:
            return
        if style not in STYLE_NAMES:
            await ctx.send("❌ 지원 테마: `깔끔`, `고딕`, `커뮤니티`, `미니멀`, `사이버`, `아포칼립스`, `판타지`")
            return
        await ctx.send(embed=_layout_preview_embed(guild, style))

    @server_renewal.command(name="적용", aliases=["apply"])
    async def server_renewal_apply(ctx: commands.Context, style: str = "깔끔"):
        guild = await require_admin(ctx)
        if guild is None or not isinstance(ctx.author, discord.Member):
            return
        if style not in STYLE_NAMES:
            await ctx.send("❌ 지원 테마: `깔끔`, `고딕`, `커뮤니티`, `미니멀`, `사이버`, `아포칼립스`, `판타지`")
            return
        bot_member = guild.me
        if bot_member is None or not bot_member.guild_permissions.manage_channels:
            await ctx.send("❌ 봇에 `채널 관리` 권한이 필요합니다.")
            return

        settings = _layout_settings(world_data, guild.id)["layout"]
        backup = _store_backup(settings, _snapshot_guild(guild, operation="layout", style=style))
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
                    _record_created(backup, "category", category.id)
                    save_data()
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
                    created_channel = await guild.create_text_channel(spec["name"], **kwargs)
                    _record_created(backup, "channel", created_channel.id)
                    save_data()
                    await _renewal_pause()
                    created_channels += 1
                elif channel is not None:
                    await channel.edit(name=spec["name"], category=category, reason=reason)
                    await _renewal_pause()
                    changed_channels += 1

            for spec, channel in voice_matches:
                category = categories[spec["category"]]
                if channel is None and spec["key"] in ESSENTIAL_KEYS:
                    created_channel = await guild.create_voice_channel(spec["name"], category=category, reason=reason)
                    _record_created(backup, "channel", created_channel.id)
                    save_data()
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
            await ctx.send("❌ 지원 테마: `깔끔`, `고딕`, `커뮤니티`, `미니멀`, `사이버`, `아포칼립스`, `판타지`")
            return
        await ctx.send(embed=_game_zone_preview_embed(guild, style))

    @server_renewal.command(name="게임정리", aliases=["봇게임정리", "게임채널정리"])
    async def server_renewal_game_apply(ctx: commands.Context, style: str = "깔끔"):
        guild = await require_admin(ctx)
        if guild is None or not isinstance(ctx.author, discord.Member):
            return
        if style not in STYLE_NAMES:
            await ctx.send("❌ 지원 테마: `깔끔`, `고딕`, `커뮤니티`, `미니멀`, `사이버`, `아포칼립스`, `판타지`")
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
        backup = _store_backup(settings, _snapshot_guild(guild, operation="game_zone", style=style))
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
                reused_ids = backup.setdefault("reused_category_ids", [])
                if preferred.id not in reused_ids:
                    reused_ids.append(preferred.id)
                    save_data()
                return preferred
            created = await guild.create_category(target_name, reason=reason)
            _record_created(backup, "category", created.id)
            save_data()
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

    @server_renewal.command(name="백업목록", aliases=["backups", "복구목록"])
    async def server_renewal_backup_list(ctx: commands.Context):
        guild = await require_admin(ctx)
        if guild is None:
            return
        settings = _layout_settings(world_data, guild.id)["layout"]
        backups: List[Dict[str, Any]] = []
        current = settings.get("backup")
        if isinstance(current, dict):
            backups.append(current)
        history = settings.get("backup_history", [])
        if isinstance(history, list):
            backups.extend(reversed([item for item in history if isinstance(item, dict)]))
        unique: List[Dict[str, Any]] = []
        seen: set[int] = set()
        for item in backups:
            stamp = int(item.get("created_at", 0) or 0)
            if stamp in seen:
                continue
            seen.add(stamp)
            unique.append(item)
        if not unique:
            await ctx.send("⚠️ 저장된 서버 리뉴얼 백업이 없습니다.")
            return
        lines = []
        for index, item in enumerate(unique[:5], start=1):
            stamp = int(item.get("created_at", 0) or 0)
            dt = f"<t:{stamp}:F>" if stamp else "시간 미상"
            lines.append(
                f"**{index}.** {dt} · `{item.get('operation', 'legacy')}` · "
                f"테마 `{item.get('style') or '없음'}` · 채널 {len(item.get('channels', []))}개"
            )
        await ctx.send(
            "🗃️ **서버 리뉴얼 복구 지점**\n"
            + "\n".join(lines)
            + "\n\n복구: `!서버리뉴얼 되돌리기 번호` (기본 1번)"
        )

    @server_renewal.command(name="되돌리기", aliases=["undo", "복원"])
    async def server_renewal_undo(ctx: commands.Context, backup_number: int = 1):
        guild = await require_admin(ctx)
        if guild is None:
            return
        settings = _layout_settings(world_data, guild.id)["layout"]
        backups: List[Dict[str, Any]] = []
        current = settings.get("backup")
        if isinstance(current, dict):
            backups.append(current)
        history = settings.get("backup_history", [])
        if isinstance(history, list):
            backups.extend(reversed([item for item in history if isinstance(item, dict)]))
        unique: List[Dict[str, Any]] = []
        seen: set[int] = set()
        for item in backups:
            stamp = int(item.get("created_at", 0) or 0)
            if stamp in seen:
                continue
            seen.add(stamp)
            unique.append(item)
        if not unique:
            await ctx.send("⚠️ 되돌릴 서버 리뉴얼 백업이 없습니다.")
            return
        if backup_number < 1 or backup_number > len(unique):
            await ctx.send(f"❌ 백업 번호는 1부터 {len(unique)} 사이여야 합니다. `!서버리뉴얼 백업목록`을 확인하세요.")
            return
        backup = unique[backup_number - 1]
        progress = await ctx.send(f"↩️ **{backup_number}번 복구 지점으로 서버를 복구하는 중입니다...**")
        restored = 0
        deleted_created_channels = 0
        kept_created_channels = 0
        deleted_created_categories = 0
        legacy_cleaned = 0
        legacy_channels_cleaned = 0
        category_map = {category.id: category for category in guild.categories}
        channel_map = {channel.id: channel for channel in [*guild.text_channels, *guild.voice_channels]}
        reason = f"ABADDON v{VERSION} 서버 리뉴얼 되돌리기 / {ctx.author}"

        # 원래 존재하던 카테고리 이름과 위치를 먼저 복원합니다.
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

        # 원래 채널의 이름·카테고리·위치를 복원합니다.
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

        # v4.3.3.4 이후 생성된 채널은 ID로 추적합니다. 사용 흔적이 있으면 보존합니다.
        for channel_id in list(backup.get("created_channel_ids", [])):
            channel = guild.get_channel(int(channel_id))
            if channel is None:
                continue
            safe_to_delete = False
            if isinstance(channel, discord.VoiceChannel):
                safe_to_delete = not channel.members
            elif isinstance(channel, discord.TextChannel):
                try:
                    latest = [message async for message in channel.history(limit=1)]
                    safe_to_delete = not latest
                except (discord.Forbidden, discord.HTTPException):
                    safe_to_delete = False
            if safe_to_delete:
                try:
                    await channel.delete(reason=reason)
                    await _renewal_pause()
                    deleted_created_channels += 1
                except (discord.Forbidden, discord.HTTPException):
                    kept_created_channels += 1
            else:
                kept_created_channels += 1

        # 추적된 신규 카테고리는 비어 있을 때만 삭제합니다.
        for category_id in list(backup.get("created_category_ids", [])):
            category = guild.get_channel(int(category_id))
            if isinstance(category, discord.CategoryChannel) and not category.channels:
                try:
                    await category.delete(reason=reason)
                    await _renewal_pause()
                    deleted_created_categories += 1
                except (discord.Forbidden, discord.HTTPException):
                    pass

        # 구버전 백업에는 생성 ID가 없었습니다. 원본에 없던 알려진 테마 채널·카테고리만 보수적으로 정리합니다.
        if int(backup.get("snapshot_version", 1) or 1) < 2 or not backup.get("created_category_ids"):
            original_channel_ids = {int(row.get("id", 0)) for row in backup.get("channels", [])}
            original_category_ids = {int(row.get("id", 0)) for row in backup.get("categories", [])}
            known_channel_names = {_normalise_name(name) for name in _all_theme_channel_names()}
            known_category_names = {_normalise_name(name) for name in _all_theme_category_names()}
            tts_settings = _layout_settings(world_data, guild.id)["tts"]
            protected_ids = {
                int(value) for value in (
                    tts_settings.get("text_channel_id"),
                    tts_settings.get("voice_channel_id"),
                    settings.get("menu_channel_id"),
                ) if value
            }
            for channel in list([*guild.text_channels, *guild.voice_channels]):
                if channel.id in original_channel_ids or channel.id in protected_ids:
                    continue
                if _normalise_name(channel.name) not in known_channel_names:
                    continue
                safe_to_delete = False
                if isinstance(channel, discord.VoiceChannel):
                    safe_to_delete = not channel.members
                elif isinstance(channel, discord.TextChannel):
                    try:
                        latest = [message async for message in channel.history(limit=1)]
                        safe_to_delete = not latest
                    except (discord.Forbidden, discord.HTTPException):
                        safe_to_delete = False
                if not safe_to_delete:
                    continue
                try:
                    await channel.delete(reason=f"{reason} / 구버전 잔여 채널")
                    await _renewal_pause()
                    legacy_channels_cleaned += 1
                except (discord.Forbidden, discord.HTTPException):
                    pass
            for category in list(guild.categories):
                if category.id in original_category_ids or category.channels:
                    continue
                if _normalise_name(category.name) not in known_category_names:
                    continue
                try:
                    await category.delete(reason=f"{reason} / 구버전 잔여 카테고리")
                    await _renewal_pause()
                    legacy_cleaned += 1
                except (discord.Forbidden, discord.HTTPException):
                    pass

        settings["style"] = None
        settings["restored_at"] = int(time.time())
        settings["last_restore_report"] = {
            "restored": restored,
            "deleted_created_channels": deleted_created_channels,
            "kept_created_channels": kept_created_channels,
            "deleted_created_categories": deleted_created_categories,
            "legacy_cleaned": legacy_cleaned,
            "legacy_channels_cleaned": legacy_channels_cleaned,
        }
        save_data()
        await progress.edit(
            content=(
                f"✅ **서버 리뉴얼 복구 완료**\n"
                f"원래 이름·위치 복원: **{restored}개**\n"
                f"빈 신규 채널 삭제: **{deleted_created_channels}개**\n"
                f"사용 흔적으로 보존: **{kept_created_channels}개**\n"
                f"빈 신규 카테고리 삭제: **{deleted_created_categories}개**\n"
                f"구버전 잔여 채널 정리: **{legacy_channels_cleaned}개**\n"
                f"구버전 잔여 카테고리 정리: **{legacy_cleaned}개**\n\n"
                "보존된 항목은 `!서버리뉴얼 빈카테고리선택`에서 직접 고를 수 있습니다."
            )
        )

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
        empty = _empty_categories(guild)
        if not empty:
            await ctx.send("✅ 비어 있는 카테고리가 없습니다.")
            return
        lines = [f"**{index}.** `{category.name}` · ID `{category.id}`" for index, category in enumerate(empty[:40], start=1)]
        suffix = "" if len(empty) <= 40 else f"\n…외 {len(empty) - 40}개"
        await ctx.send(
            "🧹 **비어 있는 카테고리 목록**\n"
            + "\n".join(lines)
            + suffix
            + "\n\n드롭다운: `!서버리뉴얼 빈카테고리선택`"
            + "\n번호 삭제: `!서버리뉴얼 빈카테고리삭제 1,3,5 확인`"
            + "\n전체 삭제: `!서버리뉴얼 빈카테고리삭제 전체 확인`"
        )

    class EmptyCategorySelect(discord.ui.Select):
        def __init__(self, categories: Sequence[discord.CategoryChannel]):
            options = [
                discord.SelectOption(
                    label=category.name[:100],
                    value=str(category.id),
                    description=f"빈 카테고리 · 위치 {category.position}"[:100],
                    emoji="🗑️",
                )
                for category in categories[:25]
            ]
            super().__init__(
                placeholder="삭제할 빈 카테고리를 선택하세요",
                min_values=1,
                max_values=max(1, len(options)),
                options=options,
            )

        async def callback(self, interaction: discord.Interaction) -> None:
            view = self.view
            if not isinstance(view, EmptyCategoryDeleteView):
                await interaction.response.send_message("❌ 선택 메뉴 상태를 확인하지 못했습니다.", ephemeral=True)
                return
            view.selected_ids = {int(value) for value in self.values}
            names = []
            if interaction.guild is not None:
                for category_id in view.selected_ids:
                    category = interaction.guild.get_channel(category_id)
                    if isinstance(category, discord.CategoryChannel):
                        names.append(category.name)
            await interaction.response.send_message(
                "선택됨: " + ", ".join(f"`{name}`" for name in names[:15]) + "\n아래 **선택 삭제** 버튼을 누르세요.",
                ephemeral=True,
            )

    class EmptyCategoryDeleteView(discord.ui.View):
        def __init__(self, owner_id: int, categories: Sequence[discord.CategoryChannel]):
            super().__init__(timeout=180)
            self.owner_id = owner_id
            self.category_ids = {category.id for category in categories}
            self.selected_ids: set[int] = set()
            self.add_item(EmptyCategorySelect(categories))

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            if interaction.user.id != self.owner_id:
                await interaction.response.send_message("❌ 이 선택 메뉴를 연 관리자만 사용할 수 있습니다.", ephemeral=True)
                return False
            return True

        @discord.ui.button(label="선택 삭제", style=discord.ButtonStyle.danger, emoji="🗑️")
        async def delete_selected(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
            if interaction.guild is None:
                await interaction.response.send_message("❌ 서버에서만 사용할 수 있습니다.", ephemeral=True)
                return
            if not self.selected_ids:
                await interaction.response.send_message("⚠️ 먼저 카테고리를 선택하세요.", ephemeral=True)
                return
            deleted = 0
            skipped = 0
            for category_id in list(self.selected_ids):
                category = interaction.guild.get_channel(category_id)
                if not isinstance(category, discord.CategoryChannel) or category.channels:
                    skipped += 1
                    continue
                try:
                    await category.delete(reason=f"ABADDON v{VERSION} 선택형 빈 카테고리 삭제 / {interaction.user}")
                    await _renewal_pause()
                    deleted += 1
                except (discord.Forbidden, discord.HTTPException):
                    skipped += 1
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(
                content=f"✅ 선택한 빈 카테고리 **{deleted}개**를 삭제했습니다. 건너뜀: **{skipped}개**",
                view=self,
            )
            self.stop()

        @discord.ui.button(label="취소", style=discord.ButtonStyle.secondary, emoji="✖️")
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(content="취소했습니다.", view=self)
            self.stop()

    @server_renewal.command(name="빈카테고리선택", aliases=["emptyselect", "선택삭제"])
    async def server_renewal_empty_select(ctx: commands.Context):
        guild = await require_admin(ctx)
        if guild is None:
            return
        empty = _empty_categories(guild)
        if not empty:
            await ctx.send("✅ 선택할 빈 카테고리가 없습니다.")
            return
        view = EmptyCategoryDeleteView(ctx.author.id, empty[:25])
        note = "" if len(empty) <= 25 else f"\n⚠️ Discord 드롭다운 제한으로 앞쪽 25개만 표시합니다. 나머지는 번호 삭제를 사용하세요."
        await ctx.send("🗑️ **삭제할 빈 카테고리를 선택하세요.**" + note, view=view)

    @server_renewal.command(name="빈카테고리삭제", aliases=["cleanempty"])
    async def server_renewal_delete_empty(ctx: commands.Context, selection: str = "", confirm: str = ""):
        guild = await require_admin(ctx)
        if guild is None:
            return
        if confirm != "확인":
            await ctx.send(
                "⚠️ 사용법: `!서버리뉴얼 빈카테고리삭제 1,3 확인` 또는 "
                "`!서버리뉴얼 빈카테고리삭제 전체 확인`"
            )
            return
        empty = _empty_categories(guild)
        targets = _parse_category_selection(selection, empty)
        if not targets:
            await ctx.send("❌ 선택한 번호에 해당하는 빈 카테고리가 없습니다. `!서버리뉴얼 빈카테고리`로 번호를 확인하세요.")
            return
        settings = _layout_settings(world_data, guild.id)["layout"]
        if not settings.get("backup"):
            _store_backup(settings, _snapshot_guild(guild, operation="empty_category_delete"))
            save_data()
        deleted = 0
        skipped = 0
        reason = f"ABADDON v{VERSION} 선택형 빈 카테고리 정리 / {ctx.author}"
        for category in targets:
            if category.channels:
                skipped += 1
                continue
            try:
                await category.delete(reason=reason)
                await _renewal_pause()
                deleted += 1
            except (discord.Forbidden, discord.HTTPException):
                skipped += 1
        await ctx.send(f"✅ 선택한 빈 카테고리 **{deleted}개**를 삭제했습니다. 건너뜀: **{skipped}개**")

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
