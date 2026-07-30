from __future__ import annotations

from typing import Dict, Tuple

from discord import app_commands
from discord.ext import commands


GROUP_DESCRIPTIONS: Dict[str, str] = {
    "직업": "직업 목록, 선택, 정보, 변경 기능을 사용합니다.",
    "의료": "상태 확인, 휴식, 의약품 구매와 치료 기능을 사용합니다.",
    "지역": "지역 목록, 정보, 이동, 탐색과 좀비 도감을 확인합니다.",
    "퀴즈": "오늘의 퀴즈, 정답, 랭킹과 알림 설정을 관리합니다.",
    "강화기능": "보호 강화, 옵션, 세트 효과와 강화 랭킹을 확인합니다.",
    "심층": "심층 던전, 기록, 보스 도감과 종합 랭킹을 확인합니다.",
    "경매": "경매 등록, 입찰, 검색, 마감과 거래 기록을 관리합니다.",
    "침공": "서버 침공 참가, 공격, 랭킹, 상점과 관리자 기능을 사용합니다.",
    "관리": "아바돈 관리자 전용 유저 및 아이템 관리 기능입니다.",
    "서버": "서버별 채널과 기능 설정을 관리합니다.",
    "튜토리얼": "초보자 튜토리얼 상태를 확인하거나 건너뜁니다.",
}


# 기존 !명령어 이름 -> (슬래시 최상위 그룹, 슬래시 하위 명령어)
# prefix 명령어는 그대로 유지되며, slash 쪽만 보기 좋게 묶습니다.
SLASH_ROUTES: Dict[str, Tuple[str, str]] = {
    # 직업
    "직업목록": ("직업", "목록"),
    "직업선택": ("직업", "선택"),
    "직업정보": ("직업", "정보"),
    "직업변경": ("직업", "변경"),

    # 의료 / 상태
    "의약품": ("의료", "의약품"),
    "약품구매": ("의료", "구매"),
    "사용": ("의료", "사용"),
    "병원": ("의료", "병원"),
    "상태": ("의료", "상태"),
    "휴식": ("의료", "휴식"),

    # 지역
    "지역목록": ("지역", "목록"),
    "지역정보": ("지역", "정보"),
    "지역이동": ("지역", "이동"),
    "좀비도감": ("지역", "좀비도감"),
    "지역탐색": ("지역", "탐색"),

    # 퀴즈
    "오늘의퀴즈": ("퀴즈", "오늘"),
    "정답": ("퀴즈", "정답"),
    "퀴즈랭킹": ("퀴즈", "랭킹"),
    "퀴즈추가": ("퀴즈", "추가"),
    "퀴즈삭제": ("퀴즈", "삭제"),
    "퀴즈목록": ("퀴즈", "목록"),
    "퀴즈알림설정": ("퀴즈", "알림설정"),
    "퀴즈알림해제": ("퀴즈", "알림해제"),
    "퀴즈알림상태": ("퀴즈", "알림상태"),

    # 강화 확장
    "강화정보": ("강화기능", "정보"),
    "보호강화": ("강화기능", "보호강화"),
    "강화랭킹": ("강화기능", "랭킹"),
    "장비옵션": ("강화기능", "장비옵션"),
    "옵션재설정": ("강화기능", "옵션재설정"),
    "세트효과": ("강화기능", "세트효과"),

    # 심층 콘텐츠
    "심층던전": ("심층", "던전"),
    "던전기록": ("심층", "던전기록"),
    "보스도감": ("심층", "보스도감"),
    "생활숙련도": ("심층", "생활숙련도"),
    "종합랭킹": ("심층", "종합랭킹"),

    # 경매
    "거래검색": ("경매", "검색"),
    "경매등록": ("경매", "등록"),
    "입찰": ("경매", "입찰"),
    "경매마감": ("경매", "마감"),
    "거래기록": ("경매", "기록"),

    # 서버 침공
    "침공": ("침공", "현황"),
    "참전": ("침공", "참전"),
    "침공공격": ("침공", "공격"),
    "침공랭킹": ("침공", "랭킹"),
    "침공기록": ("침공", "기록"),
    "침공상점": ("침공", "상점"),
    "침공시작": ("침공", "시작"),
    "침공종료": ("침공", "종료"),
    "침공토큰지급": ("침공", "토큰지급"),

    # 관리자
    "관리자명령어": ("관리", "도움말"),
    "아이템목록": ("관리", "아이템목록"),
    "아이템검색": ("관리", "아이템검색"),
    "아이템지급": ("관리", "아이템지급"),
    "아이템회수": ("관리", "아이템회수"),
    "경험치지급": ("관리", "경험치지급"),
    "레벨설정": ("관리", "레벨설정"),
    "직업설정": ("관리", "직업설정"),
    "펫설정": ("관리", "펫설정"),
    "칭호지급": ("관리", "칭호지급"),
    "체력설정": ("관리", "체력설정"),
    "스태미나설정": ("관리", "스태미나설정"),
    "감염도설정": ("관리", "감염도설정"),
    "상태이상제거": ("관리", "상태이상제거"),
    "관리자지역이동": ("관리", "지역이동"),
    "유저정보": ("관리", "유저정보"),

    # 서버 설정
    "서버설정": ("서버", "설정"),
    "서버채널": ("서버", "채널"),
    "서버기능": ("서버", "기능"),

    # 튜토리얼
    "튜토리얼": ("튜토리얼", "상태"),
    "튜토리얼건너뛰기": ("튜토리얼", "건너뛰기"),
}


# 기존 하이브리드 그룹에 하위 명령어로 붙일 항목
EXISTING_GROUP_ROUTES: Dict[str, Tuple[str, str]] = {
    "도감보상": ("도감", "보상"),
}


def _make_slash_bridge(
    prefix_command: commands.Command,
    slash_name: str,
) -> commands.HybridCommand:
    """기존 prefix callback을 그대로 사용하는 slash 전용 bridge를 만듭니다."""
    description = prefix_command.short_doc or prefix_command.description
    if not description:
        description = f"{prefix_command.name} 기능을 실행합니다."

    # wrapper의 명령어 이름은 기존 이름으로 유지합니다.
    # 따라서 튜토리얼 진행도, cooldown reset 등 ctx.command 기반 로직이 깨지지 않습니다.
    bridge = commands.HybridCommand(
        prefix_command.callback,
        name=prefix_command.name,
        description=description[:100],
        enabled=prefix_command.enabled,
        hidden=prefix_command.hidden,
        cooldown_after_parsing=prefix_command.cooldown_after_parsing,
    )
    if bridge.app_command is None:
        raise RuntimeError(f"슬래시 명령어 생성 실패: {prefix_command.name}")

    # Discord에 보이는 하위 명령어 이름만 짧고 자연스럽게 바꿉니다.
    bridge.app_command.name = slash_name
    bridge.app_command.description = description[:100]
    return bridge


def register_grouped_slash_commands(bot: commands.Bot) -> None:
    """100개 제한을 넘지 않도록 확장 명령어를 slash 그룹으로 묶어 등록합니다."""
    if getattr(bot, "_abaddon_slash_groups_registered", False):
        return

    groups = {
        name: app_commands.Group(name=name, description=description)
        for name, description in GROUP_DESCRIPTIONS.items()
    }

    missing = []

    for prefix_name, (group_name, slash_name) in SLASH_ROUTES.items():
        prefix_command = bot.get_command(prefix_name)
        if prefix_command is None:
            missing.append(prefix_name)
            continue

        bridge = _make_slash_bridge(prefix_command, slash_name)
        groups[group_name].add_command(bridge.app_command)

    for prefix_name, (existing_group_name, slash_name) in EXISTING_GROUP_ROUTES.items():
        prefix_command = bot.get_command(prefix_name)
        existing_group = bot.get_command(existing_group_name)
        if prefix_command is None:
            missing.append(prefix_name)
            continue
        if not isinstance(existing_group, commands.HybridGroup) or not existing_group.app_command:
            raise RuntimeError(f"하이브리드 그룹을 찾을 수 없습니다: {existing_group_name}")

        bridge = _make_slash_bridge(prefix_command, slash_name)
        existing_group.app_command.add_command(bridge.app_command)

    if missing:
        raise RuntimeError("슬래시 연결 대상 명령어 누락: " + ", ".join(sorted(missing)))

    for group in groups.values():
        bot.tree.add_command(group)

    # 설명이 없는 기존 하이브리드 명령어도 Discord 메뉴에서 알아보기 쉽게 표시합니다.
    for app_command in bot.tree.walk_commands():
        if isinstance(app_command, app_commands.Command) and app_command.description == "…":
            app_command.description = f"{app_command.name} 기능을 실행합니다."

    root_count = len(bot.tree.get_commands())
    if root_count > 100:
        raise RuntimeError(f"Discord 최상위 슬래시 명령어 제한 초과: {root_count}/100")

    bot._abaddon_slash_groups_registered = True
    bot._abaddon_slash_root_count = root_count
