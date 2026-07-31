from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

import discord
from discord.ext import commands


VERSION = "6.0.2"
MENU_TIMEOUT = 300
RULE_DATA_KEY = "channel_rules_v602"


@dataclass(frozen=True)
class RuleTemplate:
    key: str
    label: str
    emoji: str
    summary: str
    rules: Tuple[str, ...]
    usage: Tuple[str, ...]
    notes: Tuple[str, ...]
    keywords: Tuple[str, ...]


def _template(
    key: str,
    label: str,
    emoji: str,
    summary: str,
    rules: Sequence[str],
    usage: Sequence[str],
    notes: Sequence[str],
    keywords: Sequence[str],
) -> RuleTemplate:
    return RuleTemplate(
        key=key,
        label=label,
        emoji=emoji,
        summary=summary,
        rules=tuple(rules),
        usage=tuple(usage),
        notes=tuple(notes),
        keywords=tuple(keywords),
    )


RULE_TEMPLATES: Mapping[str, RuleTemplate] = {
    "server": _template(
        "server", "서버 기본 규칙", "📜",
        "모든 채널에 공통으로 적용되는 기본 질서입니다.",
        (
            "서로를 존중하고 욕설·비하·혐오·분쟁 유도 발언을 삼가 주세요.",
            "도배, 반복 멘션, 광고, 사기 링크, 악성 파일과 개인정보 유포는 금지됩니다.",
            "성적인 콘텐츠, 잔혹물, 불법 정보와 타인의 동의 없는 녹화·유포는 허용되지 않습니다.",
            "운영진 안내와 채널별 고정 규칙을 우선하며, 우회 행위도 동일하게 처리됩니다.",
            "문제가 생기면 공개 싸움 대신 문의·신고 채널을 이용해 주세요.",
        ),
        (
            "처음 입장했다면 공지·규칙·가입 안내를 먼저 확인합니다.",
            "채널 주제에 맞는 공간을 이용하고, 필요한 경우 운영진 안내에 따라 이동합니다.",
        ),
        (
            "규칙은 서버 상황에 따라 갱신될 수 있습니다.",
            "제재는 경고, 메시지 정리, 타임아웃, 추방 또는 차단 순서로 적용될 수 있습니다.",
        ),
        ("규칙", "기본", "서버", "안내"),
    ),
    "announcement": _template(
        "announcement", "공지사항", "📢",
        "서버의 중요 변경 사항과 운영 안내를 확인하는 채널입니다.",
        (
            "운영진 공지를 확인한 뒤 같은 질문을 반복하기 전에 관련 안내를 먼저 읽어 주세요.",
            "공지 메시지에 무관한 답글·도배·반복 반응을 남기지 않습니다.",
            "공지 내용을 임의로 편집해 전달하거나 운영진을 사칭하지 않습니다.",
            "긴급 점검·이벤트 종료·규칙 변경 시 공지에 표시된 시간이 기준입니다.",
        ),
        (
            "중요 공지는 고정 메시지와 최근 게시물을 함께 확인합니다.",
            "질문은 공지 채널이 아닌 문의 또는 일반 대화 채널을 이용합니다.",
        ),
        ("알림을 켜 두면 중요한 업데이트를 놓치지 않을 수 있습니다.",),
        ("공지", "업데이트", "소식", "알림"),
    ),
    "rules": _template(
        "rules", "규칙 전용", "⚖️",
        "서버와 각 채널의 이용 기준을 모아 두는 읽기 전용 안내 공간입니다.",
        (
            "서버 이용을 시작하기 전에 기본 규칙과 채널별 규칙을 확인해 주세요.",
            "규칙을 읽지 않았다는 사유는 위반 행위의 면책 사유가 되지 않습니다.",
            "규칙 해석이 애매하면 행동 전에 문의 채널에서 운영진에게 확인합니다.",
            "규칙 메시지에 불필요한 답글·반응·도배를 남기지 않습니다.",
        ),
        (
            "최근 수정 시간과 고정된 규칙 메시지를 기준으로 확인합니다.",
            "채널별 추가 규칙은 해당 채널의 고정 메시지가 우선 적용됩니다.",
        ),
        ("운영진은 변경 시 공지 채널을 통해 주요 내용을 안내합니다.",),
        ("규칙", "약관", "정책"),
    ),
    "welcome": _template(
        "welcome", "입장·퇴장 안내", "👋",
        "새로운 생존자의 입장과 서버 시작 방법을 안내하는 채널입니다.",
        (
            "신규 이용자를 환영하되 과도한 멘션·도배·개인정보 질문은 삼가 주세요.",
            "다른 이용자를 사칭하거나 허위 초대·가짜 운영진 안내를 작성하지 않습니다.",
            "입장·퇴장 자동 메시지를 이용한 조롱이나 분쟁 유도는 금지됩니다.",
        ),
        (
            "공지와 규칙을 읽은 뒤 가입 채널에서 `!가입 생존자`로 시작합니다.",
            "봇 기능은 `!게임`, 서버 설정은 운영진용 `!설정`에서 확인할 수 있습니다.",
        ),
        ("가입 오류는 문의 채널에 화면과 함께 남겨 주세요.",),
        ("입장", "퇴장", "환영", "welcome"),
    ),
    "registration": _template(
        "registration", "가입·역할", "🪪",
        "생존자 등록과 역할 선택을 진행하는 채널입니다.",
        (
            "한 사람의 다중 계정 악용, 보상 중복 수령과 타인 계정 사칭은 금지됩니다.",
            "역할 이름이나 가입 정보를 이용해 운영진·공식 계정을 사칭하지 않습니다.",
            "명령어를 짧은 시간에 반복 입력하지 말고 봇의 안내를 기다려 주세요.",
        ),
        (
            "기본 가입: `!가입 생존자`",
            "가입 후 `!게임` 또는 `!정보`에서 현재 상태를 확인합니다.",
        ),
        ("가입 데이터 오류가 보이면 재가입을 반복하지 말고 문의 채널에 알려 주세요.",),
        ("가입", "역할", "인증", "등록"),
    ),
    "bot_commands": _template(
        "bot_commands", "봇 명령어", "🤖",
        "아바돈과 기타 허용된 봇 명령어를 사용하는 채널입니다.",
        (
            "같은 명령어를 연속으로 도배하거나 쿨다운을 우회하지 않습니다.",
            "다른 이용자의 진행을 방해하는 멘션 명령, 사칭, 악의적인 입력을 금지합니다.",
            "오류를 발견해도 보상·재화 복제를 시도하지 말고 즉시 제보해 주세요.",
            "봇 토큰, 인증키, 개인정보와 위험한 링크를 명령어 입력값으로 보내지 않습니다.",
        ),
        (
            "통합 게임 메뉴: `!게임`",
            "통합 진단: `!아바돈진단` · 서버 설정: `!설정`",
            "명령 입력 후 결과가 나올 때까지 잠시 기다립니다.",
        ),
        ("봇 장애 시 같은 명령을 반복하기보다 Render 로그 또는 오류 화면을 운영진에게 전달해 주세요.",),
        ("봇", "명령", "command", "아바돈"),
    ),
    "chat": _template(
        "chat", "일반 대화", "💬",
        "자유롭게 대화하되 모두가 편하게 머물 수 있도록 배려하는 공간입니다.",
        (
            "욕설·비하·혐오·정치·종교 분쟁을 과도하게 끌고 가지 않습니다.",
            "도배, 의미 없는 반복 글, 과도한 대문자·이모지·멘션을 삼가 주세요.",
            "타인의 개인정보, DM 내용, 사진과 음성을 동의 없이 공개하지 않습니다.",
            "광고·홍보·초대 링크는 운영진 허가와 지정 채널 없이 게시하지 않습니다.",
        ),
        (
            "주제에 맞는 전용 채널이 있다면 해당 채널을 이용합니다.",
            "갈등이 커질 때는 대화를 멈추고 운영진 중재를 요청합니다.",
        ),
        ("가벼운 장난이라도 상대가 불편하다고 밝히면 즉시 중단해 주세요.",),
        ("대화", "잡담", "채팅", "수다", "일반"),
    ),
    "tts": _template(
        "tts", "TTS 채팅", "🎙️",
        "작성자가 들어가 있는 음성 채널에서 채팅 내용을 자동으로 읽어 주는 공간입니다.",
        (
            "큰 소리·욕설·음란 문장·반복 문자로 음성 채널을 방해하지 않습니다.",
            "다른 사람을 사칭하거나 개인정보·민감한 내용을 대신 읽게 하지 않습니다.",
            "긴 문장과 반복 메시지를 연속으로 보내 대기열을 독점하지 않습니다.",
            "봇이 다른 음성방에서 재생 중이라면 안내가 끝날 때까지 기다립니다.",
        ),
        (
            "먼저 원하는 음성 채널에 입장한 뒤 이 채널에 평범한 문장을 작성합니다.",
            "개인 목소리 선택: `/tts 목소리` · 상태 확인: `!TTS 상태`",
            "관리자 채널 지정: 이 채널에서 `!TTS채널`",
        ),
        ("아바돈은 작성자 닉네임을 읽지 않고 채팅 내용만 낭독합니다.",),
        ("아바돈tts", "tts", "티토커", "음성채팅", "읽어", "말해"),
    ),
    "rpg": _template(
        "rpg", "RPG·전투", "⚔️",
        "ABADDON RPG의 성장, 전투, 원정과 스토리를 진행하는 채널입니다.",
        (
            "버그·자동화·매크로·다중 계정을 이용한 재화와 보상 악용을 금지합니다.",
            "전투 결과나 선택을 이유로 다른 이용자를 비난하거나 강요하지 않습니다.",
            "명령 처리 중 반복 입력하지 말고 쿨다운과 안내 메시지를 지켜 주세요.",
            "오류로 비정상 보상을 받았으면 사용하지 말고 운영진에게 제보합니다.",
        ),
        (
            "처음 시작: `!가입 생존자`",
            "게임 제어실: `!게임` · 내 상태: `!정보`",
            "시즌 3: `!시즌3` · 원정: `!원정`",
        ),
        ("게임 데이터는 서버 운영 정책에 따라 밸런스 조정될 수 있습니다.",),
        ("rpg", "아포칼립스", "전투", "던전", "원정", "스토리", "성장"),
    ),
    "casino": _template(
        "casino", "카지노·도박", "🎰",
        "게임 안의 가상 재화로만 즐기는 확률형 콘텐츠 채널입니다.",
        (
            "현금·현물·외부 계정과 연결한 거래나 내기를 절대 진행하지 않습니다.",
            "패배를 이유로 타인을 비난하거나 추가 배팅을 강요하지 않습니다.",
            "오류·지연 중 명령을 반복해 중복 지급이나 복제를 시도하지 않습니다.",
            "과몰입이 느껴지면 즉시 이용을 멈추고 다른 콘텐츠를 이용해 주세요.",
        ),
        (
            "카지노 메뉴: `!게임` → 카지노·도박",
            "잔액과 기록을 먼저 확인한 뒤 감당 가능한 가상 재화만 사용합니다.",
        ),
        ("이 채널의 재화와 결과는 실제 금전적 가치가 없습니다.",),
        ("카지노", "도박", "블랙잭", "룰렛", "슬롯", "바카라"),
    ),
    "trade": _template(
        "trade", "거래·시장", "🛒",
        "게임 아이템과 가상 재화를 안전하게 교환하는 공간입니다.",
        (
            "현금 거래, 계정 거래, 외부 상품권 거래와 사기성 제안은 금지됩니다.",
            "거래 전 아이템명·수량·가격·상대방을 다시 확인해 주세요.",
            "허위 시세 조작, 반복 끌어올리기, 거래 완료 글 도배를 삼가 주세요.",
            "운영진 사칭, 가짜 중개, 외부 링크 결제 유도에 응하지 않습니다.",
        ),
        (
            "가능하면 봇의 공식 거래·시장 기능을 사용해 기록을 남깁니다.",
            "분쟁 시 메시지 링크와 거래 시각 등 확인 가능한 자료를 제출합니다.",
        ),
        ("개인 간 합의만으로 진행한 비공식 거래는 복구가 제한될 수 있습니다.",),
        ("거래", "시장", "상점", "판매", "구매", "교환"),
    ),
    "quiz": _template(
        "quiz", "퀴즈", "🧠",
        "오늘의 퀴즈와 이벤트 문제를 공정하게 즐기는 채널입니다.",
        (
            "정답을 반복 도배하거나 다른 이용자에게 답을 강요하지 않습니다.",
            "진행 중인 문제의 정답을 다른 채널·DM·외부 도구로 공유하지 않습니다.",
            "봇 지연 중 답안을 연속 입력하거나 결과 메시지를 조작하려 하지 않습니다.",
            "문제 오류는 공개 논쟁보다 화면과 함께 운영진에게 제보해 주세요.",
        ),
        (
            "문제를 끝까지 읽고 지정된 형식으로 한 번 제출합니다.",
            "일일 퀴즈 상태와 보상은 봇 안내를 기준으로 확인합니다.",
        ),
        ("이벤트별 추가 규칙이 있다면 해당 공지가 우선합니다.",),
        ("퀴즈", "문제", "정답", "quiz"),
    ),
    "media": _template(
        "media", "음악·미디어", "🎵",
        "음악, 영상, 이미지와 창작물을 공유하는 채널입니다.",
        (
            "불법 공유물, 악성 링크, 충격적·성적 콘텐츠와 개인정보가 포함된 자료는 금지됩니다.",
            "타인의 창작물을 자신의 것처럼 올리지 말고 가능한 범위에서 출처를 표시합니다.",
            "같은 영상·링크·홍보물을 반복 게시하지 않습니다.",
            "자동 재생·큰 음량·깜빡임 등 이용자에게 불편을 줄 수 있는 자료는 미리 알립니다.",
        ),
        (
            "영상과 링크에는 짧은 설명을 함께 작성합니다.",
            "노래 요청과 미디어 봇 명령은 지정된 채널에서만 사용합니다.",
        ),
        ("저작권자의 요청이나 운영 정책에 따라 게시물이 정리될 수 있습니다.",),
        ("음악", "노래", "미디어", "영상", "틱톡", "사진"),
    ),
    "voice": _template(
        "voice", "음성 채널", "🔊",
        "음성 대화와 TTS를 편안하게 이용하기 위한 기본 예절입니다.",
        (
            "고성, 마이크 테러, 음향판 도배와 의도적인 잡음 송출을 금지합니다.",
            "상대 동의 없는 녹음·방송·음성 공유는 허용되지 않습니다.",
            "잠수 인원을 끌어내리거나 반복 이동시켜 방해하지 않습니다.",
            "욕설·괴롭힘·성희롱이 이어질 경우 즉시 운영진에게 신고해 주세요.",
        ),
        (
            "장시간 자리를 비울 때는 잠수 채널을 이용하거나 음성방에서 나갑니다.",
            "TTS는 지정된 채팅 채널과 `/tts 목소리` 설정을 이용합니다.",
        ),
        ("음성방별 인원 제한과 추가 안내가 있다면 해당 설정을 우선합니다.",),
        ("음성", "보이스", "voice", "라운지", "말해라"),
    ),
    "support": _template(
        "support", "문의·신고·건의", "🛟",
        "문의, 신고, 버그 제보와 건의를 운영진에게 전달하는 채널입니다.",
        (
            "한 접수에는 한 가지 주제를 작성하고 같은 내용을 반복 제출하지 않습니다.",
            "허위 신고, 보복성 신고, 증거 조작과 공개 저격은 금지됩니다.",
            "토큰·비밀번호·실명·전화번호 등 민감한 개인정보를 게시하지 않습니다.",
            "처리 중인 문의를 재촉하거나 담당 운영진에게 반복 멘션하지 않습니다.",
        ),
        (
            "발생 시각, 관련 채널, 상황 설명과 필요한 화면을 함께 제출합니다.",
            "긴급 보안 문제는 공개 채널 대신 비공개 접수 기능을 이용합니다.",
        ),
        ("처리 결과는 증거와 서버 규칙을 기준으로 판단됩니다.",),
        ("문의", "신고", "건의", "티켓", "지원", "버그"),
    ),
    "test": _template(
        "test", "테스트", "🧪",
        "새 기능과 명령어를 안전하게 시험하는 운영·개발용 공간입니다.",
        (
            "대량 채널 생성·이동·삭제, 역할 변경과 전체 멘션은 사전 확인 없이 실행하지 않습니다.",
            "서버 리뉴얼 기능은 반드시 백업과 계획 미리보기를 확인한 뒤 단계적으로 진행합니다.",
            "실제 이용자 데이터와 운영 비밀키를 테스트 메시지에 노출하지 않습니다.",
            "429 또는 권한 오류가 보이면 즉시 추가 명령을 멈추고 로그를 확인합니다.",
        ),
        (
            "진단: `!아바돈진단` · 서버 리뉴얼: `!서버리뉴얼`",
            "테스트가 끝나면 생성한 메시지와 임시 설정을 정리합니다.",
        ),
        ("실제 서버 구조 변경은 운영진 한 명이 책임지고 순서대로 진행해 주세요.",),
        ("테스트", "개발", "실험", "debug"),
    ),
    "notification": _template(
        "notification", "알림·기록", "🔔",
        "레벨, 보상, 이벤트와 봇 상태 기록을 확인하는 알림 전용 채널입니다.",
        (
            "자동 알림 사이에 일반 대화·도배·명령어를 작성하지 않습니다.",
            "알림 메시지를 이용해 다른 이용자를 조롱하거나 반복 멘션하지 않습니다.",
            "오래된 알림을 임의로 삭제하거나 내용을 편집해 전달하지 않습니다.",
        ),
        (
            "문제가 있는 알림은 메시지 링크와 함께 문의 채널에 제보합니다.",
            "알림 빈도가 불편하면 개인 알림 설정을 조정합니다.",
        ),
        ("이 채널은 기록 보존을 위해 읽기 전용으로 운영될 수 있습니다.",),
        ("알림", "레벨", "기록", "로그", "notify"),
    ),
    "operations": _template(
        "operations", "운영·보안 로그", "🛡️",
        "운영진이 서버 상태와 보안 사건을 확인하는 제한 채널입니다.",
        (
            "로그에 포함된 사용자 정보와 신고 내용을 외부에 공유하지 않습니다.",
            "로그 메시지를 임의로 삭제·편집하거나 사건 기록을 왜곡하지 않습니다.",
            "확인되지 않은 로그만으로 공개 제재나 비난을 진행하지 않습니다.",
            "토큰·웹훅·비밀키가 노출되면 즉시 폐기하고 새 값으로 교체합니다.",
        ),
        (
            "사건 처리 시 관련 메시지 링크, 시각, 담당자와 조치 결과를 남깁니다.",
            "통합 진단은 `!아바돈진단`, 설정은 `!설정`에서 확인합니다.",
        ),
        ("민감한 운영 정보가 포함되므로 채널 접근 권한을 정기적으로 확인해 주세요.",),
        ("운영", "보안", "관리", "로그", "mod"),
    ),
}


def _normalise_channel_name(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", str(value or "").casefold())


def detect_template(channel: discord.abc.GuildChannel) -> RuleTemplate:
    haystack = _normalise_channel_name(getattr(channel, "name", ""))
    topic = _normalise_channel_name(getattr(channel, "topic", "") or "")
    combined = f"{haystack}{topic}"
    best: Optional[RuleTemplate] = None
    best_score = 0
    for template in RULE_TEMPLATES.values():
        score = sum(1 for keyword in template.keywords if _normalise_channel_name(keyword) in combined)
        if score > best_score:
            best = template
            best_score = score
    return best or RULE_TEMPLATES["chat"]


def _manager(member: discord.Member) -> bool:
    perms = member.guild_permissions
    return bool(
        member.id == member.guild.owner_id
        or perms.administrator
        or perms.manage_guild
        or perms.manage_channels
    )


def _rule_root(world_data: Dict[str, Any], guild_id: int) -> Dict[str, Any]:
    root = world_data.setdefault(RULE_DATA_KEY, {})
    if not isinstance(root, dict):
        root = {}
        world_data[RULE_DATA_KEY] = root
    guild_root = root.setdefault(str(guild_id), {})
    if not isinstance(guild_root, dict):
        guild_root = {}
        root[str(guild_id)] = guild_root
    channels = guild_root.setdefault("channels", {})
    if not isinstance(channels, dict):
        channels = {}
        guild_root["channels"] = channels
    guild_root.setdefault("last_updated_at", 0)
    return guild_root


def _record(world_data: Dict[str, Any], guild_id: int, channel_id: int) -> Dict[str, Any]:
    root = _rule_root(world_data, guild_id)
    channels = root["channels"]
    item = channels.setdefault(str(channel_id), {})
    if not isinstance(item, dict):
        item = {}
        channels[str(channel_id)] = item
    return item


def _numbered(items: Iterable[str]) -> str:
    return "\n".join(f"**{index}.** {text}" for index, text in enumerate(items, 1))


def build_rule_embed(guild: discord.Guild, channel: discord.abc.GuildChannel, template: RuleTemplate) -> discord.Embed:
    embed = discord.Embed(
        title=f"{template.emoji} #{getattr(channel, 'name', 'channel')} 이용 규칙",
        description=(
            f"**{guild.name}**의 {getattr(channel, 'mention', '#채널')} 이용 안내입니다.\n"
            f"{template.summary}"
        ),
        color=discord.Color.dark_red(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="지켜야 할 규칙", value=_numbered(template.rules), inline=False)
    embed.add_field(name="이용 방법", value="\n".join(f"• {item}" for item in template.usage), inline=False)
    embed.add_field(name="운영 안내", value="\n".join(f"• {item}" for item in template.notes), inline=False)
    embed.set_footer(text=f"ABADDON 자동 채널 규칙 · {template.label} · v{VERSION}")
    return embed


def build_preview_embed(guild: discord.Guild, channel: discord.abc.GuildChannel, template: RuleTemplate) -> discord.Embed:
    embed = build_rule_embed(guild, channel, template)
    embed.title = f"미리보기 · {embed.title}"
    embed.description = f"아래 내용을 {getattr(channel, 'mention', '#채널')}에 작성하고 고정할 예정입니다.\n\n{embed.description}"
    return embed


def _permission_report(channel: discord.abc.GuildChannel) -> Tuple[bool, Tuple[str, ...]]:
    guild = channel.guild
    me = guild.me
    if me is None:
        return False, ("봇 멤버 정보를 확인할 수 없음",)
    perms = channel.permissions_for(me)
    missing = []
    for label, enabled in (
        ("채널 보기", perms.view_channel),
        ("메시지 보내기", perms.send_messages),
        ("링크 임베드", perms.embed_links),
        ("메시지 기록 보기", perms.read_message_history),
        ("메시지 관리·고정", perms.manage_messages),
    ):
        if not enabled:
            missing.append(label)
    return not missing, tuple(missing)


def _supported_channel(channel: Any) -> bool:
    return isinstance(channel, (discord.TextChannel, discord.Thread))


async def _fetch_managed_message(
    bot: commands.Bot,
    channel: discord.abc.Messageable,
    message_id: Any,
) -> Optional[discord.Message]:
    try:
        mid = int(message_id)
    except (TypeError, ValueError):
        return None
    if mid <= 0 or not hasattr(channel, "fetch_message"):
        return None
    try:
        message = await channel.fetch_message(mid)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return None
    if bot.user is None or message.author.id != bot.user.id:
        return None
    return message


async def publish_rule(
    bot: commands.Bot,
    world_data: Dict[str, Any],
    save_data: Any,
    channel: discord.abc.GuildChannel,
    template: RuleTemplate,
    actor: discord.Member,
) -> Tuple[Optional[discord.Message], str]:
    if not _supported_channel(channel):
        return None, "텍스트 채널 또는 스레드에서만 사용할 수 있습니다."
    permitted, missing = _permission_report(channel)
    if not permitted:
        return None, "아바돈에게 필요한 권한이 부족합니다: " + ", ".join(missing)

    record = _record(world_data, channel.guild.id, channel.id)
    message = await _fetch_managed_message(bot, channel, record.get("message_id"))
    embed = build_rule_embed(channel.guild, channel, template)
    created = False

    try:
        if message is None:
            message = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            created = True
        else:
            await message.edit(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        pinned = bool(message.pinned)
        if not pinned:
            await message.pin(reason=f"ABADDON 채널 규칙 고정 · {actor} ({actor.id})")
            pinned = True
    except discord.Forbidden:
        return None, "메시지 작성 또는 고정 권한이 거부되었습니다. 채널 권한에서 메시지 관리 권한을 확인해 주세요."
    except discord.HTTPException as exc:
        return None, f"Discord API 요청에 실패했습니다: {type(exc).__name__}"

    now = int(time.time())
    record.update(
        {
            "template": template.key,
            "message_id": message.id,
            "updated_at": now,
            "updated_by": actor.id,
            "pinned": pinned,
            "channel_name": getattr(channel, "name", ""),
        }
    )
    _rule_root(world_data, channel.guild.id)["last_updated_at"] = now
    save_data()
    action = "새 규칙을 작성하고 고정했습니다." if created else "기존 규칙을 최신 내용으로 갱신했습니다."
    return message, action


async def remove_rule(
    bot: commands.Bot,
    world_data: Dict[str, Any],
    save_data: Any,
    channel: discord.abc.GuildChannel,
) -> str:
    root = _rule_root(world_data, channel.guild.id)
    record = root["channels"].get(str(channel.id))
    if not isinstance(record, dict):
        return "이 채널에 아바돈이 관리하는 규칙 기록이 없습니다."
    message = await _fetch_managed_message(bot, channel, record.get("message_id"))
    if message is not None:
        try:
            await message.delete(reason="ABADDON 채널 규칙 제거")
        except discord.Forbidden:
            return "규칙 메시지를 삭제할 권한이 없습니다."
        except discord.HTTPException:
            return "Discord API 오류로 규칙 메시지를 삭제하지 못했습니다."
    root["channels"].pop(str(channel.id), None)
    root["last_updated_at"] = int(time.time())
    save_data()
    return "이 채널의 자동 규칙 메시지와 관리 기록을 제거했습니다."


def register_v602_channel_rules(
    bot: commands.Bot,
    world_data: Dict[str, Any],
    save_data: Any,
) -> None:
    async def require_manager(ctx: commands.Context) -> bool:
        if ctx.guild is None or not isinstance(ctx.author, discord.Member):
            await ctx.send("서버 채널에서만 사용할 수 있습니다.")
            return False
        if not _manager(ctx.author):
            await ctx.send("서버 관리자 또는 채널 관리 권한이 필요합니다.")
            return False
        if not _supported_channel(ctx.channel):
            await ctx.send("텍스트 채널 또는 스레드에서만 사용할 수 있습니다.")
            return False
        return True

    class ManagerView(discord.ui.View):
        def __init__(self) -> None:
            super().__init__(timeout=MENU_TIMEOUT)

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            member = interaction.user if isinstance(interaction.user, discord.Member) else None
            if member is None or not _manager(member):
                await interaction.response.send_message("서버 관리자 또는 채널 관리 권한이 필요합니다.", ephemeral=True)
                return False
            return True

    class TemplateSelect(discord.ui.Select):
        def __init__(self, target_channel: discord.abc.GuildChannel) -> None:
            self.target_channel = target_channel
            options = [
                discord.SelectOption(
                    label=template.label,
                    value=template.key,
                    description=template.summary[:100],
                    emoji=template.emoji,
                    default=False,
                )
                for template in RULE_TEMPLATES.values()
            ]
            super().__init__(
                placeholder="이 채널에 맞는 규칙 종류를 선택하세요",
                min_values=1,
                max_values=1,
                options=options,
            )

        async def callback(self, interaction: discord.Interaction) -> None:
            template = RULE_TEMPLATES.get(self.values[0], RULE_TEMPLATES["chat"])
            await interaction.response.edit_message(
                embed=build_preview_embed(self.target_channel.guild, self.target_channel, template),
                view=RulePreviewView(self.target_channel, template),
            )

    class RuleControlView(ManagerView):
        def __init__(self, target_channel: discord.abc.GuildChannel) -> None:
            super().__init__()
            self.target_channel = target_channel
            self.add_item(TemplateSelect(target_channel))

        @discord.ui.button(label="자동 추천 미리보기", emoji="🪄", style=discord.ButtonStyle.primary)
        async def auto_preview(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
            template = detect_template(self.target_channel)
            await interaction.response.edit_message(
                embed=build_preview_embed(self.target_channel.guild, self.target_channel, template),
                view=RulePreviewView(self.target_channel, template),
            )

        @discord.ui.button(label="현재 상태", emoji="🔎", style=discord.ButtonStyle.secondary)
        async def status(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
            record = _rule_root(world_data, self.target_channel.guild.id)["channels"].get(str(self.target_channel.id), {})
            if isinstance(record, dict) and record.get("message_id"):
                template = RULE_TEMPLATES.get(str(record.get("template")), RULE_TEMPLATES["chat"])
                text = (
                    f"템플릿: **{template.label}**\n"
                    f"메시지 ID: `{record.get('message_id')}`\n"
                    f"최근 갱신: <t:{int(record.get('updated_at', 0) or 0)}:R>"
                )
            else:
                text = "이 채널에 아바돈이 관리하는 규칙이 아직 없습니다."
            await interaction.response.send_message(text, ephemeral=True)

        @discord.ui.button(label="닫기", emoji="✖️", style=discord.ButtonStyle.secondary)
        async def close(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
            await interaction.response.edit_message(content="채널 규칙 제어실을 닫았습니다.", embed=None, view=None)

    class RulePreviewView(ManagerView):
        def __init__(self, target_channel: discord.abc.GuildChannel, template: RuleTemplate) -> None:
            super().__init__()
            self.target_channel = target_channel
            self.template = template

        @discord.ui.button(label="이 채널에 작성·고정", emoji="📌", style=discord.ButtonStyle.success)
        async def publish(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
            member = interaction.user if isinstance(interaction.user, discord.Member) else None
            if member is None:
                await interaction.response.send_message("관리자 정보를 확인할 수 없습니다.", ephemeral=True)
                return
            await interaction.response.defer()
            message, result = await publish_rule(bot, world_data, save_data, self.target_channel, self.template, member)
            if message is None:
                await interaction.followup.send(f"❌ {result}", ephemeral=True)
                return
            done = discord.Embed(
                title="📌 채널 규칙 적용 완료",
                description=(
                    f"{self.target_channel.mention}에 **{self.template.label}** 규칙을 적용했습니다.\n"
                    f"{result}\n\n[고정된 규칙 메시지로 이동]({message.jump_url})"
                ),
                color=discord.Color.dark_teal(),
            )
            await interaction.message.edit(embed=done, view=RuleControlView(self.target_channel))
            await interaction.followup.send("규칙 작성과 고정이 완료되었습니다.", ephemeral=True)

        @discord.ui.button(label="다른 규칙 선택", emoji="↩️", style=discord.ButtonStyle.secondary)
        async def back(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
            detected = detect_template(self.target_channel)
            embed = discord.Embed(
                title="📜 ABADDON 채널 규칙 제어실",
                description=(
                    f"대상 채널: {self.target_channel.mention}\n"
                    f"자동 추천: **{detected.emoji} {detected.label}**\n\n"
                    "규칙 종류를 선택하면 실제 고정 전에 전체 내용을 미리 볼 수 있습니다."
                ),
                color=discord.Color.dark_red(),
            )
            await interaction.response.edit_message(embed=embed, view=RuleControlView(self.target_channel))

        @discord.ui.button(label="취소", emoji="✖️", style=discord.ButtonStyle.secondary)
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
            await interaction.response.edit_message(content="채널 규칙 적용을 취소했습니다.", embed=None, view=None)

    @bot.group(
        name="채널규칙",
        aliases=["규칙작성", "규칙고정", "채널안내"],
        invoke_without_command=True,
    )
    async def channel_rules(ctx: commands.Context) -> None:
        """현재 채널에 규칙 안내를 작성하고 고정하는 제어실."""
        if not await require_manager(ctx):
            return
        detected = detect_template(ctx.channel)
        embed = discord.Embed(
            title="📜 ABADDON 채널 규칙 제어실",
            description=(
                f"대상 채널: {ctx.channel.mention}\n"
                f"자동 추천: **{detected.emoji} {detected.label}**\n\n"
                "규칙 종류를 선택하면 아바돈이 작성한 전체 내용을 먼저 보여 줍니다. "
                "확인 후 **이 채널에 작성·고정** 버튼을 누르면 기존 관리 메시지는 중복 생성하지 않고 갱신합니다."
            ),
            color=discord.Color.dark_red(),
        )
        embed.add_field(
            name="빠른 명령",
            value=(
                "`!채널규칙 자동` — 채널 이름을 보고 즉시 작성·고정\n"
                "`!채널규칙 상태` — 현재 관리 규칙 확인\n"
                "`!채널규칙 갱신` — 기존 템플릿 최신화\n"
                "`!채널규칙 제거 확인` — 자동 규칙 메시지 삭제"
            ),
            inline=False,
        )
        await ctx.send(embed=embed, view=RuleControlView(ctx.channel))

    @channel_rules.command(name="자동")
    async def channel_rules_auto(ctx: commands.Context) -> None:
        """채널 이름을 기준으로 규칙을 자동 선택해 바로 게시·고정."""
        if not await require_manager(ctx):
            return
        template = detect_template(ctx.channel)
        message, result = await publish_rule(bot, world_data, save_data, ctx.channel, template, ctx.author)
        if message is None:
            await ctx.send(f"❌ {result}")
            return
        await ctx.send(f"✅ **{template.label}** 규칙을 적용했습니다. {result}\n{message.jump_url}")

    @channel_rules.command(name="목록")
    async def channel_rules_list(ctx: commands.Context) -> None:
        if not await require_manager(ctx):
            return
        lines = [f"{template.emoji} `{template.key}` — **{template.label}**" for template in RULE_TEMPLATES.values()]
        embed = discord.Embed(
            title=f"📚 채널 규칙 템플릿 {len(lines)}종",
            description="\n".join(lines),
            color=discord.Color.dark_teal(),
        )
        embed.set_footer(text="직접 적용: !채널규칙 자동 또는 !채널규칙 제어실 드롭다운")
        await ctx.send(embed=embed)

    @channel_rules.command(name="상태")
    async def channel_rules_status(ctx: commands.Context) -> None:
        if not await require_manager(ctx):
            return
        record = _rule_root(world_data, ctx.guild.id)["channels"].get(str(ctx.channel.id), {})
        if not isinstance(record, dict) or not record.get("message_id"):
            suggested = detect_template(ctx.channel)
            await ctx.send(f"이 채널에 관리 중인 규칙이 없습니다. 자동 추천은 **{suggested.label}**입니다.")
            return
        template = RULE_TEMPLATES.get(str(record.get("template")), RULE_TEMPLATES["chat"])
        message = await _fetch_managed_message(bot, ctx.channel, record.get("message_id"))
        state = "정상" if message is not None else "메시지를 찾을 수 없음"
        await ctx.send(
            f"📌 템플릿: **{template.label}**\n"
            f"상태: **{state}**\n"
            f"메시지 ID: `{record.get('message_id')}`\n"
            f"최근 갱신: <t:{int(record.get('updated_at', 0) or 0)}:R>"
        )

    @channel_rules.command(name="갱신")
    async def channel_rules_refresh(ctx: commands.Context) -> None:
        if not await require_manager(ctx):
            return
        record = _rule_root(world_data, ctx.guild.id)["channels"].get(str(ctx.channel.id), {})
        if not isinstance(record, dict) or not record.get("template"):
            await ctx.send("먼저 `!채널규칙` 또는 `!채널규칙 자동`으로 규칙을 설치해 주세요.")
            return
        template = RULE_TEMPLATES.get(str(record.get("template")), detect_template(ctx.channel))
        message, result = await publish_rule(bot, world_data, save_data, ctx.channel, template, ctx.author)
        if message is None:
            await ctx.send(f"❌ {result}")
            return
        await ctx.send(f"✅ **{template.label}** 규칙을 최신 문구로 갱신했습니다.\n{message.jump_url}")

    @channel_rules.command(name="제거")
    async def channel_rules_remove(ctx: commands.Context, confirm: str = "") -> None:
        if not await require_manager(ctx):
            return
        if confirm.strip() != "확인":
            await ctx.send("정말 제거하려면 `!채널규칙 제거 확인`을 입력해 주세요.")
            return
        result = await remove_rule(bot, world_data, save_data, ctx.channel)
        await ctx.send(f"🗑️ {result}")
