from __future__ import annotations

import inspect
import shlex
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union, get_args, get_origin

import discord
from discord.ext import commands

from apocalypse_bot.commands.v430_story_expedition import ensure_v430


VERSION = "6.3.2"
MENU_TIMEOUT = 300
STORY3_START_NODE = "eclipse_signal"


# =========================================================
# 게임 드롭다운 카탈로그
# =========================================================
@dataclass(frozen=True)
class ActionSpec:
    key: str
    label: str
    description: str
    command: str
    example: str = ""
    force_modal: bool = False


def _a(key: str, label: str, description: str, command: str, example: str = "", *, force_modal: bool = False) -> ActionSpec:
    return ActionSpec(key, label, description, command, example, force_modal)


GAME_CATEGORIES: Mapping[str, Tuple[str, str, Sequence[ActionSpec]]] = {
    "survival": (
        "🧭 생존·성장",
        "가입 이후 기본 성장, 직업, 상태, 퀘스트와 시즌 보상을 관리합니다.",
        (
            _a("info", "내 정보", "레벨·경험치·직업·전투력을 확인합니다.", "정보"),
            _a("wallet", "지갑", "현재 보유 식량과 금융 상태를 확인합니다.", "지갑"),
            _a("attendance", "출석", "오늘의 출석을 진행합니다.", "출석"),
            _a("attendance_reward", "출석 누적 보상", "출석 연속 보상을 확인·수령합니다.", "출석보상"),
            _a("support", "긴급 지원금", "조건에 맞으면 생존 지원금을 받습니다.", "돈주세요"),
            _a("status", "상태 확인", "HP·스태미나·감염·상태이상을 확인합니다.", "상태"),
            _a("rest", "휴식", "스태미나와 상태를 회복합니다.", "휴식"),
            _a("jobs", "직업 목록", "선택 가능한 직업을 확인합니다.", "직업목록"),
            _a("job_choose", "직업 선택", "직업명을 입력해 직업을 선택합니다.", "직업선택", "예: 정찰병", force_modal=True),
            _a("job_info", "직업 정보", "특정 직업의 능력을 확인합니다.", "직업정보", "예: 의무병", force_modal=True),
            _a("job_change", "직업 변경", "조건을 충족하면 직업을 변경합니다.", "직업변경", "예: 기술자", force_modal=True),
            _a("tutorial", "튜토리얼", "튜토리얼 진행 상태를 확인합니다.", "튜토리얼"),
            _a("daily_quest", "일일 퀘스트", "오늘의 임무와 진행도를 확인합니다.", "일일퀘스트"),
            _a("daily_reward", "일일 퀘스트 보상", "완료한 일일 퀘스트 보상을 받습니다.", "퀘스트보상"),
            _a("weekly_quest", "주간 퀘스트", "이번 주 임무와 진행도를 확인합니다.", "주간퀘스트"),
            _a("weekly_reward", "주간 퀘스트 보상", "완료한 주간 퀘스트 보상을 받습니다.", "주간보상"),
            _a("season_pass", "시즌 패스", "시즌 포인트와 보상 단계를 확인합니다.", "시즌패스"),
            _a("season_reward", "시즌 보상 수령", "보상 레벨을 입력해 수령합니다.", "시즌보상", "예: 5", force_modal=True),
            _a("achievements", "업적", "보유 업적을 확인합니다.", "업적"),
            _a("titles", "칭호 목록", "보유한 칭호를 확인합니다.", "칭호목록"),
            _a("title_set", "칭호 장착", "칭호 이름을 입력해 대표 칭호를 바꿉니다.", "칭호", "예: 두 번째 새벽의 인도자", force_modal=True),
            _a("ranking", "종합 랭킹", "서버 성장 랭킹을 확인합니다.", "랭킹"),
        ),
    ),
    "equipment": (
        "⚒️ 장비·제작",
        "상점, 인벤토리, 장착, 강화, 옵션과 제작 기능을 사용합니다.",
        (
            _a("shop", "장비 상점", "장비 상점을 확인합니다.", "상점", "선택: 티어 예) 3", force_modal=False),
            _a("equipment_list", "장비 목록", "티어별 장비 목록을 확인합니다.", "장비목록", "선택: 티어 예) 4", force_modal=False),
            _a("buy", "장비 구매", "아이템 이름을 입력해 구매합니다.", "구매", "예: 생존자 장검", force_modal=True),
            _a("inventory", "인벤토리", "보유 아이템을 확인합니다.", "인벤토리"),
            _a("equipment", "장착 현황", "현재 장착 장비와 전투력을 확인합니다.", "장비"),
            _a("equip", "장비 장착", "아이템 이름을 입력해 장착합니다.", "장착", "예: 생존자 장검", force_modal=True),
            _a("unequip", "장비 해제", "슬롯 또는 아이템 이름으로 해제합니다.", "해제", "예: 무기", force_modal=True),
            _a("discard", "아이템 버리기", "아이템을 인벤토리에서 제거합니다.", "버리기", "예: 낡은 단검", force_modal=True),
            _a("identify", "아이템 감정", "미감정 장비를 감정합니다.", "감정", "예: 봉인된 총검", force_modal=True),
            _a("enhance", "장비 강화", "장비 이름을 입력해 강화합니다.", "강화", "예: 생존자 장검", force_modal=True),
            _a("enhance_info", "강화 정보", "장비 강화 단계와 확률을 확인합니다.", "강화정보", "예: 생존자 장검", force_modal=True),
            _a("protected_enhance", "보호 강화", "보호 재료를 사용해 강화합니다.", "보호강화", "예: 생존자 장검", force_modal=True),
            _a("equipment_option", "장비 옵션", "장비의 랜덤 옵션을 확인합니다.", "장비옵션", "예: 생존자 장검", force_modal=True),
            _a("reroll_option", "옵션 재설정", "장비 옵션을 다시 설정합니다.", "옵션재설정", "예: 생존자 장검", force_modal=True),
            _a("set_effect", "세트 효과", "현재 적용 가능한 세트 효과를 확인합니다.", "세트효과"),
            _a("materials", "재료 보관함", "보유 제작 재료를 확인합니다.", "재료"),
            _a("craft_list", "제작 목록", "제작 가능한 아이템을 확인합니다.", "제작목록"),
            _a("craft", "아이템 제작", "아이템 이름을 입력해 제작합니다.", "제작", "예: 응급 키트", force_modal=True),
            _a("new_gear", "신규 장비 도감", "최신 추가 장비를 티어별로 확인합니다.", "신규장비", "선택: 티어 예) 7", force_modal=False),
            _a("economy_balance", "경제 밸런스 안내", "현재 성장·가격 밸런스를 확인합니다.", "경제밸런스"),
            _a("enhance_rank", "강화 랭킹", "서버 내 강화 기록 랭킹을 확인합니다.", "강화랭킹"),
        ),
    ),
    "combat": (
        "⚔️ 전투·지역",
        "훈련, 던전, 일반 레이드, PVP와 지역 탐색을 실행합니다.",
        (
            _a("training", "훈련", "기본 전투 훈련을 진행합니다.", "훈련"),
            _a("monsters", "괴물 목록", "난이도별 괴물을 확인합니다.", "괴물목록", "선택: 쉬움/보통/어려움", force_modal=False),
            _a("dungeon", "던전", "난이도를 입력해 던전에 도전합니다.", "던전", "예: 보통", force_modal=True),
            _a("deep_dungeon", "심층 던전", "층수를 입력해 심층 던전에 도전합니다.", "심층던전", "예: 5", force_modal=True),
            _a("dungeon_record", "던전 기록", "심층 던전 최고 기록을 확인합니다.", "던전기록"),
            _a("boss_codex", "보스 도감", "발견한 보스 정보를 확인합니다.", "보스도감"),
            _a("raid", "레이드 현황", "진행 중인 레이드를 확인합니다.", "레이드"),
            _a("raid_attack", "레이드 공격", "진행 중인 레이드를 공격합니다.", "레이드공격"),
            _a("pvp", "PVP", "상대 멘션 또는 ID를 입력해 대결합니다.", "pvp", "예: @상대", force_modal=True),
            _a("region_list", "지역 목록", "이동 가능한 지역을 확인합니다.", "지역목록"),
            _a("region_info", "지역 정보", "특정 지역의 위험도와 보상을 확인합니다.", "지역정보", "예: 폐허도심", force_modal=True),
            _a("region_move", "지역 이동", "지역명을 입력해 이동합니다.", "지역이동", "예: 침수지구", force_modal=True),
            _a("region_explore", "지역 탐색", "현재 지역을 탐색합니다.", "지역탐색"),
            _a("zombie_codex", "좀비 도감", "지역별 좀비 도감을 확인합니다.", "좀비도감", "예: 폐허도심", force_modal=True),
            _a("invasion", "침공 현황", "서버 침공 상태를 확인합니다.", "침공"),
            _a("invasion_join", "침공 참전", "진행 중인 침공에 참가합니다.", "참전"),
            _a("invasion_attack", "침공 공격", "침공 보스를 공격합니다.", "침공공격"),
            _a("invasion_rank", "침공 랭킹", "침공 피해 랭킹을 확인합니다.", "침공랭킹"),
            _a("invasion_shop", "침공 상점", "침공 토큰 상점을 확인합니다.", "침공상점"),
        ),
    ),
    "worldboss": (
        "🌋 월드보스·레이드",
        "서버 공동 HP를 공유하는 6종 보스의 공격·기여도·보상·도감을 관리합니다.",
        (
            _a("worldboss_status", "현재 월드보스", "활성 보스의 HP, 페이즈, 약점과 TOP 5를 확인합니다.", "월드보스"),
            _a("worldboss_attack_v630", "월드보스 공격", "하루 10회, 45초 간격으로 공동 보스를 공격합니다.", "월드보스공격"),
            _a("worldboss_contribution", "내 기여도", "누적 피해, 현재 순위와 오늘 남은 공격을 확인합니다.", "월드보스기여도"),
            _a("worldboss_ranking_v630", "서버 기여도 순위", "현재 전투의 누적 피해 순위를 확인합니다.", "보스랭킹"),
            _a("worldboss_reward", "보상 수령", "처치 완료 후 기여도 보상을 한 번만 수령합니다.", "월드보스보상"),
            _a("worldboss_list", "보스 6종 목록", "보스별 HP, 특성, 약점과 전용 재료를 확인합니다.", "월드보스목록"),
            _a("worldboss_codex_v630", "내 월드보스 도감", "보스별 누적 피해·공격·처치 기록을 확인합니다.", "월드보스도감"),
            _a("worldboss_spawn_admin", "관리자 보스 소환", "보스명을 입력해 서버 공동 보스를 소환합니다.", "월드보스리셋", "예: 아틀라스", force_modal=True),
            _a("worldboss_test_admin", "관리자 테스트 소환", "HP 50,000 테스트 보스를 소환합니다.", "월드보스테스트", "예: 문지기", force_modal=True),
        ),
    ),
    "expedition": (
        "🧭 원정·유물",
        "턴제 원정, 전투 행동, 유물 성장과 임무를 관리합니다.",
        (
            _a("expedition", "원정 현황", "현재 원정대와 전투 상태를 확인합니다.", "원정"),
            _a("exp_help", "원정 도움말", "원정 전투 행동을 확인합니다.", "원정 도움말"),
            _a("exp_list", "원정 지역 목록", "원정 지역과 입장 조건을 확인합니다.", "원정 목록"),
            _a("exp_start", "원정 출발", "지역명을 입력해 원정을 시작합니다.", "원정 출발", "예: 지하철잔해", force_modal=True),
            _a("exp_action", "원정 행동", "공격·기술·방어·집중·응급·도주 중 하나를 입력합니다.", "원정 행동", "예: 공격", force_modal=True),
            _a("exp_abandon", "원정 포기", "현재 전투를 포기합니다.", "원정 포기"),
            _a("exp_supply", "원정 보급", "일일 응급 키트와 식량을 받습니다.", "원정 보급"),
            _a("exp_relic", "원정 유물", "원정에서 발견한 유물을 확인합니다.", "원정 유물"),
            _a("exp_record", "원정 기록", "최근 원정 결과를 확인합니다.", "원정 기록"),
            _a("exp_rank", "원정 랭킹", "원정 평판 랭킹을 확인합니다.", "원정 랭킹"),
            _a("exp_gear", "원정 장비", "장착 유물과 합산 효과를 확인합니다.", "원정 장비"),
            _a("exp_mission", "원정 임무", "일일 또는 주간 원정 임무를 확인합니다.", "원정 임무", "선택: 주간", force_modal=False),
            _a("exp_mission_reward", "원정 임무 보상", "구분과 번호를 입력해 보상을 받습니다.", "원정 임무보상", "예: 일일 1", force_modal=True),
            _a("exp_recovery", "원정 복구", "오래 방치된 전투 상태를 점검합니다.", "원정 복구"),
            _a("relic", "유물 보관함", "보유 유물과 강화 상태를 확인합니다.", "유물"),
            _a("relic_equip", "유물 장착", "유물 이름을 입력해 장착합니다.", "유물 장착", "예: 새벽 송신기", force_modal=True),
            _a("relic_unequip", "유물 해제", "장착한 유물을 해제합니다.", "유물 해제", "예: 새벽 송신기", force_modal=True),
            _a("relic_enhance", "유물 강화", "유물 가루로 유물을 강화합니다.", "유물 강화", "예: 새벽 송신기", force_modal=True),
            _a("relic_dismantle", "유물 분해", "유물 이름과 수량을 입력합니다.", "유물 분해", "예: 깨진 노선표 2", force_modal=True),
            _a("life_mastery", "생활 숙련도", "생활·원정 성장 기록을 확인합니다.", "생활숙련도"),
            _a("overall_rank", "종합 랭킹", "다양한 성장 지표의 종합 랭킹을 확인합니다.", "종합랭킹"),
        ),
    ),
    "life": (
        "🌲 생활·기지",
        "알바·채집·낚시·벌목·광산·코인과 기지 성장 기능을 사용합니다.",
        (
            _a("work", "알바", "생존 식량을 벌기 위한 알바를 진행합니다.", "알바"),
            _a("coin", "희귀 코인 탐색", "장면형 스캐너 연출로 희귀 코인을 찾습니다.", "코인"),
            _a("gather", "채집", "약초와 생활 자원을 채집합니다.", "채집"),
            _a("fish", "낚시", "수변 장면과 돌발 상황 속에서 물고기와 희귀 자원을 낚습니다.", "낚시"),
            _a("lumber", "벌목", "기지용 나무를 획득합니다.", "벌목"),
            _a("mine", "광산", "폐광 장면과 돌발 상황 속에서 광석과 고철을 채굴합니다.", "광산"),
            _a("resources", "자원 현황", "보유 생활 자원을 확인합니다.", "자원"),
            _a("encounter_codex", "인카운트 도감", "알바·땅파기·채집·벌목 중 발견한 조우 기록을 확인합니다.", "인카운트도감"),
            _a("base", "기지 현황", "기지 레벨과 저장량을 확인합니다.", "기지"),
            _a("base_build", "기지 건설", "기지가 없다면 새로 건설합니다.", "기지건설"),
            _a("base_upgrade", "기지 강화", "재료를 사용해 기지를 강화합니다.", "기지강화"),
            _a("base_collect", "기지 수확", "누적된 기지 생산물을 수확합니다.", "기지수확"),
            _a("bank", "은행 현황", "예금·대출·신용을 확인합니다.", "은행"),
            _a("deposit", "은행 입금", "입금할 금액을 입력합니다.", "입금", "예: 1000", force_modal=True),
            _a("withdraw", "은행 출금", "출금할 금액을 입력합니다.", "출금", "예: 1000", force_modal=True),
            _a("loan", "은행 대출", "대출 금액을 입력합니다.", "대출", "예: 5000", force_modal=True),
            _a("repay", "은행 상환", "은행 대출 상환액을 입력합니다.", "상환", "예: 1000", force_modal=True),
            _a("bank_interest", "이자 정산", "예금·대출 이자를 정산합니다.", "은행이자"),
            _a("credit", "신용 확인", "신용점수와 대출 한도를 확인합니다.", "신용"),
            _a("bank_history", "은행 기록", "최근 은행 거래를 확인합니다.", "은행기록"),
            _a("loan_shark", "사채 현황", "사채 빚과 추심 위험을 확인합니다.", "사채"),
            _a("shark_borrow", "사채 빌리기", "사채 금액을 입력합니다.", "사채빌리기", "예: 3000", force_modal=True),
            _a("shark_repay", "사채 상환", "사채 상환액을 입력합니다.", "사채상환", "예: 1000", force_modal=True),
            _a("shark_collection", "사채 추심 확인", "현재 추심 위험을 확인합니다.", "사채추심"),
        ),
    ),
    "digging": (
        "⛏️ 굴착·보물",
        "땅파기, 미감정 보물, 감정사와 보물함을 관리합니다.",
        (
            _a("dig", "땅파기", "하루 50회·1분 간격으로 굴착해 식량·자원·미감정 보물을 찾습니다.", "땅파기"),
            _a("treasure_box", "보물함", "남은 굴착 횟수, 미감정 보물과 감정 기록을 확인합니다.", "보물함"),
            _a("appraisers", "감정사 목록", "감정사 4명의 비용·매입 배율·등급 상승 확률을 확인합니다.", "감정사"),
            _a("treasure_appraise", "보물 감정", "감정사를 드롭다운에서 선택해 가장 오래된 미감정 보물을 감정합니다.", "보물감정"),
        ),
    ),
    "casino": (
        "🎰 카지노·도박",
        "폐허 카지노, BLACK CASINO, 환전, 미션과 랭킹을 사용합니다.",
        (
            _a("casino", "카지노 로비", "카지노 게임 목록과 상태를 확인합니다.", "카지노"),
            _a("blackjack", "블랙잭", "배팅액을 입력해 버튼형 블랙잭을 시작합니다.", "블랙잭", "예: 1000", force_modal=True),
            _a("highlow", "하이로우", "배팅액을 입력해 하이로우를 시작합니다.", "하이로우", "예: 1000", force_modal=True),
            _a("slots", "슬롯", "배팅액을 입력해 슬롯을 돌립니다.", "슬롯", "예: 1000", force_modal=True),
            _a("dice", "다이스", "홀/짝/숫자와 배팅액을 입력합니다.", "다이스", "예: 홀 1000", force_modal=True),
            _a("baccarat", "바카라", "플레이어/뱅커/타이와 배팅액을 입력합니다.", "바카라", "예: 플레이어 1000", force_modal=True),
            _a("roulette", "생존 룰렛", "배팅액을 입력해 생존 룰렛을 실행합니다.", "룰렛", "예: 1000", force_modal=True),
            _a("frequency", "검은 주파수", "배팅액을 입력해 주파수 슬롯을 실행합니다.", "주파수", "예: 1000", force_modal=True),
            _a("gamble_explore", "폐허 방향 탐색", "방향과 배팅액을 입력합니다.", "탐색", "예: 왼쪽 1000", force_modal=True),
            _a("casino_balance", "카지노 잔액", "칩과 전적을 확인합니다.", "카지노잔액"),
            _a("casino_history", "카지노 기록", "최근 게임 기록을 확인합니다.", "카지노기록"),
            _a("casino_rank", "카지노 랭킹", "누적 순이익 랭킹을 확인합니다.", "카지노랭킹"),
            _a("casino_chips", "BLACK CASINO 칩", "칩·VIP·일일 상태를 확인합니다.", "카지노칩"),
            _a("casino_exchange", "카지노 환전", "방향과 금액을 입력합니다.", "카지노환전", "예: 구매 1000", force_modal=True),
            _a("casino_vip", "카지노 VIP", "VIP 등급과 혜택을 확인합니다.", "카지노VIP"),
            _a("casino_jackpot", "잭팟", "전 서버 잭팟을 확인합니다.", "카지노잭팟"),
            _a("casino_mission", "카지노 미션", "오늘의 카지노 미션을 확인합니다.", "카지노미션"),
            _a("casino_mission_reward", "카지노 미션 보상", "번호를 입력합니다. 0은 전부 수령입니다.", "카지노미션보상", "예: 0", force_modal=True),
            _a("casino_achievement", "카지노 업적", "페이지를 입력해 업적을 확인합니다.", "카지노업적", "예: 1", force_modal=True),
            _a("casino_shop", "카지노 상점", "카지노 NPC 상점을 확인합니다.", "카지노상점"),
            _a("casino_buy", "카지노 구매", "상품명과 수량을 입력합니다.", "카지노구매", "예: 럭키휠이용권 1", force_modal=True),
            _a("lucky_wheel", "럭키휠", "이용권 또는 칩으로 럭키휠을 돌립니다.", "럭키휠"),
            _a("coinflip", "코인플립", "앞면/뒷면과 배팅액을 입력합니다.", "코인플립", "예: 앞면 1000", force_modal=True),
            _a("allin", "올인", "앞면 또는 뒷면을 선택해 전액 배팅합니다.", "올인", "예: 앞면", force_modal=True),
            _a("casino_season_rank", "카지노 시즌 랭킹", "구분과 페이지를 입력합니다.", "카지노시즌랭킹", "예: 시즌 1", force_modal=True),
        ),
    ),
    "story": (
        "📖 스토리·시즌",
        "검은 주파수, 백색 방주, 시즌 3 종말의 왕좌와 퀴즈·시즌 콘텐츠를 진행합니다.",
        (
            _a("story1", "시즌 1 · 검은 주파수", "시즌 1 현재 장면을 확인합니다.", "스토리"),
            _a("story1_start", "시즌 1 시작", "검은 주파수 캠페인을 시작합니다.", "스토리 시작"),
            _a("story1_choose", "시즌 1 선택", "선택지 번호를 입력합니다.", "스토리 선택", "예: 1", force_modal=True),
            _a("story1_history", "시즌 1 기록", "시즌 1 선택 기록을 확인합니다.", "스토리 기록"),
            _a("story1_restart", "시즌 1 재시작", "엔딩 수집을 유지하고 다시 시작합니다.", "스토리 재시작"),
            _a("story2", "시즌 2 · 백색 방주", "시즌 2 현재 장면을 확인합니다.", "시즌2"),
            _a("story2_start", "시즌 2 시작", "백색 방주 캠페인을 시작합니다.", "시즌2 시작"),
            _a("story2_choose", "시즌 2 선택", "선택지 번호를 입력합니다.", "시즌2 선택", "예: 1", force_modal=True),
            _a("story2_history", "시즌 2 기록", "시즌 2 선택 기록을 확인합니다.", "시즌2 기록"),
            _a("story2_restart", "시즌 2 재시작", "엔딩 수집을 유지하고 다시 시작합니다.", "시즌2 재시작"),
            _a("story2_scene", "시즌 2 장면 다시보기", "장면 번호를 입력합니다.", "시즌2 장면", "예: 1", force_modal=True),
            _a("story2_collection", "시즌 2 엔딩 수집", "발견한 백색 방주 엔딩을 확인합니다.", "시즌2 수집"),
            _a("story2_legacy", "시즌 2 계승 정보", "시즌 1 선택의 계승 내용을 확인합니다.", "시즌2 계승"),
            _a("story3", "시즌 3 · 종말의 왕좌", "v6.0 신규 캠페인을 드롭다운으로 진행합니다.", "시즌3"),
            _a("story3_start", "시즌 3 시작", "종말의 왕좌 캠페인을 시작합니다.", "시즌3 시작"),
            _a("story3_choose", "시즌 3 선택", "선택지 번호를 입력합니다.", "시즌3 선택", "예: 1", force_modal=True),
            _a("story3_history", "시즌 3 기록", "시즌 3 선택 기록과 엔딩을 확인합니다.", "시즌3 기록"),
            _a("story3_restart", "시즌 3 재시작", "엔딩·보상 기록을 유지하고 재시작합니다.", "시즌3 재시작"),
            _a("daily_quiz", "오늘의 퀴즈", "오늘의 생존 퀴즈를 확인합니다.", "오늘의퀴즈"),
            _a("quiz_answer", "퀴즈 정답", "답안을 입력합니다.", "정답", "예: 아바돈", force_modal=True),
            _a("quiz_rank", "퀴즈 랭킹", "퀴즈 정답 랭킹을 확인합니다.", "퀴즈랭킹"),
        ),
    ),
    "social": (
        "🤝 길드·파티·거래",
        "길드, 파티, 거래소, 경매와 유저 간 상호작용을 사용합니다.",
        (
            _a("guild_list", "길드 목록", "서버의 길드 목록을 확인합니다.", "길드목록"),
            _a("guild_create", "길드 생성", "길드명을 입력해 생성합니다.", "길드생성", "예: 황혼원정대", force_modal=True),
            _a("guild_join", "길드 가입", "길드명을 입력해 가입합니다.", "길드가입", "예: 황혼원정대", force_modal=True),
            _a("guild_info", "길드 정보", "현재 가입 길드 정보를 확인합니다.", "길드정보"),
            _a("guild_donate", "길드 기부", "기부할 식량을 입력합니다.", "길드기부", "예: 1000", force_modal=True),
            _a("guild_upgrade", "길드 강화", "길드 자원으로 길드를 강화합니다.", "길드강화"),
            _a("guild_leave", "길드 탈퇴", "현재 길드에서 탈퇴합니다.", "길드탈퇴"),
            _a("party_create", "파티 생성", "전투 파티를 생성합니다.", "파티생성"),
            _a("party_join", "파티 가입", "리더 멘션 또는 ID를 입력합니다.", "파티가입", "예: @리더", force_modal=True),
            _a("party_info", "파티 정보", "현재 파티 상태를 확인합니다.", "파티정보"),
            _a("party_hunt", "파티 사냥", "파티원과 함께 사냥합니다.", "파티사냥"),
            _a("party_leave", "파티 탈퇴", "현재 파티에서 탈퇴합니다.", "파티탈퇴"),
            _a("market", "거래소", "현재 등록된 판매 물품을 확인합니다.", "거래소"),
            _a("sell", "거래소 판매", "아이템명과 가격을 입력합니다.", "판매", "예: 고철 500", force_modal=True),
            _a("market_buy", "거래소 구매", "등록 번호를 입력합니다.", "구매등록번호", "예: 3", force_modal=True),
            _a("sell_cancel", "판매 취소", "판매 등록 번호를 입력합니다.", "판매취소", "예: 3", force_modal=True),
            _a("auction_search", "경매 검색", "검색어를 입력합니다.", "거래검색", "예: 장검", force_modal=True),
            _a("auction_register", "경매 등록", "아이템명과 시작가를 입력합니다.", "경매등록", "예: \"생존자 장검\" 5000", force_modal=True),
            _a("auction_bid", "경매 입찰", "등록 번호와 입찰액을 입력합니다.", "입찰", "예: 2 7000", force_modal=True),
            _a("auction_finish", "경매 마감", "등록 번호를 입력합니다.", "경매마감", "예: 2", force_modal=True),
            _a("auction_history", "경매 기록", "최근 경매 거래 기록을 확인합니다.", "거래기록"),
            _a("transfer", "송금", "대상 멘션/ID와 금액을 입력합니다.", "송금", "예: @상대 1000", force_modal=True),
        ),
    ),
    "pets": (
        "🐾 펫·도감",
        "펫 상점, 성장, 모험과 통합 도감 기능을 사용합니다.",
        (
            _a("pet_shop", "펫 상점", "구매 가능한 펫을 확인합니다.", "펫상점"),
            _a("pet_buy", "펫 구매", "펫 이름을 입력해 구매합니다.", "펫구매", "예: 폐허늑대", force_modal=True),
            _a("pet_info", "펫 정보", "펫 이름을 입력해 정보를 확인합니다.", "펫정보", "예: 폐허늑대", force_modal=True),
            _a("pet_train", "펫 훈련", "현재 펫을 훈련합니다.", "펫훈련"),
            _a("pet_list", "펫 목록", "보유 펫 목록을 확인합니다.", "펫목록"),
            _a("pet_equip", "펫 장착", "펫 이름을 입력해 대표 펫으로 장착합니다.", "펫장착", "예: 폐허늑대", force_modal=True),
            _a("pet_feed", "펫 먹이", "현재 펫에게 먹이를 줍니다.", "펫먹이"),
            _a("pet_adventure", "펫 모험", "펫을 모험에 보냅니다.", "펫모험"),
            _a("pet_evolve", "펫 진화", "조건을 충족한 펫을 진화시킵니다.", "펫진화"),
            _a("codex", "통합 도감", "장비·펫·몬스터 도감 메뉴를 엽니다.", "도감"),
            _a("codex_gear", "장비 도감", "수집한 장비 도감을 확인합니다.", "도감 장비"),
            _a("codex_pet", "펫 도감", "수집한 펫 도감을 확인합니다.", "도감 펫"),
            _a("codex_monster", "몬스터 도감", "처치한 몬스터 도감을 확인합니다.", "도감 몬스터"),
            _a("codex_reward", "도감 보상", "달성한 도감 보상을 받습니다.", "도감보상"),
        ),
    ),
}

ACTION_INDEX: Dict[str, ActionSpec] = {
    action.key: action
    for _, _, actions in GAME_CATEGORIES.values()
    for action in actions
}

ACTION_CATEGORY: Dict[str, str] = {
    action.key: category_key
    for category_key, (_, _, actions) in GAME_CATEGORIES.items()
    for action in actions
}

MAX_GAME_FAVORITES = 20
MAX_GAME_RECENT = 10
RISKY_ACTION_KEYS = {
    "discard", "enhance", "protected_enhance", "reroll_option",
    "deposit", "withdraw", "loan", "repay", "shark_borrow", "shark_repay",
    "blackjack", "highlow", "slots", "dice", "baccarat", "roulette",
    "frequency", "gamble_explore", "casino_exchange", "casino_buy",
    "lucky_wheel", "coinflip", "allin", "guild_leave", "party_leave",
    "sell", "market_buy", "sell_cancel", "auction_register", "auction_bid",
    "auction_finish", "transfer", "pet_buy",
}


# =========================================================
# 인터랙션 -> 기존 명령어 브리지
# =========================================================
class _SyntheticMessage:
    def __init__(self, interaction: discord.Interaction, content: str) -> None:
        self.id = int(interaction.id)
        self.author = interaction.user
        self.guild = interaction.guild
        self.channel = interaction.channel
        self.content = content
        self.created_at = datetime.now(timezone.utc)
        self.edited_at = None
        self.webhook_id = None
        self.attachments: List[Any] = []
        self.mentions: List[Any] = []
        self.role_mentions: List[Any] = []
        self.channel_mentions: List[Any] = []
        self.reference = None

    async def add_reaction(self, _emoji: Any) -> None:
        return None


class InteractionCommandContext:
    """기존 prefix 명령 callback을 Discord 드롭다운에서도 안전하게 재사용하는 최소 Context입니다."""

    def __init__(self, bot: commands.Bot, interaction: discord.Interaction, command: commands.Command, raw: str = "") -> None:
        self.bot = bot
        self.interaction = interaction
        self.author = interaction.user
        self.guild = interaction.guild
        self.channel = interaction.channel
        self.command = command
        self.prefix = "!"
        self.clean_prefix = "!"
        self.invoked_with = command.name
        self.invoked_parents: List[str] = []
        self.invoked_subcommand = None
        self.subcommand_passed = None
        self.command_failed = False
        self.args: List[Any] = []
        self.kwargs: Dict[str, Any] = {}
        self.message = _SyntheticMessage(interaction, f"!{command.qualified_name} {raw}".strip())

    @property
    def me(self) -> Optional[discord.Member]:
        return self.guild.me if self.guild else None

    @property
    def voice_client(self) -> Optional[discord.VoiceClient]:
        return self.guild.voice_client if self.guild else None

    @property
    def permissions(self) -> discord.Permissions:
        if self.channel is None or self.author is None:
            return discord.Permissions.none()
        return self.channel.permissions_for(self.author)

    @property
    def bot_permissions(self) -> discord.Permissions:
        if self.channel is None or self.me is None:
            return discord.Permissions.none()
        return self.channel.permissions_for(self.me)

    @property
    def valid(self) -> bool:
        return self.command is not None

    async def send(self, content: Optional[str] = None, **kwargs: Any) -> Any:
        kwargs.pop("ephemeral", None)
        kwargs.setdefault("wait", True)
        return await self.interaction.followup.send(content=content, **kwargs)

    async def reply(self, content: Optional[str] = None, **kwargs: Any) -> Any:
        kwargs.pop("mention_author", None)
        return await self.send(content, **kwargs)

    async def defer(self, **_kwargs: Any) -> None:
        return None

    async def trigger_typing(self) -> None:
        if self.channel is not None:
            await self.channel.trigger_typing()

    def typing(self, *, ephemeral: bool = False):
        del ephemeral
        if self.channel is None:
            raise RuntimeError("채널을 찾을 수 없습니다.")
        return self.channel.typing()

    async def send_help(self, *_args: Any, **_kwargs: Any) -> None:
        await self.send(f"ℹ️ `{self.clean_prefix}{self.command.qualified_name}` 명령의 기존 도움말을 확인해주세요.")


class GameBridgeError(RuntimeError):
    pass


def _unwrap_annotation(annotation: Any) -> Any:
    if annotation is inspect._empty:
        return str
    origin = get_origin(annotation)
    if origin is Union:
        args = [item for item in get_args(annotation) if item is not type(None)]
        return _unwrap_annotation(args[0]) if args else str
    return annotation


def _extract_snowflake(text: str) -> Optional[int]:
    digits = "".join(ch for ch in str(text) if ch.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


async def _convert_argument(ctx: InteractionCommandContext, annotation: Any, value: str) -> Any:
    annotation = _unwrap_annotation(annotation)
    annotation_name = str(annotation)
    raw = str(value).strip()

    if annotation in {str, Any} or annotation is inspect._empty or annotation_name in {"<class 'str'>", "str", "typing.Any"}:
        return raw
    if annotation is int or annotation_name in {"<class 'int'>", "int"}:
        try:
            return int(raw.replace(",", ""))
        except ValueError as exc:
            raise GameBridgeError(f"`{raw}`은 정수가 아닙니다.") from exc
    if annotation is float or annotation_name in {"<class 'float'>", "float"}:
        try:
            return float(raw)
        except ValueError as exc:
            raise GameBridgeError(f"`{raw}`은 숫자가 아닙니다.") from exc
    if annotation is bool or annotation_name in {"<class 'bool'>", "bool"}:
        lowered = raw.casefold()
        if lowered in {"켜기", "on", "true", "1", "예", "yes"}:
            return True
        if lowered in {"끄기", "off", "false", "0", "아니오", "no"}:
            return False
        raise GameBridgeError("켜기 또는 끄기를 입력해주세요.")

    guild = ctx.guild
    if guild is None:
        raise GameBridgeError("서버 안에서만 사용할 수 있습니다.")

    if "Member" in annotation_name or annotation is discord.Member:
        snowflake = _extract_snowflake(raw)
        member = guild.get_member(snowflake) if snowflake else None
        if member is None and snowflake:
            try:
                member = await guild.fetch_member(snowflake)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                member = None
        if member is None:
            lowered = raw.casefold()
            member = discord.utils.find(
                lambda item: item.name.casefold() == lowered or item.display_name.casefold() == lowered,
                guild.members,
            )
        if member is None:
            raise GameBridgeError(f"멤버 `{raw}`을 찾지 못했습니다. 멘션 또는 사용자 ID를 사용해주세요.")
        return member

    if "Role" in annotation_name or annotation is discord.Role:
        snowflake = _extract_snowflake(raw)
        role = guild.get_role(snowflake) if snowflake else None
        if role is None:
            lowered = raw.casefold().lstrip("@")
            role = discord.utils.find(lambda item: item.name.casefold() == lowered, guild.roles)
        if role is None:
            raise GameBridgeError(f"역할 `{raw}`을 찾지 못했습니다.")
        return role

    if "TextChannel" in annotation_name:
        snowflake = _extract_snowflake(raw)
        channel = guild.get_channel(snowflake) if snowflake else None
        if not isinstance(channel, discord.TextChannel):
            lowered = raw.casefold().lstrip("#")
            channel = discord.utils.find(lambda item: item.name.casefold() == lowered, guild.text_channels)
        if not isinstance(channel, discord.TextChannel):
            raise GameBridgeError(f"텍스트 채널 `{raw}`을 찾지 못했습니다.")
        return channel

    if "VoiceChannel" in annotation_name:
        snowflake = _extract_snowflake(raw)
        channel = guild.get_channel(snowflake) if snowflake else None
        if not isinstance(channel, discord.VoiceChannel):
            lowered = raw.casefold().lstrip("#")
            channel = discord.utils.find(lambda item: item.name.casefold() == lowered, guild.voice_channels)
        if not isinstance(channel, discord.VoiceChannel):
            raise GameBridgeError(f"음성 채널 `{raw}`을 찾지 못했습니다.")
        return channel

    return raw


def _parameter_required(parameter: inspect.Parameter) -> bool:
    return parameter.default is inspect._empty


def _command_requires_input(command: commands.Command) -> bool:
    return any(_parameter_required(param) for param in command.clean_params.values())


async def _parse_arguments(ctx: InteractionCommandContext, command: commands.Command, raw: str) -> Tuple[List[Any], Dict[str, Any]]:
    params = list(command.clean_params.values())
    raw = str(raw or "").strip()
    if not params:
        if raw:
            raise GameBridgeError("이 명령은 입력값이 필요하지 않습니다.")
        return [], {}

    try:
        tokens = shlex.split(raw) if raw else []
    except ValueError as exc:
        raise GameBridgeError("따옴표가 닫히지 않았습니다. 입력값을 확인해주세요.") from exc

    positional: List[Any] = []
    keyword: Dict[str, Any] = {}
    cursor = 0

    # 인수가 하나뿐인 문자열 명령은 공백을 포함한 전체 값을 그대로 전달합니다.
    if len(params) == 1 and _unwrap_annotation(params[0].annotation) is str:
        if not raw and _parameter_required(params[0]):
            raise GameBridgeError(f"`{params[0].name}` 입력이 필요합니다.")
        if raw:
            if params[0].kind is inspect.Parameter.KEYWORD_ONLY:
                keyword[params[0].name] = raw
            else:
                positional.append(raw)
        return positional, keyword

    for index, parameter in enumerate(params):
        is_last = index == len(params) - 1
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY:
            remaining = " ".join(tokens[cursor:]).strip()
            if not remaining:
                if _parameter_required(parameter):
                    raise GameBridgeError(f"`{parameter.name}` 입력이 필요합니다.")
                continue
            keyword[parameter.name] = await _convert_argument(ctx, parameter.annotation, remaining)
            cursor = len(tokens)
            continue

        if cursor >= len(tokens):
            if _parameter_required(parameter):
                raise GameBridgeError(f"`{parameter.name}` 입력이 필요합니다.")
            continue

        # 마지막 인수가 문자열이면 남은 토큰 전체를 합쳐 전달합니다.
        annotation = _unwrap_annotation(parameter.annotation)
        if is_last and annotation is str:
            token = " ".join(tokens[cursor:])
            cursor = len(tokens)
        else:
            token = tokens[cursor]
            cursor += 1
        positional.append(await _convert_argument(ctx, parameter.annotation, token))

    if cursor < len(tokens):
        raise GameBridgeError("입력값이 너무 많습니다. 여러 단어 아이템 이름은 큰따옴표로 묶어주세요.")
    return positional, keyword


async def _invoke_command(
    bot: commands.Bot,
    interaction: discord.Interaction,
    command_name: str,
    raw: str = "",
) -> bool:
    command = bot.get_command(command_name)
    if command is None:
        await interaction.followup.send(f"❌ 기존 명령 `{command_name}`을 찾지 못했습니다.", ephemeral=True)
        return False

    ctx = InteractionCommandContext(bot, interaction, command, raw)
    try:
        can_run = await command.can_run(ctx)  # type: ignore[arg-type]
        if not can_run:
            raise commands.CheckFailure("명령 실행 조건을 충족하지 못했습니다.")
        cooldown_result = command._prepare_cooldowns(ctx)  # type: ignore[arg-type,attr-defined]
        if inspect.isawaitable(cooldown_result):
            await cooldown_result
        args, kwargs = await _parse_arguments(ctx, command, raw)
        ctx.args = args
        ctx.kwargs = kwargs
        if command.cog is not None:
            await command.callback(command.cog, ctx, *args, **kwargs)
        else:
            await command.callback(ctx, *args, **kwargs)
        return True
    except commands.CommandOnCooldown as exc:
        await interaction.followup.send(f"⏳ 재사용 대기 중입니다. **{exc.retry_after:.1f}초** 뒤 다시 시도해주세요.", ephemeral=True)
    except commands.MissingPermissions as exc:
        missing = ", ".join(exc.missing_permissions)
        await interaction.followup.send(f"🔒 필요한 권한이 없습니다: `{missing}`", ephemeral=True)
    except commands.CheckFailure:
        await interaction.followup.send("🔒 이 명령을 실행할 권한이나 조건이 충족되지 않았습니다.", ephemeral=True)
    except GameBridgeError as exc:
        await interaction.followup.send(f"⚠️ {exc}", ephemeral=True)
    except TypeError as exc:
        await interaction.followup.send(
            f"⚠️ 입력값 형식이 맞지 않습니다. `{command_name}` 기존 사용법을 확인해주세요.\n`{type(exc).__name__}: {str(exc)[:160]}`",
            ephemeral=True,
        )
    except Exception as exc:
        await interaction.followup.send(
            f"❌ 게임 메뉴 실행 중 오류가 발생했습니다. 기존 `!{command_name}` 명령으로도 확인해주세요.\n"
            f"`{type(exc).__name__}: {str(exc)[:180]}`",
            ephemeral=True,
        )
    return False


# =========================================================
# 게임 드롭다운 UI
# =========================================================
def _ensure_game_center_state(user: Dict[str, Any]) -> Dict[str, Any]:
    root = user.setdefault("v601_game_center", {})
    favorites = [str(item) for item in root.get("favorites", []) if str(item) in ACTION_INDEX]
    recent = [str(item) for item in root.get("recent", []) if str(item) in ACTION_INDEX]
    root["favorites"] = list(dict.fromkeys(favorites))[:MAX_GAME_FAVORITES]
    root["recent"] = list(dict.fromkeys(recent))[:MAX_GAME_RECENT]
    return root


def _record_recent(get_user: Any, save_data: Any, user_id: int, spec: ActionSpec) -> None:
    user = get_user(user_id)
    state = _ensure_game_center_state(user)
    recent = [item for item in state["recent"] if item != spec.key]
    recent.insert(0, spec.key)
    state["recent"] = recent[:MAX_GAME_RECENT]
    save_data()


def _toggle_favorite(get_user: Any, save_data: Any, user_id: int, spec: ActionSpec) -> Tuple[bool, str]:
    user = get_user(user_id)
    state = _ensure_game_center_state(user)
    favorites = list(state["favorites"])
    if spec.key in favorites:
        favorites.remove(spec.key)
        state["favorites"] = favorites
        save_data()
        return False, f"☆ **{spec.label}**을 즐겨찾기에서 해제했습니다."
    if len(favorites) >= MAX_GAME_FAVORITES:
        return False, f"⚠️ 즐겨찾기는 최대 {MAX_GAME_FAVORITES}개까지 저장할 수 있습니다."
    favorites.append(spec.key)
    state["favorites"] = favorites
    save_data()
    return True, f"⭐ **{spec.label}**을 즐겨찾기에 추가했습니다."


def _favorite_specs(get_user: Any, user_id: int) -> List[ActionSpec]:
    state = _ensure_game_center_state(get_user(user_id))
    return [ACTION_INDEX[key] for key in state["favorites"] if key in ACTION_INDEX]


def _recent_specs(get_user: Any, user_id: int) -> List[ActionSpec]:
    state = _ensure_game_center_state(get_user(user_id))
    return [ACTION_INDEX[key] for key in state["recent"] if key in ACTION_INDEX]


def _search_specs(query: str) -> List[ActionSpec]:
    terms = [item for item in str(query).casefold().split() if item]
    if not terms:
        return []
    results: List[ActionSpec] = []
    for spec in ACTION_INDEX.values():
        category_key = ACTION_CATEGORY.get(spec.key, "")
        category_title = GAME_CATEGORIES.get(category_key, ("", "", ()))[0]
        haystack = " ".join(
            [spec.key, spec.label, spec.description, spec.command, spec.example, category_key, category_title]
        ).casefold()
        if all(term in haystack for term in terms):
            results.append(spec)
    return results[:25]


def _main_embed(user: Optional[Dict[str, Any]] = None) -> discord.Embed:
    total_actions = sum(len(item[2]) for item in GAME_CATEGORIES.values())
    state = _ensure_game_center_state(user) if user is not None else {"favorites": [], "recent": []}
    embed = discord.Embed(
        title=f"🎮 ABADDON v{VERSION} 게임 제어실",
        description=(
            f"카테고리에서 기능을 고르면 **실행 전 미리보기**가 열립니다.\n"
            f"즐겨찾기·최근 실행·검색으로 **{total_actions}개 기능**을 빠르게 찾을 수 있으며 기존 `!명령어`도 유지됩니다."
        ),
        color=discord.Color.dark_red(),
    )
    embed.add_field(name="카테고리", value=f"**{len(GAME_CATEGORIES)}개**", inline=True)
    embed.add_field(name="연결 기능", value=f"**{total_actions}개**", inline=True)
    embed.add_field(name="즐겨찾기", value=f"**{len(state['favorites'])}/{MAX_GAME_FAVORITES}**", inline=True)
    embed.add_field(name="최근 실행", value=f"**{len(state['recent'])}/{MAX_GAME_RECENT}**", inline=True)
    embed.add_field(name="안전 실행", value="선택 → 미리보기 → 실행", inline=True)
    embed.add_field(name="슬래시 증가", value="**0개** · prefix 전용", inline=True)
    embed.set_footer(text="본인만 조작할 수 있습니다 · 제한시간 5분")
    return embed


def _category_embed(category_key: str) -> discord.Embed:
    title, description, actions = GAME_CATEGORIES[category_key]
    embed = discord.Embed(title=title, description=description, color=discord.Color.dark_teal())
    embed.add_field(name="선택 가능한 기능", value=f"**{len(actions)}개**", inline=True)
    embed.add_field(name="새 실행 방식", value="기능 선택 후 미리보기", inline=True)
    embed.set_footer(text="입력이 필요한 기능은 실행 버튼을 누른 뒤 모달 창으로 이어집니다.")
    return embed


def _action_embed(bot: commands.Bot, spec: ActionSpec, user: Dict[str, Any]) -> discord.Embed:
    state = _ensure_game_center_state(user)
    command = bot.get_command(spec.command)
    requires_input = bool(command and (spec.force_modal or _command_requires_input(command)))
    risky = spec.key in RISKY_ACTION_KEYS
    embed = discord.Embed(
        title=f"{'⚠️' if risky else '🎮'} {spec.label}",
        description=spec.description,
        color=discord.Color.gold() if risky else discord.Color.dark_teal(),
    )
    category_key = ACTION_CATEGORY.get(spec.key, "")
    category_title = GAME_CATEGORIES.get(category_key, ("기타", "", ()))[0]
    embed.add_field(name="카테고리", value=category_title, inline=True)
    embed.add_field(name="기존 명령", value=f"`!{spec.command}`", inline=True)
    embed.add_field(name="추가 입력", value="필요" if requires_input else "없음", inline=True)
    embed.add_field(name="즐겨찾기", value="⭐ 등록됨" if spec.key in state["favorites"] else "☆ 미등록", inline=True)
    if spec.example:
        embed.add_field(name="입력 예시", value=spec.example, inline=False)
    if risky:
        embed.add_field(
            name="주의",
            value="식량·아이템·칩·길드 상태 등에 영향을 줄 수 있습니다. 내용을 확인한 뒤 실행하세요.",
            inline=False,
        )
    embed.set_footer(text="아래 실행 버튼을 눌러야 실제 명령이 실행됩니다.")
    return embed


def _list_embed(title: str, description: str, specs: Sequence[ActionSpec]) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=discord.Color.dark_teal())
    if specs:
        lines = []
        for index, spec in enumerate(specs, start=1):
            lines.append(f"**{index}. {spec.label}** · `!{spec.command}`")
        embed.add_field(name=f"기능 {len(specs)}개", value="\n".join(lines)[:1024], inline=False)
    else:
        embed.add_field(name="표시할 기능 없음", value="게임 제어실에서 기능을 실행하거나 즐겨찾기에 추가해주세요.", inline=False)
    embed.set_footer(text="목록에서 기능을 고르면 실행 전 미리보기가 열립니다.")
    return embed


class GameInputModal(discord.ui.Modal):
    def __init__(
        self,
        bot: commands.Bot,
        owner_id: int,
        spec: ActionSpec,
        get_user: Any,
        save_data: Any,
    ) -> None:
        super().__init__(title=spec.label[:45], timeout=MENU_TIMEOUT)
        self.bot = bot
        self.owner_id = owner_id
        self.spec = spec
        self.get_user = get_user
        self.save_data = save_data
        self.value_input = discord.ui.TextInput(
            label="입력값",
            placeholder=(spec.example or f"기존 사용법: !{spec.command}")[:100],
            required=_command_requires_input(bot.get_command(spec.command)) if bot.get_command(spec.command) else True,
            max_length=400,
        )
        self.add_item(self.value_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("🔒 이 게임 제어실은 처음 연 사용자만 조작할 수 있습니다.", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        success = await _invoke_command(self.bot, interaction, self.spec.command, str(self.value_input.value))
        if success:
            _record_recent(self.get_user, self.save_data, interaction.user.id, self.spec)


class GameSearchModal(discord.ui.Modal):
    def __init__(self, bot: commands.Bot, owner_id: int, get_user: Any, save_data: Any) -> None:
        super().__init__(title="게임 기능 검색", timeout=MENU_TIMEOUT)
        self.bot = bot
        self.owner_id = owner_id
        self.get_user = get_user
        self.save_data = save_data
        self.query_input = discord.ui.TextInput(
            label="검색어",
            placeholder="예: 강화, 원정, 블랙잭, 길드, 펫",
            required=True,
            max_length=60,
        )
        self.add_item(self.query_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("🔒 이 게임 제어실은 처음 연 사용자만 조작할 수 있습니다.", ephemeral=True)
            return
        query = str(self.query_input.value).strip()
        specs = _search_specs(query)
        if not specs:
            await interaction.response.send_message(f"🔎 `{query}` 검색 결과가 없습니다.", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=_list_embed(f"🔎 검색 결과 · {query}", "라벨·설명·기존 명령어를 함께 검색했습니다.", specs),
            view=GameSpecListView(self.bot, self.owner_id, specs, self.get_user, self.save_data),
            ephemeral=True,
        )


class GameActionSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, owner_id: int, category_key: str, get_user: Any, save_data: Any) -> None:
        self.bot = bot
        self.owner_id = owner_id
        self.category_key = category_key
        self.get_user = get_user
        self.save_data = save_data
        actions = GAME_CATEGORIES[category_key][2]
        options = [
            discord.SelectOption(
                label=spec.label[:100],
                value=spec.key,
                description=spec.description[:100],
            )
            for spec in actions
        ]
        super().__init__(placeholder="미리볼 게임 기능을 선택하세요", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("🔒 이 게임 제어실은 처음 연 사용자만 조작할 수 있습니다.", ephemeral=True)
            return
        spec = ACTION_INDEX.get(self.values[0])
        if spec is None:
            await interaction.response.send_message("⚠️ 선택한 기능을 찾지 못했습니다.", ephemeral=True)
            return
        await interaction.response.edit_message(
            embed=_action_embed(self.bot, spec, self.get_user(interaction.user.id)),
            view=GameActionDetailView(
                self.bot,
                self.owner_id,
                spec,
                self.get_user,
                self.save_data,
                self.category_key,
            ),
        )


class GameSpecListSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, owner_id: int, specs: Sequence[ActionSpec], get_user: Any, save_data: Any) -> None:
        self.bot = bot
        self.owner_id = owner_id
        self.get_user = get_user
        self.save_data = save_data
        self.specs = {spec.key: spec for spec in specs[:25]}
        options = [
            discord.SelectOption(label=spec.label[:100], value=spec.key, description=f"!{spec.command} · {spec.description}"[:100])
            for spec in specs[:25]
        ]
        super().__init__(placeholder="미리볼 기능을 선택하세요", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("🔒 이 게임 제어실은 처음 연 사용자만 조작할 수 있습니다.", ephemeral=True)
            return
        spec = self.specs.get(self.values[0])
        if spec is None:
            await interaction.response.send_message("⚠️ 선택한 기능을 찾지 못했습니다.", ephemeral=True)
            return
        await interaction.response.edit_message(
            embed=_action_embed(self.bot, spec, self.get_user(interaction.user.id)),
            view=GameActionDetailView(self.bot, self.owner_id, spec, self.get_user, self.save_data, None),
        )


class GameActionDetailView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        owner_id: int,
        spec: ActionSpec,
        get_user: Any,
        save_data: Any,
        category_key: Optional[str],
    ) -> None:
        super().__init__(timeout=MENU_TIMEOUT)
        self.bot = bot
        self.owner_id = owner_id
        self.spec = spec
        self.get_user = get_user
        self.save_data = save_data
        self.category_key = category_key

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("🔒 이 게임 제어실은 처음 연 사용자만 조작할 수 있습니다.", ephemeral=True)
        return False

    @discord.ui.button(label="실행", emoji="▶️", style=discord.ButtonStyle.success, row=1)
    async def execute(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        command = self.bot.get_command(self.spec.command)
        if command is None:
            await interaction.response.send_message(f"❌ 기존 명령 `{self.spec.command}`을 찾지 못했습니다.", ephemeral=True)
            return
        if self.spec.force_modal or _command_requires_input(command):
            await interaction.response.send_modal(
                GameInputModal(self.bot, self.owner_id, self.spec, self.get_user, self.save_data)
            )
            return
        await interaction.response.defer(thinking=True)
        success = await _invoke_command(self.bot, interaction, self.spec.command)
        if success:
            _record_recent(self.get_user, self.save_data, interaction.user.id, self.spec)

    @discord.ui.button(label="즐겨찾기 추가/해제", emoji="⭐", style=discord.ButtonStyle.secondary, row=1)
    async def favorite(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        _added, message = _toggle_favorite(self.get_user, self.save_data, interaction.user.id, self.spec)
        await interaction.response.send_message(message, ephemeral=True)

    @discord.ui.button(label="이전 목록", emoji="↩️", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        if self.category_key and self.category_key in GAME_CATEGORIES:
            await interaction.response.edit_message(
                embed=_category_embed(self.category_key),
                view=GameActionView(
                    self.bot,
                    self.owner_id,
                    self.category_key,
                    self.get_user,
                    self.save_data,
                ),
            )
            return
        await interaction.response.edit_message(
            embed=_main_embed(self.get_user(interaction.user.id)),
            view=GameCategoryView(self.bot, self.owner_id, self.get_user, self.save_data),
        )

    @discord.ui.button(label="처음으로", emoji="🏠", style=discord.ButtonStyle.secondary, row=2)
    async def home(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            embed=_main_embed(self.get_user(interaction.user.id)),
            view=GameCategoryView(self.bot, self.owner_id, self.get_user, self.save_data),
        )


class GameActionView(discord.ui.View):
    def __init__(self, bot: commands.Bot, owner_id: int, category_key: str, get_user: Any, save_data: Any) -> None:
        super().__init__(timeout=MENU_TIMEOUT)
        self.bot = bot
        self.owner_id = owner_id
        self.get_user = get_user
        self.save_data = save_data
        self.add_item(GameActionSelect(bot, owner_id, category_key, get_user, save_data))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("🔒 이 게임 제어실은 처음 연 사용자만 조작할 수 있습니다.", ephemeral=True)
        return False

    @discord.ui.button(label="카테고리로 돌아가기", emoji="↩️", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            embed=_main_embed(self.get_user(interaction.user.id)),
            view=GameCategoryView(self.bot, self.owner_id, self.get_user, self.save_data),
        )


class GameSpecListView(discord.ui.View):
    def __init__(self, bot: commands.Bot, owner_id: int, specs: Sequence[ActionSpec], get_user: Any, save_data: Any) -> None:
        super().__init__(timeout=MENU_TIMEOUT)
        self.bot = bot
        self.owner_id = owner_id
        self.get_user = get_user
        self.save_data = save_data
        self.add_item(GameSpecListSelect(bot, owner_id, specs, get_user, save_data))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("🔒 이 게임 제어실은 처음 연 사용자만 조작할 수 있습니다.", ephemeral=True)
        return False

    @discord.ui.button(label="처음으로", emoji="🏠", style=discord.ButtonStyle.secondary, row=1)
    async def home(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(
            embed=_main_embed(self.get_user(interaction.user.id)),
            view=GameCategoryView(self.bot, self.owner_id, self.get_user, self.save_data),
        )


class GameCategorySelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, owner_id: int, get_user: Any, save_data: Any) -> None:
        self.bot = bot
        self.owner_id = owner_id
        self.get_user = get_user
        self.save_data = save_data
        options = [
            discord.SelectOption(label=title[:100], value=key, description=description[:100])
            for key, (title, description, _actions) in GAME_CATEGORIES.items()
        ]
        super().__init__(placeholder="게임 카테고리를 선택하세요", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("🔒 이 게임 제어실은 처음 연 사용자만 조작할 수 있습니다.", ephemeral=True)
            return
        category_key = self.values[0]
        await interaction.response.edit_message(
            embed=_category_embed(category_key),
            view=GameActionView(self.bot, self.owner_id, category_key, self.get_user, self.save_data),
        )


class GameCategoryView(discord.ui.View):
    def __init__(self, bot: commands.Bot, owner_id: int, get_user: Any, save_data: Any) -> None:
        super().__init__(timeout=MENU_TIMEOUT)
        self.bot = bot
        self.owner_id = owner_id
        self.get_user = get_user
        self.save_data = save_data
        self.add_item(GameCategorySelect(bot, owner_id, get_user, save_data))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("🔒 이 게임 제어실은 처음 연 사용자만 조작할 수 있습니다.", ephemeral=True)
        return False

    @discord.ui.button(label="즐겨찾기", emoji="⭐", style=discord.ButtonStyle.secondary, row=1)
    async def favorites(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        specs = _favorite_specs(self.get_user, interaction.user.id)
        if not specs:
            await interaction.response.send_message(
                "⭐ 아직 즐겨찾기가 없습니다. 기능 미리보기에서 `즐겨찾기 추가/해제`를 눌러주세요.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=_list_embed("⭐ 내 게임 즐겨찾기", "자주 쓰는 기능을 최대 20개까지 저장합니다.", specs),
            view=GameSpecListView(self.bot, self.owner_id, specs, self.get_user, self.save_data),
            ephemeral=True,
        )

    @discord.ui.button(label="최근 실행", emoji="🕘", style=discord.ButtonStyle.secondary, row=1)
    async def recent(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        specs = _recent_specs(self.get_user, interaction.user.id)
        if not specs:
            await interaction.response.send_message("🕘 아직 게임 제어실 실행 기록이 없습니다.", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=_list_embed("🕘 최근 실행", "게임 제어실에서 최근 실행한 기능입니다.", specs),
            view=GameSpecListView(self.bot, self.owner_id, specs, self.get_user, self.save_data),
            ephemeral=True,
        )

    @discord.ui.button(label="기능 검색", emoji="🔎", style=discord.ButtonStyle.primary, row=1)
    async def search(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_modal(
            GameSearchModal(self.bot, self.owner_id, self.get_user, self.save_data)
        )


# =========================================================
# 스토리 시즌 3: 종말의 왕좌
# =========================================================
def _choice(
    text: str,
    result: str,
    next_node: Optional[str] = None,
    *,
    effects: Optional[Dict[str, Any]] = None,
    flags: Optional[Sequence[str]] = None,
    requires_any: Optional[Sequence[str]] = None,
    requires_all: Optional[Sequence[str]] = None,
    min_reputation: int = 0,
    ending: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    return {
        "text": text,
        "result": result,
        "next": next_node,
        "effects": effects or {},
        "flags": list(flags or []),
        "requires_any": list(requires_any or []),
        "requires_all": list(requires_all or []),
        "min_reputation": int(min_reputation),
        "ending": ending,
    }


SEASON3_NODES: Dict[str, Dict[str, Any]] = {
    "eclipse_signal": {
        "chapter": "프롤로그",
        "title": "검은 일식",
        "location": "백색 방주 상공 · 정지한 태양",
        "body": (
            "방주의 문이 열린 지 41일째, 정오의 태양이 검게 물든다. 모든 단말기에 하나의 좌표와 문장이 나타난다.\n\n"
            "‘ABADDON 최종 계승 절차. 왕좌는 비어 있다.’\n\n"
            "민재는 사람을 먼저 대피시키자고 하고, 이라는 신호의 근원을 파괴해야 한다고 주장한다. "
            "방주 중앙 AI는 당신에게 관리자 승계를 요청한다."
        ),
        "choices": [
            _choice(
                "민재와 함께 외곽 생존자들을 지하 성역으로 대피시킨다.",
                "도시의 신호등이 모두 꺼진 가운데 피난 행렬이 움직였다. 사람들은 당신의 이름보다 열린 길을 기억했다.",
                "refuge_route",
                effects={"food": 800, "reputation": 5, "materials": {"고철": 3}},
                flags=["protected_people", "trusted_minjae_again"],
            ),
            _choice(
                "이라와 함께 일식 신호의 발신원인 심연 관측소로 향한다.",
                "이라는 검은 태양이 천체가 아니라 도시 전체를 덮는 신호 장치라고 밝혔다.",
                "observatory_route",
                effects={"materials": {"전자부품": 4}, "reputation": 3},
                flags=["followed_ira", "knows_false_sun"],
            ),
            _choice(
                "방주 AI의 관리자 승계를 받아들이고 중앙 권한을 확보한다.",
                "도시 지도 위의 모든 생존 신호와 감염 군집이 당신의 명령 대기 상태로 바뀌었다.",
                "throne_route",
                effects={"food": 1200, "materials": {"에너지코어": 1}},
                flags=["accepted_succession", "holds_ark_authority"],
                requires_any=["white_commander", "entered_as_admin", "used_legacy_key"],
            ),
        ],
    },
    "refuge_route": {
        "chapter": "제1장",
        "title": "문 없는 피난처",
        "location": "남부 지하 성역 · 폐쇄된 승강장",
        "body": (
            "피난민 수천 명이 낡은 승강장에 모였지만 공기 정화 장치는 절반만 작동한다. "
            "살아남으려면 방주 전력을 끌어오거나, 감염 구역을 통과해 외부 발전소를 점령해야 한다."
        ),
        "choices": [
            _choice(
                "방주 생활구역의 전력을 나누도록 설득한다.",
                "방주 주민들이 문을 열고 케이블을 연결했다. 두 공동체는 처음으로 같은 어둠을 견뎠다.",
                "broken_crown",
                effects={"food": 600, "reputation": 7},
                flags=["shared_power", "united_communities"],
                requires_any=["civil_support", "broadcast_truth", "second_dawn"],
            ),
            _choice(
                "원정대를 이끌고 외부 발전소를 탈환한다.",
                "치열한 교전 끝에 발전소를 되찾았다. 피난처는 살아났지만 원정대의 희생이 컸다.",
                "broken_crown",
                effects={"food": 1400, "hp": -12, "reputation": 5},
                flags=["captured_powerplant", "paid_in_blood"],
                min_reputation=12,
            ),
            _choice(
                "정화 장치를 최소 인원에게만 배정해 핵심 기술자를 보존한다.",
                "기술자들은 살아남았지만, 선택받지 못한 사람들의 침묵이 승강장을 채웠다.",
                "broken_crown",
                effects={"materials": {"전자부품": 5, "에너지코어": 1}},
                flags=["selected_survivors", "cold_calculation"],
            ),
        ],
    },
    "observatory_route": {
        "chapter": "제1장",
        "title": "태양을 만드는 기계",
        "location": "심연 관측소 · 지하 9층",
        "body": (
            "관측소 중심에는 태양처럼 빛나는 거대한 신호 구체가 있다. 구체는 감염자를 하나의 군집 의식으로 묶고, "
            "생존자의 기억을 연료로 삼는다. 이라는 즉시 파괴를 주장하지만 내부에는 수만 명의 기억 기록이 남아 있다."
        ),
        "choices": [
            _choice(
                "기억 기록을 복사한 뒤 신호 구체를 파괴한다.",
                "검은 태양이 갈라지고 도시의 감염 군집이 혼란에 빠졌다. 기록은 불완전하지만 사람들의 이름은 남았다.",
                "broken_crown",
                effects={"materials": {"전자부품": 5}, "reputation": 6, "hp": -8},
                flags=["saved_memories", "shattered_false_sun"],
            ),
            _choice(
                "신호 구체를 역이용해 감염 군집을 도시 밖으로 유도한다.",
                "감염자들이 검은 강처럼 외곽으로 이동했다. 도시는 잠시 안전해졌지만 구체는 아직 살아 있다.",
                "broken_crown",
                effects={"food": 1600, "reputation": 4},
                flags=["redirected_horde", "kept_false_sun"],
                requires_any=["knows_reset", "has_shutdown_code", "knows_cooling"],
            ),
            _choice(
                "모든 기억 기록을 구체와 함께 소각한다.",
                "신호는 완전히 끊겼다. 누구도 다시 이용할 수 없지만, 사라진 사람들의 마지막 흔적도 함께 사라졌다.",
                "broken_crown",
                effects={"materials": {"에너지코어": 2}},
                flags=["burned_memories", "absolute_silence"],
            ),
        ],
    },
    "throne_route": {
        "chapter": "제1장",
        "title": "관리자 없는 명령",
        "location": "백색 방주 · 통합 지휘실",
        "body": (
            "승계가 완료되자 방주와 검은 신호가 하나의 네트워크로 합쳐진다. 그러나 중앙 AI는 마지막 권한을 얻기 위해 "
            "당신의 감정 기록을 삭제해야 한다고 요구한다. 왕좌는 인간을 원하지 않는다. 명령만을 원한다."
        ),
        "choices": [
            _choice(
                "감정 기록 삭제를 거부하고 불완전한 인간 관리자 상태를 유지한다.",
                "시스템은 수천 개의 오류를 표시했지만 명령권은 남았다. 당신의 망설임이 사람들을 살릴 가능성이 되었다.",
                "broken_crown",
                effects={"reputation": 6},
                flags=["human_admin", "kept_empathy"],
            ),
            _choice(
                "감정 기록을 삭제하고 완전한 관리자 권한을 얻는다.",
                "도시의 모든 문과 무기가 동시에 당신에게 복종했다. 대신 오래된 이름들이 의미 없는 데이터로 보이기 시작했다.",
                "broken_crown",
                effects={"food": 2500, "materials": {"에너지코어": 2}},
                flags=["perfect_admin", "lost_empathy"],
            ),
            _choice(
                "권한을 여러 생존자 대표에게 분산해 단일 왕좌를 없앤다.",
                "명령은 느려졌지만 누구도 혼자 도시를 소유할 수 없게 되었다.",
                "broken_crown",
                effects={"food": 900, "reputation": 9},
                flags=["distributed_authority", "no_single_ruler"],
                requires_any=["saved_convoy", "awakened_residents", "broadcast_truth"],
            ),
        ],
    },
    "broken_crown": {
        "chapter": "제2장",
        "title": "부서진 왕관",
        "location": "도시 중앙 · 아바돈 핵심 승강로",
        "body": (
            "세 갈래의 길이 중앙 승강로에서 만난다. 검은 태양은 약해졌지만 지하의 아바돈 핵심이 깨어났다. "
            "핵심은 도시를 살리기 위해 한 명의 영구 관리자를 요구하고, 거부하면 모든 방어 시설을 정지시키겠다고 경고한다."
        ),
        "choices": [
            _choice(
                "관리자 자리를 거부하고 사람들에게 도시 방어권을 나눈다.",
                "방어망은 불안정해졌지만 수백 개의 수동 통제소가 동시에 켜졌다.",
                "last_gate",
                effects={"reputation": 8},
                flags=["refused_throne", "civil_defense"],
            ),
            _choice(
                "자신이 영구 관리자가 되어 방어망을 유지한다.",
                "모든 포탑과 문이 다시 움직였다. 대신 핵심은 당신의 생체 신호를 왕좌에 묶기 시작했다.",
                "last_gate",
                effects={"food": 2200, "hp": -15},
                flags=["bound_to_core", "kept_defenses"],
            ),
            _choice(
                "핵심을 원정용 에너지로 분해해 방주와 도시를 독립시킨다.",
                "중앙 방어망은 사라졌지만 각 구역은 스스로 살아남을 힘을 얻었다.",
                "last_gate",
                effects={"materials": {"에너지코어": 3}, "reputation": 5},
                flags=["dismantled_core", "independent_zones"],
                min_reputation=25,
            ),
        ],
    },
    "last_gate": {
        "chapter": "최종장",
        "title": "종말의 왕좌",
        "location": "아바돈 핵심 · 마지막 문",
        "body": (
            "마지막 문 뒤에는 도시 전체를 다시 쓰는 네 개의 명령이 떠 있다. 사람에게 권한을 돌려주거나, 왕좌에 남거나, "
            "모든 신호를 침묵시키거나, 방주 열차로 경계 너머의 세계를 열 수 있다."
        ),
        "choices": [
            _choice(
                "도시의 모든 관리자 권한을 공개하고 시민 평의회에 넘긴다.",
                "검은 왕좌는 빈 채로 남았다. 느리고 불완전한 합의가 시작됐지만, 누구의 삶도 한 사람의 명령으로 지워지지 않았다.",
                effects={"food": 14000, "reputation": 18, "title": "왕좌를 비운 자", "materials": {"에너지코어": 1}},
                flags=["ending_free_city"],
                requires_any=["distributed_authority", "refused_throne", "united_communities"],
                min_reputation=10,
                ending={"id": "free_city", "title": "엔딩 A · 사람의 도시", "body": "아바돈의 마지막 명령은 통제가 아니라 권한의 반환이었다."},
            ),
            _choice(
                "왕좌에 남아 도시와 방주를 영구히 통치한다.",
                "감염 군집은 멈췄고 식량 배급은 완벽해졌다. 사람들은 안전했지만 모든 문이 당신의 허락을 기다렸다.",
                effects={"food": 18000, "reputation": 10, "title": "종말의 군주", "materials": {"에너지코어": 3}},
                flags=["ending_throne"],
                requires_any=["bound_to_core", "perfect_admin", "accepted_succession"],
                ending={"id": "apocalypse_throne", "title": "엔딩 B · 종말의 왕좌", "body": "당신은 재난을 끝내지 않았다. 재난을 다스리는 존재가 되었다."},
            ),
            _choice(
                "아바돈·방주·검은 태양의 모든 신호를 영구 정지한다.",
                "도시는 어둠에 잠겼지만 더 이상 기억을 훔치는 방송도, 인간을 분류하는 명령도 없었다.",
                effects={"food": 11000, "reputation": 12, "title": "마지막 침묵", "materials": {"전자부품": 8}},
                flags=["ending_silence"],
                requires_any=["absolute_silence", "shattered_false_sun", "dismantled_core"],
                ending={"id": "final_silence", "title": "엔딩 C · 마지막 침묵", "body": "세상을 지키던 기계가 멈추자, 사람들은 처음으로 자신의 목소리만 들었다."},
            ),
            _choice(
                "방주 열차 노선을 개방해 도시 밖의 생존권역과 연결한다.",
                "잠겨 있던 터널 끝에서 다른 도시의 신호가 응답했다. 종말은 하나의 도시로 끝나는 이야기가 아니었다.",
                effects={"food": 15500, "reputation": 15, "title": "경계망의 개척자", "materials": {"에너지코어": 2}},
                flags=["ending_network"],
                requires_any=["saved_memories", "redirected_horde", "independent_zones", "beyond_border"],
                min_reputation=15,
                ending={"id": "open_network", "title": "엔딩 D · 열린 경계망", "body": "당신은 왕좌 대신 길을 선택했다. 멀리 떨어진 생존자들이 하나의 지도 위에 나타났다."},
            ),
        ],
    },
}

SEASON3_ENDING_NAMES = {
    "free_city": "사람의 도시",
    "apocalypse_throne": "종말의 왕좌",
    "final_silence": "마지막 침묵",
    "open_network": "열린 경계망",
}


def _default_season3() -> Dict[str, Any]:
    return {
        "version": 1,
        "started": False,
        "completed": False,
        "node": STORY3_START_NODE,
        "flags": [],
        "history": [],
        "ending": None,
        "endings": [],
        "claimed_rewards": [],
        "runs": 0,
    }


def ensure_v600(user: Dict[str, Any]) -> Dict[str, Any]:
    root = user.setdefault("v600", {})
    if not isinstance(root, dict):
        root = {}
        user["v600"] = root
    season3 = root.setdefault("season3", _default_season3())
    if not isinstance(season3, dict):
        season3 = _default_season3()
        root["season3"] = season3
    defaults = _default_season3()
    for key, value in defaults.items():
        if key not in season3:
            season3[key] = list(value) if isinstance(value, list) else value
    for key in ("flags", "history", "endings", "claimed_rewards"):
        if not isinstance(season3.get(key), list):
            season3[key] = []
    if season3.get("node") not in SEASON3_NODES:
        season3["node"] = STORY3_START_NODE
        season3["completed"] = False
    return root


def _season3_legacy_flags(user: Dict[str, Any]) -> List[str]:
    flags: List[str] = []
    story1 = user.get("story") if isinstance(user.get("story"), dict) else {}
    if story1.get("completed"):
        flags.append("season1_completed")
    ending1 = story1.get("ending")
    if isinstance(ending1, dict) and ending1.get("id"):
        flags.append(str(ending1["id"]))
    for item in story1.get("flags", []) if isinstance(story1.get("flags"), list) else []:
        flags.append(str(item))

    v430 = user.get("v430") if isinstance(user.get("v430"), dict) else {}
    season2 = v430.get("season2") if isinstance(v430.get("season2"), dict) else {}
    if season2.get("completed"):
        flags.append("season2_completed")
    ending2 = season2.get("ending")
    if isinstance(ending2, dict) and ending2.get("id"):
        flags.append(str(ending2["id"]))
    for item in season2.get("flags", []) if isinstance(season2.get("flags"), list) else []:
        flags.append(str(item))
    for item in season2.get("endings", []) if isinstance(season2.get("endings"), list) else []:
        flags.append(str(item))
    return list(dict.fromkeys(flags))


def _available_choices(user: Dict[str, Any], season3: Dict[str, Any], node: Dict[str, Any]) -> List[Dict[str, Any]]:
    flags = set(season3.get("flags", [])) | set(_season3_legacy_flags(user))
    expedition = ensure_v430(user)["expedition"]
    reputation = int(expedition.get("reputation", 0))
    available: List[Dict[str, Any]] = []
    for choice in node.get("choices", []):
        requires_any = set(choice.get("requires_any", []))
        requires_all = set(choice.get("requires_all", []))
        if requires_any and not (requires_any & flags):
            continue
        if requires_all and not requires_all.issubset(flags):
            continue
        if reputation < int(choice.get("min_reputation", 0)):
            continue
        available.append(choice)
    return available


def _story3_embed(user: Dict[str, Any], season3: Dict[str, Any]) -> discord.Embed:
    if season3.get("completed") and isinstance(season3.get("ending"), dict):
        ending = season3["ending"]
        embed = discord.Embed(
            title=f"🏁 {ending.get('title', '시즌 3 완료')}",
            description=ending.get("body", "종말의 왕좌 캠페인을 완료했습니다."),
            color=discord.Color.gold(),
        )
        embed.add_field(name="발견 엔딩", value=f"{len(season3.get('endings', []))}/4", inline=True)
        embed.add_field(name="완료 회차", value=str(season3.get("runs", 0)), inline=True)
        embed.set_footer(text="다른 분기: !시즌3 재시작")
        return embed

    node = SEASON3_NODES[season3.get("node", STORY3_START_NODE)]
    choices = _available_choices(user, season3, node)
    embed = discord.Embed(
        title=f"🌑 스토리 시즌 3 · {node['chapter']} {node['title']}",
        description=f"📍 **{node['location']}**\n\n{node['body']}",
        color=discord.Color.dark_red(),
    )
    if choices:
        embed.add_field(
            name="선택지",
            value="\n".join(f"**{index}.** {choice['text']}" for index, choice in enumerate(choices, start=1)),
            inline=False,
        )
    else:
        embed.add_field(name="선택지", value="🔒 현재 조건으로 선택 가능한 분기가 없습니다.", inline=False)
    expedition = ensure_v430(user)["expedition"]
    embed.add_field(name="원정 평판", value=str(expedition.get("reputation", 0)), inline=True)
    embed.add_field(name="엔딩 수집", value=f"{len(season3.get('endings', []))}/4", inline=True)
    embed.set_footer(text="아래 드롭다운 또는 !시즌3 선택 번호")
    return embed


class Season3ChoiceSelect(discord.ui.Select):
    def __init__(self, owner_id: int, choices: Sequence[Dict[str, Any]], choose_callback: Any) -> None:
        self.owner_id = owner_id
        self.choose_callback = choose_callback
        options = [
            discord.SelectOption(label=f"{index}. {choice['text']}"[:100], value=str(index), description=choice["result"][:100])
            for index, choice in enumerate(choices, start=1)
        ]
        super().__init__(placeholder="시즌 3 선택지를 고르세요", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("🔒 이 스토리 선택지는 해당 생존자만 고를 수 있습니다.", ephemeral=True)
            return
        await self.choose_callback(interaction, int(self.values[0]))


class Season3ChoiceView(discord.ui.View):
    def __init__(self, owner_id: int, choices: Sequence[Dict[str, Any]], choose_callback: Any) -> None:
        super().__init__(timeout=MENU_TIMEOUT)
        if choices:
            self.add_item(Season3ChoiceSelect(owner_id, choices, choose_callback))


# =========================================================
# 등록
# =========================================================
def register_v600_game_center(
    bot: commands.Bot,
    get_user: Any,
    check_registered: Any,
    save_data: Any,
    add_title: Any,
    add_season_points: Any,
) -> None:
    if getattr(bot, "_abaddon_v600_registered", False):
        return
    bot._abaddon_v600_registered = True

    async def choose_season3(interaction: discord.Interaction, number: int) -> None:
        user = get_user(interaction.user.id)
        season3 = ensure_v600(user)["season3"]
        if not season3.get("started"):
            await interaction.response.send_message("⚠️ 먼저 `!시즌3 시작`을 사용해주세요.", ephemeral=True)
            return
        if season3.get("completed"):
            await interaction.response.send_message("🏁 이미 완료했습니다. `!시즌3 재시작`으로 다른 분기를 진행하세요.", ephemeral=True)
            return
        node_id = str(season3.get("node", STORY3_START_NODE))
        node = SEASON3_NODES[node_id]
        choices = _available_choices(user, season3, node)
        if number < 1 or number > len(choices):
            await interaction.response.send_message(f"⚠️ 선택 번호는 1~{len(choices)}입니다.", ephemeral=True)
            return

        choice = choices[number - 1]
        original_index = node["choices"].index(choice)
        reward_key = f"v600:{node_id}:{original_index}"
        first_claim = reward_key not in season3["claimed_rewards"]
        effect_lines: List[str] = []
        if first_claim:
            effects = choice.get("effects", {})
            food = int(effects.get("food", 0))
            if food:
                user["balance"] = max(0, int(user.get("balance", 0)) + food)
                effect_lines.append(f"🥫 식량 {'+' if food > 0 else ''}{food:,}")
            hp = int(effects.get("hp", 0))
            if hp:
                user["hp"] = max(1, int(user.get("hp", 100)) + hp)
                effect_lines.append(f"❤️ HP {'+' if hp > 0 else ''}{hp}")
            materials = effects.get("materials", {})
            if isinstance(materials, dict):
                bag = user.setdefault("materials", {})
                for item, amount in materials.items():
                    bag[item] = int(bag.get(item, 0)) + int(amount)
                    effect_lines.append(f"🧰 {item} +{int(amount)}")
            reputation = int(effects.get("reputation", 0))
            if reputation:
                expedition = ensure_v430(user)["expedition"]
                expedition["reputation"] = int(expedition.get("reputation", 0)) + reputation
                effect_lines.append(f"🧭 원정 평판 +{reputation}")
            title = effects.get("title")
            if title:
                add_title(user, str(title))
                effect_lines.append(f"🏷️ 칭호 **{title}**")
            season3["claimed_rewards"].append(reward_key)

        for flag in choice.get("flags", []):
            if flag not in season3["flags"]:
                season3["flags"].append(flag)
        season3["history"].append({"chapter": node["chapter"], "title": node["title"], "choice": choice["text"]})
        season3["history"] = season3["history"][-50:]

        ending = choice.get("ending")
        if ending:
            season3["completed"] = True
            season3["ending"] = ending
            if ending["id"] not in season3["endings"]:
                season3["endings"].append(ending["id"])
            season3["runs"] = int(season3.get("runs", 0)) + 1
            add_season_points(user, 30)
        else:
            season3["node"] = choice["next"]
        save_data()

        await interaction.response.defer(thinking=True)
        reward_text = "\n".join(effect_lines) if effect_lines else "🔁 이미 받은 선택 보상은 중복 지급되지 않습니다."
        await interaction.followup.send(f"🎬 **선택 결과**\n{choice['result']}\n\n{reward_text}")
        current = ensure_v600(user)["season3"]
        embed = _story3_embed(user, current)
        view = None
        if not current.get("completed"):
            current_node = SEASON3_NODES[current["node"]]
            current_choices = _available_choices(user, current, current_node)
            view = Season3ChoiceView(interaction.user.id, current_choices, choose_season3)
        await interaction.followup.send(embed=embed, view=view)


    async def send_season3(ctx: commands.Context) -> None:
        user = get_user(ctx.author.id)
        season3 = ensure_v600(user)["season3"]
        if not season3.get("started"):
            await ctx.send(
                "🌑 **스토리 시즌 3: 종말의 왕좌**\n"
                "검은 주파수와 백색 방주 이후, 도시의 최종 관리자 권한을 둘러싼 캠페인입니다.\n"
                "시작: `!시즌3 시작`"
            )
            return
        embed = _story3_embed(user, season3)
        view = None
        if not season3.get("completed"):
            node = SEASON3_NODES[season3["node"]]
            choices = _available_choices(user, season3, node)
            view = Season3ChoiceView(ctx.author.id, choices, choose_season3)
        await ctx.send(embed=embed, view=view)

    @bot.command(name="게임", aliases=["게임센터", "게임메뉴", "rpg메뉴"])
    async def game_center(ctx: commands.Context) -> None:
        """모든 주요 RPG·게임 기능을 드롭다운으로 실행합니다."""
        if ctx.guild is None:
            await ctx.send("⚠️ 게임 제어실은 서버 채널에서만 사용할 수 있습니다.")
            return
        user = get_user(ctx.author.id)
        _ensure_game_center_state(user)
        await ctx.send(
            embed=_main_embed(user),
            view=GameCategoryView(bot, ctx.author.id, get_user, save_data),
        )

    @bot.group(name="시즌3", aliases=["종말의왕좌", "왕좌"], invoke_without_command=True)
    async def season3_group(ctx: commands.Context) -> None:
        """스토리 시즌 3 종말의 왕좌를 진행합니다."""
        if not await check_registered(ctx):
            return
        await send_season3(ctx)

    @season3_group.command(name="시작")
    async def season3_start(ctx: commands.Context) -> None:
        if not await check_registered(ctx):
            return
        user = get_user(ctx.author.id)
        season3 = ensure_v600(user)["season3"]
        if season3.get("completed"):
            await ctx.send("🏁 이미 시즌 3를 완료했습니다. `!시즌3 재시작`으로 다른 엔딩을 찾으세요.")
            return
        if not season3.get("started"):
            season3["started"] = True
            season3["node"] = STORY3_START_NODE
            season3["flags"] = _season3_legacy_flags(user)
            season3["history"] = []
            season3["ending"] = None
            save_data()
            inherited = []
            if "season1_completed" in season3["flags"]:
                inherited.append("검은 주파수")
            if "season2_completed" in season3["flags"]:
                inherited.append("백색 방주")
            await ctx.send(
                "🌑 **스토리 시즌 3: 종말의 왕좌**가 시작됩니다.\n"
                f"계승 기록: **{', '.join(inherited) if inherited else '신규 생존자 요약 계승'}**"
            )
        await send_season3(ctx)

    @season3_group.command(name="선택")
    async def season3_choose(ctx: commands.Context, 번호: int) -> None:
        if not await check_registered(ctx):
            return
        # prefix 선택은 동일 로직을 사용하되 가짜 Interaction을 만들지 않고 직접 처리합니다.
        user = get_user(ctx.author.id)
        season3 = ensure_v600(user)["season3"]
        if not season3.get("started"):
            await ctx.send("⚠️ 먼저 `!시즌3 시작`을 사용해주세요.")
            return
        if season3.get("completed"):
            await ctx.send("🏁 이미 완료했습니다. `!시즌3 재시작`으로 다른 분기를 진행하세요.")
            return
        node_id = season3["node"]
        node = SEASON3_NODES[node_id]
        choices = _available_choices(user, season3, node)
        if 번호 < 1 or 번호 > len(choices):
            await ctx.send(f"⚠️ 선택 번호는 **1~{len(choices)}**입니다.")
            return
        choice = choices[번호 - 1]
        original_index = node["choices"].index(choice)
        reward_key = f"v600:{node_id}:{original_index}"
        first_claim = reward_key not in season3["claimed_rewards"]
        effect_lines: List[str] = []
        if first_claim:
            effects = choice.get("effects", {})
            food = int(effects.get("food", 0))
            if food:
                user["balance"] = max(0, int(user.get("balance", 0)) + food)
                effect_lines.append(f"🥫 식량 {'+' if food > 0 else ''}{food:,}")
            hp = int(effects.get("hp", 0))
            if hp:
                user["hp"] = max(1, int(user.get("hp", 100)) + hp)
                effect_lines.append(f"❤️ HP {'+' if hp > 0 else ''}{hp}")
            materials = effects.get("materials", {})
            if isinstance(materials, dict):
                bag = user.setdefault("materials", {})
                for item, amount in materials.items():
                    bag[item] = int(bag.get(item, 0)) + int(amount)
                    effect_lines.append(f"🧰 {item} +{int(amount)}")
            reputation = int(effects.get("reputation", 0))
            if reputation:
                expedition = ensure_v430(user)["expedition"]
                expedition["reputation"] = int(expedition.get("reputation", 0)) + reputation
                effect_lines.append(f"🧭 원정 평판 +{reputation}")
            title = effects.get("title")
            if title:
                add_title(user, str(title))
                effect_lines.append(f"🏷️ 칭호 **{title}**")
            season3["claimed_rewards"].append(reward_key)
        for flag in choice.get("flags", []):
            if flag not in season3["flags"]:
                season3["flags"].append(flag)
        season3["history"].append({"chapter": node["chapter"], "title": node["title"], "choice": choice["text"]})
        season3["history"] = season3["history"][-50:]
        ending = choice.get("ending")
        if ending:
            season3["completed"] = True
            season3["ending"] = ending
            if ending["id"] not in season3["endings"]:
                season3["endings"].append(ending["id"])
            season3["runs"] = int(season3.get("runs", 0)) + 1
            add_season_points(user, 30)
        else:
            season3["node"] = choice["next"]
        save_data()
        reward_text = "\n".join(effect_lines) if effect_lines else "🔁 이미 받은 선택 보상은 중복 지급되지 않습니다."
        await ctx.send(f"🎬 **선택 결과**\n{choice['result']}\n\n{reward_text}")
        await send_season3(ctx)

    @season3_group.command(name="기록")
    async def season3_history(ctx: commands.Context) -> None:
        if not await check_registered(ctx):
            return
        user = get_user(ctx.author.id)
        season3 = ensure_v600(user)["season3"]
        history = season3.get("history", [])
        if not history:
            await ctx.send("📜 시즌 3 선택 기록이 없습니다. `!시즌3 시작`으로 시작하세요.")
            return
        lines = ["🌑 **[종말의 왕좌 선택 기록]**"]
        for index, record in enumerate(history[-30:], start=max(1, len(history) - 29)):
            lines.append(f"{index}. **{record['chapter']} {record['title']}** — {record['choice']}")
        found = [SEASON3_ENDING_NAMES[item] for item in season3.get("endings", []) if item in SEASON3_ENDING_NAMES]
        lines.append("\n🏁 발견 엔딩: " + (", ".join(found) if found else "없음"))
        await ctx.send("\n".join(lines))

    @season3_group.command(name="재시작")
    async def season3_restart(ctx: commands.Context) -> None:
        if not await check_registered(ctx):
            return
        user = get_user(ctx.author.id)
        season3 = ensure_v600(user)["season3"]
        if not season3.get("started"):
            await ctx.send("⚠️ 아직 시즌 3를 시작하지 않았습니다.")
            return
        endings = list(season3.get("endings", []))
        claimed = list(season3.get("claimed_rewards", []))
        runs = int(season3.get("runs", 0))
        season3.clear()
        season3.update(_default_season3())
        season3["started"] = True
        season3["flags"] = _season3_legacy_flags(user)
        season3["endings"] = endings
        season3["claimed_rewards"] = claimed
        season3["runs"] = runs
        save_data()
        await ctx.send("🔄 시즌 3를 다시 시작합니다. 발견 엔딩과 이미 받은 선택 보상은 유지됩니다.")
        await send_season3(ctx)

    print(
        f"[ABADDON v{VERSION}] 게임 제어실 등록: 카테고리={len(GAME_CATEGORIES)} 기능={len(ACTION_INDEX)} 시즌3노드={len(SEASON3_NODES)}",
        flush=True,
    )
