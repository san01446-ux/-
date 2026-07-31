import discord
from discord.ext import commands, tasks
import random
import asyncio
import json
import os
import traceback
from datetime import datetime, timedelta
from dotenv import load_dotenv
from apocalypse_bot.game_data.jobs import JOBS
from apocalypse_bot.commands.conditions import (
    apply_dungeon_conditions, condition_text, ensure_conditions,
    exploration_modifier, refresh_conditions, register_condition_commands,
)
from apocalypse_bot.commands.status import (
    DUNGEON_STAMINA_COSTS, LIFE_STAMINA_COSTS, apply_damage,
    ensure_vitals, get_max_hp, get_max_stamina, refresh_vitals,
    register_status_commands, spend_stamina,
)

# =========================================================
# 기본 설정
# =========================================================
load_dotenv()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

DATA_FILE = os.getenv("DATA_FILE", "/var/data/survival_data.json")
CORRECT_PASSWORD = "생존자"
MAX_MESSAGE_LENGTH = 1900

# =========================================================
# 데이터 로드 / 저장 / 마이그레이션
# =========================================================
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "world": {}}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"users": {}, "world": {}}

    # 구버전 데이터는 최상위에 유저 ID가 바로 존재함
    if "users" not in raw:
        old_users = {
            k: v for k, v in raw.items()
            if str(k).isdigit() and isinstance(v, dict)
        }
        return {"users": old_users, "world": {}}

    raw.setdefault("users", {})
    raw.setdefault("world", {})
    return raw


data = load_data()
user_data = data["users"]
world_data = data["world"]


def save_data():
    directory = os.path.dirname(DATA_FILE)
    if directory:
        os.makedirs(directory, exist_ok=True)

    temp_file = f"{DATA_FILE}.tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(
            {"users": user_data, "world": world_data},
            f,
            ensure_ascii=False,
            indent=4
        )
    os.replace(temp_file, DATA_FILE)


def default_user():
    return {
        "balance": 1000,
        "level": 1,
        "exp": 0,
        "job": None,
        "job_changed_at": "",
        "hp": 100,
        "stamina": 100,
        "last_vitals_update": "",
        "infection": 0,
        "conditions": {"출혈": 0, "감염": 0, "중독": 0, "골절": 0, "기절": 0},
        "medical_items": {"붕대": 0, "소독약": 0, "항생제": 0, "진통제": 0, "백신": 0},
        "last_condition_update": "",
        "last_attendance": "",
        "inventory": [],
        "equipment": {"무기": None, "방어구": None, "머리": None, "장갑": None, "신발": None, "반지": None, "목걸이": None},
        "identified_items": [],
        "enhancements": {},
        "equipment_options": {},
        "dungeon_v21": {"max_floor": 1, "best_floor": 0, "clears": 0, "hidden_kills": 0},
        "life_mastery": {"채집": 0, "낚시": 0, "벌목": 0, "광산": 0},
        "worldboss_codex": {},
        "collection_codex": {"items": [], "pets": [], "monsters": {}, "claimed_milestones": []},
        "dungeon_monster_kills": {},
        "tutorial": {"started": False, "step": 0, "completed": False, "skipped": False, "rewards_received": 0},
        "story": {"version": 1, "started": False, "completed": False, "node": "s1_signal", "flags": [], "history": [], "ending": None, "endings": [], "claimed_rewards": [], "runs": 0},
        "market_history": [],
        "pet": None,
        "pet_level": 1,
        "pet_collection": {},
        "materials": {},
        "title": "신입 생존자",
        "titles": ["신입 생존자"],
        "achievements": [],
        "stats": {
            "dungeon_wins": 0,
            "dungeon_losses": 0,
            "boss_damage": 0,
            "worldboss_damage": 0,
            "items_bought": 0,
            "craft_count": 0,
            "enhance_success": 0,
            "gambles": 0,
            "earned": 0
        },
        "daily_quest": {
            "date": "",
            "type": "",
            "target": 0,
            "progress": 0,
            "reward": 0,
            "claimed": False
        },
        "weekly_quest": {
            "week": "",
            "type": "",
            "target": 0,
            "progress": 0,
            "reward": 0,
            "claimed": False
        },
        "attendance_streak": 0,
        "attendance_milestones": [],
        "daily_quiz": {"date": "", "solved": False, "attempts": 0, "correct": 0, "total_correct": 0},
        "base": {
            "level": 1,
            "last_collect": "",
            "storage": 0,
            "built": False
        },
        "resources": {
            "나무": 0,
            "광석": 0,
            "물고기": 0,
            "약초": 0,
            "고철": 0
        },
        "guild_id": None,
        "region": "폐허도심",
        "region_discoveries": ["폐허도심"],
        "zombie_kills": {},
        "exploration_count": 0,
        "season_pass": {
            "season": "",
            "points": 0,
            "claimed_levels": []
        },
        "black_casino": {},
        "finance": {}
    }



def _safe_int(value, default=0, minimum=None):
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = int(default)
    if minimum is not None:
        result = max(minimum, result)
    return result


def ensure_dungeon_user_state(u):
    """구버전 가입 데이터도 던전 보상 처리에서 안전하게 사용할 수 있게 정리합니다."""
    if not isinstance(u, dict):
        return u

    u["balance"] = _safe_int(u.get("balance", 1000), 1000)
    u["level"] = _safe_int(u.get("level", 1), 1, 1)
    u["exp"] = _safe_int(u.get("exp", 0), 0, 0)
    u["infection"] = _safe_int(u.get("infection", 0), 0, 0)

    stats = u.get("stats")
    if not isinstance(stats, dict):
        stats = {}
        u["stats"] = stats
    for key in [
        "dungeon_wins", "dungeon_losses", "boss_damage", "worldboss_damage",
        "items_bought", "craft_count", "enhance_success", "gambles", "earned",
    ]:
        stats[key] = _safe_int(stats.get(key, 0), 0, 0)

    for key in ["materials", "enhancements", "dungeon_monster_kills"]:
        if not isinstance(u.get(key), dict):
            u[key] = {}

    inventory = u.get("inventory")
    if not isinstance(inventory, list):
        if isinstance(inventory, (tuple, set)):
            u["inventory"] = list(inventory)
        elif isinstance(inventory, dict):
            u["inventory"] = list(inventory.keys())
        else:
            u["inventory"] = []

    achievements = u.get("achievements")
    if not isinstance(achievements, list):
        if isinstance(achievements, dict):
            u["achievements"] = list(achievements.keys())
        elif isinstance(achievements, (tuple, set)):
            u["achievements"] = list(achievements)
        elif achievements:
            u["achievements"] = [str(achievements)]
        else:
            u["achievements"] = []

    titles = u.get("titles")
    if not isinstance(titles, list):
        u["titles"] = [str(u.get("title") or "신입 생존자")]

    return u


def migrate_user(u):
    base = default_user()

    for key, value in base.items():
        if key not in u:
            if isinstance(value, dict):
                u[key] = value.copy()
            elif isinstance(value, list):
                u[key] = value.copy()
            else:
                u[key] = value

    if not isinstance(u.get("stats"), dict):
        u["stats"] = {}
    if not isinstance(u.get("daily_quest"), dict):
        u["daily_quest"] = base["daily_quest"].copy()

    for key, value in base["stats"].items():
        u["stats"].setdefault(key, value)

    for key, value in base["daily_quest"].items():
        u["daily_quest"].setdefault(key, value)

    for nested_key in ["weekly_quest", "base", "resources", "season_pass"]:
        if not isinstance(u.get(nested_key), dict):
            u[nested_key] = base[nested_key].copy()
        for key, value in base[nested_key].items():
            if isinstance(value, list):
                u[nested_key].setdefault(key, value.copy())
            else:
                u[nested_key].setdefault(key, value)

    if not isinstance(u.get("equipment"), dict):
        u["equipment"] = base["equipment"].copy()
    for slot, value in base["equipment"].items():
        u["equipment"].setdefault(slot, value)
    if not isinstance(u.get("identified_items"), list):
        u["identified_items"] = []
    if not isinstance(u.get("enhancements"), dict):
        u["enhancements"] = {}
    if not isinstance(u.get("equipment_options"), dict):
        u["equipment_options"] = {}
    if not isinstance(u.get("dungeon_v21"), dict):
        u["dungeon_v21"] = base["dungeon_v21"].copy()
    for key, value in base["dungeon_v21"].items():
        u["dungeon_v21"].setdefault(key, value)
    if not isinstance(u.get("life_mastery"), dict):
        u["life_mastery"] = base["life_mastery"].copy()
    for key, value in base["life_mastery"].items():
        u["life_mastery"].setdefault(key, value)
    if not isinstance(u.get("worldboss_codex"), dict):
        u["worldboss_codex"] = {}
    if not isinstance(u.get("collection_codex"), dict):
        u["collection_codex"] = base["collection_codex"].copy()
    for key, value in base["collection_codex"].items():
        if isinstance(value, list):
            u["collection_codex"].setdefault(key, value.copy())
        elif isinstance(value, dict):
            u["collection_codex"].setdefault(key, value.copy())
        else:
            u["collection_codex"].setdefault(key, value)
    if not isinstance(u.get("dungeon_monster_kills"), dict):
        u["dungeon_monster_kills"] = {}
    if not isinstance(u.get("tutorial"), dict):
        u["tutorial"] = base["tutorial"].copy()
    for key, value in base["tutorial"].items():
        u["tutorial"].setdefault(key, value)
    if not isinstance(u.get("story"), dict):
        u["story"] = base["story"].copy()
    for key, value in base["story"].items():
        if isinstance(value, list):
            u["story"].setdefault(key, value.copy())
        else:
            u["story"].setdefault(key, value)
    if not isinstance(u["story"].get("flags"), list):
        u["story"]["flags"] = []
    if not isinstance(u["story"].get("history"), list):
        u["story"]["history"] = []
    if not isinstance(u["story"].get("endings"), list):
        u["story"]["endings"] = []
    if not isinstance(u["story"].get("claimed_rewards"), list):
        u["story"]["claimed_rewards"] = []
    if not isinstance(u.get("market_history"), list):
        u["market_history"] = []

    # V3.5 펫 동료 시스템: 기존 단일 펫 데이터를 컬렉션 형태로 자동 이전합니다.
    if not isinstance(u.get("pet_collection"), dict):
        u["pet_collection"] = {}
    active_pet = u.get("pet")
    if active_pet:
        record = u["pet_collection"].setdefault(active_pet, {})
        record.setdefault("level", max(1, int(u.get("pet_level", 1) or 1)))
        record.setdefault("exp", 0)
        record.setdefault("friendship", 0)
        record.setdefault("evolution", 0)
        record.setdefault("last_feed", "")
        record.setdefault("last_adventure", "")
    for pet_name, record in list(u["pet_collection"].items()):
        if not isinstance(record, dict):
            record = {}
            u["pet_collection"][pet_name] = record
        record.setdefault("level", 1)
        record.setdefault("exp", 0)
        record.setdefault("friendship", 0)
        record.setdefault("evolution", 0)
        record.setdefault("last_feed", "")
        record.setdefault("last_adventure", "")
        record["level"] = max(1, int(record.get("level", 1) or 1))
        record["exp"] = max(0, int(record.get("exp", 0) or 0))
        record["friendship"] = max(0, int(record.get("friendship", 0) or 0))
        record["evolution"] = max(0, min(2, int(record.get("evolution", 0) or 0)))
    if active_pet and active_pet in u["pet_collection"]:
        u["pet_level"] = u["pet_collection"][active_pet]["level"]

    if not isinstance(u.get("materials"), dict):
        u["materials"] = {}
    for material in ["강화석", "강화보호권", "옵션재설정권"]:
        u["materials"].setdefault(material, 0)
    if not isinstance(u.get("titles"), list):
        u["titles"] = ["신입 생존자"]
    if u.get("title") not in u["titles"]:
        u["titles"].append(u.get("title", "신입 생존자"))

    ensure_dungeon_user_state(u)
    ensure_vitals(u)
    ensure_conditions(u)
    return u


for uid in list(user_data.keys()):
    if isinstance(user_data[uid], dict):
        migrate_user(user_data[uid])

save_data()


def get_user(user_id):
    user_id = str(user_id)
    if user_id not in user_data:
        return None
    return migrate_user(user_data[user_id])


async def send_pages(channel, text, limit=MAX_MESSAGE_LENGTH):
    lines = text.split("\n")
    current = ""

    for line in lines:
        candidate = current + line + "\n"
        if len(candidate) > limit:
            if current:
                await channel.send(current.rstrip())
            current = line + "\n"
        else:
            current = candidate

    if current:
        await channel.send(current.rstrip())


async def check_registered(ctx):
    u = get_user(ctx.author.id)
    if u is None:
        await ctx.send(
            "⛔ **[출입 거부]** 아직 암시장 생존자 명부에 없습니다.\n"
            "`!가입 생존자`를 입력해 먼저 등록하세요."
        )
        return False
    ensure_daily_quest(u)
    ensure_weekly_quest(u)
    ensure_season_pass(u)
    return True


# =========================================================
# 아이템 DB: 7티어 / 70종
# =========================================================
ITEM_DB = {
    "일반": {
        "몽둥이": {"price": 300, "power": 1, "desc": "주변에서 쉽게 구한 둔기"},
        "손전등": {"price": 350, "power": 1, "desc": "어두운 폐허에서 시야 확보"},
        "녹슨파이프": {"price": 450, "power": 2, "desc": "무겁지만 쓸 만한 철제 파이프"},
        "작업용장갑": {"price": 500, "power": 2, "desc": "손을 보호하는 기본 장갑"},
        "등산가방": {"price": 600, "power": 2, "desc": "보급품을 넉넉하게 운반"},
        "낡은헬멧": {"price": 650, "power": 3, "desc": "충격을 조금 줄여주는 헬멧"},
        "주방칼": {"price": 700, "power": 3, "desc": "짧지만 날카로운 근접 무기"},
        "신호탄": {"price": 800, "power": 3, "desc": "위기 때 적의 시선을 분산"},
        "방수우의": {"price": 850, "power": 3, "desc": "오염된 비를 막아준다"},
        "구급주머니": {"price": 900, "power": 4, "desc": "전투 후 응급 처치용"},
    },
    "고급": {
        "철근조각": {"price": 1200, "power": 4, "desc": "끝이 뾰족하게 부러진 철근"},
        "녹슨권총": {"price": 1500, "power": 5, "desc": "잼이 자주 걸리는 오래된 권총"},
        "소방도끼": {"price": 1800, "power": 6, "desc": "문과 감염자를 함께 부순다"},
        "야구보호대": {"price": 2000, "power": 6, "desc": "급조한 사지 방어구"},
        "수제석궁": {"price": 2300, "power": 7, "desc": "조용한 원거리 무기"},
        "경찰방패": {"price": 2500, "power": 7, "desc": "근접 공격을 막는 진압 방패"},
        "군용나이프": {"price": 2700, "power": 8, "desc": "날카롭게 갈린 생존용 나이프"},
        "방독면": {"price": 3000, "power": 8, "desc": "독성 포자와 가스를 걸러준다"},
        "응급키트": {"price": 3200, "power": 9, "desc": "부상을 빠르게 안정시킨다"},
        "경량방탄복": {"price": 3500, "power": 9, "desc": "가볍고 활동성이 좋은 방탄복"},
    },
    "희귀": {
        "전술샷건": {"price": 5000, "power": 11, "desc": "근거리 감염자 무리 제압"},
        "군용방탄조끼": {"price": 5500, "power": 12, "desc": "총탄과 이빨을 함께 막는다"},
        "쇠크로스보우": {"price": 6000, "power": 12, "desc": "고장 적고 강력한 석궁"},
        "전기충격봉": {"price": 6500, "power": 13, "desc": "감염자의 근육을 마비시킨다"},
        "소음권총": {"price": 7000, "power": 14, "desc": "소음을 줄인 은밀한 권총"},
        "강화전술복": {"price": 7500, "power": 14, "desc": "절단과 충격에 강한 전투복"},
        "열감지스코프": {"price": 8200, "power": 15, "desc": "연기 속에서도 목표를 추적"},
        "전투드론": {"price": 9000, "power": 16, "desc": "정찰과 화력 지원을 동시에"},
        "감염차단주사": {"price": 9800, "power": 17, "desc": "감염 진행을 늦추는 실험약"},
        "개조소총": {"price": 10500, "power": 18, "desc": "정밀 부품으로 개조한 돌격소총"},
    },
    "영웅": {
        "야간투시경": {"price": 14000, "power": 20, "desc": "완전한 암흑에서도 시야 확보"},
        "전술방패": {"price": 15000, "power": 21, "desc": "중화기 파편까지 막는 방패"},
        "폭발화살석궁": {"price": 16500, "power": 22, "desc": "폭발 화살을 발사하는 특수 석궁"},
        "대물저격총": {"price": 18000, "power": 24, "desc": "거대 변이체 장갑 관통"},
        "고주파검": {"price": 20000, "power": 25, "desc": "진동 칼날로 두꺼운 조직 절단"},
        "중장갑외골격": {"price": 22000, "power": 27, "desc": "힘과 방어력을 동시에 증폭"},
        "EMP수류탄": {"price": 23500, "power": 28, "desc": "기계형 감염체를 무력화"},
        "플라즈마권총": {"price": 25000, "power": 30, "desc": "실험실에서 회수한 에너지 무기"},
        "생체탐지기": {"price": 27000, "power": 31, "desc": "벽 너머 생체 반응 탐지"},
        "재생갑옷": {"price": 30000, "power": 33, "desc": "손상 부위가 서서히 복구되는 갑옷"},
    },
    "전설": {
        "화염방사기": {"price": 38000, "power": 36, "desc": "감염자 무리를 불태우는 광역 병기"},
        "파워조준경": {"price": 42000, "power": 38, "desc": "탄도 보정이 자동 적용되는 조준경"},
        "전술경장갑": {"price": 45000, "power": 40, "desc": "특수부대용 최첨단 방호 장비"},
        "레일건": {"price": 50000, "power": 43, "desc": "전자기력으로 금속탄을 초고속 발사"},
        "썬더해머": {"price": 55000, "power": 45, "desc": "충격파를 발생시키는 전기 해머"},
        "드래곤브레스": {"price": 60000, "power": 48, "desc": "고온 탄환을 뿜는 특수 산탄총"},
        "블랙팬텀슈트": {"price": 68000, "power": 50, "desc": "은폐 기능이 내장된 전투복"},
        "타이탄캐논": {"price": 75000, "power": 54, "desc": "거대 괴수 전용 중화기"},
        "심연의낫": {"price": 82000, "power": 58, "desc": "검은 에너지를 흡수하는 낫"},
        "불사조장갑": {"price": 90000, "power": 62, "desc": "치명상을 한 번 버틴다는 전설의 장갑"},
    },
    "신화": {
        "종말의검": {"price": 120000, "power": 70, "desc": "재앙의 날에 발견된 검"},
        "천벌의창": {"price": 135000, "power": 74, "desc": "번개를 끌어내리는 창"},
        "아크리액터갑옷": {"price": 150000, "power": 78, "desc": "소형 반응로가 장착된 강화복"},
        "공허포식자": {"price": 170000, "power": 82, "desc": "목표의 에너지를 흡수하는 소총"},
        "시간왜곡장치": {"price": 190000, "power": 86, "desc": "찰나의 시간을 느리게 만든다"},
        "불멸자의가면": {"price": 210000, "power": 90, "desc": "착용자의 공포를 제거한다"},
        "신경동기화드론": {"price": 230000, "power": 94, "desc": "생각만으로 조종하는 전투 드론"},
        "오메가레일건": {"price": 260000, "power": 100, "desc": "벙커 벽도 관통하는 최종병기"},
        "세계수혈청": {"price": 290000, "power": 105, "desc": "생체 능력을 극한까지 끌어올린다"},
        "아포칼립스코어": {"price": 330000, "power": 112, "desc": "그라운드 제로에서 회수한 핵심체"},
    },
    "유일": {
        "루시퍼의대검": {"price": 500000, "power": 130, "desc": "지옥군단장의 검. 단 하나만 존재"},
        "창세의방패": {"price": 560000, "power": 138, "desc": "모든 공격을 거부한다는 방패"},
        "절대영도포": {"price": 620000, "power": 146, "desc": "주변을 순간 동결시키는 초병기"},
        "차원절단기": {"price": 700000, "power": 155, "desc": "공간 자체를 베는 실험 무기"},
        "메시아의왕관": {"price": 780000, "power": 164, "desc": "감염 군체를 지배한다는 왕관"},
        "판도라의심장": {"price": 860000, "power": 175, "desc": "무한 동력을 내뿜는 생체 핵"},
        "심판자의낫": {"price": 950000, "power": 188, "desc": "대상의 생명력을 직접 끊는다"},
        "천공요새코어": {"price": 1050000, "power": 202, "desc": "이동식 요새의 중앙 동력원"},
        "태초의유전자": {"price": 1200000, "power": 218, "desc": "인간 진화의 금지된 샘플"},
        "종말통제키": {"price": 1500000, "power": 240, "desc": "세계 멸망 병기의 최종 제어 장치"},
    }
}

TIER_ORDER = ["일반", "고급", "희귀", "영웅", "전설", "신화", "유일"]
TIER_DROP_WEIGHT = {
    "일반": 40,
    "고급": 28,
    "희귀": 17,
    "영웅": 9,
    "전설": 4,
    "신화": 1.5,
    "유일": 0.5
}


def find_item(item_name):
    for tier, items in ITEM_DB.items():
        if item_name in items:
            return tier, items[item_name]
    return None, None


EQUIPMENT_SLOTS = ["무기", "방어구", "머리", "장갑", "신발", "반지", "목걸이"]
TIER_EMOJI = {"일반": "⚪", "고급": "🟢", "희귀": "🔵", "영웅": "🟣", "전설": "🟠", "신화": "🔴", "유일": "🌈"}
TIER_MULTIPLIER = {"일반": 1.0, "고급": 1.15, "희귀": 1.35, "영웅": 1.65, "전설": 2.0, "신화": 2.5, "유일": 3.2}

def get_item_slot(item_name):
    name = item_name.lower()
    if any(k in name for k in ["반지", "링"]):
        return "반지"
    if any(k in name for k in ["목걸이", "팬던트", "부적"]):
        return "목걸이"
    if any(k in name for k in ["장갑", "글러브"]):
        return "장갑"
    if any(k in name for k in ["신발", "부츠", "군화"]):
        return "신발"
    if any(k in name for k in ["헬멧", "모자", "고글", "마스크"]):
        return "머리"
    if any(k in name for k in ["조끼", "갑옷", "방탄복", "우의", "코트", "재킷", "가방"]):
        return "방어구"
    return "무기"

def get_item_stats(item_name):
    tier, info = find_item(item_name)
    if not info:
        return {}
    slot = get_item_slot(item_name)
    mult = TIER_MULTIPLIER.get(tier, 1.0)
    power = max(1, int(info["power"] * mult))
    stats = {"공격력": 0, "방어력": 0, "치명타": 0, "회피": 0, "감염저항": 0, "행운": 0}
    if slot == "무기":
        stats["공격력"] = power
        stats["치명타"] = max(0, int(mult * 2) - 1)
    elif slot == "방어구":
        stats["방어력"] = power
        stats["감염저항"] = max(1, int(mult * 3))
    elif slot == "머리":
        stats["방어력"] = max(1, power // 2)
        stats["감염저항"] = max(1, int(mult * 2))
    elif slot == "장갑":
        stats["공격력"] = max(1, power // 2)
        stats["치명타"] = max(1, int(mult * 2))
    elif slot == "신발":
        stats["방어력"] = max(1, power // 3)
        stats["회피"] = max(1, int(mult * 2))
    elif slot == "반지":
        stats["치명타"] = max(1, int(mult * 3))
        stats["행운"] = max(1, int(mult * 2))
    elif slot == "목걸이":
        stats["감염저항"] = max(1, int(mult * 3))
        stats["행운"] = max(1, int(mult * 2))
    return stats

def equipment_totals(u):
    totals = {"공격력": 0, "방어력": 0, "치명타": 0, "회피": 0, "감염저항": 0, "행운": 0}
    for item_name in u.get("equipment", {}).values():
        if not item_name:
            continue
        stats = get_item_stats(item_name)
        enhance = u.get("enhancements", {}).get(item_name, 0)
        for key, value in stats.items():
            totals[key] += value + (enhance if key in ["공격력", "방어력"] else enhance // 5)
    return totals

def item_power_for_user(u, item_name):
    _, item = find_item(item_name)
    if not item:
        return 0
    enhance = u.get("enhancements", {}).get(item_name, 0)
    return item["power"] + enhance * max(1, int(item["power"] * 0.08))


def calculate_user_power(u):
    power = u["level"] * 2
    equipped = [x for x in u.get("equipment", {}).values() if x]
    for item_name in equipped:
        power += item_power_for_user(u, item_name)

    totals = equipment_totals(u)
    power += totals["공격력"] + totals["방어력"] // 2

    # V2.1 장비 랜덤 옵션 및 세트 효과
    for item_name in equipped:
        options = u.get("equipment_options", {}).get(item_name, {})
        power += int(options.get("공격력", 0))
        power += int(options.get("방어력", 0)) // 2
        power += int(options.get("치명타", 0)) + int(options.get("회피", 0))
    set_rules = [
        (["타이탄", "중장갑"], 2, 24),
        (["심연", "공허"], 2, 26),
        (["천공", "오메가"], 2, 25),
        (["종말", "아포칼립스"], 2, 35),
    ]
    for keywords, need, bonus in set_rules:
        count = sum(1 for item in equipped if any(keyword in item for keyword in keywords))
        if count >= need:
            power += bonus

    if u.get("pet"):
        power += get_pet_power(u)

    job_name = u.get("job")
    if job_name in JOBS:
        power += JOBS[job_name]["power_bonus"]

    return power


# =========================================================
# 괴물 DB: 난이도별 20종 / 총 80종
# =========================================================
DUNGEONS = {
    "약함": {
        "name": "버려진 지하철 / 도심 골목",
        "base_power": 5,
        "reward": 800,
        "drop_tiers": ["일반", "고급"],
        "monsters": [
            {"name": "굶주린 들개 무리", "desc": "빠르지만 체력이 약한 야생 동물"},
            {"name": "부패한 방랑자", "desc": "느리지만 방심하면 물리는 초기 감염자"},
            {"name": "거대 들쥐 떼", "desc": "시체를 파먹어 비대해진 쥐 무리"},
            {"name": "비틀거리는 노숙자 좀비", "desc": "소리에 반응해 다가오는 감염자"},
            {"name": "변이 길고양이", "desc": "민첩하게 목을 노리는 감염 동물"},
            {"name": "악취 구더기 떼", "desc": "장비 틈새로 파고드는 벌레"},
            {"name": "폐허의 약탈자 잔당", "desc": "굶주림에 이성을 잃은 인간"},
            {"name": "미쳐버린 까마귀", "desc": "눈을 노리고 급강하하는 조류"},
            {"name": "유리조각 부상자", "desc": "고통에 미쳐 날뛰는 감염체"},
            {"name": "감염된 우체부", "desc": "무거운 우편 가방을 휘두른다"},
            {"name": "폐허의 청소부", "desc": "날카로운 집게를 무기로 사용"},
            {"name": "돌연변이 비둘기 떼", "desc": "분진과 바이러스를 흩뿌린다"},
            {"name": "감염된 순찰견", "desc": "명령 없이도 집요하게 추격한다"},
            {"name": "독침 벌레", "desc": "붓기와 마비를 일으키는 독침"},
            {"name": "피투성이 학생", "desc": "책가방 속 물건을 마구 던진다"},
            {"name": "변이 너구리", "desc": "쓰레기 더미에서 갑자기 튀어나온다"},
            {"name": "하수구 악어", "desc": "도심 지하에서 비대해진 포식자"},
            {"name": "떠돌이 사냥꾼", "desc": "생존자를 먹잇감으로 보는 인간"},
            {"name": "감염된 배달기사", "desc": "오토바이 헬멧 때문에 머리가 단단하다"},
            {"name": "골목의 덫사냥꾼", "desc": "녹슨 철사 덫을 설치한다"},
        ]
    },
    "보통": {
        "name": "침식된 군부대 / 외곽 하수구",
        "base_power": 20,
        "reward": 3000,
        "drop_tiers": ["고급", "희귀"],
        "monsters": [
            {"name": "완력형 감염자 러너", "desc": "소리를 듣고 폭주하는 돌연변이"},
            {"name": "방독면 군인 좀비", "desc": "군장 때문에 방어력이 높다"},
            {"name": "스크리머", "desc": "비명으로 주변 감염자를 불러모은다"},
            {"name": "철근을 든 거한", "desc": "괴력으로 방어를 무너뜨린다"},
            {"name": "하수구 독성 슬라임", "desc": "장비를 부식시키는 액체 괴물"},
            {"name": "군견 케르베로스", "desc": "머리가 둘로 갈라진 군견 감염체"},
            {"name": "폭동진압 경찰 좀비", "desc": "단단한 방패를 들고 전진한다"},
            {"name": "감염된 간호사", "desc": "예측하기 어려운 동작으로 급습"},
            {"name": "소방수 돌연변이", "desc": "방화복 때문에 화염에 강하다"},
            {"name": "전기 파동 변이체", "desc": "접근한 장비를 오작동시킨다"},
            {"name": "브루트", "desc": "벽을 부수며 돌진하는 육중한 감염자"},
            {"name": "체인톱 광신도", "desc": "고통을 느끼지 않는 인간 약탈자"},
            {"name": "고장난 군용 드론", "desc": "적아 식별 없이 총탄을 난사한다"},
            {"name": "돌연변이 흑곰", "desc": "두꺼운 지방층으로 탄환을 버틴다"},
            {"name": "감염된 특공대원", "desc": "훈련된 전투 습관이 남아 있다"},
            {"name": "바이오 실험체 B-12", "desc": "불완전한 재생 능력을 지녔다"},
            {"name": "포자 살포자", "desc": "시야를 가리는 감염 포자를 퍼뜨린다"},
            {"name": "독가스 감염체", "desc": "죽을 때 유독가스를 뿜는다"},
            {"name": "중장갑 경비병", "desc": "방탄판을 여러 겹 덧댄 감염자"},
            {"name": "블러드 헌터", "desc": "피 냄새를 따라 끝까지 추적한다"},
        ]
    },
    "강함": {
        "name": "지하 연구소 폐허 / 오염된 병원",
        "base_power": 55,
        "reward": 10000,
        "drop_tiers": ["희귀", "영웅", "전설"],
        "monsters": [
            {"name": "변이된 거대 괴수 탱크", "desc": "일반 총알을 튕기는 근육 괴수"},
            {"name": "스토커", "desc": "빛을 굴절시키며 은폐한다"},
            {"name": "산성 침뱉기 돌연변이", "desc": "부식성 액체를 원거리 발사"},
            {"name": "철갑 호위병", "desc": "전신에 철판을 용접한 감염자"},
            {"name": "프로젝트 0호기", "desc": "최초의 인간형 생체 병기"},
            {"name": "신경 독소 살포충", "desc": "마비 가스를 뿜는 거대 곤충"},
            {"name": "그림자 암살자", "desc": "빛이 없는 곳에서 순간 이동"},
            {"name": "광란의 연구원", "desc": "수술 도구로 급소를 노린다"},
            {"name": "고열 방출형 변이체", "desc": "주변 온도를 비정상적으로 상승"},
            {"name": "폭탄 내장형 자폭병", "desc": "근접하면 체내 폭약이 폭발한다"},
            {"name": "데스 리퍼", "desc": "낫 모양 골격으로 생존자를 절단"},
            {"name": "타락한 기사", "desc": "실험용 외골격에 융합된 병사"},
            {"name": "심연의 집행관", "desc": "정신을 압박하는 저주파를 방출"},
            {"name": "플레임 비스트", "desc": "몸에서 인화성 체액을 뿜는다"},
            {"name": "크림슨 헌터", "desc": "상처 입은 적에게 더욱 빨라진다"},
            {"name": "블랙 팬텀", "desc": "전자 장비의 탐지를 회피한다"},
            {"name": "타이탄 Mk-II", "desc": "기계 장갑과 생체 조직이 결합"},
            {"name": "생체 병기 오메가", "desc": "다양한 감염체 능력을 복제한다"},
            {"name": "헬 브루트", "desc": "폭발에도 멈추지 않는 거대 감염자"},
            {"name": "네크로맨서", "desc": "죽은 감염체의 신경을 재가동한다"},
        ]
    },
    "지옥": {
        "name": "그라운드 제로 지하벙커",
        "base_power": 120,
        "reward": 30000,
        "drop_tiers": ["영웅", "전설", "신화", "유일"],
        "monsters": [
            {"name": "학살자 아포칼립스 퀸", "desc": "모든 감염자의 정점"},
            {"name": "오염된 메카 타이란트", "desc": "폭주한 생체 기계 병기"},
            {"name": "군단장 둠브링어", "desc": "주변 공기를 얼리는 초위험체"},
            {"name": "차원 왜곡형 초월자", "desc": "공간을 일그러뜨려 공격을 회피"},
            {"name": "불멸의 하이드라 가디언", "desc": "머리가 잘려도 재생한다"},
            {"name": "지옥의 화염 악마", "desc": "검붉은 용암을 두른 파괴자"},
            {"name": "사이킥 마인드 브레이커", "desc": "정신 공격으로 의지를 꺾는다"},
            {"name": "붕괴된 실험체의 신", "desc": "수많은 시체가 융합된 괴물"},
            {"name": "종말의 메시아", "desc": "멸망을 선고하는 정체불명의 재앙"},
            {"name": "앱솔루트 제로 타이탄", "desc": "절대 영도의 냉기를 방출"},
            {"name": "루시퍼의 사도", "desc": "검은 날개로 초고속 돌진"},
            {"name": "지옥군단 사령관", "desc": "주변 감염체를 전술적으로 지휘"},
            {"name": "심판자", "desc": "생명 반응을 지우는 광선을 발사"},
            {"name": "공허의 군주", "desc": "주변 에너지를 빨아들인다"},
            {"name": "혼돈의 용", "desc": "산성과 화염을 동시에 토한다"},
            {"name": "데스킹", "desc": "죽을수록 더 강해지는 왕"},
            {"name": "종말의 사신", "desc": "방어구를 무시하는 낫을 휘두른다"},
            {"name": "심연의 여왕", "desc": "환각으로 동료와 적을 뒤바꾼다"},
            {"name": "타락한 천사", "desc": "신성한 외형을 한 살육 병기"},
            {"name": "악마황", "desc": "그라운드 제로 최심부의 절대자"},
        ]
    }
}


# =========================================================
# 랜덤 인사말 60개
# =========================================================
GREETINGS = [
    "오늘도 살아남았군.",
    "암시장은 언제나 열려 있다.",
    "살아 있는 게 기적인 세상이야.",
    "피 냄새가 진동하는군.",
    "또 식량 벌러 왔나?",
    "총알은 충분한가?",
    "어젯밤에도 생존자 한 명이 사라졌어.",
    "감염자보다 사람이 더 무서운 법이지.",
    "환영한다, 생존자.",
    "목소리 낮춰. 놈들이 듣는다.",
    "`!가입 생존자`는 했겠지?",
    "오늘은 전설 장비가 나올지도 모르지.",
    "방아쇠에 손가락 올리고 다녀.",
    "남쪽 골목은 가지 마. 느낌이 안 좋아.",
    "무전기에 이상한 신호가 잡혔다.",
    "자네 뒤에 있는 건 동료가 맞나?",
    "암시장 물건은 환불 불가다.",
    "빚부터 갚아. 사채업자가 널 찾고 있어.",
    "던전에 갈 거면 유언부터 남겨.",
    "오늘 출석 보급은 챙겼나?",
    "한 번의 방심이 감염으로 이어진다.",
    "장비가 너무 허술한데 살아 돌아오겠어?",
    "뭔가 타는 냄새가 나는데.",
    "그라운드 제로에서 신호가 들어왔다.",
    "레이드 인원이 필요해 보이는군.",
    "펫은 귀엽다고 방심하면 안 돼.",
    "강화는 욕심내는 순간 터지는 법이지.",
    "제작대가 비어 있다. 뭘 만들 생각인가?",
    "오늘의 퀘스트부터 확인해.",
    "랭킹은 냉정하다. 강한 자만 남지.",
    "식량이 곧 목숨이다.",
    "소음은 곧 죽음이다.",
    "운이 나쁘면 약한 던전에서도 끝난다.",
    "좋은 장비는 살아남은 자의 특권이지.",
    "저쪽 벽에서 긁는 소리 안 들리나?",
    "대답하지 마. 네 목소리를 흉내 내는 놈일 수 있어.",
    "창고 문을 세 번 두드리면 절대 열지 마.",
    "누군가 무전으로 네 이름을 부르더군.",
    "빛이 깜빡이면 즉시 자리를 떠.",
    "오늘은 공기가 유난히 썩었군.",
    "죽은 줄 알았는데 또 왔네.",
    "레벨만 믿지 마. 장비가 더 중요할 때도 있다.",
    "전투력은 거짓말하지 않는다.",
    "크리티컬 한 방이면 전세가 뒤집히지.",
    "회피에 실패하면 바로 저녁 식사가 된다.",
    "희귀 드롭은 준비된 자에게 온다.",
    "보스가 다시 깨어났다는 소문이 있다.",
    "월드보스가 뜨면 모두가 적이자 동료다.",
    "암시장 규칙은 하나다. 먼저 살아남아.",
    "감염은 빠르고 치료는 느리다.",
    "사람을 믿되 탄창은 확인해.",
    "오늘은 날씨보다 감염 지수가 더 위험하다.",
    "네 그림자가 하나 더 많은 것 같은데?",
    "기분 탓이겠지. 아마도.",
    "바닥의 핏자국을 따라가지 마.",
    "낡은 엘리베이터는 지하 13층에서 멈춘다.",
    "보급품 상자에 손이 달려 있었다는 소문이야.",
    "오늘도 목숨값은 싸고 탄약값은 비싸다.",
    "살고 싶으면 팀을 만들고, 강해지고 싶으면 경쟁해.",
    "어서 와. 종말은 아직 끝나지 않았다."
]


# =========================================================
# 펫 / 제작 / 업적 / 칭호
# =========================================================
PET_DB = {
    "폐허쥐": {
        "emoji": "🐀", "rarity": "일반", "price": 5000, "power": 3,
        "desc": "재료 냄새를 기가 막히게 찾아내는 작은 생존 동료",
        "skill": "수집 본능",
        "skill_desc": "던전 승리 시 추가 재료를 발견할 확률이 증가합니다.",
        "evolutions": ["폐허쥐", "철니 폐허쥐", "군체의 왕"],
        "bonuses": {"material": 0.12},
    },
    "정찰까마귀": {
        "emoji": "🐦‍⬛", "rarity": "고급", "price": 12000, "power": 7,
        "desc": "높은 곳에서 적의 빈틈과 이동 경로를 먼저 찾아냅니다.",
        "skill": "급소 탐지",
        "skill_desc": "던전 전투의 치명타 확률이 증가합니다.",
        "evolutions": ["정찰까마귀", "야간정찰 까마귀", "검은 감시자"],
        "bonuses": {"crit": 0.04},
    },
    "군견제로": {
        "emoji": "🐕", "rarity": "희귀", "price": 25000, "power": 13,
        "desc": "군부대 출신의 충직한 군견. 전투 중 주인을 끝까지 지킵니다.",
        "skill": "전투 지원",
        "skill_desc": "던전 승리 확률이 소폭 증가합니다.",
        "evolutions": ["군견제로", "강화군견 제로", "전쟁견 제로"],
        "bonuses": {"victory": 0.04},
    },
    "변이살쾡이": {
        "emoji": "🐈", "rarity": "영웅", "price": 50000, "power": 22,
        "desc": "소리 없이 움직이며 치명적인 공격을 피하게 돕는 포식자",
        "skill": "그림자 보행",
        "skill_desc": "던전 전투의 회피 확률이 증가합니다.",
        "evolutions": ["변이살쾡이", "그림자 살쾡이", "야수왕"],
        "bonuses": {"dodge": 0.05},
    },
    "미니드론": {
        "emoji": "🤖", "rarity": "전설", "price": 90000, "power": 34,
        "desc": "전투 기록을 분석하고 가치 있는 보급품을 선별하는 소형 드론",
        "skill": "보급 분석",
        "skill_desc": "던전에서 획득하는 식량 보상이 증가합니다.",
        "evolutions": ["미니드론", "전투드론", "오메가 드론"],
        "bonuses": {"reward": 0.08},
    },
    "어린하이드라": {
        "emoji": "🐍", "rarity": "신화", "price": 200000, "power": 55,
        "desc": "재생 능력을 나누어 주인의 상처를 조금씩 회복시킵니다.",
        "skill": "재생 세포",
        "skill_desc": "던전 승리 후 잃은 HP를 일부 회복합니다.",
        "evolutions": ["어린하이드라", "삼두 하이드라", "재생의 군주"],
        "bonuses": {"heal": 4},
    },
    "공허의새끼용": {
        "emoji": "🐉", "rarity": "초월", "price": 500000, "power": 90,
        "desc": "공간 에너지를 먹고 자라며 전투와 탐색 전반을 강화하는 희귀 용",
        "skill": "공허 공명",
        "skill_desc": "치명타, 회피, 보상, 재료 발견과 회복을 모두 강화합니다.",
        "evolutions": ["공허의새끼용", "공허의 비룡", "차원룡"],
        "bonuses": {"crit": 0.03, "dodge": 0.03, "reward": 0.05, "material": 0.08, "heal": 3, "victory": 0.02},
    },
}

PET_MAX_LEVEL = 50
PET_MAX_EVOLUTION = 2
PET_FEED_COOLDOWN_MINUTES = 30
PET_ADVENTURE_COOLDOWN_MINUTES = 60
PET_RARITY_ORDER = {"일반": 1, "고급": 2, "희귀": 3, "영웅": 4, "전설": 5, "신화": 6, "초월": 7}


def _new_pet_record(level=1):
    return {
        "level": max(1, int(level or 1)),
        "exp": 0,
        "friendship": 0,
        "evolution": 0,
        "last_feed": "",
        "last_adventure": "",
    }


def _parse_pet_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def ensure_pet_collection(u):
    collection = u.setdefault("pet_collection", {})
    if not isinstance(collection, dict):
        collection = {}
        u["pet_collection"] = collection

    active = u.get("pet")
    if active:
        record = collection.setdefault(active, _new_pet_record(u.get("pet_level", 1)))
        if not isinstance(record, dict):
            record = _new_pet_record(u.get("pet_level", 1))
            collection[active] = record
        record["level"] = max(int(record.get("level", 1) or 1), int(u.get("pet_level", 1) or 1))

    for name, record in list(collection.items()):
        if not isinstance(record, dict):
            record = _new_pet_record()
            collection[name] = record
        defaults = _new_pet_record(record.get("level", 1))
        for key, value in defaults.items():
            record.setdefault(key, value)
        record["level"] = max(1, min(PET_MAX_LEVEL, int(record.get("level", 1) or 1)))
        record["exp"] = max(0, int(record.get("exp", 0) or 0))
        record["friendship"] = max(0, int(record.get("friendship", 0) or 0))
        record["evolution"] = max(0, min(PET_MAX_EVOLUTION, int(record.get("evolution", 0) or 0)))

    if active and active not in PET_DB:
        u["pet"] = None
        u["pet_level"] = 1
    elif active and active in collection:
        u["pet_level"] = collection[active]["level"]
    return collection


def get_pet_record(u, pet_name=None):
    collection = ensure_pet_collection(u)
    name = pet_name or u.get("pet")
    if not name or name not in collection or name not in PET_DB:
        return None, None
    return name, collection[name]


def get_pet_display_name(pet_name, record):
    info = PET_DB.get(pet_name, {})
    evolutions = info.get("evolutions", [pet_name])
    stage = max(0, min(len(evolutions) - 1, int(record.get("evolution", 0) or 0)))
    return evolutions[stage]


def get_pet_power(u, pet_name=None):
    name, record = get_pet_record(u, pet_name)
    if not name:
        return 0
    info = PET_DB[name]
    level = record["level"]
    evolution = record["evolution"]
    evolution_bonus = int(info["power"] * 0.35 * evolution) + evolution * 5
    return info["power"] + (level - 1) * 2 + evolution_bonus


def get_pet_bonuses(u):
    name, record = get_pet_record(u)
    empty = {"crit": 0.0, "dodge": 0.0, "reward": 0.0, "material": 0.0, "heal": 0, "victory": 0.0}
    if not name:
        return empty

    level = record["level"]
    evolution = record["evolution"]
    scale = 1.0 + (level - 1) * 0.012 + evolution * 0.25
    raw = PET_DB[name].get("bonuses", {})
    result = empty.copy()
    for key in ["crit", "dodge", "reward", "material", "victory"]:
        result[key] = min(0.25, float(raw.get(key, 0)) * scale)
    result["heal"] = max(0, int(float(raw.get("heal", 0)) * scale))
    # 모든 펫은 성장에 따라 아주 작은 기본 회피 보너스를 얻습니다.
    result["dodge"] = min(0.25, result["dodge"] + min(0.05, level * 0.001))
    return result


def pet_exp_required(level):
    return 60 + max(1, int(level)) * 20


def gain_pet_exp(u, amount):
    name, record = get_pet_record(u)
    if not name or amount <= 0:
        return 0

    record["exp"] += int(amount)
    level_ups = 0
    while record["level"] < PET_MAX_LEVEL:
        required = pet_exp_required(record["level"])
        if record["exp"] < required:
            break
        record["exp"] -= required
        record["level"] += 1
        level_ups += 1
    if record["level"] >= PET_MAX_LEVEL:
        record["level"] = PET_MAX_LEVEL
        record["exp"] = 0
    u["pet_level"] = record["level"]
    return level_ups


def pet_cooldown_remaining(record, key, minutes):
    last = _parse_pet_time(record.get(key))
    if not last:
        return 0
    remaining = int((last + timedelta(minutes=minutes) - datetime.now()).total_seconds())
    return max(0, remaining)


def format_seconds(seconds):
    if seconds <= 0:
        return "사용 가능"
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}분 {seconds}초"


MATERIALS = ["철조각", "화약", "전자부품", "생체조직", "에너지코어", "고대파편"]

# 던전 기본 재료 전용 드롭 테이블.
# V2.1 모듈이 MATERIALS에 강화석 계열 재료를 추가하므로,
# 고정 길이 weights와 공유 목록을 함께 사용하면 개수가 달라질 수 있다.
DUNGEON_MATERIAL_DROP_WEIGHTS = {
    "철조각": 35,
    "화약": 25,
    "전자부품": 20,
    "생체조직": 12,
    "에너지코어": 6,
    "고대파편": 2,
}

CRAFT_RECIPES = {
    "응급키트": {"철조각": 2, "생체조직": 1},
    "수제석궁": {"철조각": 4, "전자부품": 1},
    "전기충격봉": {"철조각": 4, "전자부품": 3},
    "EMP수류탄": {"화약": 4, "전자부품": 5},
    "플라즈마권총": {"전자부품": 8, "에너지코어": 2},
    "레일건": {"철조각": 12, "전자부품": 12, "에너지코어": 4},
    "공허포식자": {"생체조직": 15, "에너지코어": 8, "고대파편": 3},
    "차원절단기": {"에너지코어": 20, "고대파편": 15},
}

ACHIEVEMENTS = {
    "첫 승리": ("dungeon_wins", 1, "전투의 시작"),
    "숙련 사냥꾼": ("dungeon_wins", 25, "감염자 사냥꾼"),
    "학살자": ("dungeon_wins", 100, "백전노장"),
    "제작 입문": ("craft_count", 1, "손재주 좋은 생존자"),
    "대장장이": ("enhance_success", 10, "강화의 달인"),
    "부자": ("earned", 100000, "암시장 큰손"),
    "보스 사냥꾼": ("boss_damage", 5000, "보스 브레이커"),
    "세계의 수호자": ("worldboss_damage", 20000, "종말 저지자"),
}


def add_title(u, title):
    if title not in u["titles"]:
        u["titles"].append(title)


def check_achievements(u):
    unlocked = []
    for name, (stat_key, target, title) in ACHIEVEMENTS.items():
        if name in u["achievements"]:
            continue
        if u["stats"].get(stat_key, 0) >= target:
            u["achievements"].append(name)
            add_title(u, title)
            unlocked.append((name, title))
    return unlocked


def random_materials(difficulty):
    table = {
        "약함": (1, 2),
        "보통": (1, 3),
        "강함": (2, 4),
        "지옥": (3, 6)
    }
    count = random.randint(*table[difficulty])
    gained = {}
    material_names = list(DUNGEON_MATERIAL_DROP_WEIGHTS)
    material_weights = list(DUNGEON_MATERIAL_DROP_WEIGHTS.values())

    for _ in range(count):
        material = random.choices(
            material_names,
            weights=material_weights,
            k=1,
        )[0]
        gained[material] = gained.get(material, 0) + 1
    return gained


def give_materials(u, gained):
    for material, amount in gained.items():
        u["materials"][material] = u["materials"].get(material, 0) + amount


def select_drop(tiers):
    available_tiers = [tier for tier in tiers if tier in ITEM_DB]
    weights = [TIER_DROP_WEIGHT[tier] for tier in available_tiers]
    tier = random.choices(available_tiers, weights=weights, k=1)[0]
    item_name = random.choice(list(ITEM_DB[tier].keys()))
    return tier, item_name



# =========================================================
# 주간 퀘스트 / 시즌패스 공통 처리
# =========================================================
WEEKLY_QUEST_TYPES = [
    ("생활 활동", 20, 18000),
    ("PVP 참여", 5, 15000),
    ("파티 사냥", 5, 20000),
    ("던전 승리", 15, 22000),
]

SEASON_REWARDS = {
    1: {"points": 100, "food": 5000, "title": None},
    2: {"points": 250, "food": 12000, "title": None},
    3: {"points": 450, "food": 22000, "title": "시즌 개척자"},
    4: {"points": 700, "food": 35000, "title": None},
    5: {"points": 1000, "food": 55000, "title": "종말 시즌 정복자"},
    6: {"points": 1400, "food": 80000, "title": None},
    7: {"points": 1900, "food": 120000, "title": "아포칼립스 챔피언"},
}


def current_week_key():
    year, week, _ = datetime.now().isocalendar()
    return f"{year}-W{week:02d}"


def ensure_weekly_quest(u):
    week = current_week_key()
    q = u["weekly_quest"]
    if q.get("week") == week:
        return

    qtype, target, reward = random.choice(WEEKLY_QUEST_TYPES)
    u["weekly_quest"] = {
        "week": week,
        "type": qtype,
        "target": target,
        "progress": 0,
        "reward": reward,
        "claimed": False
    }


def progress_weekly(u, quest_type, amount=1):
    ensure_weekly_quest(u)
    q = u["weekly_quest"]
    if q["type"] == quest_type and not q["claimed"]:
        q["progress"] = min(q["target"], q["progress"] + amount)


def ensure_season_pass(u):
    season = datetime.now().strftime("%Y-%m")
    sp = u["season_pass"]
    if sp.get("season") != season:
        u["season_pass"] = {
            "season": season,
            "points": 0,
            "claimed_levels": []
        }


def add_season_points(u, amount):
    ensure_season_pass(u)
    u["season_pass"]["points"] += max(0, int(amount))

# =========================================================
# 일일 퀘스트
# =========================================================
QUEST_TYPES = [
    ("던전 승리", 3, 2500),
    ("도박 참여", 5, 2000),
    ("아이템 구매", 1, 3000),
    ("제작 성공", 1, 4000),
    ("강화 성공", 1, 5000),
]


def ensure_daily_quest(u):
    today = datetime.now().strftime("%Y-%m-%d")
    q = u["daily_quest"]

    if q.get("date") == today:
        return

    qtype, target, reward = random.choice(QUEST_TYPES)
    u["daily_quest"] = {
        "date": today,
        "type": qtype,
        "target": target,
        "progress": 0,
        "reward": reward,
        "claimed": False
    }
    save_data()


def progress_quest(u, quest_type, amount=1):
    ensure_daily_quest(u)
    q = u["daily_quest"]

    if q["type"] == quest_type and not q["claimed"]:
        q["progress"] = min(q["target"], q["progress"] + amount)


# =========================================================
# 월드보스 / 서버 보스
# =========================================================
WORLD_BOSS_POOL = [
    {"name": "종말의 포식자 아바돈", "max_hp": 90000, "grade": "전설", "trait": "광폭화", "material": "생체조직"},
    {"name": "심연룡 네메시스", "max_hp": 120000, "grade": "전설", "trait": "재생", "material": "고대파편"},
    {"name": "기계신 타이란트-X", "max_hp": 150000, "grade": "신화", "trait": "중장갑", "material": "에너지코어"},
    {"name": "그라운드 제로의 군주", "max_hp": 180000, "grade": "신화", "trait": "감염폭풍", "material": "생체조직"},
    {"name": "붉은 여왕 이브", "max_hp": 220000, "grade": "유일", "trait": "피의 장막", "material": "고대파편"},
    {"name": "천공요새 파괴자 오메가", "max_hp": 260000, "grade": "유일", "trait": "전자 방벽", "material": "에너지코어"},
]


def create_world_boss(forced_name=None):
    selected = None
    if forced_name:
        for candidate in WORLD_BOSS_POOL:
            if forced_name.lower() in candidate["name"].lower():
                selected = candidate
                break
    selected = selected or random.choice(WORLD_BOSS_POOL)
    hp = selected["max_hp"]
    return {
        "name": selected["name"],
        "grade": selected["grade"],
        "trait": selected["trait"],
        "material": selected["material"],
        "max_hp": hp,
        "hp": hp,
        "participants": {},
        "status": "active",
        "spawned_at": datetime.now().isoformat(),
        "defeated_at": None,
    }


def migrate_world_boss(boss):
    if not isinstance(boss, dict) or not boss.get("name"):
        return create_world_boss()
    boss.setdefault("grade", "전설")
    boss.setdefault("trait", "알 수 없음")
    boss.setdefault("material", "고대파편")
    boss.setdefault("status", "defeated" if boss.get("hp", 0) <= 0 else "active")
    boss.setdefault("defeated_at", None)
    participants = boss.setdefault("participants", {})
    for uid, value in list(participants.items()):
        if isinstance(value, (int, float)):
            participants[uid] = {"damage": int(value), "attacks": 0, "last_hit": False}
        elif isinstance(value, dict):
            value.setdefault("damage", 0)
            value.setdefault("attacks", 0)
            value.setdefault("last_hit", False)
        else:
            participants[uid] = {"damage": 0, "attacks": 0, "last_hit": False}
    return boss


world_data["world_boss"] = migrate_world_boss(world_data.get("world_boss"))
world_data.setdefault("season", datetime.now().strftime("%Y-%m"))
world_data.setdefault("server_bosses", {})
world_data.setdefault("guilds", {})
world_data.setdefault("market", {})
world_data.setdefault("market_next_id", 1)
world_data.setdefault("parties", {})
save_data()


def get_server_boss(guild_id):
    guild_id = str(guild_id)
    bosses = world_data["server_bosses"]

    if guild_id not in bosses or bosses[guild_id]["hp"] <= 0:
        bosses[guild_id] = {
            "name": random.choice([
                "지하벙커의 폭군",
                "감염 군단장",
                "타이탄 실험체",
                "붉은 여왕"
            ]),
            "max_hp": 10000,
            "hp": 10000,
            "participants": {}
        }
        save_data()

    return bosses[guild_id]


# =========================================================
# 이벤트
# =========================================================
@bot.event
async def on_ready():
    print(f"로그인 완료: {bot.user} / 서버 {len(bot.guilds)}개")

    if not getattr(bot, "_abaddon_slash_synced", False):
        try:
            synced = await bot.tree.sync()
            bot._abaddon_slash_synced = True
            print(
                f"슬래시 명령어 동기화 완료: "
                f"최상위 {len(synced)}개 / 전체 {sum(1 for _ in bot.tree.walk_commands())}개"
            )
        except Exception as exc:
            print(f"[슬래시 명령어 동기화 실패] {type(exc).__name__}: {exc}")

    if not bot_presence.is_running():
        bot_presence.start()


@tasks.loop(seconds=45)
async def bot_presence():
    registered = len(user_data)
    guild_count = len(bot.guilds)
    member_count = sum(g.member_count or 0 for g in bot.guilds)
    boss = migrate_world_boss(world_data.get("world_boss"))
    boss_active = boss.get("status") == "active" and boss.get("hp", 0) > 0
    boss_percent = boss.get("hp", 0) / max(1, boss.get("max_hp", 1)) * 100
    market_count = len(world_data.get("market", {}))
    guilds = len(world_data.get("guilds", {}))
    activities = [
        discord.Game("!명령어 | 종말에서 생존하기"),
        discord.Game("!던전 약함 | 감염자 사냥"),
        discord.Game("!심층던전 | 100층에 도전"),
        discord.Game("!상점 | 암시장 거래"),
        discord.Game("!오늘의퀴즈 | 지식도 생존력"),
        discord.Game("!출석 | 매일 생존 보급품"),
        discord.Game("!길드 | 함께 살아남아라"),
        discord.Game("!강화정보 | 장비 한계 돌파"),
        discord.Game("!보스도감 | 재앙을 기록하라"),
        discord.Game("!거래소 | 생존자 직거래"),
        discord.Activity(type=discord.ActivityType.watching, name=f"등록 생존자 {registered:,}명"),
        discord.Activity(type=discord.ActivityType.watching, name=f"{guild_count}개 서버 · {member_count:,}명"),
        discord.Activity(type=discord.ActivityType.watching, name=f"생존 길드 {guilds:,}개"),
        discord.Activity(type=discord.ActivityType.watching, name=f"거래소 매물 {market_count:,}개"),
        discord.Activity(type=discord.ActivityType.listening, name="폐허 너머의 구조 신호"),
        discord.Activity(type=discord.ActivityType.listening, name="감염자들의 발소리"),
        discord.Activity(type=discord.ActivityType.competing, name="종말 생존 랭킹"),
    ]
    if boss_active:
        activities.extend([
            discord.Activity(type=discord.ActivityType.competing, name=f"{boss['name']} 토벌"),
            discord.Activity(type=discord.ActivityType.watching, name=f"월드보스 HP {boss_percent:.1f}%"),
            discord.Game("!월드보스공격 | 전 서버 협동"),
        ])
    else:
        activities.append(discord.Game("월드보스 처치 완료 · 다음 재앙 대기"))
    await bot.change_presence(status=discord.Status.online, activity=random.choice(activities))


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if bot.user and bot.user.mentioned_in(message):
        await message.channel.send(
            f"{message.author.mention} 🗣️ {random.choice(GREETINGS)}"
        )

    await bot.process_commands(message)


@bot.event
async def on_command_error(ctx, error):
    if hasattr(ctx.command, "on_error"):
        return

    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ 명령어에 필요한 값이 빠졌습니다. `!명령어`를 확인하세요.")
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send("⚠️ 유저, 숫자 또는 입력값 형식이 잘못됐습니다.")
        return
    if isinstance(error, commands.CommandOnCooldown):
        remaining = int(error.retry_after)
        mins, secs = divmod(remaining, 60)
        await ctx.send(f"⏳ 쿨타임이 남았습니다: **{mins}분 {secs}초**")
        return

    original = getattr(error, "original", error)
    print(
        f"[명령어 오류] 명령={getattr(ctx.command, 'qualified_name', None)} "
        f"유저={getattr(ctx.author, 'id', None)} "
        f"오류={type(original).__name__}: {original}",
        flush=True,
    )
    traceback.print_exception(type(original), original, original.__traceback__)
    try:
        await ctx.send("❌ 명령어 처리 중 오류가 발생했습니다. 관리자에게 알려주세요.")
    except (discord.NotFound, discord.Forbidden, discord.HTTPException) as notify_exc:
        print(
            f"[명령어 오류 알림 실패] channel={getattr(getattr(ctx, 'channel', None), 'id', None)} "
            f"{type(notify_exc).__name__}: {notify_exc}",
            flush=True,
        )


# =========================================================
# 가입 / 기본 정보
# =========================================================
@bot.hybrid_command()
async def 가입(ctx, *, 암호: str = ""):
    user_id = str(ctx.author.id)

    if user_id in user_data:
        await ctx.send("⚠️ 이미 암시장에 가입된 생존자입니다.")
        return

    if 암호 != CORRECT_PASSWORD:
        await ctx.send(
            "❌ 암호가 틀렸습니다.\n"
            "사용법: `!가입 생존자`"
        )
        return

    user_data[user_id] = default_user()
    user_data[user_id]["tutorial"]["started"] = True
    ensure_daily_quest(user_data[user_id])
    save_data()

    await ctx.send(
        f"🎉 **[가입 승인]** {ctx.author.mention}님, 암시장 출입이 허가되었습니다.\n"
        "초기 생존 식량 **1,000개** 지급!\n"
        "🧭 초보자 튜토리얼이 시작되었습니다. `!튜토리얼`을 입력하세요."
    )


@bot.hybrid_command()
async def 명령어(ctx):
    text = """📜 **[아포칼립스 생존 봇 명령어]**

✅ 기존 `!명령어`는 이름 변경 없이 그대로 사용할 수 있습니다.
ℹ️ 슬래시 명령어는 Discord의 최상위 100개 제한 때문에 카테고리로 정리되었습니다.
예: `/장비 강화`, `/전투 던전`, `/도박 룰렛`, `/거래 판매`, `/시즌 일일퀘스트`

🔹 **가입 / 정보**
`!가입 생존자` `!정보` `!출석` `!출석보상`
`!지갑` `!송금 @유저 금액` `!돈주세요` `!훈련` `!랭킹`
`!칭호목록` `!칭호 칭호이름`
`!직업목록` `!직업선택 직업명` `!직업정보 [직업명]` `!직업변경 직업명`
`!상태` `!휴식`

🔹 **상점 / 장비 / 제작**
`!상점 [티어]` `!장비목록 [티어]` `!구매 아이템명`
`!인벤토리` `!강화 아이템명` `!강화정보 아이템명` `!보호강화 아이템명`
`!강화랭킹` `!장비옵션 아이템명` `!옵션재설정 아이템명` `!세트효과` `!재료`
`!제작목록` `!제작 아이템명`

🔹 **전투 / 보스**
`!괴물목록 [난이도]` `!던전 약함/보통/강함/지옥`
`!지역목록` `!지역정보 [지역명]` `!지역이동 지역명` `!지역탐색` `!좀비도감 [지역명]`
`!레이드` `!레이드공격` `!월드보스` `!월드보스공격` `!보스도감`
`!심층던전 [층]` `!던전기록` `!PVP @유저`

🔹 **채집 생활**
`!채집` `!낚시` `!벌목` `!광산` `!생활숙련도`

🔹 **치료 / 감염**
`!상태` `!의약품` `!약품구매 붕대 1` `!사용 붕대` `!병원`
`!자원` `!기지` `!기지건설` `!기지강화` `!기지수확`

🔹 **길드**
`!길드목록` `!길드생성 길드명` `!길드가입 길드명`
`!길드정보` `!길드기부 금액` `!길드강화` `!길드탈퇴`

🔹 **거래소**
`!거래소` `!거래검색 키워드` `!판매 아이템명 가격` `!구매등록번호 번호`
`!판매취소 번호` `!경매등록 아이템명 시작가` `!입찰 번호 금액` `!경매마감 번호` `!거래기록`

🔹 **파티**
`!파티생성` `!파티가입 @리더` `!파티정보`
`!파티사냥` `!파티탈퇴`

🔹 **펫**
`!펫` `!펫상점` `!펫구매 펫이름` `!펫목록` `!펫장착 펫이름`
`!펫정보 [펫이름]` `!펫훈련` `!펫먹이` `!펫모험` `!펫진화`
슬래시: `/펫 정보/상점/구매/목록/장착/훈련/먹이/모험/진화`

🔹 **퀘스트 / 시즌패스 / 업적**
`!일일퀘스트` `!퀘스트보상`
`!주간퀘스트` `!주간보상`
`!시즌패스` `!시즌보상 레벨`
`!업적`

🔹 **스토리 / 원정 / 도감 / 서버 설정**
`!스토리` `!스토리 시작` `!스토리 선택 번호` `!스토리 기록` `!스토리 재시작`
`!시즌2` `!시즌2 시작` `!시즌2 선택 번호` `!시즌2 기록` `!시즌2 재시작`
`!원정 도움말` `!원정 목록` `!원정 출발 지역명` `!원정 행동 공격/방어/집중/응급/도주`
`!원정 보급` `!원정 유물` `!원정 기록` `!원정 랭킹`
`!도감` `!도감 장비/펫/몬스터` `!도감보상` `!튜토리얼`
`!서버설정` `!서버세팅 미리보기/실행/상태/취소`
`!퀴즈알림설정` `!퀴즈알림상태` `!퀴즈알림해제`

🔹 **BLACK CASINO / 도박 / 금융**
`!카지노` `!카지노환전 구매/판매 금액` `!블랙잭` `!하이로우` `!슬롯` `!다이스` `!바카라`
`!럭키휠` `!코인플립 앞/뒤 금액` `!올인 앞/뒤` `!카지노미션` `!카지노상점`
`!룰렛 배팅액` `!주파수 배팅액` `!탐색 왼쪽/오른쪽 배팅액` `!파산신청`
`!은행` `!입금 금액` `!출금 금액` `!대출 금액` `!상환 금액`
`!사채` `!사채빌리기 금액` `!사채상환 금액` `!사채추심`
슬래시: `/카지노` `/은행` `/사채` `/암시장`
※ 카지노는 별도 칩을 사용합니다. 생존 룰렛 피격 시 식량이 최대 배팅액의 10배까지 감소하며 마이너스가 될 수 있습니다.

🔹 **알바 / 코인 / 실시간 암시장**
`!도박잔액` `!알바` `!코인` `!도박정보`
`!시세` `!매수 일반 10` `!매도`/`!코인판매`(드롭다운) `!자산` `!암시장기록`
`!암시장알림설정 [@역할]` `!암시장알림상태` `!암시장알림해제`
※ 시세는 전 서버 공통으로 1분마다 변동합니다.

🔹 **관리자**
`!가방조회 @유저` `!식량지급 @유저 금액`
`!식량회수 @유저 금액` `!월드보스리셋`
"""
    await send_pages(ctx.channel, text)

@bot.hybrid_command()
async def 정보(ctx):
    if not await check_registered(ctx):
        return

    u = get_user(ctx.author.id)
    total_power = calculate_user_power(u)
    inv_count = len(u["inventory"])
    active_pet_name, active_pet_record = get_pet_record(u)
    pet = (
        f"{get_pet_display_name(active_pet_name, active_pet_record)} Lv.{active_pet_record['level']}"
        if active_pet_name else "없음"
    )
    job_name = u.get("job") or "미선택"
    job_emoji = JOBS.get(job_name, {}).get("emoji", "👤")
    refresh_vitals(u)
    refresh_conditions(u, get_max_hp)
    max_hp = get_max_hp(u)
    max_stamina = get_max_stamina(u)
    save_data()

    await ctx.send(
        f"📊 **[{ctx.author.name} | {u['title']}]**\n"
        f"{job_emoji} 직업: **{job_name}**\n"
        f"🔹 레벨: **Lv.{u['level']}**\n"
        f"❤️ HP: **{u['hp']} / {max_hp}**\n"
        f"⚡ 스태미나: **{u['stamina']} / {max_stamina}**\n"
        f"🦠 감염도: **{u['infection']}%**\n"
        f"📌 상태: **{condition_text(u)}**\n"
        f"⚔️ 종합 전투력: **{total_power}**\n"
        f"🥫 식량: **{u['balance']:,}개**\n"
        f"🎒 장비 수: **{inv_count}개**\n"
        f"🐾 펫: **{pet}**\n"
        f"🏆 던전 승리: **{u['stats']['dungeon_wins']}회**"
    )


@bot.hybrid_command()
async def 지갑(ctx):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    debt = " 🚨 식량 빚 상태" if u["balance"] < 0 else ""
    await ctx.send(f"🥫 보유 식량: **{u['balance']:,}개**{debt}")


@bot.hybrid_command()
async def 송금(ctx, 대상: discord.Member, 금액: int):
    if not await check_registered(ctx):
        return

    sender = get_user(ctx.author.id)
    receiver = get_user(대상.id)

    if 대상.bot or 대상.id == ctx.author.id:
        await ctx.send("⚠️ 자기 자신이나 봇에게는 송금할 수 없습니다.")
        return
    if receiver is None:
        await ctx.send("⚠️ 상대방이 가입하지 않았습니다.")
        return
    if 금액 <= 0 or sender["balance"] < 금액:
        await ctx.send("⚠️ 금액이 잘못됐거나 잔액이 부족합니다.")
        return
    if sender["balance"] < 0:
        await ctx.send("⚠️ 빚이 있는 상태에서는 송금할 수 없습니다.")
        return

    sender["balance"] -= 금액
    receiver["balance"] += 금액
    save_data()

    await ctx.send(
        f"🤝 {ctx.author.mention} → {대상.mention}\n"
        f"생존 식량 **{금액:,}개** 송금 완료."
    )


# =========================================================
# 출석 / 구걸 / 훈련
# =========================================================
@bot.hybrid_command()
async def 출석(ctx):
    if not await check_registered(ctx):
        return

    u = get_user(ctx.author.id)
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    if u["last_attendance"] == today:
        await ctx.send("⚠️ 오늘은 이미 출석했습니다.")
        return

    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    if u["last_attendance"] == yesterday:
        u["attendance_streak"] += 1
    else:
        u["attendance_streak"] = 1

    streak_bonus = min(5000, u["attendance_streak"] * 150)
    bonus = 500 + u["level"] * 100 + streak_bonus
    milestone_bonus = 0
    milestone_text = ""
    if u["attendance_streak"] % 30 == 0:
        milestone_bonus = 15000
        add_season_points(u, 150)
        milestone_text = "\n🏆 **30일 연속 출석 보너스!** 식량 +15,000 / 시즌 +150P"
    elif u["attendance_streak"] % 14 == 0:
        milestone_bonus = 7000
        add_season_points(u, 70)
        milestone_text = "\n🎁 **14일 연속 출석 보너스!** 식량 +7,000 / 시즌 +70P"
    elif u["attendance_streak"] % 7 == 0:
        milestone_bonus = 3000
        add_season_points(u, 35)
        milestone_text = "\n✨ **7일 연속 출석 보너스!** 식량 +3,000 / 시즌 +35P"

    total_bonus = bonus + milestone_bonus
    u["last_attendance"] = today
    u["balance"] += total_bonus
    u["stats"]["earned"] += total_bonus
    add_season_points(u, 10)
    save_data()

    await ctx.send(
        f"📅 **[출석 완료]** {u['attendance_streak']}일 연속 출석!\n"
        f"오늘 지급 합계: **{total_bonus:,}개**\n"
        f"현재 잔액: **{u['balance']:,}개**" + milestone_text
    )


@bot.hybrid_command()
async def 출석보상(ctx):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    streak = u.get("attendance_streak", 0)
    next_bonus = min(5000, (streak + 1) * 150)
    await ctx.send(
        f"🎁 **[연속 출석 보상]**\n"
        f"현재 연속 출석: **{streak}일**\n"
        f"다음 출석 연속 보너스: **{next_bonus:,}개**\n"
        "7일·14일·30일째에는 시즌패스 포인트도 함께 쌓입니다."
    )

@bot.hybrid_command()
@commands.cooldown(1, 600, commands.BucketType.user)
async def 돈주세요(ctx):
    if not await check_registered(ctx):
        return

    u = get_user(ctx.author.id)
    reward = random.randint(0, 10000)
    u["balance"] += reward
    u["stats"]["earned"] += reward
    save_data()

    await ctx.send(
        f"🎁 떠돌이 상인이 식량 **{reward:,}개**를 던져줬습니다.\n"
        f"현재 잔액: **{u['balance']:,}개**"
    )


@bot.hybrid_command()
async def 훈련(ctx):
    if not await check_registered(ctx):
        return

    u = get_user(ctx.author.id)
    cost = u["level"] * 700

    if u["balance"] < cost:
        await ctx.send(f"⚠️ 훈련 비용 부족: **{cost:,}개** 필요")
        return

    u["balance"] -= cost
    u["level"] += 1
    save_data()

    await ctx.send(
        f"🎯 **[훈련 성공]** Lv.{u['level']} 달성!\n"
        f"전투력: **{calculate_user_power(u)}**"
    )


# =========================================================
# 상점 / 구매 / 인벤토리
# =========================================================
@bot.hybrid_command()
async def 상점(ctx, 티어: str = None):
    if not await check_registered(ctx):
        return

    tiers = [티어] if 티어 in ITEM_DB else TIER_ORDER
    text = "🛒 **[아포칼립스 암시장]**\n"

    for tier in tiers:
        text += f"\n🔹 **[{tier}]**\n"
        for item, info in ITEM_DB[tier].items():
            text += f"• {item} | {info['price']:,}개 | 전투력 +{info['power']}\n"

    text += "\n구매: `!구매 아이템명`"
    await send_pages(ctx.channel, text)


@bot.hybrid_command()
async def 장비목록(ctx, 티어: str = None):
    if not await check_registered(ctx):
        return

    tiers = [티어] if 티어 in ITEM_DB else TIER_ORDER
    text = "📋 **[장비 전체 목록]**\n"

    for tier in tiers:
        text += f"\n**[{tier}]**\n"
        for item, info in ITEM_DB[tier].items():
            text += f"• **{item}**: {info['desc']} / +{info['power']}\n"

    await send_pages(ctx.channel, text)


@bot.hybrid_command()
async def 구매(ctx, *, 아이템이름: str):
    if not await check_registered(ctx):
        return

    u = get_user(ctx.author.id)
    tier, item = find_item(아이템이름)

    if not item:
        await ctx.send("⚠️ 존재하지 않는 장비입니다.")
        return
    if 아이템이름 in u["inventory"]:
        await ctx.send("⚠️ 이미 보유한 장비입니다.")
        return
    if u["balance"] < item["price"]:
        await ctx.send(f"⚠️ 식량 부족: **{item['price']:,}개** 필요")
        return

    u["balance"] -= item["price"]
    u["inventory"].append(아이템이름)
    u["enhancements"].setdefault(아이템이름, 0)
    u["stats"]["items_bought"] += 1
    progress_quest(u, "아이템 구매")
    unlocked = check_achievements(u)
    save_data()

    msg = (
        f"🛍️ **[구매 성공]** {아이템이름} 획득!\n"
        f"티어: **{tier}** / 기본 전투력 +{item['power']}"
    )
    if unlocked:
        msg += "\n🏆 업적 달성: " + ", ".join(x[0] for x in unlocked)
    await ctx.send(msg)


@bot.hybrid_command()
async def 인벤토리(ctx):
    if not await check_registered(ctx):
        return

    u = get_user(ctx.author.id)
    equipped_names = {x for x in u.get("equipment", {}).values() if x}
    text = f"🎒 **[{ctx.author.name}님의 인벤토리]**\n"

    if not u["inventory"]:
        text += "보유 장비 없음\n"
    else:
        for item_name in u["inventory"]:
            tier, info = find_item(item_name)
            enhance = u["enhancements"].get(item_name, 0)
            slot = get_item_slot(item_name)
            mark = "✅ 장착" if item_name in equipped_names else "보관"
            text += (
                f"• {TIER_EMOJI.get(tier, '⚪')} [{tier}] {item_name} +{enhance} "
                f"| {slot} | {mark}\n"
            )

    text += (
        f"\n🥫 식량: **{u['balance']:,}개**"
        f"\n🧰 재료 종류: **{sum(1 for v in u.get('materials', {}).values() if v > 0)}종**"
        "\n사용: `!장착 아이템명` / `!버리기 아이템명`"
    )
    await send_pages(ctx.channel, text)


@bot.hybrid_command()
async def 장비(ctx):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    totals = equipment_totals(u)
    lines = ["⚔️ **[장비 현황]**"]
    for slot in EQUIPMENT_SLOTS:
        item = u["equipment"].get(slot)
        if item:
            tier, _ = find_item(item)
            enhance = u["enhancements"].get(item, 0)
            lines.append(f"• {slot}: {TIER_EMOJI.get(tier, '⚪')} **{item} +{enhance}**")
        else:
            lines.append(f"• {slot}: 비어 있음")
    lines.append(
        "\n📊 **장비 능력치**\n"
        f"공격력 +{totals['공격력']} | 방어력 +{totals['방어력']}\n"
        f"치명타 +{totals['치명타']}% | 회피 +{totals['회피']}%\n"
        f"감염저항 +{totals['감염저항']}% | 행운 +{totals['행운']}"
    )
    await ctx.send("\n".join(lines))


@bot.hybrid_command()
async def 장착(ctx, *, 아이템이름: str):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    if 아이템이름 not in u["inventory"]:
        await ctx.send("⚠️ 해당 장비를 보유하고 있지 않습니다.")
        return
    slot = get_item_slot(아이템이름)
    previous = u["equipment"].get(slot)
    u["equipment"][slot] = 아이템이름
    save_data()
    msg = f"✅ **{아이템이름}**을(를) **{slot}** 슬롯에 장착했습니다."
    if previous and previous != 아이템이름:
        msg += f"\n기존 장비 **{previous}**은 인벤토리로 돌아갔습니다."
    await ctx.send(msg)


@bot.hybrid_command()
async def 해제(ctx, *, 슬롯또는아이템: str):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    target_slot = None
    if 슬롯또는아이템 in EQUIPMENT_SLOTS:
        target_slot = 슬롯또는아이템
    else:
        for slot, item in u["equipment"].items():
            if item == 슬롯또는아이템:
                target_slot = slot
                break
    if not target_slot or not u["equipment"].get(target_slot):
        await ctx.send("⚠️ 해당 슬롯이나 장착 중인 아이템을 찾지 못했습니다.")
        return
    item = u["equipment"][target_slot]
    u["equipment"][target_slot] = None
    save_data()
    await ctx.send(f"📦 **{item}** 장착을 해제했습니다.")


@bot.hybrid_command()
async def 버리기(ctx, *, 아이템이름: str):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    if 아이템이름 not in u["inventory"]:
        await ctx.send("⚠️ 보유하지 않은 아이템입니다.")
        return
    if 아이템이름 in u.get("equipment", {}).values():
        await ctx.send("⚠️ 장착 중인 장비는 버릴 수 없습니다. 먼저 `!해제`하세요.")
        return
    tier, info = find_item(아이템이름)
    scrap = max(1, info["price"] // 20) if info else 1
    u["inventory"].remove(아이템이름)
    u["enhancements"].pop(아이템이름, None)
    u["balance"] += scrap
    save_data()
    await ctx.send(f"🗑️ **{아이템이름}**을 버리고 식량 **{scrap:,}개**를 회수했습니다.")


@bot.hybrid_command()
async def 감정(ctx, *, 아이템이름: str):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    if 아이템이름 not in u["inventory"]:
        await ctx.send("⚠️ 보유하지 않은 아이템입니다.")
        return
    tier, info = find_item(아이템이름)
    stats = get_item_stats(아이템이름)
    if 아이템이름 not in u["identified_items"]:
        cost = max(100, info["price"] // 25)
        if u["balance"] < cost:
            await ctx.send(f"⚠️ 감정 비용 **{cost:,}개**가 필요합니다.")
            return
        u["balance"] -= cost
        u["identified_items"].append(아이템이름)
        save_data()
    stat_text = ", ".join(f"{k} +{v}{'%' if k in ['치명타','회피','감염저항'] else ''}" for k, v in stats.items() if v)
    await ctx.send(
        f"🔍 **[장비 감정서]**\n"
        f"{TIER_EMOJI.get(tier, '⚪')} **[{tier}] {아이템이름}**\n"
        f"슬롯: **{get_item_slot(아이템이름)}**\n"
        f"설명: {info['desc']}\n"
        f"능력치: {stat_text or '특수 능력치 없음'}"
    )


# =========================================================
# 강화 시스템
# =========================================================
@bot.hybrid_command()
async def 강화(ctx, *, 아이템이름: str):
    if not await check_registered(ctx):
        return

    u = get_user(ctx.author.id)

    if 아이템이름 not in u["inventory"]:
        await ctx.send("⚠️ 해당 장비를 보유하고 있지 않습니다.")
        return

    current = u["enhancements"].get(아이템이름, 0)
    if current >= 20:
        await ctx.send("⚠️ 이미 최대 강화 수치 +20입니다.")
        return

    _, info = find_item(아이템이름)
    cost = int(info["price"] * (0.12 + current * 0.04))
    success_rate = max(15, 90 - current * 4)

    if u["balance"] < cost:
        await ctx.send(f"⚠️ 강화 비용 **{cost:,}개**가 필요합니다.")
        return

    u["balance"] -= cost
    roll = random.randint(1, 100)

    if roll <= success_rate:
        u["enhancements"][아이템이름] = current + 1
        u["stats"]["enhance_success"] += 1
        progress_quest(u, "강화 성공")
        result = f"✅ 강화 성공! **{아이템이름} +{current + 1}**"
    else:
        # +10 이상부터 낮은 확률로 1단계 하락
        if current >= 10 and random.random() < 0.35:
            u["enhancements"][아이템이름] = current - 1
            result = f"💥 강화 실패! 장비가 **+{current - 1}**로 하락했습니다."
        else:
            result = "❌ 강화 실패! 강화 수치는 유지됩니다."

    unlocked = check_achievements(u)
    save_data()

    msg = (
        f"🔨 **[강화 결과]**\n{result}\n"
        f"비용: {cost:,}개 / 성공 확률: {success_rate}%"
    )
    if unlocked:
        msg += "\n🏆 업적 달성: " + ", ".join(x[0] for x in unlocked)
    await ctx.send(msg)


# =========================================================
# 재료 / 제작
# =========================================================
@bot.hybrid_command()
async def 재료(ctx):
    if not await check_registered(ctx):
        return

    u = get_user(ctx.author.id)
    lines = [
        f"• {m}: {u['materials'].get(m, 0)}개"
        for m in MATERIALS
    ]
    await ctx.send("🧰 **[보유 재료]**\n" + "\n".join(lines))


@bot.hybrid_command()
async def 제작목록(ctx):
    if not await check_registered(ctx):
        return

    text = "🛠️ **[제작 레시피]**\n"
    for item, recipe in CRAFT_RECIPES.items():
        materials = ", ".join(f"{k} {v}개" for k, v in recipe.items())
        text += f"• **{item}**: {materials}\n"

    await send_pages(ctx.channel, text)


@bot.hybrid_command()
async def 제작(ctx, *, 아이템이름: str):
    if not await check_registered(ctx):
        return

    u = get_user(ctx.author.id)
    recipe = CRAFT_RECIPES.get(아이템이름)

    if not recipe:
        await ctx.send("⚠️ 제작 가능한 아이템이 아닙니다.")
        return
    if 아이템이름 in u["inventory"]:
        await ctx.send("⚠️ 이미 보유한 장비입니다.")
        return

    missing = []
    for material, amount in recipe.items():
        owned = u["materials"].get(material, 0)
        if owned < amount:
            missing.append(f"{material} {amount - owned}개")

    if missing:
        await ctx.send("⚠️ 부족한 재료: " + ", ".join(missing))
        return

    for material, amount in recipe.items():
        u["materials"][material] -= amount

    u["inventory"].append(아이템이름)
    u["enhancements"][아이템이름] = 0
    u["stats"]["craft_count"] += 1
    progress_quest(u, "제작 성공")
    unlocked = check_achievements(u)
    save_data()

    msg = f"🛠️ **[제작 성공]** {아이템이름} 완성!"
    if unlocked:
        msg += "\n🏆 업적 달성: " + ", ".join(x[0] for x in unlocked)
    await ctx.send(msg)


# =========================================================
# 펫 동료 시스템 V3.5
# =========================================================
async def _pet_shop_message(ctx):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    owned = ensure_pet_collection(u)
    lines = ["🐾 **[펫 동료 상점]**"]
    for name, info in PET_DB.items():
        marker = "✅ 보유" if name in owned else f"🥫 {info['price']:,}개"
        lines.append(
            f"{info['emoji']} **{name}** · {info['rarity']} · {marker}\n"
            f"└ 기본 전투력 +{info['power']} · **{info['skill']}**: {info['skill_desc']}"
        )
    lines.append("\n구매: `!펫구매 펫이름` 또는 `/펫 구매`")
    await send_pages(ctx.channel, "\n".join(lines))


async def _pet_buy(ctx, pet_name):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    pet_name = (pet_name or "").strip()
    info = PET_DB.get(pet_name)
    if not info:
        await ctx.send("⚠️ 존재하지 않는 펫입니다. `!펫상점` 또는 `/펫 상점`을 확인하세요.")
        return

    collection = ensure_pet_collection(u)
    if pet_name in collection:
        await ctx.send(f"⚠️ **{pet_name}**은(는) 이미 보유 중입니다. `!펫장착 {pet_name}`으로 동행시킬 수 있습니다.")
        return
    if u["balance"] < info["price"]:
        await ctx.send(f"⚠️ 식량 **{info['price']:,}개**가 필요합니다. 현재 **{u['balance']:,}개**")
        return

    u["balance"] -= info["price"]
    collection[pet_name] = _new_pet_record()
    if not u.get("pet"):
        u["pet"] = pet_name
        u["pet_level"] = 1
        equipped_text = "\n⭐ 첫 펫이라 자동으로 장착되었습니다."
    else:
        equipped_text = f"\n`!펫장착 {pet_name}` 또는 `/펫 장착`으로 교체할 수 있습니다."
    codex = u.setdefault("collection_codex", {}).setdefault("pets", [])
    if pet_name not in codex:
        codex.append(pet_name)
    save_data()
    await ctx.send(
        f"{info['emoji']} **{pet_name}**이(가) 새로운 동료가 되었습니다!\n"
        f"고유 능력: **{info['skill']}** — {info['skill_desc']}"
        f"{equipped_text}"
    )


async def _pet_list_message(ctx):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    collection = ensure_pet_collection(u)
    if not collection:
        await ctx.send("🐾 아직 보유한 펫이 없습니다. `!펫상점` 또는 `/펫 상점`을 확인하세요.")
        return

    owned_count = sum(1 for name in collection if name in PET_DB)
    lines = [f"🐾 **[{ctx.author.name}님의 펫 목록]** · {owned_count}/{len(PET_DB)}"]
    for name in PET_DB:
        if name not in collection:
            continue
        record = collection[name]
        info = PET_DB[name]
        active = "⭐" if u.get("pet") == name else "▫️"
        display = get_pet_display_name(name, record)
        lines.append(
            f"{active} {info['emoji']} **{display}** · Lv.{record['level']} · 친밀도 {record['friendship']} "
            f"· 전투력 +{get_pet_power(u, name)}"
        )
    lines.append("\n⭐ = 현재 동행 중 · 장착: `!펫장착 펫이름` 또는 `/펫 장착`")
    await send_pages(ctx.channel, "\n".join(lines))


async def _pet_equip(ctx, pet_name):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    pet_name = (pet_name or "").strip()
    collection = ensure_pet_collection(u)
    if pet_name not in collection:
        await ctx.send("⚠️ 보유하지 않은 펫입니다. `!펫목록` 또는 `/펫 목록`을 확인하세요.")
        return
    if pet_name not in PET_DB:
        await ctx.send("⚠️ 현재 버전에서 사용할 수 없는 펫입니다.")
        return
    if u.get("pet") == pet_name:
        await ctx.send(f"🐾 **{pet_name}**은(는) 이미 함께하고 있습니다.")
        return
    u["pet"] = pet_name
    u["pet_level"] = collection[pet_name]["level"]
    save_data()
    await ctx.send(f"⭐ {PET_DB[pet_name]['emoji']} **{get_pet_display_name(pet_name, collection[pet_name])}**을(를) 동행 펫으로 장착했습니다.")


async def _pet_info_message(ctx, pet_name=None):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    pet_name = (pet_name or "").strip() or None
    name, record = get_pet_record(u, pet_name)
    if not name:
        if pet_name:
            await ctx.send("⚠️ 보유하지 않은 펫입니다. `!펫목록` 또는 `/펫 목록`을 확인하세요.")
        else:
            await ctx.send("⚠️ 현재 동행 중인 펫이 없습니다. `!펫상점` 또는 `/펫 상점`을 확인하세요.")
        return

    info = PET_DB[name]
    required = pet_exp_required(record["level"]) if record["level"] < PET_MAX_LEVEL else 0
    feed_left = pet_cooldown_remaining(record, "last_feed", PET_FEED_COOLDOWN_MINUTES)
    adventure_left = pet_cooldown_remaining(record, "last_adventure", PET_ADVENTURE_COOLDOWN_MINUTES)
    evolution_text = ["기본", "1차 진화", "최종 진화"][record["evolution"]]
    exp_text = "MAX" if record["level"] >= PET_MAX_LEVEL else f"{record['exp']} / {required}"
    active_text = "⭐ 현재 동행 중" if u.get("pet") == name else "보유 중 · 미장착"

    await ctx.send(
        f"{info['emoji']} **[{get_pet_display_name(name, record)}]** · {info['rarity']}\n"
        f"상태: **{active_text}**\n"
        f"레벨: **Lv.{record['level']} / {PET_MAX_LEVEL}** · 경험치 **{exp_text}**\n"
        f"진화: **{evolution_text}** · 친밀도 **{record['friendship']}**\n"
        f"전투력 보너스: **+{get_pet_power(u, name)}**\n"
        f"고유 능력: **{info['skill']}** — {info['skill_desc']}\n"
        f"🍖 먹이: **{format_seconds(feed_left)}** · 🧭 모험: **{format_seconds(adventure_left)}**\n"
        f"설명: {info['desc']}"
    )


async def _pet_train(ctx):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    name, record = get_pet_record(u)
    if not name:
        await ctx.send("⚠️ 먼저 펫을 장착하세요.")
        return
    if record["level"] >= PET_MAX_LEVEL:
        await ctx.send(f"🏆 **{get_pet_display_name(name, record)}**은(는) 이미 최고 레벨입니다.")
        return

    rarity = PET_RARITY_ORDER.get(PET_DB[name]["rarity"], 1)
    cost = 1000 + record["level"] * 900 + rarity * 300
    if u["balance"] < cost:
        await ctx.send(f"⚠️ 훈련 비용 **식량 {cost:,}개**가 필요합니다. 현재 **{u['balance']:,}개**")
        return

    before_power = get_pet_power(u)
    u["balance"] -= cost
    record["level"] += 1
    record["friendship"] += 2
    u["pet_level"] = record["level"]
    after_power = get_pet_power(u)
    save_data()
    await ctx.send(
        f"🏋️ **[펫 훈련 완료]** {get_pet_display_name(name, record)} Lv.{record['level']} 달성!\n"
        f"전투력 **+{before_power} → +{after_power}** · 친밀도 **+2** · 식량 **-{cost:,}**"
    )


async def _pet_feed(ctx):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    name, record = get_pet_record(u)
    if not name:
        await ctx.send("⚠️ 먼저 펫을 장착하세요.")
        return
    remaining = pet_cooldown_remaining(record, "last_feed", PET_FEED_COOLDOWN_MINUTES)
    if remaining:
        await ctx.send(f"⏳ 다시 먹이를 줄 수 있을 때까지 **{format_seconds(remaining)}** 남았습니다.")
        return

    cost = 300 + record["level"] * 50
    if u["balance"] < cost:
        await ctx.send(f"⚠️ 먹이 비용 **식량 {cost:,}개**가 필요합니다.")
        return

    u["balance"] -= cost
    friendship_gain = random.randint(5, 9)
    exp_gain = random.randint(15, 25)
    record["friendship"] += friendship_gain
    record["last_feed"] = datetime.now().isoformat()
    level_ups = gain_pet_exp(u, exp_gain)
    save_data()
    level_text = f"\n🎉 펫 레벨이 **{level_ups}단계** 올랐습니다!" if level_ups else ""
    await ctx.send(
        f"🍖 **{get_pet_display_name(name, record)}**에게 먹이를 주었습니다.\n"
        f"친밀도 **+{friendship_gain}** · 펫 경험치 **+{exp_gain}** · 식량 **-{cost:,}**"
        f"{level_text}"
    )


async def _pet_adventure(ctx):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    name, record = get_pet_record(u)
    if not name:
        await ctx.send("⚠️ 먼저 펫을 장착하세요.")
        return
    remaining = pet_cooldown_remaining(record, "last_adventure", PET_ADVENTURE_COOLDOWN_MINUTES)
    if remaining:
        await ctx.send(f"⏳ 펫이 다시 모험을 떠날 때까지 **{format_seconds(remaining)}** 남았습니다.")
        return

    rarity = PET_RARITY_ORDER.get(PET_DB[name]["rarity"], 1)
    evolution = record["evolution"]
    food = random.randint(250, 650) + rarity * 100 + record["level"] * 15 + evolution * 300
    material_name = random.choice(MATERIALS)
    material_amount = random.randint(1, 2 + max(0, rarity // 3) + evolution)
    exp_gain = random.randint(25, 45) + rarity * 3
    friendship_gain = random.randint(2, 5)

    u["balance"] += food
    u.setdefault("stats", {}).setdefault("earned", 0)
    u["stats"]["earned"] += food
    u.setdefault("materials", {})
    u["materials"][material_name] = u["materials"].get(material_name, 0) + material_amount
    record["friendship"] += friendship_gain
    record["last_adventure"] = datetime.now().isoformat()
    level_ups = gain_pet_exp(u, exp_gain)
    save_data()

    level_text = f"\n🎉 모험 중 펫 레벨이 **{level_ups}단계** 올랐습니다!" if level_ups else ""
    await ctx.send(
        f"🧭 **[펫 모험 귀환]** {get_pet_display_name(name, record)}이(가) 무사히 돌아왔습니다.\n"
        f"🥫 식량 **+{food:,}개** · 🧰 {material_name} **+{material_amount}개**\n"
        f"✨ 펫 경험치 **+{exp_gain}** · 친밀도 **+{friendship_gain}**"
        f"{level_text}"
    )


async def _pet_evolve(ctx):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    name, record = get_pet_record(u)
    if not name:
        await ctx.send("⚠️ 먼저 펫을 장착하세요.")
        return
    stage = record["evolution"]
    if stage >= PET_MAX_EVOLUTION:
        await ctx.send(f"🌌 **{get_pet_display_name(name, record)}**은(는) 이미 최종 진화를 완료했습니다.")
        return

    requirements = [
        {"level": 10, "friendship": 30, "cost": 20000},
        {"level": 25, "friendship": 100, "cost": 80000},
    ][stage]
    missing = []
    if record["level"] < requirements["level"]:
        missing.append(f"레벨 {requirements['level']}")
    if record["friendship"] < requirements["friendship"]:
        missing.append(f"친밀도 {requirements['friendship']}")
    if u["balance"] < requirements["cost"]:
        missing.append(f"식량 {requirements['cost']:,}개")
    if missing:
        await ctx.send("⚠️ 진화 조건이 부족합니다: **" + " / ".join(missing) + "**")
        return

    before_name = get_pet_display_name(name, record)
    before_power = get_pet_power(u)
    u["balance"] -= requirements["cost"]
    record["evolution"] += 1
    after_name = get_pet_display_name(name, record)
    after_power = get_pet_power(u)
    save_data()
    await ctx.send(
        f"🌌 **[펫 진화 성공]**\n"
        f"{PET_DB[name]['emoji']} **{before_name} → {after_name}**\n"
        f"전투력 **+{before_power} → +{after_power}** · 식량 **-{requirements['cost']:,}개**"
    )


# 기존 최상위 ! 및 / 명령어 호환 유지
@bot.hybrid_command(description="구매 가능한 펫과 고유 능력을 확인합니다.")
async def 펫상점(ctx):
    await _pet_shop_message(ctx)


@bot.hybrid_command(description="새 펫을 구매해 컬렉션에 추가합니다.")
async def 펫구매(ctx, *, 펫이름: str):
    await _pet_buy(ctx, 펫이름)


@bot.hybrid_command(description="현재 동행 중이거나 보유한 펫의 정보를 확인합니다.")
async def 펫정보(ctx, *, 펫이름: str = None):
    await _pet_info_message(ctx, 펫이름)


@bot.hybrid_command(description="현재 동행 중인 펫을 한 단계 훈련합니다.")
async def 펫훈련(ctx):
    await _pet_train(ctx)


# 새로운 펫 명령어는 !최상위 명령어와 /펫 하위 명령어를 모두 지원합니다.
@bot.command(name="펫목록")
async def pet_list_legacy(ctx):
    await _pet_list_message(ctx)


@bot.command(name="펫장착")
async def pet_equip_legacy(ctx, *, 펫이름: str):
    await _pet_equip(ctx, 펫이름)


@bot.command(name="펫먹이")
async def pet_feed_legacy(ctx):
    await _pet_feed(ctx)


@bot.command(name="펫모험")
async def pet_adventure_legacy(ctx):
    await _pet_adventure(ctx)


@bot.command(name="펫진화")
async def pet_evolve_legacy(ctx):
    await _pet_evolve(ctx)


@bot.hybrid_group(name="펫", fallback="정보", invoke_without_command=True, description="펫 동료를 수집하고 성장시킵니다.")
async def pet_group(ctx, 펫이름: str = None):
    await _pet_info_message(ctx, 펫이름)


@pet_group.command(name="상점", description="구매 가능한 펫과 고유 능력을 확인합니다.")
async def pet_group_shop(ctx):
    await _pet_shop_message(ctx)


@pet_group.command(name="구매", description="새 펫을 구매해 컬렉션에 추가합니다.")
async def pet_group_buy(ctx, 펫이름: str):
    await _pet_buy(ctx, 펫이름)


@pet_group.command(name="목록", description="보유한 모든 펫과 성장 상태를 확인합니다.")
async def pet_group_list(ctx):
    await _pet_list_message(ctx)


@pet_group.command(name="장착", description="보유한 펫을 동행 펫으로 교체합니다.")
async def pet_group_equip(ctx, 펫이름: str):
    await _pet_equip(ctx, 펫이름)


@pet_group.command(name="훈련", description="현재 동행 중인 펫을 한 단계 훈련합니다.")
async def pet_group_train(ctx):
    await _pet_train(ctx)


@pet_group.command(name="먹이", description="펫에게 먹이를 주어 친밀도와 경험치를 올립니다.")
async def pet_group_feed(ctx):
    await _pet_feed(ctx)


@pet_group.command(name="모험", description="펫을 모험에 보내 식량과 재료를 획득합니다.")
async def pet_group_adventure(ctx):
    await _pet_adventure(ctx)


@pet_group.command(name="진화", description="레벨과 친밀도 조건을 충족한 펫을 진화시킵니다.")
async def pet_group_evolve(ctx):
    await _pet_evolve(ctx)


# =========================================================
# 던전 / 괴물 / 드롭 / 크리티컬 / 회피
# =========================================================
@bot.hybrid_command()
async def 괴물목록(ctx, 난이도: str = None):
    if not await check_registered(ctx):
        return

    difficulties = [난이도] if 난이도 in DUNGEONS else list(DUNGEONS.keys())
    text = "💀 **[괴물 도감]**\n"

    for diff in difficulties:
        d = DUNGEONS[diff]
        text += f"\n🚨 **[{diff}] {d['name']}**\n"
        for monster in d["monsters"]:
            text += f"• {monster['name']} — {monster['desc']}\n"

    await send_pages(ctx.channel, text)


@bot.hybrid_command()
@commands.cooldown(1, 180, commands.BucketType.user)
async def 던전(ctx, 난이도: str = None):
    if not await check_registered(ctx):
        return

    if 난이도 not in DUNGEONS:
        ctx.command.reset_cooldown(ctx)
        await ctx.send("⚠️ 사용법: `!던전 약함/보통/강함/지옥`")
        return

    u = get_user(ctx.author.id)
    ensure_dungeon_user_state(u)
    refresh_conditions(u, get_max_hp)
    if u["conditions"].get("기절", 0) > 0:
        ctx.command.reset_cooldown(ctx)
        await ctx.send("😵 기절 상태라 던전에 갈 수 없습니다. `!병원`에서 치료하세요.")
        return
    d = DUNGEONS[난이도]
    stamina_cost = DUNGEON_STAMINA_COSTS[난이도]
    if not spend_stamina(u, stamina_cost):
        ctx.command.reset_cooldown(ctx)
        await ctx.send(
            f"⚡ 스태미나가 부족합니다. **{stamina_cost}** 필요 / 현재 **{u['stamina']}**\n"
            "`!휴식` 또는 시간이 지난 뒤 다시 도전하세요."
        )
        return
    monster = random.choice(d["monsters"])

    user_power = calculate_user_power(u)
    monster_power = max(1, int(d["base_power"] * random.uniform(0.85, 1.25)))

    pet_bonus = get_pet_bonuses(u)
    crit = random.random() < min(0.45, 0.08 + u["level"] * 0.003 + pet_bonus["crit"])
    dodge = random.random() < min(0.40, 0.06 + pet_bonus["dodge"])

    effective_power = int(user_power * (1.7 if crit else 1.0))
    victory_chance = 0.15
    if effective_power >= monster_power:
        victory_chance += 0.65
    else:
        ratio = effective_power / max(monster_power, 1)
        victory_chance += min(0.45, ratio * 0.45)

    if dodge:
        victory_chance += 0.15
    victory_chance += pet_bonus["victory"]

    victory_chance *= exploration_modifier(u)
    victory = random.random() < min(0.95, victory_chance)

    await ctx.send(
        f"⚔️ **[{d['name']}]**\n"
        f"🚨 {monster['name']} 출현!\n"
        f"내 전투력: **{user_power}** / 적 전투력: **{monster_power}**"
    )
    await asyncio.sleep(1.5)

    if victory:
        reward = int(d["reward"] * random.uniform(0.85, 1.25) * (1.0 + pet_bonus["reward"]))
        u["balance"] += reward
        u["stats"]["earned"] += reward
        u["stats"]["dungeon_wins"] += 1
        u.setdefault("dungeon_monster_kills", {})
        u["dungeon_monster_kills"][monster["name"]] = u["dungeon_monster_kills"].get(monster["name"], 0) + 1
        progress_quest(u, "던전 승리")
        progress_weekly(u, "던전 승리")
        add_season_points(u, {"약함": 5, "보통": 8, "강함": 12, "지옥": 20}[난이도])

        gained = random_materials(난이도)
        pet_material = None
        if random.random() < pet_bonus["material"]:
            pet_material = random.choice(MATERIALS)
            gained[pet_material] = gained.get(pet_material, 0) + 1
        give_materials(u, gained)

        drop_message = ""
        drop_chance = {
            "약함": 0.12,
            "보통": 0.18,
            "강함": 0.26,
            "지옥": 0.38
        }[난이도]

        if random.random() < drop_chance:
            tier, dropped_item = select_drop(d["drop_tiers"])
            if dropped_item not in u["inventory"]:
                u["inventory"].append(dropped_item)
                u["enhancements"][dropped_item] = 0
                drop_message = f"\n🎁 장비 드롭: **[{tier}] {dropped_item}**"
            else:
                duplicate_reward = ITEM_DB[tier][dropped_item]["price"] // 5
                u["balance"] += duplicate_reward
                drop_message = f"\n♻️ 중복 장비 환전: **{duplicate_reward:,}개**"

        event_text = []
        if crit:
            event_text.append("💥 크리티컬")
        if dodge:
            event_text.append("💨 회피")
        event_line = " / ".join(event_text) if event_text else "정면 승부"

        materials_text = ", ".join(f"{k} {v}개" for k, v in gained.items())
        battle_damage = 0 if dodge else random.randint(1, {
            "약함": 5, "보통": 9, "강함": 14, "지옥": 20
        }[난이도])
        damage_taken, knocked_out = apply_damage(u, battle_damage)
        pet_healed = 0
        if pet_bonus["heal"] > 0 and u.get("hp", 0) > 0:
            pet_healed = min(pet_bonus["heal"], max(0, get_max_hp(u) - u["hp"]))
            u["hp"] += pet_healed
        pet_exp = {"약함": 8, "보통": 12, "강함": 18, "지옥": 28}[난이도]
        pet_level_ups = gain_pet_exp(u, pet_exp)
        condition_events = apply_dungeon_conditions(u, 난이도, True)
        unlocked = check_achievements(u)
        save_data()

        msg = (
            f"🎉 **[승리]** {event_line}\n"
            f"🥫 식량 +{reward:,}개\n"
            f"🧰 재료: {materials_text}"
            f"{drop_message}\n"
            f"❤️ 전투 피해: **-{damage_taken}** | HP **{u['hp']} / {get_max_hp(u)}**\n"
            f"⚡ 스태미나: **-{stamina_cost}** | 현재 **{u['stamina']} / {get_max_stamina(u)}**"
        )
        if pet_material:
            msg += f"\n🐾 펫이 추가 재료 **{pet_material} 1개**를 발견했습니다."
        if pet_healed:
            msg += f"\n🐾 펫의 능력으로 HP **+{pet_healed}** 회복"
        if u.get("pet"):
            msg += f"\n✨ 펫 경험치 **+{pet_exp}**"
            if pet_level_ups:
                msg += f" · 레벨 **+{pet_level_ups}**"
        if condition_events:
            msg += "\n⚠️ " + " / ".join(condition_events)
        msg += f"\n🦠 감염도 **{u['infection']}%** | {condition_text(u)}"
        if unlocked:
            msg += "\n🏆 업적 달성: " + ", ".join(x[0] for x in unlocked)
        await ctx.send(msg)
    else:
        penalty = int(d["reward"] * random.uniform(0.18, 0.35))
        damage = random.randint({"약함": 12, "보통": 20, "강함": 30, "지옥": 42}[난이도],
                                {"약함": 24, "보통": 36, "강함": 50, "지옥": 70}[난이도])
        damage_taken, knocked_out = apply_damage(u, damage)
        u["balance"] -= penalty
        u["stats"]["dungeon_losses"] += 1
        pet_exp = {"약함": 3, "보통": 5, "강함": 7, "지옥": 10}[난이도]
        pet_level_ups = gain_pet_exp(u, pet_exp)
        condition_events = apply_dungeon_conditions(u, 난이도, False)
        save_data()

        knockout_text = (
            "\n🚑 HP가 0이 되어 구조대에게 발견됐습니다. "
            f"HP가 **{u['hp']}**까지 회복됐습니다."
            if knocked_out else ""
        )
        await ctx.send(
            f"💀 **[패배]** 식량 **{penalty:,}개** 상실.\n"
            f"❤️ 피해 **-{damage_taken}** | HP **{u['hp']} / {get_max_hp(u)}**\n"
            f"⚡ 스태미나 **-{stamina_cost}** | 현재 **{u['stamina']} / {get_max_stamina(u)}**\n"
            f"현재 잔액: **{u['balance']:,}개**"
            f"{knockout_text}"
            + (f"\n✨ 펫 경험치 **+{pet_exp}**" + (f" · 레벨 **+{pet_level_ups}**" if pet_level_ups else "") if u.get("pet") else "")
            + ("\n⚠️ " + " / ".join(condition_events) if condition_events else "")
            + f"\n🦠 감염도 **{u['infection']}%** | {condition_text(u)}"
        )


# =========================================================
# 서버 레이드
# =========================================================
@bot.hybrid_command()
async def 레이드(ctx):
    if not await check_registered(ctx):
        return

    boss = get_server_boss(ctx.guild.id)
    await ctx.send(
        f"👹 **[서버 레이드] {boss['name']}**\n"
        f"HP: **{boss['hp']:,} / {boss['max_hp']:,}**\n"
        "`!레이드공격`으로 공격하세요. 쿨타임 60초."
    )


@bot.hybrid_command()
@commands.cooldown(1, 60, commands.BucketType.user)
async def 레이드공격(ctx):
    if not await check_registered(ctx):
        return

    u = get_user(ctx.author.id)
    boss = get_server_boss(ctx.guild.id)

    base = calculate_user_power(u)
    damage = random.randint(max(1, base // 2), max(2, int(base * 1.4)))
    critical = random.random() < 0.15

    if critical:
        damage *= 2

    damage = min(damage, boss["hp"])
    boss["hp"] -= damage

    uid = str(ctx.author.id)
    boss["participants"][uid] = boss["participants"].get(uid, 0) + damage
    u["stats"]["boss_damage"] += damage

    message = (
        f"⚔️ {ctx.author.mention} 공격!\n"
        f"데미지: **{damage:,}**{' 💥크리티컬' if critical else ''}\n"
        f"보스 HP: **{boss['hp']:,} / {boss['max_hp']:,}**"
    )

    if boss["hp"] <= 0:
        participants = boss["participants"]
        total_damage = sum(participants.values())

        for participant_id, dealt in participants.items():
            pu = get_user(participant_id)
            if not pu:
                continue

            reward = 5000 + int(25000 * (dealt / max(1, total_damage)))
            pu["balance"] += reward
            pu["stats"]["earned"] += reward

        killer_reward = 10000
        u["balance"] += killer_reward
        u["stats"]["earned"] += killer_reward
        add_title(u, "레이드 최후의 일격")

        guild_id = str(ctx.guild.id)
        del world_data["server_bosses"][guild_id]
        message += (
            f"\n\n🏆 **레이드 보스 처치!**\n"
            f"참가자 보상 분배 완료.\n"
            f"마지막 일격 추가 보상: **{killer_reward:,}개**"
        )

    unlocked = check_achievements(u)
    save_data()

    if unlocked:
        message += "\n🏆 업적 달성: " + ", ".join(x[0] for x in unlocked)
    await ctx.send(message)


# =========================================================
# 전 서버 월드보스 V2.0-8
# =========================================================
def _world_boss_rows(boss):
    rows = []
    for uid, record in boss.get("participants", {}).items():
        if isinstance(record, dict):
            rows.append((uid, int(record.get("damage", 0)), int(record.get("attacks", 0))))
        else:
            rows.append((uid, int(record), 0))
    return sorted(rows, key=lambda x: x[1], reverse=True)


def _world_boss_bar(hp, max_hp, size=18):
    ratio = max(0.0, min(1.0, hp / max(1, max_hp)))
    filled = int(ratio * size)
    return "█" * filled + "░" * (size - filled)


def _grant_world_boss_drop(u, boss, rank):
    material = boss.get("material", "고대파편")
    material_amount = max(1, 8 - min(rank, 7))
    u.setdefault("materials", {})[material] = u.setdefault("materials", {}).get(material, 0) + material_amount

    item = None
    roll = random.random()
    if rank == 1 and roll < 0.18:
        item = random.choice(list(ITEM_DB["전설"].keys()))
    elif rank <= 3 and roll < 0.08:
        item = random.choice(list(ITEM_DB["영웅"].keys()))
    elif roll < 0.02:
        item = random.choice(list(ITEM_DB["희귀"].keys()))
    if item:
        u.setdefault("inventory", []).append(item)
    return material, material_amount, item


@bot.hybrid_command(name="월드보스", aliases=["보스현황"])
async def 월드보스(ctx):
    if not await check_registered(ctx):
        return

    boss = migrate_world_boss(world_data.get("world_boss"))
    world_data["world_boss"] = boss
    rows = _world_boss_rows(boss)
    ranking = [f"{i}. <@{uid}> — **{damage:,}** 피해 / {attacks}회" for i, (uid, damage, attacks) in enumerate(rows[:5], 1)]
    rank_text = "\n".join(ranking) if ranking else "아직 참가자 없음"
    percent = boss["hp"] / max(1, boss["max_hp"]) * 100
    status = "전투 중" if boss.get("status") == "active" and boss["hp"] > 0 else "처치 완료"

    await ctx.send(
        f"🌍 **[{boss['grade']} 월드보스] {boss['name']}**\n"
        f"상태: **{status}** | 특성: **{boss['trait']}**\n"
        f"HP: **{boss['hp']:,} / {boss['max_hp']:,}** ({percent:.1f}%)\n"
        f"`{_world_boss_bar(boss['hp'], boss['max_hp'])}`\n\n"
        f"🏅 **누적 피해 TOP 5**\n{rank_text}\n\n"
        "공격: `!보스공격` 또는 `!월드보스공격` · 개인 쿨타임 5분"
    )


@bot.hybrid_command(name="보스랭킹", aliases=["월드보스랭킹"])
async def 보스랭킹(ctx):
    if not await check_registered(ctx):
        return
    boss = migrate_world_boss(world_data.get("world_boss"))
    rows = _world_boss_rows(boss)
    if not rows:
        await ctx.send("📭 아직 월드보스 공격 기록이 없습니다.")
        return
    lines = [f"{i}. <@{uid}> — **{damage:,}** 피해 / {attacks}회" for i, (uid, damage, attacks) in enumerate(rows[:20], 1)]
    await ctx.send(f"🏆 **{boss['name']} 피해 랭킹**\n" + "\n".join(lines))


@bot.hybrid_command(name="월드보스공격", aliases=["보스공격"])
@commands.cooldown(1, 300, commands.BucketType.user)
async def 월드보스공격(ctx):
    if not await check_registered(ctx):
        return

    u = get_user(ctx.author.id)
    boss = migrate_world_boss(world_data.get("world_boss"))
    world_data["world_boss"] = boss
    u.setdefault("worldboss_codex", {})
    codex = u["worldboss_codex"].setdefault(boss["name"], {"damage": 0, "attacks": 0, "kills": 0})

    if boss.get("status") != "active" or boss["hp"] <= 0:
        ctx.command.reset_cooldown(ctx)
        await ctx.send("⚠️ 월드보스가 이미 처치되었습니다. 다음 소환을 기다려 주세요.")
        return

    power = max(1, calculate_user_power(u))
    trait = boss.get("trait", "")
    defense_rate = 0.18 if trait in {"중장갑", "전자 방벽"} else 0.08
    damage = random.randint(max(1, int(power * 1.4)), max(2, int(power * 3.6)))
    damage = max(1, int(damage * (1.0 - defense_rate)))

    totals = equipment_totals(u)
    critical_rate = min(0.35, 0.10 + totals.get("치명타", 0) / 250)
    critical = random.random() < critical_rate
    if critical:
        damage = int(damage * 2.5)

    pattern_text = ""
    hp_ratio = boss["hp"] / max(1, boss["max_hp"])
    if hp_ratio <= 0.30:
        damage = int(damage * 1.20)
        pattern_text = "\n🔥 보스가 광폭화했습니다! 가한 피해도 20% 증가합니다."
    if random.random() < 0.14:
        trait = boss.get("trait", "")
        if trait in {"중장갑", "전자 방벽", "피의 장막"}:
            damage = max(1, int(damage * 0.55))
            pattern_text += f"\n🛡️ **{trait}** 패턴으로 피해가 감소했습니다."
        elif trait in {"재생"}:
            heal = min(int(boss["max_hp"] * 0.015), boss["max_hp"] - boss["hp"])
            boss["hp"] += heal
            pattern_text += f"\n💚 **재생** 패턴: HP {heal:,} 회복."
        elif trait in {"감염폭풍", "광폭화"}:
            infection = random.randint(2, 6)
            u["infection"] = min(100, u.get("infection", 0) + infection)
            pattern_text += f"\n☣️ **{trait}** 패턴: 감염도 +{infection}."

    damage = min(damage, boss["hp"])
    boss["hp"] -= damage
    uid = str(ctx.author.id)
    record = boss["participants"].setdefault(uid, {"damage": 0, "attacks": 0, "last_hit": False})
    record["damage"] += damage
    record["attacks"] += 1
    u.setdefault("stats", {}).setdefault("worldboss_damage", 0)
    u["stats"]["worldboss_damage"] += damage
    codex["damage"] += damage
    codex["attacks"] += 1

    message = (
        f"⚔️ {ctx.author.mention}이(가) **{boss['name']}**을 공격했습니다!\n"
        f"피해량: **{damage:,}**{' 💥 치명타!' if critical else ''}\n"
        f"남은 HP: **{boss['hp']:,} / {boss['max_hp']:,}**"
        f"{pattern_text}"
    )

    if boss["hp"] <= 0:
        boss["status"] = "defeated"
        boss["defeated_at"] = datetime.now().isoformat()
        record["last_hit"] = True
        rows = _world_boss_rows(boss)
        total_damage = sum(row[1] for row in rows)
        reward_lines = []

        for rank, (participant_id, dealt, attacks) in enumerate(rows, 1):
            pu = get_user(participant_id)
            if not pu:
                continue
            participation = 12000
            share = int(90000 * dealt / max(1, total_damage))
            rank_bonus = 50000 if rank == 1 else 25000 if rank <= 3 else 8000 if rank <= 10 else 0
            food = participation + share + rank_bonus
            exp = 600 + max(0, 2200 - (rank - 1) * 150)
            pu["balance"] = pu.get("balance", 0) + food
            pu["exp"] = pu.get("exp", 0) + exp
            pu.setdefault("stats", {}).setdefault("earned", 0)
            pu["stats"]["earned"] += food
            material, material_amount, item = _grant_world_boss_drop(pu, boss, rank)
            if rank == 1:
                add_title(pu, "월드보스 1위")
            elif rank <= 3:
                add_title(pu, "월드보스 정복자")
            if participant_id == uid:
                reward_lines.append(f"내 보상: 식량 **{food:,}** · 경험치 **{exp:,}** · {material} **{material_amount}개**")
                if item:
                    reward_lines.append(f"🎁 특별 장비 획득: **{item}**")

        add_title(u, "종말을 끝낸 자")
        codex["kills"] += 1
        message += "\n\n🏆 **월드보스 처치! 참가자 전원에게 기여도 보상이 지급되었습니다.**"
        if reward_lines:
            message += "\n" + "\n".join(reward_lines)

    unlocked = check_achievements(u)
    save_data()
    if unlocked:
        message += "\n🏆 업적 달성: " + ", ".join(x[0] for x in unlocked)
    await ctx.send(message)


async def _require_world_boss_admin(ctx):
    if ctx.guild and (ctx.author == ctx.guild.owner or ctx.author.guild_permissions.administrator):
        return True
    await ctx.send("❌ 관리자 전용 명령어입니다.")
    return False


@bot.hybrid_command(name="월드보스리셋", aliases=["월드보스소환"])
async def 월드보스리셋(ctx, *, 보스이름: str = None):
    if not await _require_world_boss_admin(ctx):
        return
    boss = create_world_boss(보스이름)
    world_data["world_boss"] = boss
    save_data()
    await ctx.send(f"🌍 **{boss['grade']} 월드보스 {boss['name']}**이(가) 소환되었습니다!\nHP: **{boss['max_hp']:,}** · 특성: **{boss['trait']}**")


@bot.hybrid_command(name="월드보스체력")
async def 월드보스체력(ctx, 체력: int):
    if not await _require_world_boss_admin(ctx):
        return
    if 체력 < 1:
        await ctx.send("⚠️ 체력은 1 이상이어야 합니다.")
        return
    boss = migrate_world_boss(world_data.get("world_boss"))
    boss["max_hp"] = 체력
    boss["hp"] = 체력
    boss["status"] = "active"
    world_data["world_boss"] = boss
    save_data()
    await ctx.send(f"❤️ 월드보스 체력을 **{체력:,}**으로 설정했습니다.")


@bot.hybrid_command(name="월드보스종료")
async def 월드보스종료(ctx):
    if not await _require_world_boss_admin(ctx):
        return
    boss = migrate_world_boss(world_data.get("world_boss"))
    boss["hp"] = 0
    boss["status"] = "defeated"
    boss["defeated_at"] = datetime.now().isoformat()
    world_data["world_boss"] = boss
    save_data()
    await ctx.send(f"🛑 **{boss['name']}** 월드보스를 관리자 권한으로 종료했습니다.")


# =========================================================
# 일일 퀘스트 / 업적 / 칭호
# =========================================================
@bot.hybrid_command()
async def 일일퀘스트(ctx):
    if not await check_registered(ctx):
        return

    u = get_user(ctx.author.id)
    q = u["daily_quest"]
    status = "완료" if q["progress"] >= q["target"] else "진행 중"
    claimed = " / 보상 수령 완료" if q["claimed"] else ""

    await ctx.send(
        f"📌 **[오늘의 퀘스트]**\n"
        f"내용: **{q['type']} {q['target']}회**\n"
        f"진행: **{q['progress']} / {q['target']}**\n"
        f"보상: **식량 {q['reward']:,}개**\n"
        f"상태: **{status}{claimed}**"
    )


@bot.hybrid_command()
async def 퀘스트보상(ctx):
    if not await check_registered(ctx):
        return

    u = get_user(ctx.author.id)
    q = u["daily_quest"]

    if q["claimed"]:
        await ctx.send("⚠️ 오늘의 퀘스트 보상은 이미 받았습니다.")
        return
    if q["progress"] < q["target"]:
        await ctx.send("⚠️ 아직 퀘스트를 완료하지 못했습니다.")
        return

    q["claimed"] = True
    u["balance"] += q["reward"]
    u["stats"]["earned"] += q["reward"]
    save_data()

    await ctx.send(f"🎁 퀘스트 보상 **{q['reward']:,}개** 수령 완료!")


@bot.hybrid_command()
async def 업적(ctx):
    if not await check_registered(ctx):
        return

    u = get_user(ctx.author.id)
    check_achievements(u)
    save_data()

    text = "🏆 **[업적]**\n"
    for name, (stat_key, target, title) in ACHIEVEMENTS.items():
        done = "✅" if name in u["achievements"] else "⬜"
        progress = min(u["stats"].get(stat_key, 0), target)
        text += (
            f"{done} **{name}** — {progress:,}/{target:,} "
            f"| 칭호: {title}\n"
        )

    await send_pages(ctx.channel, text)


@bot.hybrid_command()
async def 칭호목록(ctx):
    if not await check_registered(ctx):
        return

    u = get_user(ctx.author.id)
    await send_pages(
        ctx.channel,
        "🏷️ **[보유 칭호]**\n" + "\n".join(f"• {x}" for x in u["titles"])
    )


@bot.hybrid_command()
async def 칭호(ctx, *, 칭호이름: str):
    if not await check_registered(ctx):
        return

    u = get_user(ctx.author.id)

    if 칭호이름 not in u["titles"]:
        await ctx.send("⚠️ 보유하지 않은 칭호입니다.")
        return

    u["title"] = 칭호이름
    save_data()
    await ctx.send(f"🏷️ 대표 칭호를 **{칭호이름}**으로 변경했습니다.")


# =========================================================
# 시즌 랭킹
# =========================================================
@bot.hybrid_command()
async def 랭킹(ctx):
    if not await check_registered(ctx):
        return

    ranking = sorted(
        user_data.items(),
        key=lambda x: calculate_user_power(migrate_user(x[1])),
        reverse=True
    )[:10]

    lines = []
    for i, (uid, u) in enumerate(ranking, 1):
        lines.append(
            f"{i}. <@{uid}> | {u['title']} | "
            f"전투력 **{calculate_user_power(u):,}** | Lv.{u['level']}"
        )

    await ctx.send(
        f"🏆 **[{world_data['season']} 시즌 전투력 랭킹]**\n" +
        ("\n".join(lines) if lines else "랭킹 데이터 없음")
    )


# =========================================================
# 도박 시스템
# =========================================================
@bot.hybrid_command()
@commands.cooldown(1, 60, commands.BucketType.user)
async def 탐색(ctx, 방향: str, 배팅액: int):
    if not await check_registered(ctx):
        return

    u = get_user(ctx.author.id)

    if 방향 not in ["왼쪽", "오른쪽"]:
        ctx.command.reset_cooldown(ctx)
        await ctx.send("⚠️ 사용법: `!탐색 왼쪽 1000`")
        return
    if 배팅액 <= 0 or u["balance"] < 배팅액:
        ctx.command.reset_cooldown(ctx)
        await ctx.send("⚠️ 배팅액이 잘못됐거나 식량이 부족합니다.")
        return

    u["stats"]["gambles"] += 1
    progress_quest(u, "도박 참여")

    if random.random() < 0.5:
        reward = 배팅액 * random.choice([1, 1, 2, 3])
        u["balance"] += reward
        u["stats"]["earned"] += reward
        result = f"📦 성공! 식량 **{reward:,}개** 획득."
    else:
        u["balance"] -= 배팅액
        result = f"🩸 실패! 식량 **{배팅액:,}개** 상실."

    save_data()
    await ctx.send(result)


@bot.hybrid_command()
@commands.cooldown(1, 60, commands.BucketType.user)
async def 주파수(ctx, 배팅액: int):
    if not await check_registered(ctx):
        return

    u = get_user(ctx.author.id)

    if 배팅액 <= 0 or u["balance"] < 배팅액:
        ctx.command.reset_cooldown(ctx)
        await ctx.send("⚠️ 배팅액이 잘못됐거나 잔액이 부족합니다.")
        return

    signals = ["🔴", "🟢", "🔵", "⚡", "💀"]
    result = [random.choice(signals) for _ in range(3)]
    screen = f"**[ {' | '.join(result)} ]**\n"

    u["stats"]["gambles"] += 1
    progress_quest(u, "도박 참여")

    if len(set(result)) == 1:
        if result[0] == "💀":
            loss = 배팅액 * 3
            u["balance"] -= loss
            message = f"☠️ 저주받은 신호! **{loss:,}개** 상실."
        else:
            multiplier = random.randint(5, 20)
            gain = 배팅액 * multiplier
            u["balance"] += gain
            u["stats"]["earned"] += gain
            message = f"📡 잭팟 {multiplier}배! **{gain:,}개** 획득."
    elif len(set(result)) == 2:
        gain = 배팅액 // 2
        u["balance"] += gain
        u["stats"]["earned"] += gain
        message = f"📻 부분 일치! **{gain:,}개** 획득."
    else:
        u["balance"] -= 배팅액
        message = f"📵 통신 실패! **{배팅액:,}개** 상실."

    save_data()
    await ctx.send(screen + message)


roulette_state = {}


@bot.hybrid_command()
@commands.cooldown(1, 60, commands.BucketType.user)
async def 룰렛(ctx, 배팅액: int):
    if not await check_registered(ctx):
        return

    u = get_user(ctx.author.id)

    if 배팅액 <= 0 or u["balance"] < 배팅액:
        ctx.command.reset_cooldown(ctx)
        await ctx.send("⚠️ 배팅액이 잘못됐거나 잔액이 부족합니다.")
        return

    guild_id = str(ctx.guild.id)
    if guild_id not in roulette_state:
        roulette_state[guild_id] = {
            "bullet": random.randint(1, 6),
            "chamber": 1
        }

    state = roulette_state[guild_id]
    u["stats"]["gambles"] += 1
    progress_quest(u, "도박 참여")

    if state["chamber"] == state["bullet"]:
        u["balance"] -= 배팅액
        del roulette_state[guild_id]
        result = f"💥 **탕!** 식량 **{배팅액:,}개** 상실."
    else:
        multiplier = random.randint(2, 8)
        gain = 배팅액 * multiplier
        u["balance"] += gain
        u["stats"]["earned"] += gain
        state["chamber"] += 1
        result = f"💨 생존! {multiplier}배 보상 **{gain:,}개** 획득."

    save_data()
    await ctx.send(result)


@bot.hybrid_command()
@commands.cooldown(1, 3600, commands.BucketType.user)
async def 파산신청(ctx):
    if not await check_registered(ctx):
        return

    u = get_user(ctx.author.id)

    if u["balance"] >= 0:
        ctx.command.reset_cooldown(ctx)
        await ctx.send("⚠️ 빚이 없어 파산 신청이 불가능합니다.")
        return

    debt = abs(u["balance"])
    rate = random.randint(10, 100)
    forgiven = int(debt * rate / 100)
    u["balance"] += forgiven

    if u["balance"] > 0:
        u["balance"] = 0

    save_data()

    await ctx.send(
        f"⚖️ 빚의 **{rate}%** 탕감!\n"
        f"남은 빚: **{abs(min(0, u['balance'])):,}개**"
    )


# =========================================================
# 관리자 명령어
# =========================================================
@bot.hybrid_command()
async def 가방조회(ctx, 대상: discord.Member):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ 관리자 전용 명령어입니다.")
        return

    u = get_user(대상.id)
    if not u:
        await ctx.send("⚠️ 가입하지 않은 유저입니다.")
        return

    await ctx.send(
        f"🔍 **[{대상.name}]**\n"
        f"식량: {u['balance']:,}개\n"
        f"레벨: {u['level']}\n"
        f"전투력: {calculate_user_power(u)}\n"
        f"장착 장비: {', '.join(x for x in u.get('equipment', {}).values() if x) or '없음'}"
    )


@bot.hybrid_command()
async def 식량지급(ctx, 대상: discord.Member, 금액: int):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ 관리자 전용 명령어입니다.")
        return

    u = get_user(대상.id)
    if not u:
        await ctx.send("⚠️ 가입하지 않은 유저입니다.")
        return
    if 금액 <= 0:
        await ctx.send("⚠️ 1 이상의 금액을 입력하세요.")
        return

    u["balance"] += 금액
    u["stats"]["earned"] += 금액
    save_data()

    await ctx.send(f"✅ {대상.mention}에게 식량 **{금액:,}개** 지급.")


@bot.hybrid_command()
async def 식량회수(ctx, 대상: discord.Member, 금액: int):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ 관리자 전용 명령어입니다.")
        return

    u = get_user(대상.id)
    if not u:
        await ctx.send("⚠️ 가입하지 않은 유저입니다.")
        return
    if 금액 <= 0:
        await ctx.send("⚠️ 1 이상의 금액을 입력하세요.")
        return

    u["balance"] -= 금액
    save_data()

    await ctx.send(f"✅ {대상.mention}에게서 식량 **{금액:,}개** 회수.")



# =========================================================
# 채집 생활: 채집 / 낚시 / 벌목 / 광산
# =========================================================
LIFE_TABLES = {
    "채집": [
        ("약초", 1, 4, 50),
        ("고철", 1, 3, 40),
        ("식량", 300, 1200, 10),
    ],
    "낚시": [
        ("물고기", 1, 5, 75),
        ("식량", 500, 2500, 25),
    ],
    "벌목": [
        ("나무", 2, 6, 85),
        ("고철", 1, 2, 15),
    ],
    "광산": [
        ("광석", 2, 6, 75),
        ("고철", 1, 4, 20),
        ("식량", 1000, 4000, 5),
    ],
}


async def perform_life_activity(ctx, activity):
    if not await check_registered(ctx):
        return

    u = get_user(ctx.author.id)
    refresh_conditions(u, get_max_hp)
    if u["conditions"].get("기절", 0) > 0:
        if ctx.command:
            ctx.command.reset_cooldown(ctx)
        await ctx.send("😵 기절 상태라 생활 활동을 할 수 없습니다. `!병원`에서 치료하세요.")
        return
    stamina_cost = LIFE_STAMINA_COSTS[activity]
    if not spend_stamina(u, stamina_cost):
        if ctx.command:
            ctx.command.reset_cooldown(ctx)
        await ctx.send(
            f"⚡ 스태미나가 부족합니다. **{stamina_cost}** 필요 / 현재 **{u['stamina']}**\n"
            "`!휴식` 또는 시간이 지난 뒤 다시 시도하세요."
        )
        return
    entries = LIFE_TABLES[activity]
    names = [x[0] for x in entries]
    weights = [x[3] for x in entries]
    selected = random.choices(entries, weights=weights, k=1)[0]
    name, minimum, maximum, _ = selected
    u.setdefault("life_mastery", {"채집": 0, "낚시": 0, "벌목": 0, "광산": 0})
    mastery_exp = int(u["life_mastery"].get(activity, 0))
    mastery_level = 1 + mastery_exp // 20
    mastery_bonus = min(0.30, (mastery_level - 1) * 0.02)
    amount = max(1, int(random.randint(minimum, maximum) * exploration_modifier(u) * (1.0 + mastery_bonus)))
    u["life_mastery"][activity] = mastery_exp + 1

    rare_text = ""
    if name == "식량":
        u["balance"] += amount
        u["stats"]["earned"] += amount
        result = f"🥫 버려진 보급품 **{amount:,}개** 발견"
    else:
        u["resources"][name] = u["resources"].get(name, 0) + amount
        result = f"📦 **{name} {amount}개** 획득"

    if random.random() < 0.05:
        u["materials"]["고대파편"] = u["materials"].get("고대파편", 0) + 1
        rare_text = "\n✨ 희귀 발견: **고대파편 1개**"

    progress_weekly(u, "생활 활동")
    add_season_points(u, 4)
    save_data()

    await ctx.send(
        f"🌿 **[{activity} 결과]** {result}{rare_text}\n"
        f"⚡ 스태미나 **-{stamina_cost}** | 현재 **{u['stamina']} / {get_max_stamina(u)}**"
    )


@bot.hybrid_command()
@commands.cooldown(1, 120, commands.BucketType.user)
async def 채집(ctx):
    await perform_life_activity(ctx, "채집")


@bot.hybrid_command()
@commands.cooldown(1, 120, commands.BucketType.user)
async def 낚시(ctx):
    await perform_life_activity(ctx, "낚시")


@bot.hybrid_command()
@commands.cooldown(1, 120, commands.BucketType.user)
async def 벌목(ctx):
    await perform_life_activity(ctx, "벌목")


@bot.hybrid_command()
@commands.cooldown(1, 180, commands.BucketType.user)
async def 광산(ctx):
    await perform_life_activity(ctx, "광산")


@bot.hybrid_command()
async def 자원(ctx):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    lines = [f"• {name}: **{amount}개**" for name, amount in u["resources"].items()]
    await ctx.send("🌲 **[생활 자원]**\n" + "\n".join(lines))


# =========================================================
# 기지 건설 / 강화 / 수확
# =========================================================
BASE_COSTS = {
    1: {"나무": 20, "광석": 10, "고철": 10, "food": 5000},
    2: {"나무": 45, "광석": 30, "고철": 25, "food": 15000},
    3: {"나무": 80, "광석": 60, "고철": 50, "food": 40000},
    4: {"나무": 140, "광석": 100, "고철": 90, "food": 90000},
}


@bot.hybrid_command()
async def 기지(ctx):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    base = u["base"]
    built = base["level"] > 0 and base.get("built", False)
    state = "건설 완료" if built else "미건설"
    hourly = base["level"] * 400 if built else 0
    await ctx.send(
        f"🏠 **[{ctx.author.name}의 기지]**\n"
        f"상태: **{state}**\n"
        f"레벨: **Lv.{base['level']}**\n"
        f"시간당 식량 생산량: **{hourly:,}개**\n"
        f"저장 식량: **{base.get('storage', 0):,}개**"
    )


@bot.hybrid_command()
async def 기지건설(ctx):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    base = u["base"]
    if base.get("built", False):
        await ctx.send("⚠️ 기지가 이미 건설되어 있습니다.")
        return

    cost = {"나무": 10, "광석": 5, "고철": 5, "food": 3000}
    missing = []
    for resource in ["나무", "광석", "고철"]:
        if u["resources"].get(resource, 0) < cost[resource]:
            missing.append(f"{resource} {cost[resource] - u['resources'].get(resource, 0)}개")
    if u["balance"] < cost["food"]:
        missing.append(f"식량 {cost['food'] - u['balance']:,}개")
    if missing:
        await ctx.send("⚠️ 부족한 건설 자원: " + ", ".join(missing))
        return

    for resource in ["나무", "광석", "고철"]:
        u["resources"][resource] -= cost[resource]
    u["balance"] -= cost["food"]
    base["built"] = True
    base["level"] = 1
    base["last_collect"] = datetime.now().isoformat()
    add_title(u, "기지 개척자")
    add_season_points(u, 30)
    save_data()
    await ctx.send("🏠 **기지 건설 완료!** 이제 `!기지수확`으로 식량을 생산할 수 있습니다.")


@bot.hybrid_command()
async def 기지강화(ctx):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    base = u["base"]
    if not base.get("built", False):
        await ctx.send("⚠️ 먼저 `!기지건설`을 해야 합니다.")
        return
    if base["level"] >= 5:
        await ctx.send("⚠️ 기지가 최대 레벨입니다.")
        return

    cost = BASE_COSTS[base["level"]]
    missing = []
    for resource in ["나무", "광석", "고철"]:
        if u["resources"].get(resource, 0) < cost[resource]:
            missing.append(f"{resource} {cost[resource] - u['resources'].get(resource, 0)}개")
    if u["balance"] < cost["food"]:
        missing.append(f"식량 {cost['food'] - u['balance']:,}개")
    if missing:
        await ctx.send("⚠️ 부족한 강화 자원: " + ", ".join(missing))
        return

    for resource in ["나무", "광석", "고철"]:
        u["resources"][resource] -= cost[resource]
    u["balance"] -= cost["food"]
    base["level"] += 1
    add_season_points(u, 40)
    save_data()
    await ctx.send(f"🏗️ **기지 강화 성공! Lv.{base['level']}**")


@bot.hybrid_command()
async def 기지수확(ctx):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    base = u["base"]
    if not base.get("built", False):
        await ctx.send("⚠️ 먼저 기지를 건설하세요.")
        return

    now = datetime.now()
    last_text = base.get("last_collect") or now.isoformat()
    try:
        last = datetime.fromisoformat(last_text)
    except ValueError:
        last = now

    elapsed_hours = min(24, max(0, (now - last).total_seconds() / 3600))
    reward = int(elapsed_hours * base["level"] * 400)
    if reward < 100:
        await ctx.send("⏳ 아직 수확할 식량이 충분히 쌓이지 않았습니다.")
        return

    u["balance"] += reward
    u["stats"]["earned"] += reward
    base["last_collect"] = now.isoformat()
    add_season_points(u, min(20, int(elapsed_hours)))
    save_data()
    await ctx.send(f"🏠 기지 생산 식량 **{reward:,}개** 수확 완료!")


# =========================================================
# 길드 시스템
# =========================================================
def find_guild_by_name(name):
    for gid, guild in world_data["guilds"].items():
        if guild["name"].lower() == name.lower():
            return gid, guild
    return None, None


@bot.hybrid_command()
async def 길드목록(ctx):
    if not await check_registered(ctx):
        return
    guilds = list(world_data["guilds"].items())
    if not guilds:
        await ctx.send("🛡️ 아직 생성된 길드가 없습니다.")
        return
    guilds.sort(key=lambda x: (x[1]["level"], x[1]["fund"]), reverse=True)
    lines = []
    for _, g in guilds[:20]:
        lines.append(
            f"• **{g['name']}** | Lv.{g['level']} | "
            f"인원 {len(g['members'])}명 | 기금 {g['fund']:,}"
        )
    await send_pages(ctx.channel, "🛡️ **[길드 목록]**\n" + "\n".join(lines))


@bot.hybrid_command()
async def 길드생성(ctx, *, 길드명: str):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    if u.get("guild_id"):
        await ctx.send("⚠️ 이미 길드에 소속되어 있습니다.")
        return
    if len(길드명) < 2 or len(길드명) > 16:
        await ctx.send("⚠️ 길드명은 2~16자로 입력하세요.")
        return
    if find_guild_by_name(길드명)[1]:
        await ctx.send("⚠️ 이미 존재하는 길드명입니다.")
        return
    cost = 30000
    if u["balance"] < cost:
        await ctx.send(f"⚠️ 길드 창설 비용 **{cost:,}개**가 필요합니다.")
        return

    guild_id = str(max([int(x) for x in world_data["guilds"].keys()] + [0]) + 1)
    world_data["guilds"][guild_id] = {
        "name": 길드명,
        "owner": str(ctx.author.id),
        "members": [str(ctx.author.id)],
        "level": 1,
        "fund": 0,
        "exp": 0
    }
    u["balance"] -= cost
    u["guild_id"] = guild_id
    add_title(u, "길드 창설자")
    add_season_points(u, 50)
    save_data()
    await ctx.send(f"🛡️ 길드 **{길드명}** 창설 완료!")


@bot.hybrid_command()
async def 길드가입(ctx, *, 길드명: str):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    if u.get("guild_id"):
        await ctx.send("⚠️ 이미 길드에 소속되어 있습니다.")
        return
    gid, guild = find_guild_by_name(길드명)
    if not guild:
        await ctx.send("⚠️ 해당 길드를 찾을 수 없습니다.")
        return
    max_members = 10 + guild["level"] * 5
    if len(guild["members"]) >= max_members:
        await ctx.send("⚠️ 해당 길드는 인원이 가득 찼습니다.")
        return
    guild["members"].append(str(ctx.author.id))
    u["guild_id"] = gid
    save_data()
    await ctx.send(f"🛡️ **{guild['name']}** 길드에 가입했습니다.")


@bot.hybrid_command()
async def 길드정보(ctx):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    gid = u.get("guild_id")
    if not gid or gid not in world_data["guilds"]:
        await ctx.send("⚠️ 소속된 길드가 없습니다.")
        return
    g = world_data["guilds"][gid]
    owner = f"<@{g['owner']}>"
    await ctx.send(
        f"🛡️ **[{g['name']}]**\n"
        f"길드장: {owner}\n"
        f"레벨: **Lv.{g['level']}**\n"
        f"인원: **{len(g['members'])}/{10 + g['level'] * 5}명**\n"
        f"길드 기금: **{g['fund']:,}개**\n"
        f"길드 전투력 보너스: **+{g['level'] * 2}%**"
    )


@bot.hybrid_command()
async def 길드기부(ctx, 금액: int):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    gid = u.get("guild_id")
    if not gid or gid not in world_data["guilds"]:
        await ctx.send("⚠️ 길드에 가입되어 있지 않습니다.")
        return
    if 금액 <= 0 or u["balance"] < 금액:
        await ctx.send("⚠️ 기부 금액이 잘못됐거나 잔액이 부족합니다.")
        return
    g = world_data["guilds"][gid]
    u["balance"] -= 금액
    g["fund"] += 금액
    g["exp"] += 금액 // 100
    add_season_points(u, min(30, 금액 // 1000))
    save_data()
    await ctx.send(f"💰 길드에 식량 **{금액:,}개** 기부 완료.")


@bot.hybrid_command()
async def 길드강화(ctx):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    gid = u.get("guild_id")
    if not gid or gid not in world_data["guilds"]:
        await ctx.send("⚠️ 길드에 가입되어 있지 않습니다.")
        return
    g = world_data["guilds"][gid]
    if g["owner"] != str(ctx.author.id):
        await ctx.send("❌ 길드장만 길드를 강화할 수 있습니다.")
        return
    cost = g["level"] * 50000
    if g["fund"] < cost:
        await ctx.send(f"⚠️ 길드 기금 **{cost:,}개**가 필요합니다.")
        return
    g["fund"] -= cost
    g["level"] += 1
    save_data()
    await ctx.send(f"🛡️ 길드가 **Lv.{g['level']}**로 성장했습니다!")


@bot.hybrid_command()
async def 길드탈퇴(ctx):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    gid = u.get("guild_id")
    if not gid or gid not in world_data["guilds"]:
        await ctx.send("⚠️ 소속된 길드가 없습니다.")
        return
    g = world_data["guilds"][gid]
    uid = str(ctx.author.id)
    if g["owner"] == uid and len(g["members"]) > 1:
        await ctx.send("⚠️ 길드장은 다른 길드원이 있는 동안 탈퇴할 수 없습니다.")
        return
    if uid in g["members"]:
        g["members"].remove(uid)
    u["guild_id"] = None
    if not g["members"]:
        del world_data["guilds"][gid]
        await ctx.send("🛡️ 길드에서 탈퇴했으며, 남은 인원이 없어 길드가 해산됐습니다.")
    else:
        await ctx.send("🛡️ 길드에서 탈퇴했습니다.")
    save_data()


# =========================================================
# 거래소
# =========================================================
@bot.hybrid_command()
async def 거래소(ctx):
    if not await check_registered(ctx):
        return
    listings = world_data["market"]
    if not listings:
        await ctx.send("🏪 거래소에 등록된 장비가 없습니다.")
        return
    lines = []
    for listing_id, listing in sorted(
        listings.items(), key=lambda x: int(x[0])
    )[:30]:
        if listing.get("auction"):
            current = listing.get("highest_bid", 0) or listing.get("price", 0)
            label = f"🔨 경매 {current:,}개"
        else:
            label = f"🛒 즉시구매 {listing['price']:,}개"
        lines.append(
            f"`#{listing_id}` **{listing['item']} +{listing['enhance']}** "
            f"| {label} | 판매자 <@{listing['seller']}>"
        )
    await send_pages(ctx.channel, "🏪 **[생존자 거래소]**\n" + "\n".join(lines))


@bot.hybrid_command()
async def 판매(ctx, 아이템이름: str, 가격: int):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    if 아이템이름 not in u["inventory"]:
        await ctx.send("⚠️ 보유하지 않은 장비입니다.")
        return
    if 가격 <= 0:
        await ctx.send("⚠️ 판매 가격은 1 이상이어야 합니다.")
        return

    listing_id = str(world_data["market_next_id"])
    world_data["market_next_id"] += 1
    enhance = u["enhancements"].get(아이템이름, 0)
    options = u.get("equipment_options", {}).pop(아이템이름, None)
    u["inventory"].remove(아이템이름)
    u["enhancements"].pop(아이템이름, None)
    world_data["market"][listing_id] = {
        "seller": str(ctx.author.id),
        "item": 아이템이름,
        "enhance": enhance,
        "price": 가격,
        "options": options,
        "created": datetime.now().isoformat()
    }
    save_data()
    await ctx.send(
        f"🏪 **판매 등록 완료** `#{listing_id}`\n"
        f"{아이템이름} +{enhance} / **{가격:,}개**"
    )


@bot.hybrid_command()
async def 구매등록번호(ctx, 번호: int):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    listing_id = str(번호)
    listing = world_data["market"].get(listing_id)
    if not listing:
        await ctx.send("⚠️ 존재하지 않는 판매 등록 번호입니다.")
        return
    if listing.get("auction"):
        await ctx.send(f"⚠️ 이 매물은 경매입니다. `!입찰 {번호} 금액`을 사용하세요.")
        return
    if listing["seller"] == str(ctx.author.id):
        await ctx.send("⚠️ 자기 물건은 구매할 수 없습니다.")
        return
    if u["balance"] < listing["price"]:
        await ctx.send("⚠️ 식량이 부족합니다.")
        return
    if listing["item"] in u["inventory"]:
        await ctx.send("⚠️ 이미 같은 장비를 보유하고 있습니다.")
        return

    seller = get_user(listing["seller"])
    u["balance"] -= listing["price"]
    u["inventory"].append(listing["item"])
    u["enhancements"][listing["item"]] = listing["enhance"]
    if listing.get("options"):
        u.setdefault("equipment_options", {})[listing["item"]] = listing["options"]
    u.setdefault("market_history", []).append({"type": "구매", "item": listing["item"], "price": listing["price"], "date": datetime.now().isoformat()})
    if seller:
        seller["balance"] += listing["price"]
        seller["stats"]["earned"] += listing["price"]
        seller.setdefault("market_history", []).append({"type": "판매", "item": listing["item"], "price": listing["price"], "date": datetime.now().isoformat()})
    del world_data["market"][listing_id]
    add_season_points(u, 10)
    save_data()
    await ctx.send(
        f"🛒 **거래 완료!** {listing['item']} +{listing['enhance']} 획득."
    )


@bot.hybrid_command()
async def 판매취소(ctx, 번호: int):
    if not await check_registered(ctx):
        return
    listing_id = str(번호)
    listing = world_data["market"].get(listing_id)
    if not listing:
        await ctx.send("⚠️ 존재하지 않는 판매 등록 번호입니다.")
        return
    if listing["seller"] != str(ctx.author.id):
        await ctx.send("❌ 본인의 판매글만 취소할 수 있습니다.")
        return
    if listing.get("auction") and listing.get("highest_bidder"):
        await ctx.send("⚠️ 입찰자가 있는 경매는 취소할 수 없습니다. `!경매마감 번호`를 사용하세요.")
        return
    u = get_user(ctx.author.id)
    u["inventory"].append(listing["item"])
    u["enhancements"][listing["item"]] = listing["enhance"]
    if listing.get("options"):
        u.setdefault("equipment_options", {})[listing["item"]] = listing["options"]
    del world_data["market"][listing_id]
    save_data()
    await ctx.send(f"↩️ 판매 취소: **{listing['item']}**이 인벤토리로 돌아왔습니다.")


# =========================================================
# 파티 시스템
# =========================================================
def find_party_of(user_id):
    uid = str(user_id)
    for leader_id, party in world_data["parties"].items():
        if uid in party["members"]:
            return leader_id, party
    return None, None


@bot.hybrid_command()
async def 파티생성(ctx):
    if not await check_registered(ctx):
        return
    if find_party_of(ctx.author.id)[1]:
        await ctx.send("⚠️ 이미 파티에 소속되어 있습니다.")
        return
    uid = str(ctx.author.id)
    world_data["parties"][uid] = {"leader": uid, "members": [uid]}
    save_data()
    await ctx.send(f"👥 {ctx.author.mention}님이 파티를 생성했습니다.")


@bot.hybrid_command()
async def 파티가입(ctx, 리더: discord.Member):
    if not await check_registered(ctx):
        return
    if find_party_of(ctx.author.id)[1]:
        await ctx.send("⚠️ 이미 파티에 소속되어 있습니다.")
        return
    party = world_data["parties"].get(str(리더.id))
    if not party:
        await ctx.send("⚠️ 해당 유저가 이끄는 파티가 없습니다.")
        return
    if len(party["members"]) >= 4:
        await ctx.send("⚠️ 파티 정원이 가득 찼습니다.")
        return
    party["members"].append(str(ctx.author.id))
    save_data()
    await ctx.send(f"👥 {리더.mention}님의 파티에 가입했습니다.")


@bot.hybrid_command()
async def 파티정보(ctx):
    if not await check_registered(ctx):
        return
    leader_id, party = find_party_of(ctx.author.id)
    if not party:
        await ctx.send("⚠️ 파티에 소속되어 있지 않습니다.")
        return
    members = "\n".join(f"• <@{uid}>" for uid in party["members"])
    await ctx.send(
        f"👥 **[파티 정보]**\n리더: <@{leader_id}>\n"
        f"인원: {len(party['members'])}/4\n{members}"
    )


@bot.hybrid_command()
@commands.cooldown(1, 300, commands.BucketType.user)
async def 파티사냥(ctx):
    if not await check_registered(ctx):
        return
    leader_id, party = find_party_of(ctx.author.id)
    if not party:
        ctx.command.reset_cooldown(ctx)
        await ctx.send("⚠️ 먼저 파티를 생성하거나 가입하세요.")
        return
    if leader_id != str(ctx.author.id):
        ctx.command.reset_cooldown(ctx)
        await ctx.send("❌ 파티장만 파티 사냥을 시작할 수 있습니다.")
        return

    active = []
    total_power = 0
    for uid in party["members"]:
        member_u = get_user(uid)
        if member_u:
            active.append((uid, member_u))
            total_power += calculate_user_power(member_u)

    enemy_power = random.randint(30, 220) * max(1, len(active))
    victory = total_power >= enemy_power or random.random() < 0.30

    if victory:
        base_reward = random.randint(4000, 9000)
        for _, member_u in active:
            reward = base_reward + calculate_user_power(member_u) * 20
            member_u["balance"] += reward
            member_u["stats"]["earned"] += reward
            progress_weekly(member_u, "파티 사냥")
            add_season_points(member_u, 15)
        save_data()
        await ctx.send(
            f"👥 **[파티 사냥 승리]**\n"
            f"파티 전투력 {total_power:,} / 적 전투력 {enemy_power:,}\n"
            f"전원에게 개인별 식량 보상이 지급되었습니다."
        )
    else:
        save_data()
        await ctx.send(
            f"💀 **[파티 사냥 실패]**\n"
            f"파티 전투력 {total_power:,} / 적 전투력 {enemy_power:,}"
        )


@bot.hybrid_command()
async def 파티탈퇴(ctx):
    if not await check_registered(ctx):
        return
    leader_id, party = find_party_of(ctx.author.id)
    if not party:
        await ctx.send("⚠️ 파티에 소속되어 있지 않습니다.")
        return
    uid = str(ctx.author.id)
    if uid == leader_id:
        del world_data["parties"][leader_id]
        await ctx.send("👥 파티장이 탈퇴하여 파티가 해산되었습니다.")
    else:
        party["members"].remove(uid)
        await ctx.send("👥 파티에서 탈퇴했습니다.")
    save_data()


# =========================================================
# PVP
# =========================================================
@bot.hybrid_command(name="pvp", aliases=["PVP", "피브이피"])
@commands.cooldown(1, 120, commands.BucketType.user)
async def pvp_command(ctx, 상대: discord.Member):
    if not await check_registered(ctx):
        return
    if 상대.bot or 상대.id == ctx.author.id:
        ctx.command.reset_cooldown(ctx)
        await ctx.send("⚠️ 자기 자신이나 봇과는 대결할 수 없습니다.")
        return

    attacker = get_user(ctx.author.id)
    defender = get_user(상대.id)
    if not defender:
        ctx.command.reset_cooldown(ctx)
        await ctx.send("⚠️ 상대방이 가입하지 않았습니다.")
        return

    a_power = calculate_user_power(attacker)
    d_power = calculate_user_power(defender)
    a_score = a_power * random.uniform(0.75, 1.35)
    d_score = d_power * random.uniform(0.75, 1.35)

    if a_score >= d_score:
        winner_member, winner_u = ctx.author, attacker
        loser_member = 상대
    else:
        winner_member, winner_u = 상대, defender
        loser_member = ctx.author

    reward = random.randint(1500, 3500)
    winner_u["balance"] += reward
    winner_u["stats"]["earned"] += reward
    progress_weekly(attacker, "PVP 참여")
    progress_weekly(defender, "PVP 참여")
    add_season_points(attacker, 8)
    add_season_points(defender, 5)
    save_data()

    await ctx.send(
        f"⚔️ **[PVP 결과]**\n"
        f"{ctx.author.mention} 전투력 {a_power:,} VS {상대.mention} 전투력 {d_power:,}\n"
        f"🏆 승자: {winner_member.mention}\n"
        f"보상: 식량 **{reward:,}개**\n"
        f"패자 {loser_member.mention}의 식량은 차감되지 않습니다."
    )


# =========================================================
# 주간 퀘스트
# =========================================================
@bot.hybrid_command()
async def 주간퀘스트(ctx):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    ensure_weekly_quest(u)
    q = u["weekly_quest"]
    await ctx.send(
        f"📆 **[주간 퀘스트 {q['week']}]**\n"
        f"내용: **{q['type']} {q['target']}회**\n"
        f"진행: **{q['progress']} / {q['target']}**\n"
        f"보상: **식량 {q['reward']:,}개**\n"
        f"수령 여부: {'완료' if q['claimed'] else '미수령'}"
    )


@bot.hybrid_command()
async def 주간보상(ctx):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    q = u["weekly_quest"]
    if q["claimed"]:
        await ctx.send("⚠️ 이번 주 보상을 이미 받았습니다.")
        return
    if q["progress"] < q["target"]:
        await ctx.send("⚠️ 주간 퀘스트가 아직 완료되지 않았습니다.")
        return
    q["claimed"] = True
    u["balance"] += q["reward"]
    u["stats"]["earned"] += q["reward"]
    add_season_points(u, 80)
    save_data()
    await ctx.send(f"🎁 주간 퀘스트 보상 **{q['reward']:,}개** 지급!")


# =========================================================
# 시즌패스
# =========================================================
@bot.hybrid_command()
async def 시즌패스(ctx):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    ensure_season_pass(u)
    sp = u["season_pass"]
    lines = []
    for level, reward in SEASON_REWARDS.items():
        unlocked = sp["points"] >= reward["points"]
        claimed = level in sp["claimed_levels"]
        mark = "✅" if claimed else ("🔓" if unlocked else "🔒")
        title_text = f" + 칭호 `{reward['title']}`" if reward["title"] else ""
        lines.append(
            f"{mark} Lv.{level} | {reward['points']}P | "
            f"식량 {reward['food']:,}{title_text}"
        )
    await send_pages(
        ctx.channel,
        f"🎖️ **[{sp['season']} 시즌패스]** 현재 **{sp['points']}P**\n" +
        "\n".join(lines) +
        "\n\n수령: `!시즌보상 레벨`"
    )


@bot.hybrid_command()
async def 시즌보상(ctx, 레벨: int):
    if not await check_registered(ctx):
        return
    u = get_user(ctx.author.id)
    ensure_season_pass(u)
    sp = u["season_pass"]
    reward = SEASON_REWARDS.get(레벨)
    if not reward:
        await ctx.send("⚠️ 존재하지 않는 시즌패스 레벨입니다.")
        return
    if 레벨 in sp["claimed_levels"]:
        await ctx.send("⚠️ 이미 받은 시즌 보상입니다.")
        return
    if sp["points"] < reward["points"]:
        await ctx.send(f"⚠️ 시즌 포인트 **{reward['points']}P**가 필요합니다.")
        return

    sp["claimed_levels"].append(레벨)
    u["balance"] += reward["food"]
    u["stats"]["earned"] += reward["food"]
    if reward["title"]:
        add_title(u, reward["title"])
    save_data()
    await ctx.send(
        f"🎖️ 시즌패스 Lv.{레벨} 보상 수령!\n"
        f"식량 **{reward['food']:,}개**"
        + (f"\n칭호 **{reward['title']}** 획득!" if reward["title"] else "")
    )


# =========================================================
# 분리 모듈 명령어 등록
# =========================================================
from apocalypse_bot.commands.jobs import register_job_commands
register_job_commands(bot, get_user, check_registered, save_data)
register_status_commands(bot, get_user, check_registered, save_data)
register_condition_commands(bot, get_user, check_registered, save_data, get_max_hp)
from apocalypse_bot.commands.world_exploration import register_world_commands
register_world_commands(bot, get_user, check_registered, save_data, spend_stamina, apply_damage, get_max_hp, get_max_stamina)

# V2.0-8 퀴즈 개선 + 월드보스 개편
from apocalypse_bot.commands.daily_quiz import register_quiz_commands
register_quiz_commands(
    bot, get_user, check_registered, save_data, world_data, send_pages, add_season_points
)

# V2.0-6 관리자 통합 도구
from apocalypse_bot.commands.admin_tools import register_admin_commands
register_admin_commands(
    bot,
    get_user,
    save_data,
    send_pages,
    ITEM_DB,
    MATERIALS,
    PET_DB,
    calculate_user_power,
)


# V2.1 Apocalypse Reborn 확장
from apocalypse_bot.commands.v21_reborn import register_v21_commands
register_v21_commands(
    bot, get_user, check_registered, save_data, send_pages, world_data,
    ITEM_DB, MATERIALS, find_item, calculate_user_power, spend_stamina,
    apply_damage, get_max_hp, add_season_points,
)

# V3.0 Abaddon: 서버 침공 + 통합 도움말
from apocalypse_bot.commands.v30_invasion import register_v30_commands
register_v30_commands(
    bot, get_user, check_registered, save_data, send_pages, world_data,
    calculate_user_power, add_season_points,
)

# V3.1: 일일 퀴즈 자동 알림/스레드 + RPG 시작 온보딩
from apocalypse_bot.commands.v31_quiz_notify import register_v31_commands
register_v31_commands(
    bot, get_user, check_registered, save_data, world_data,
)


# V3.2: 통합 도감 + 서버별 설정 패널 + 초보자 튜토리얼
from apocalypse_bot.commands.v32_codex_settings_tutorial import register_v32_commands
register_v32_commands(
    bot, get_user, check_registered, save_data, world_data,
    send_pages, ITEM_DB, PET_DB,
)

# V3.3: 선택형 스토리 시즌 1 "검은 주파수"
from apocalypse_bot.commands.v33_story import register_v33_commands
register_v33_commands(
    bot, get_user, check_registered, save_data, world_data,
    get_max_hp, add_title,
)

# V3.6: 실시간 변동 암시장 + 도박 안내
from apocalypse_bot.commands.v36_gambling_market import register_v36_commands
register_v36_commands(
    bot, get_user, check_registered, save_data, world_data, progress_quest,
)

# V3.7: 도박 연출/잔액 통계 + 알바 + 희귀 코인 + 암시장 자동 알림
from apocalypse_bot.commands.v37_gambling_experience import register_v37_commands
register_v37_commands(
    bot, get_user, check_registered, save_data, world_data, progress_quest,
)

# V3.9: 통합 폐허 카지노 (블랙잭/하이로우/슬롯/다이스/바카라)
from apocalypse_bot.commands.v39_casino import register_v39_commands
register_v39_commands(
    bot, get_user, check_registered, save_data, user_data, world_data, progress_quest,
)

# V4.0: BLACK CASINO 확장 (칩/VIP/잭팟/미션/NPC/상점/럭키휠/올인)
from apocalypse_bot.commands.v40_black_casino import register_v40_casino_commands
register_v40_casino_commands(
    bot, get_user, check_registered, save_data, world_data, user_data,
)

# V4.0: 은행 + 사채 금융 시스템
from apocalypse_bot.commands.v40_finance import register_v40_finance_commands
register_v40_finance_commands(
    bot, get_user, check_registered, save_data,
)

# V4.0.3: 관리자 전용 서버 자동 꾸미기
# prefix 전용이라 Discord 글로벌 slash 100개 제한을 사용하지 않습니다.
from apocalypse_bot.commands.v403_server_builder import register_v403_server_builder
register_v403_server_builder(bot, world_data, save_data)

# V4.1: SERVER GUARD 서버 운영/제재/로그/자동관리/문의 시스템
from apocalypse_bot.commands.v410_server_management import register_v410_server_management
register_v410_server_management(bot, world_data, save_data)
print(f"[SERVER GUARD 등록 확인] 운영초기설정={bot.get_command('운영초기설정') is not None} 운영진단={bot.get_command('운영진단') is not None}", flush=True)

# V4.2: SERVER GUARD PLUS 스마트 자동 이모지/안티레이드/비상관리 확장
# prefix 전용으로 추가하여 글로벌 슬래시 100개 제한을 사용하지 않습니다.
from apocalypse_bot.commands.v411_server_guard_plus import register_v411_server_guard_plus
register_v411_server_guard_plus(bot, world_data, save_data)

# V4.2: 운영 대시보드/설정 내보내기/운영 메모/채널 보조 도구
# prefix 전용이라 Discord 글로벌 slash 100개 제한을 사용하지 않습니다.
from apocalypse_bot.commands.v420_ops_center import register_v420_ops_center
register_v420_ops_center(bot, world_data, save_data)

# V4.2.1: 셀프 역할 패널/가입자 점검/일반 편의 기능
# prefix 전용이라 Discord 글로벌 slash 100개 제한을 사용하지 않습니다.
from apocalypse_bot.commands.v421_utility_pack import register_v421_utility_pack
register_v421_utility_pack(bot, world_data, save_data)

# V4.2.2: 통합 보안센터/분리 로그/자동관리 정책/사용자 제재 기록
# prefix 전용이라 Discord 글로벌 slash 100개 제한을 사용하지 않습니다.
from apocalypse_bot.commands.v422_security_center import register_v422_security_center
register_v422_security_center(bot, world_data, save_data)

# V4.2.3: 유형별 문의·신고·건의 접수/담당자/처리상태/빠른답변 센터
# prefix 전용이라 Discord 글로벌 slash 100개 제한을 사용하지 않습니다.
from apocalypse_bot.commands.v423_intake_center import register_v423_intake_center
register_v423_intake_center(bot, world_data, save_data)

# V4.3.0: 스토리 시즌 2 "백색 방주" + 턴제 원정 전투/평판/유물
# prefix 전용 그룹으로 추가하여 Discord 글로벌 slash 100개 제한을 사용하지 않습니다.
from apocalypse_bot.commands.v430_story_expedition import register_v430_story_expedition
register_v430_story_expedition(
    bot, get_user, check_registered, save_data, calculate_user_power,
    spend_stamina, apply_damage, get_max_hp, get_max_stamina,
    add_title, add_season_points,
)

# 모든 기존 !명령어에 대응하는 / 슬래시 명령어 등록
# Discord의 최상위 명령어 100개 제한 때문에 확장 명령어는 카테고리 그룹으로 묶습니다.
from apocalypse_bot.core.slash_setup import register_grouped_slash_commands
register_grouped_slash_commands(bot)
