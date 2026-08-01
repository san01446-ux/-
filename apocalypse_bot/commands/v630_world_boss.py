from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

import discord
from discord.ext import commands

from apocalypse_bot.commands.v637_dynamic_events import consume_weapon_durability

VERSION = "6.3.0"
ROOT_KEY = "world_boss_v630"
DAILY_ATTACK_LIMIT = 10
ATTACK_COOLDOWN_SECONDS = 45
HISTORY_LIMIT = 8
ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets" / "world_boss"

BOSSES: Mapping[str, Dict[str, Any]] = {
    "gatekeeper": {
        "name": "검은 성역의 문지기",
        "aliases": ("문지기", "성역", "게이트"),
        "grade": "전설",
        "max_hp": 1_200_000,
        "trait": "흑철 방벽",
        "material": "성역의 흑철",
        "weakness": "강화 5단계 이상 무기",
        "image": "gatekeeper.png",
        "color": 0xBE263E,
        "dodge": 0.04,
        "defense": 0.18,
        "counter": (70, 240),
        "parts": {"방벽 핵": 240_000, "봉인 사슬": 180_000},
        "lore": "검은 성역의 문을 지키며 생존자의 공격 기록을 수집하는 고대 수문장.",
        "patterns": (
            "🛡️ 흑철 방벽이 닫히며 이번 공격 피해가 감소했습니다.",
            "⛓️ 봉인 사슬이 전장을 휘감아 다음 공격의 명중률을 흔듭니다.",
            "🔻 성역의 문양이 붉게 빛나며 반격이 강화됩니다.",
        ),
    },
    "atlas": {
        "name": "방사능 거신 아틀라스",
        "aliases": ("아틀라스", "거신", "방사능"),
        "grade": "신화",
        "max_hp": 1_500_000,
        "trait": "방사능 노심",
        "material": "오염된 노심",
        "weakness": "방호 장비와 기술자 직업",
        "image": "atlas.png",
        "color": 0x4FDC75,
        "dodge": 0.02,
        "defense": 0.13,
        "counter": (100, 320),
        "parts": {"노심 냉각관": 260_000, "오른팔 장갑": 230_000},
        "lore": "오래된 원자로와 융합한 거대 병기. 걸음을 옮길 때마다 지표가 오염된다.",
        "patterns": (
            "☢️ 노심이 폭주해 전장에 방사능 구름이 퍼졌습니다.",
            "🦾 장갑판이 맞물리며 물리 방어가 일시적으로 상승했습니다.",
            "⚡ 축전기가 방전되며 공격자 주변 장비에 충격을 줍니다.",
        ),
    },
    "nemesis": {
        "name": "심연 포식자 네메시스",
        "aliases": ("네메시스", "포식자", "심연"),
        "grade": "신화",
        "max_hp": 1_350_000,
        "trait": "생명 흡수",
        "material": "심연의 점액핵",
        "weakness": "화염 계열 장비와 치명타",
        "image": "nemesis.png",
        "color": 0x7647D2,
        "dodge": 0.08,
        "defense": 0.08,
        "counter": (80, 270),
        "parts": {"포식 기관": 220_000, "심연 촉수": 190_000},
        "lore": "바닥 없는 균열에서 올라온 포식체. 피해 일부를 먹어 치워 자신의 생명으로 바꾼다.",
        "patterns": (
            "🩸 네메시스가 흩어진 생명 신호를 흡수해 체력을 회복했습니다.",
            "🕳️ 심연의 입이 열리며 공격 궤적 일부가 사라졌습니다.",
            "🟣 촉수가 지면을 뚫고 올라와 공격자의 발을 묶었습니다.",
        ),
    },
    "babel": {
        "name": "폐허의 기계왕 바벨",
        "aliases": ("바벨", "기계왕", "기계"),
        "grade": "유일",
        "max_hp": 1_650_000,
        "trait": "자가 수복 장갑",
        "material": "바벨 구동축",
        "weakness": "고철·광석 계열 자원 보유량",
        "image": "babel.png",
        "color": 0xDB8029,
        "dodge": 0.03,
        "defense": 0.20,
        "counter": (120, 360),
        "parts": {"중앙 연산핵": 300_000, "왼팔 포대": 240_000},
        "lore": "폐허의 공장 전체를 몸으로 삼은 전쟁 기계. 파괴된 부품을 주변 잔해로 즉시 교체한다.",
        "patterns": (
            "🔧 주변 고철이 바벨의 장갑에 달라붙어 손상 부위를 메웠습니다.",
            "🚨 자동 포대가 공격자를 추적하며 제압 사격을 시작합니다.",
            "⚙️ 중앙 연산핵이 공격 패턴을 분석해 방어 수치를 재조정했습니다.",
        ),
    },
    "ark_ghost": {
        "name": "백색 방주의 망령",
        "aliases": ("망령", "백색 방주", "방주"),
        "grade": "유일",
        "max_hp": 1_450_000,
        "trait": "환영 분신",
        "material": "백색 기억결정",
        "weakness": "스토리 시즌 2 기록과 원정 유물",
        "image": "ark_ghost.png",
        "color": 0xA4DAEE,
        "dodge": 0.13,
        "defense": 0.07,
        "counter": (60, 220),
        "parts": {"기억 닻": 210_000, "환영 투영기": 200_000},
        "lore": "백색 방주에 남은 마지막 항해 기록이 사람의 형상을 얻은 존재.",
        "patterns": (
            "👻 환영 분신이 진짜 몸을 가리며 공격 일부가 허공을 갈랐습니다.",
            "🤍 기억 파동이 전장을 덮어 과거의 목소리가 들려옵니다.",
            "🪞 공격자의 움직임을 복제한 분신이 반대편에서 나타났습니다.",
        ),
    },
    "abaddon": {
        "name": "종말의 왕 아바돈",
        "aliases": ("아바돈", "종말의 왕", "왕좌"),
        "grade": "종말",
        "max_hp": 2_500_000,
        "trait": "왕좌의 심판",
        "material": "왕좌의 검은 파편",
        "weakness": "서버 전체의 다양한 역할 참여",
        "image": "abaddon.png",
        "color": 0xDE223F,
        "dodge": 0.08,
        "defense": 0.16,
        "counter": (160, 480),
        "parts": {"종말의 왕관": 420_000, "왕좌의 심장": 380_000, "검은 날개": 310_000},
        "lore": "모든 종말 신호가 수렴한 왕좌의 주인. 서버 공동 전투의 최종 시험.",
        "patterns": (
            "👑 왕좌의 심판이 내려와 전장의 모든 신호가 잠시 정지했습니다.",
            "🌑 검은 날개가 하늘을 덮으며 치명타 방어가 상승했습니다.",
            "🔥 종말의 불꽃이 번져 공격자들의 장비를 시험합니다.",
        ),
    },
}

PHASE_NAMES = {1: "탐색 단계", 2: "적응 단계", 3: "붕괴 단계", 4: "광폭화 단계"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utc_now().isoformat()


def _date_key() -> str:
    return _utc_now().astimezone().strftime("%Y-%m-%d")


def _bar(current: int, maximum: int, size: int = 20) -> str:
    ratio = max(0.0, min(1.0, current / max(1, maximum)))
    filled = int(round(ratio * size))
    return "█" * filled + "░" * (size - filled)


def _signed(value: int) -> str:
    return f"+{value:,}" if value >= 0 else f"{value:,}"


def _boss_key(query: Optional[str]) -> Optional[str]:
    text = str(query or "").strip().casefold()
    if not text:
        return None
    for key, info in BOSSES.items():
        candidates = (key, info["name"], *info.get("aliases", ()))
        if any(text == str(item).casefold() or text in str(item).casefold() for item in candidates):
            return key
    return None


def _root(world_data: Dict[str, Any]) -> Dict[str, Any]:
    root = world_data.setdefault(ROOT_KEY, {})
    if not isinstance(root, dict):
        root = {}
        world_data[ROOT_KEY] = root
    root.setdefault("guilds", {})
    root.setdefault("version", VERSION)
    return root


def _guild_state(world_data: Dict[str, Any], guild_id: int) -> Dict[str, Any]:
    root = _root(world_data)
    state = root["guilds"].setdefault(str(guild_id), {})
    if not isinstance(state, dict):
        state = {}
        root["guilds"][str(guild_id)] = state
    state.setdefault("active", None)
    state.setdefault("history", [])
    state.setdefault("sequence", 0)
    return state


def _new_battle(state: Dict[str, Any], key: str, *, hp_override: Optional[int] = None, test: bool = False) -> Dict[str, Any]:
    info = BOSSES[key]
    state["sequence"] = int(state.get("sequence", 0)) + 1
    maximum = max(1, int(hp_override if hp_override is not None else info["max_hp"]))
    battle_id = f"{_utc_now().strftime('%Y%m%d%H%M%S')}-{int(state['sequence']):03d}"
    battle = {
        "battle_id": battle_id,
        "boss_key": key,
        "name": info["name"],
        "max_hp": maximum,
        "hp": maximum,
        "phase": 1,
        "status": "active",
        "spawned_at": _iso_now(),
        "defeated_at": "",
        "participants": {},
        "rewards_claimed": [],
        "killer_id": None,
        "parts": {name: {"target": max(1, int(target * maximum / info["max_hp"])), "damage": 0, "broken": False} for name, target in info.get("parts", {}).items()},
        "event_log": [],
        "test": bool(test),
    }
    state["active"] = battle
    return battle


def _migrate_legacy(world_data: Dict[str, Any], guild_id: int) -> Optional[Dict[str, Any]]:
    state = _guild_state(world_data, guild_id)
    if isinstance(state.get("active"), dict):
        return state["active"]
    legacy = world_data.get("world_boss")
    if not isinstance(legacy, dict) or not legacy.get("name"):
        return None
    key = _boss_key(str(legacy.get("name"))) or random.choice(tuple(BOSSES))
    battle = _new_battle(state, key, hp_override=max(1, int(legacy.get("max_hp", BOSSES[key]["max_hp"]))))
    battle["hp"] = max(0, min(int(battle["max_hp"]), int(legacy.get("hp", battle["max_hp"]))))
    battle["status"] = "defeated" if battle["hp"] <= 0 or legacy.get("status") == "defeated" else "active"
    participants = legacy.get("participants", {})
    if isinstance(participants, dict):
        for uid, row in participants.items():
            if isinstance(row, dict):
                damage = int(row.get("damage", 0))
                attacks = int(row.get("attacks", 0))
            else:
                damage = int(row or 0)
                attacks = 0
            battle["participants"][str(uid)] = {
                "damage": max(0, damage), "attacks": max(0, attacks), "last_at": "", "daily": {"date": _date_key(), "count": 0}
            }
    return battle


def _battle(world_data: Dict[str, Any], guild_id: int) -> Optional[Dict[str, Any]]:
    state = _guild_state(world_data, guild_id)
    active = state.get("active")
    if not isinstance(active, dict):
        active = _migrate_legacy(world_data, guild_id)
    return active if isinstance(active, dict) else None


def _rows(battle: Dict[str, Any]) -> List[Tuple[str, int, int]]:
    rows: List[Tuple[str, int, int]] = []
    participants = battle.get("participants", {})
    if isinstance(participants, dict):
        for uid, row in participants.items():
            if not isinstance(row, dict):
                continue
            rows.append((str(uid), int(row.get("damage", 0)), int(row.get("attacks", 0))))
    return sorted(rows, key=lambda item: (-item[1], item[0]))


def _phase_for(hp: int, maximum: int) -> int:
    ratio = hp / max(1, maximum)
    if ratio <= 0.25:
        return 4
    if ratio <= 0.50:
        return 3
    if ratio <= 0.75:
        return 2
    return 1


def _asset_file(name: str) -> Optional[discord.File]:
    path = ASSET_ROOT / name
    if not path.is_file():
        return None
    return discord.File(path, filename=name)


async def _send_asset(ctx: commands.Context, embed: discord.Embed, filename: str, *, content: Optional[str] = None) -> discord.Message:
    file = _asset_file(filename)
    if file is None:
        return await ctx.send(content=content, embed=embed)
    embed.set_image(url=f"attachment://{filename}")
    return await ctx.send(content=content, embed=embed, file=file)


async def _safe_reactions(message: Optional[discord.Message], emojis: Iterable[str]) -> None:
    if message is None:
        return
    for emoji in emojis:
        try:
            await message.add_reaction(emoji)
        except (discord.Forbidden, discord.HTTPException, AttributeError):
            return


def _status_embed(battle: Dict[str, Any]) -> discord.Embed:
    key = str(battle.get("boss_key"))
    info = BOSSES.get(key, BOSSES["gatekeeper"])
    hp = int(battle.get("hp", 0)); maximum = max(1, int(battle.get("max_hp", 1)))
    percent = hp / maximum * 100
    phase = int(battle.get("phase", _phase_for(hp, maximum)))
    rows = _rows(battle)
    top = "\n".join(f"**{idx}.** <@{uid}> · `{damage:,}` 피해 · {attacks}회" for idx, (uid, damage, attacks) in enumerate(rows[:5], 1)) or "아직 참가자가 없습니다."
    parts=[]
    for name, part in battle.get("parts", {}).items():
        if not isinstance(part, dict):
            continue
        marker = "💥" if part.get("broken") else "🔧"
        parts.append(f"{marker} {name} · {int(part.get('damage',0)):,}/{int(part.get('target',1)):,}")
    embed = discord.Embed(
        title=f"🌋 [{info['grade']}] {info['name']}",
        description=(
            f"`{_bar(hp, maximum)}`\n"
            f"**HP {hp:,} / {maximum:,} ({percent:.1f}%)**\n"
            f"현재 **{PHASE_NAMES.get(phase, '전투 단계')}** · 특성 **{info['trait']}**"
        ),
        color=int(info["color"]),
        timestamp=_utc_now(),
    )
    embed.add_field(name="🎯 약점", value=info["weakness"], inline=False)
    embed.add_field(name="🧩 부위 파괴", value="\n".join(parts) if parts else "파괴 가능한 부위 없음", inline=False)
    embed.add_field(name="🏅 기여도 TOP 5", value=top, inline=False)
    embed.add_field(name="⚔️ 공격", value=f"`!월드보스공격` · 하루 {DAILY_ATTACK_LIMIT}회 · {ATTACK_COOLDOWN_SECONDS}초 간격", inline=False)
    embed.set_footer(text=f"전투 ID {battle.get('battle_id','-')} · !월드보스목록 · !월드보스보상")
    return embed


def _boss_list_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🌋 ABADDON 다중 월드보스 도감",
        description="각 보스는 체력만 다른 복제품이 아니라 약점·패턴·부위 파괴·전용 재료가 다릅니다.",
        color=discord.Color.dark_red(),
    )
    for info in BOSSES.values():
        embed.add_field(
            name=f"{info['grade']} · {info['name']}",
            value=f"HP **{info['max_hp']:,}** · {info['trait']}\n약점: {info['weakness']}\n재료: {info['material']}",
            inline=False,
        )
    embed.set_footer(text="관리자 소환: !월드보스소환 보스명")
    return embed


def _require_guild(ctx: commands.Context) -> bool:
    return ctx.guild is not None


def register_v630_world_boss(
    bot: commands.Bot,
    get_user: Callable[[Any], Optional[Dict[str, Any]]],
    check_registered: Callable[[commands.Context], Any],
    save_data: Callable[[], None],
    world_data: Dict[str, Any],
    calculate_user_power: Callable[[Dict[str, Any]], int],
    add_title: Callable[[Dict[str, Any], str], Any],
) -> None:
    """기존 하이브리드 월드보스 명령의 이름은 보존하고 callback만 v6.3.0으로 교체합니다."""

    async def require_registered_guild(ctx: commands.Context) -> Optional[int]:
        if not await check_registered(ctx):
            return None
        if not _require_guild(ctx):
            await ctx.send("⚠️ 월드보스는 서버 채널에서만 이용할 수 있습니다.")
            return None
        return int(ctx.guild.id)

    async def status_callback(ctx: commands.Context) -> None:
        guild_id = await require_registered_guild(ctx)
        if guild_id is None:
            return
        battle = _battle(world_data, guild_id)
        if battle is None:
            embed = discord.Embed(
                title="🌋 현재 출현한 월드보스가 없습니다",
                description="관리자가 `!월드보스소환 보스명`을 사용하거나 기존 보스를 불러오면 전투가 시작됩니다.",
                color=discord.Color.dark_grey(),
            )
            embed.add_field(name="보스 목록", value="`!월드보스목록`", inline=True)
            embed.add_field(name="관리자 테스트", value="`!월드보스테스트 보스명`", inline=True)
            await ctx.send(embed=embed)
            return
        key = str(battle.get("boss_key", "gatekeeper"))
        info = BOSSES.get(key, BOSSES["gatekeeper"])
        await _send_asset(ctx, _status_embed(battle), str(info["image"]))

    async def ranking_callback(ctx: commands.Context) -> None:
        guild_id = await require_registered_guild(ctx)
        if guild_id is None:
            return
        battle = _battle(world_data, guild_id)
        if battle is None or not _rows(battle):
            await ctx.send("📭 현재 월드보스 기여 기록이 없습니다.")
            return
        rows = _rows(battle)
        total = sum(row[1] for row in rows)
        lines=[]
        for idx,(uid,damage,attacks) in enumerate(rows[:20],1):
            share=damage/max(1,total)*100
            lines.append(f"**{idx}.** <@{uid}> · **{damage:,}** 피해 · {share:.1f}% · {attacks}회")
        embed=discord.Embed(title=f"🏆 {battle.get('name','월드보스')} 기여도 순위",description="\n".join(lines),color=discord.Color.gold())
        embed.set_footer(text=f"총 누적 피해 {total:,} · 전투 ID {battle.get('battle_id','-')}")
        await ctx.send(embed=embed)

    def user_attack_state(battle: Dict[str, Any], uid: str) -> Dict[str, Any]:
        participants=battle.setdefault("participants",{})
        row=participants.setdefault(uid,{"damage":0,"attacks":0,"last_at":"","daily":{"date":_date_key(),"count":0}})
        if not isinstance(row,dict):
            row={"damage":0,"attacks":0,"last_at":"","daily":{"date":_date_key(),"count":0}}
            participants[uid]=row
        daily=row.setdefault("daily",{"date":_date_key(),"count":0})
        if daily.get("date")!=_date_key():
            daily["date"]=_date_key(); daily["count"]=0
        return row

    async def attack_callback(ctx: commands.Context) -> None:
        guild_id = await require_registered_guild(ctx)
        if guild_id is None:
            return
        battle = _battle(world_data, guild_id)
        if battle is None or battle.get("status") != "active" or int(battle.get("hp",0)) <= 0:
            if getattr(ctx,"command",None):
                try: ctx.command.reset_cooldown(ctx)
                except Exception: pass
            await ctx.send("⚠️ 현재 공격 가능한 월드보스가 없습니다. `!월드보스`로 상태를 확인하세요.")
            return
        uid=str(ctx.author.id)
        user=get_user(ctx.author.id)
        if not isinstance(user,dict):
            await ctx.send("⚠️ 생존자 데이터를 찾지 못했습니다.")
            return
        row=user_attack_state(battle,uid)
        daily=row["daily"]
        if int(daily.get("count",0)) >= DAILY_ATTACK_LIMIT:
            if getattr(ctx,"command",None):
                try: ctx.command.reset_cooldown(ctx)
                except Exception: pass
            await ctx.send(f"🛑 오늘의 월드보스 공격 **{DAILY_ATTACK_LIMIT}회**를 모두 사용했습니다.")
            return

        key=str(battle.get("boss_key","gatekeeper")); info=BOSSES.get(key,BOSSES["gatekeeper"])
        before_hp=int(battle["hp"]); maximum=max(1,int(battle["max_hp"])); old_phase=int(battle.get("phase",1))
        power=max(1,int(calculate_user_power(user)))
        level=max(1,int(user.get("level",1)))
        base=random.randint(max(80,int(power*1.15)),max(120,int(power*2.25)))+level*35
        base=min(base,max(50_000,int(maximum*0.055)))
        critical=random.random() < min(.28,.09+level/900)
        dodge=random.random() < float(info.get("dodge",0))
        broken_count=sum(1 for p in battle.get("parts",{}).values() if isinstance(p,dict) and p.get("broken"))
        defense=max(0.0,float(info.get("defense",0))-broken_count*.035)
        phase_multiplier={1:1.0,2:.96,3:.92,4:.88}.get(old_phase,.9)
        damage=0 if dodge else max(1,int(base*(1-defense)*phase_multiplier*(1.75 if critical else 1.0)))
        detail=[]
        if dodge:
            detail.append("👻 보스가 공격 궤적을 벗어났습니다.")
        elif critical:
            detail.append("💥 약점에 치명타가 적중했습니다!")

        # 보스별 패턴
        heal=0
        if random.random()<.18:
            detail.append(random.choice(tuple(info.get("patterns",()))))
            if key in {"nemesis","babel"} and before_hp < maximum:
                heal=min(maximum-before_hp,max(1,int(maximum*(.006 if key=="nemesis" else .004))))
                battle["hp"]=min(maximum,before_hp+heal)
                before_hp=int(battle["hp"])
                detail.append(f"💚 보스 체력 **{heal:,}** 회복")
            elif key=="ark_ghost" and damage>0:
                damage=max(1,int(damage*.55)); detail.append("🪞 환영 때문에 피해가 감소했습니다.")
            elif key=="gatekeeper" and damage>0:
                damage=max(1,int(damage*.65))

        # 부위 피해
        part_text=""
        available=[(name,p) for name,p in battle.get("parts",{}).items() if isinstance(p,dict) and not p.get("broken")]
        if damage>0 and available and random.random()<.28:
            part_name,part=random.choice(available)
            part_damage=max(1,int(damage*random.uniform(.38,.72)))
            part["damage"]=int(part.get("damage",0))+part_damage
            if int(part["damage"])>=int(part.get("target",1)):
                part["broken"]=True
                part_text=f"\n💥 **{part_name} 파괴!** 이후 방어력이 감소합니다."
            else:
                part_text=f"\n🔧 {part_name}에 **{part_damage:,}** 부위 피해"

        damage=min(max(0,damage),int(battle["hp"]))
        battle["hp"]=max(0,int(battle["hp"])-damage)
        row["damage"]=int(row.get("damage",0))+damage
        row["attacks"]=int(row.get("attacks",0))+1
        row["last_at"]=_iso_now(); daily["count"]=int(daily.get("count",0))+1
        user.setdefault("stats",{}).setdefault("worldboss_damage",0)
        user["stats"]["worldboss_damage"]+=damage
        codex=user.setdefault("worldboss_codex",{}).setdefault(info["name"],{"damage":0,"attacks":0,"kills":0})
        codex["damage"]=int(codex.get("damage",0))+damage; codex["attacks"]=int(codex.get("attacks",0))+1
        weapon_state=consume_weapon_durability(user, 2 if critical else 1)

        new_phase=_phase_for(int(battle["hp"]),maximum); battle["phase"]=new_phase
        counter=random.randint(*info.get("counter",(0,0))) if damage>0 and random.random()<.24 else 0
        if counter:
            detail.append(f"🩹 반격으로 장비 내구 비용 **{counter:,} 식량**이 예상됐지만 레이드 보험이 보호했습니다.")

        remaining=DAILY_ATTACK_LIMIT-int(daily["count"])
        embed=discord.Embed(
            title=f"⚔️ {info['name']} 공격 결과",
            description="\n".join(detail) if detail else "공격이 보스의 외피를 가르며 전장에 충격파가 번졌습니다.",
            color=discord.Color.gold() if critical else int(info["color"]),
            timestamp=_utc_now(),
        )
        embed.add_field(name="⚔️ 가한 피해",value=f"**{damage:,}**",inline=True)
        embed.add_field(name="❤️ 남은 HP",value=f"**{int(battle['hp']):,}/{maximum:,}**",inline=True)
        embed.add_field(name="🎫 오늘 남은 공격",value=f"**{remaining}회**",inline=True)
        embed.add_field(name="📊 내 누적 기여",value=f"**{int(row['damage']):,} 피해** · {int(row['attacks'])}회",inline=False)
        if weapon_state.get("name"):
            embed.add_field(name="🔧 무기 내구도",value=f"**{weapon_state['current']} / {weapon_state['maximum']} · {weapon_state['label']}**",inline=False)
        if part_text:
            embed.add_field(name="🧩 부위 파괴",value=part_text.strip(),inline=False)
        embed.set_thumbnail(url=str(ctx.author.display_avatar.url))
        embed.set_footer(text=f"{PHASE_NAMES.get(new_phase)} · {ATTACK_COOLDOWN_SECONDS}초 후 재공격")

        defeated=int(battle["hp"])<=0
        if defeated:
            battle["status"]="defeated"; battle["defeated_at"]=_iso_now(); battle["killer_id"]=uid
            codex["kills"]=int(codex.get("kills",0))+1
            add_title(user,"마지막 일격의 생존자")
            history=_guild_state(world_data,guild_id).setdefault("history",[])
            history.insert(0,{"battle_id":battle["battle_id"],"boss_key":key,"name":info["name"],"defeated_at":battle["defeated_at"],"participants":len(_rows(battle))})
            del history[HISTORY_LIMIT:]
        save_data()
        msg=await ctx.send(embed=embed)
        await _safe_reactions(msg,("💥","⚔️","🔥") if critical else ("⚔️","🛡️"))

        if new_phase>old_phase and not defeated:
            phase_file="enrage.png" if new_phase==4 else "phase.png"
            phase_embed=discord.Embed(
                title=f"⚠️ {PHASE_NAMES.get(new_phase)} 진입",
                description=("보스가 광폭화했습니다. 공격 패턴과 방어 계산이 강화됩니다." if new_phase==4 else "체력 임계점을 통과해 보스의 행동 패턴이 변경됩니다."),
                color=discord.Color.red() if new_phase==4 else discord.Color.blue(),
            )
            await _send_asset(ctx,phase_embed,phase_file)
        if defeated:
            victory=discord.Embed(
                title=f"🏆 {info['name']} 토벌 완료",
                description=f"마지막 일격: {ctx.author.mention}\n참가자 **{len(_rows(battle))}명** · `!월드보스보상`으로 개인 보상을 수령하세요.",
                color=discord.Color.gold(),
            )
            await _send_asset(ctx,victory,"victory.png")

    async def spawn_callback(ctx: commands.Context, *, 보스이름: str = None) -> None:
        guild_id = await require_registered_guild(ctx)
        if guild_id is None:
            return
        if not (ctx.author == ctx.guild.owner or ctx.author.guild_permissions.manage_guild or ctx.author.guild_permissions.administrator):
            await ctx.send("❌ 서버 관리 권한이 필요합니다.")
            return
        key=_boss_key(보스이름) if 보스이름 else random.choice(tuple(BOSSES))
        if key is None:
            await ctx.send("⚠️ 보스를 찾지 못했습니다. `!월드보스목록`에서 이름을 확인하세요.")
            return
        state=_guild_state(world_data,guild_id)
        active=state.get("active")
        if isinstance(active,dict) and active.get("status")=="active" and int(active.get("hp",0))>0:
            await ctx.send("⚠️ 이미 활성 월드보스가 있습니다. 먼저 `!월드보스종료`를 사용하세요.")
            return
        battle=_new_battle(state,key)
        save_data()
        info=BOSSES[key]
        embed=discord.Embed(
            title=f"🌋 [{info['grade']}] {info['name']} 출현",
            description=f"서버 공동 HP **{battle['max_hp']:,}**\n특성 **{info['trait']}** · 약점 **{info['weakness']}**\n`!월드보스공격`으로 전투에 참가하세요.",
            color=int(info["color"]),
        )
        await _send_asset(ctx,embed,str(info["image"]),content="@here 월드보스 출현 신호가 감지되었습니다.")

    async def health_callback(ctx: commands.Context, 체력: int) -> None:
        guild_id=await require_registered_guild(ctx)
        if guild_id is None:return
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ 관리자 전용 명령어입니다."); return
        battle=_battle(world_data,guild_id)
        if battle is None:
            await ctx.send("⚠️ 활성 월드보스가 없습니다."); return
        value=max(1,int(체력)); battle["max_hp"]=value; battle["hp"]=value; battle["status"]="active"; battle["phase"]=1
        save_data(); await ctx.send(f"❤️ 월드보스 체력을 **{value:,}**으로 재설정했습니다.")

    async def end_callback(ctx: commands.Context) -> None:
        guild_id=await require_registered_guild(ctx)
        if guild_id is None:return
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ 관리자 전용 명령어입니다."); return
        battle=_battle(world_data,guild_id)
        if battle is None:
            await ctx.send("⚠️ 활성 월드보스가 없습니다."); return
        battle["status"]="ended"; battle["hp"]=0; battle["defeated_at"]=_iso_now(); save_data()
        await ctx.send(f"🛑 **{battle.get('name','월드보스')}** 전투를 관리자 권한으로 종료했습니다. 보상은 열리지 않습니다.")

    # 기존 HybridCommand를 보존한 채 callback을 교체해 slash 최상위 개수 증가 0개
    replacements={
        "월드보스":status_callback,
        "보스랭킹":ranking_callback,
        "월드보스공격":attack_callback,
        "월드보스리셋":spawn_callback,
        "월드보스체력":health_callback,
        "월드보스종료":end_callback,
    }
    for name,callback in replacements.items():
        cmd=bot.get_command(name)
        if cmd is not None:
            cmd.callback=callback
            if name=="월드보스공격":
                cmd._buckets=commands.CooldownMapping.from_cooldown(1,ATTACK_COOLDOWN_SECONDS,commands.BucketType.user)

    @bot.command(name="월드보스목록", aliases=["보스목록", "월보목록"])
    async def boss_list(ctx: commands.Context) -> None:
        if await require_registered_guild(ctx) is None:return
        await ctx.send(embed=_boss_list_embed())

    @bot.command(name="월드보스기여도", aliases=["내기여도", "월보기여도"])
    async def contribution(ctx: commands.Context) -> None:
        guild_id=await require_registered_guild(ctx)
        if guild_id is None:return
        battle=_battle(world_data,guild_id)
        if battle is None:
            await ctx.send("📭 현재 전투가 없습니다."); return
        rows=_rows(battle); uid=str(ctx.author.id); row=battle.get("participants",{}).get(uid,{})
        rank=next((idx for idx,item in enumerate(rows,1) if item[0]==uid),None)
        daily=row.get("daily",{}) if isinstance(row,dict) else {}
        if daily.get("date")!=_date_key(): count=0
        else: count=int(daily.get("count",0))
        embed=discord.Embed(title=f"📊 {ctx.author.display_name} 월드보스 기여도",color=discord.Color.blue())
        embed.add_field(name="누적 피해",value=f"**{int(row.get('damage',0)):,}**",inline=True)
        embed.add_field(name="현재 순위",value=f"**{rank or '-'}위**",inline=True)
        embed.add_field(name="공격 횟수",value=f"누적 {int(row.get('attacks',0))}회 · 오늘 {count}/{DAILY_ATTACK_LIMIT}",inline=False)
        await ctx.send(embed=embed)

    @bot.command(name="월드보스보상", aliases=["보스보상", "월보보상"])
    async def reward(ctx: commands.Context) -> None:
        guild_id=await require_registered_guild(ctx)
        if guild_id is None:return
        battle=_battle(world_data,guild_id)
        if battle is None or battle.get("status")!="defeated":
            await ctx.send("⚠️ 처치 완료된 월드보스 보상이 없습니다."); return
        uid=str(ctx.author.id); claimed=battle.setdefault("rewards_claimed",[])
        if uid in claimed:
            await ctx.send("✅ 이 전투의 보상을 이미 수령했습니다."); return
        rows=_rows(battle); entry=next((row for row in rows if row[0]==uid),None)
        if entry is None or entry[1]<=0:
            await ctx.send("⚠️ 전투 기여 기록이 없어 보상을 받을 수 없습니다."); return
        rank=next(idx for idx,row in enumerate(rows,1) if row[0]==uid)
        total=sum(row[1] for row in rows); damage=entry[1]
        info=BOSSES.get(str(battle.get("boss_key")),BOSSES["gatekeeper"])
        base=2200 if battle.get("test") else 8000
        share=min(45_000,int((damage/max(1,total))*90_000))
        rank_bonus=25_000 if rank==1 else 14_000 if rank<=3 else 6_000 if rank<=10 else 2_000
        food=base+share+rank_bonus
        material_amount=max(1,10-min(rank,8))
        user=get_user(ctx.author.id)
        user["balance"]=int(user.get("balance",0))+food
        user.setdefault("stats",{}).setdefault("earned",0); user["stats"]["earned"]+=food
        user.setdefault("materials",{})[info["material"]]=int(user.setdefault("materials",{}).get(info["material"],0))+material_amount
        titles=[]
        if rank==1:
            title=f"{info['name']} 최우수 토벌자"; add_title(user,title); titles.append(title)
        elif rank<=3:
            title=f"{info['name']} 선봉대"; add_title(user,title); titles.append(title)
        if str(battle.get("killer_id"))==uid:
            title="마지막 일격의 생존자"; add_title(user,title); titles.append(title)
        claimed.append(uid); save_data()
        embed=discord.Embed(title="🎁 월드보스 기여도 보상 수령",description=f"전투 순위 **{rank}위** · 기여 피해 **{damage:,}**",color=discord.Color.gold())
        embed.add_field(name="💰 식량",value=f"**+{food:,}**",inline=True)
        embed.add_field(name=f"🧩 {info['material']}",value=f"**+{material_amount}개**",inline=True)
        embed.add_field(name="💳 현재 잔액",value=f"**{int(user['balance']):,} 식량**",inline=True)
        if titles: embed.add_field(name="🏷️ 칭호",value="\n".join(f"`{t}`" for t in dict.fromkeys(titles)),inline=False)
        await _send_asset(ctx,embed,"reward.png")

    @bot.command(name="월드보스도감", aliases=["월보도감"])
    async def codex(ctx: commands.Context) -> None:
        if await require_registered_guild(ctx) is None:return
        user=get_user(ctx.author.id); records=user.setdefault("worldboss_codex",{})
        lines=[]
        for info in BOSSES.values():
            row=records.get(info["name"],{}) if isinstance(records,dict) else {}
            lines.append(f"**{info['name']}** · 피해 {int(row.get('damage',0)):,} · 공격 {int(row.get('attacks',0))}회 · 처치 {int(row.get('kills',0))}회")
        embed=discord.Embed(title=f"📚 {ctx.author.display_name} 월드보스 도감",description="\n".join(lines),color=discord.Color.purple())
        await ctx.send(embed=embed)

    @bot.command(name="월드보스테스트", aliases=["월보테스트"])
    async def test_spawn(ctx: commands.Context, *, 보스이름: str = None) -> None:
        guild_id=await require_registered_guild(ctx)
        if guild_id is None:return
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ 관리자 전용 명령어입니다."); return
        key=_boss_key(보스이름) if 보스이름 else "gatekeeper"
        if key is None:
            await ctx.send("⚠️ 보스 이름을 찾지 못했습니다."); return
        state=_guild_state(world_data,guild_id); battle=_new_battle(state,key,hp_override=50_000,test=True); save_data()
        info=BOSSES[key]
        embed=discord.Embed(title=f"🧪 테스트 월드보스 · {info['name']}",description="HP **50,000** · 보상 축소 · 실제 데이터 구조와 동일하게 저장됩니다.",color=int(info["color"]))
        await _send_asset(ctx,embed,str(info["image"]))

    setattr(bot,"_abaddon_v630_world_boss",True)

