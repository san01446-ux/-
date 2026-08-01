from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands

VERSION = "6.3.2"
ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets" / "v632"
KST = ZoneInfo("Asia/Seoul")
ENCOUNTER_CHANCE = 0.10
ENCOUNTER_DAILY_LIMIT = 8
ENCOUNTER_REWARD_CAP = 16_000

ACTIVITY_LABELS: Mapping[str, Tuple[str, str]] = {
    "fishing": ("🎣", "낚시"),
    "mining": ("⛏️", "광산"),
    "coin": ("🪙", "코인 탐색"),
    "exploration": ("🔦", "갈림길 탐색"),
    "support": ("🎁", "긴급 지원 교섭"),
}
ACTIVITY_ALIASES = {"낚시":"fishing","광산":"mining","코인":"coin","코인탐색":"coin","탐색":"exploration","돈주세요":"support"}

TIP_POOLS: Mapping[str, Sequence[str]] = {
    "fishing": (
        "낚시 숙련도는 20회마다 상승하며 물고기와 보급품 획득량을 높입니다.",
        "수면의 비정상적인 파문은 큰 물고기일 수도, 수변 감염체일 수도 있습니다.",
        "희귀 어종은 제작 재료나 고대파편 발견으로 이어질 수 있습니다.",
        "폭우가 시작되면 낚싯줄보다 주변 철수 경로를 먼저 확인하세요.",
    ),
    "mining": (
        "광산 숙련도가 오르면 광석과 고철 획득량이 점차 증가합니다.",
        "붉은 균열은 고열 구간이므로 곡괭이보다 환기 장치를 먼저 확인하세요.",
        "푸른 결정맥 주변에는 오래된 기계 장치가 남아 있을 가능성이 큽니다.",
        "낙석음이 연속으로 들리면 희귀 광맥보다 안전한 통로가 우선입니다.",
    ),
    "coin": (
        "코인 실패 수리비는 현재 잔액을 넘지 않으며 잔액이 없으면 보호됩니다.",
        "희귀도가 높은 자산일수록 시세 변동이 크므로 보유 현황을 함께 확인하세요.",
        "위조 신호는 반복 패턴이 짧고 실물 자산 신호는 잡음 속에서도 서명이 유지됩니다.",
        "오늘 코인 탐색을 모두 사용했다면 알바와 땅파기가 다음 수입 루트입니다.",
    ),
    "exploration": (
        "갈림길 탐색은 성공 시 배팅액 이상의 보상을 얻지만 실패하면 배팅액을 잃습니다.",
        "발소리보다 먼저 꺼지는 조명은 매복이나 전력 함정의 신호일 수 있습니다.",
        "보급함을 발견해도 주변 출구와 와이어 덫을 먼저 확인하는 편이 안전합니다.",
        "왼쪽과 오른쪽 통로의 성공 확률은 같으며 결과는 매번 독립적으로 결정됩니다.",
    ),
    "support": (
        "긴급 지원 교섭은 정상 지원·빈 배급소·사기 거래로 갈릴 수 있습니다.",
        "봉인 번호와 무전 호출 부호가 다르면 보증금을 먼저 내지 마세요.",
        "특별 지원 물자는 드물지만 일반 지원보다 훨씬 큰 식량을 제공합니다.",
        "실패 손실은 현재 잔액을 넘지 않아 잔액이 음수가 되지 않습니다.",
    ),
}

_RECENT_ASSETS: Dict[str, List[str]] = {}
_ACTIVE_USERS: set[int] = set()


def random_tip(activity: str) -> str:
    pool = TIP_POOLS.get(activity) or ("현장 상황을 확인한 뒤 안전한 선택을 고르세요.",)
    return random.choice(tuple(pool))


def _asset_files(relative: str) -> List[Path]:
    folder = ASSET_ROOT / relative
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})


def pick_asset(relative: str) -> Optional[Path]:
    files = _asset_files(relative)
    if not files:
        return None
    recent = _RECENT_ASSETS.setdefault(relative, [])
    blocked = set(recent[-3:])
    choices = [p for p in files if p.name not in blocked] or files
    selected = random.choice(choices)
    recent.append(selected.name)
    del recent[:-6]
    return selected


def _discord_file(path: Path) -> discord.File:
    safe = "_".join(path.relative_to(ASSET_ROOT).parts)
    return discord.File(str(path), filename=f"abaddon_v632_{safe}")


def _set_image(embed: discord.Embed, path: Optional[Path]) -> Optional[discord.File]:
    if path is None or not path.is_file():
        return None
    file = _discord_file(path)
    embed.set_image(url=f"attachment://{file.filename}")
    return file


async def send_visual(target: Any, embed: discord.Embed, relative: str, *, view: Optional[discord.ui.View] = None) -> discord.Message:
    file = _set_image(embed, pick_asset(relative))
    kwargs: Dict[str, Any] = {"embed": embed}
    if view is not None:
        kwargs["view"] = view
    if file is not None:
        kwargs["file"] = file
    return await target.send(**kwargs)


async def edit_visual(message: discord.Message, embed: discord.Embed, relative: str, *, view: Optional[discord.ui.View] = None) -> None:
    file = _set_image(embed, pick_asset(relative))
    try:
        if file is not None:
            await message.edit(content=None, embed=embed, view=view, attachments=[file])
        else:
            await message.edit(content=None, embed=embed, view=view)
    except TypeError:
        await message.edit(content=None, embed=embed, view=view)
    except (discord.Forbidden, discord.HTTPException, AttributeError):
        return


@dataclass(frozen=True)
class Encounter:
    encounter_id: str
    activity: str
    rarity: str
    title: str
    description: str
    options: Tuple[Tuple[str, str, str], ...]


ENCOUNTERS: Tuple[Encounter, ...] = (
    Encounter("fish_raider_boat", "fishing", "danger", "수면 위 약탈자 보트", "낚싯줄 끝의 큰 물고기와 함께 엔진을 끈 소형 보트가 접근합니다.", (("줄을 끊고 숨는다","✂️","safe"),("무전으로 경고한다","📻","help"),("물고기를 끝까지 끌어낸다","🎣","risk"))),
    Encounter("fish_mutant_school", "fishing", "rare", "빛나는 변이 어군", "푸른빛을 내는 어군이 부두 아래를 선회하며 수면에 이상한 문양을 만듭니다.", (("외곽에서 한 마리만 낚는다","🪝","safe"),("표본망을 함께 펼친다","🕸️","help"),("무리 중심에 미끼를 던진다","💠","risk"))),
    Encounter("fish_flood_cache", "fishing", "common", "침수된 보급 상자", "낚싯줄에 물고기 대신 군용 방수 상자의 손잡이가 걸렸습니다.", (("얕은 곳으로 끌어낸다","🧵","safe"),("동료와 도르래를 건다","⚙️","help"),("잠금 장치를 물속에서 연다","🔐","risk"))),
    Encounter("mine_gas_fault", "mining", "danger", "폐광 가스 경보", "낡은 경보기와 전등이 동시에 붉게 점멸하기 시작했습니다.", (("즉시 환기한다","🌬️","safe"),("인접 갱도에 경고한다","📢","help"),("광맥만 빠르게 캔다","⛏️","risk"))),
    Encounter("mine_machine_heart", "mining", "rare", "지하 기계의 심장", "결정맥 뒤에서 오래된 동력핵이 낮은 진동과 청색광을 내뿜습니다.", (("전원을 분리한다","🔌","safe"),("기술 기록을 복구한다","🛠️","help"),("핵을 즉시 추출한다","💎","risk"))),
    Encounter("mine_survivor_map", "mining", "common", "광부 생존자의 지도", "폐광 감시소에서 살아남은 광부가 안전한 광맥 지도를 들고 나타났습니다.", (("소량 식량으로 교환한다","🤝","safe"),("탈출로를 함께 정비한다","🧱","help"),("표시되지 않은 금지 갱도를 묻는다","🗺️","risk"))),
    Encounter("coin_broker", "coin", "common", "신호를 가로챈 데이터 브로커", "스캐너 주파수에 익명의 브로커가 접속해 자산 서명 일부를 판매하겠다고 제안합니다.", (("소액 정보만 산다","🪙","safe"),("서명을 함께 검증한다","🔍","help"),("암호 지갑 전체를 연다","💻","risk"))),
    Encounter("coin_black_node", "coin", "rare", "검은 노드의 숨은 지갑", "폐쇄된 서버 노드에서 정상 시장에 기록되지 않은 고액 지갑 신호가 감지됩니다.", (("읽기 전용으로 확인한다","👁️","safe"),("백업 키를 복원한다","🔑","help"),("즉시 자산을 이전한다","⚡","risk"))),
    Encounter("explore_tripwire", "exploration", "danger", "붉은 와이어가 걸린 통로", "보급함 앞 바닥에서 매우 얇은 와이어와 벽면 폭약 흔적을 발견했습니다.", (("표시하고 우회한다","🚩","safe"),("함정을 해체한다","✂️","help"),("보급함만 끌어온다","🪝","risk"))),
    Encounter("explore_lost_scout", "exploration", "common", "길을 잃은 정찰병", "부상당한 정찰병이 반대편 통로의 매복 위치를 알고 있다고 말합니다.", (("응급처치만 한다","🩹","safe"),("거점까지 호위한다","🛡️","help"),("숨은 보급고 위치를 요구한다","📍","risk"))),
    Encounter("support_quartermaster", "support", "common", "임시 보급 담당자", "임시 배급소 담당자가 신원과 최근 활동 기록을 확인해 추가 지원 여부를 판단합니다.", (("정상 배급을 신청한다","📋","safe"),("봉사 기록을 제시한다","🧰","help"),("긴급 물자까지 요청한다","🚨","risk"))),
    Encounter("support_night_market", "support", "danger", "암시장 지원 중개인", "밤 시장의 중개인이 큰 지원 상자를 보여주며 선불 운송료를 요구합니다.", (("봉인 번호만 확인한다","🔎","safe"),("제3자 보증을 요청한다","🤝","help"),("즉시 운송료를 낸다","💸","risk"))),
)


def _kst_date() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def _ensure_profile(user: Dict[str, Any]) -> Dict[str, Any]:
    profile = user.setdefault("life_encounters_v632", {})
    defaults = {"date":_kst_date(),"daily_count":0,"daily_reward":0,"total":0,"seen":[],"recent":[],"choices":{},"last_at":""}
    for key,value in defaults.items():
        profile.setdefault(key, value.copy() if isinstance(value,(dict,list)) else value)
    if profile.get("date") != _kst_date():
        profile["date"]=_kst_date(); profile["daily_count"]=0; profile["daily_reward"]=0
    return profile


def _apply_outcome(user: Dict[str, Any], profile: Dict[str, Any], encounter: Encounter, mode: str) -> Tuple[str, int]:
    chance={"safe":0.82,"help":0.72,"risk":0.54}.get(mode,0.65)
    if encounter.rarity=="rare": chance-=0.05
    elif encounter.rarity=="danger": chance-=0.08
    success=random.random()<max(0.25,min(0.93,chance))
    if success:
        room=max(0,ENCOUNTER_REWARD_CAP-int(profile.get("daily_reward",0)))
        reward=min(room,random.randint(180,650 if mode=="safe" else 1000 if mode=="help" else 1700))
        user["balance"]=int(user.get("balance",0))+reward
        user.setdefault("stats",{}).setdefault("earned",0); user["stats"]["earned"]=int(user["stats"].get("earned",0))+reward
        resource={"fishing":"물고기","mining":"광석","coin":"고철","exploration":"고철","support":None}[encounter.activity]
        resource_text=""
        if resource:
            amount=random.randint(1,3 if mode=="safe" else 5 if mode=="help" else 8)
            user.setdefault("resources",{}); user["resources"][resource]=int(user["resources"].get(resource,0))+amount
            resource_text=f" · 📦 {resource} +{amount}"
        rare=""
        if encounter.rarity=="rare" and random.random()<0.24:
            user.setdefault("materials",{}); user["materials"]["고대파편"]=int(user["materials"].get("고대파편",0))+1
            rare=" · 🧩 고대파편 +1"
        profile["daily_reward"]=int(profile.get("daily_reward",0))+reward
        return f"선택이 성공했습니다. 💰 식량 +{reward:,}{resource_text}{rare}", reward
    balance=max(0,int(user.get("balance",0)))
    loss_max=280 if mode=="safe" else 550 if mode=="help" else 1000
    loss=min(balance,random.randint(50,loss_max)); user["balance"]=balance-loss
    hp_loss=random.randint(0,3 if mode=="safe" else 6 if mode=="help" else 10)
    if hp_loss and isinstance(user.get("hp"),int): user["hp"]=max(1,int(user["hp"])-hp_loss)
    hp_text=f" · ❤️ HP -{hp_loss}" if hp_loss else ""
    return f"현장 변수를 피하지 못해 철수했습니다. 💸 식량 -{loss:,}{hp_text}", -loss


class EncounterView(discord.ui.View):
    def __init__(self, *, owner_id: int, encounter: Encounter, user: Dict[str, Any], save_data: Callable[[], None]) -> None:
        super().__init__(timeout=150); self.owner_id=int(owner_id); self.encounter=encounter; self.user=user; self.save_data=save_data; self.resolved=False; self.message:Optional[discord.Message]=None
        for label,emoji,mode in encounter.options:
            style=discord.ButtonStyle.danger if mode=="risk" else discord.ButtonStyle.success if mode=="help" else discord.ButtonStyle.primary
            button=discord.ui.Button(label=label,emoji=emoji,style=style)
            async def callback(interaction:discord.Interaction,*,selected_mode:str=mode,selected_label:str=label)->None:
                await self._resolve(interaction,selected_mode,selected_label)
            button.callback=callback; self.add_item(button)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if int(interaction.user.id)!=self.owner_id:
            await interaction.response.send_message("이 상황은 발견한 생존자만 선택할 수 있습니다.",ephemeral=True); return False
        return True

    async def _resolve(self, interaction: discord.Interaction, mode: str, label: str) -> None:
        if self.resolved:
            await interaction.response.send_message("이미 선택이 끝난 상황입니다.",ephemeral=True); return
        self.resolved=True; profile=_ensure_profile(self.user); text,delta=_apply_outcome(self.user,profile,self.encounter,mode)
        profile["choices"][self.encounter.encounter_id]=int(profile["choices"].get(self.encounter.encounter_id,0))+1; profile["last_at"]=datetime.now(timezone.utc).isoformat(); self.save_data()
        for item in self.children: item.disabled=True
        emoji,label_text=ACTIVITY_LABELS[self.encounter.activity]
        embed=discord.Embed(title=f"{emoji} 상황 결과 · {self.encounter.title}",description=f"선택: **{label}**\n\n{text}",color=discord.Color.green() if delta>0 else discord.Color.red(),timestamp=datetime.now(timezone.utc))
        embed.add_field(name="💳 현재 잔액",value=f"**{int(self.user.get('balance',0)):,} 식량**",inline=True); embed.add_field(name="🎬 활동",value=label_text,inline=True); embed.add_field(name="💡 TIP",value=random_tip(self.encounter.activity),inline=False)
        suffix="encounter_success" if delta>0 else "encounter_failure"
        relative=f"activities/{self.encounter.activity}/{suffix}"
        # 6장 그룹은 반대 결과 폴더가 없을 수 있으므로 일반 결과로 폴백합니다.
        if not _asset_files(relative): relative=f"activities/{self.encounter.activity}/{'success' if delta>0 else 'failure'}"
        file=_set_image(embed,pick_asset(relative)); kwargs:Dict[str,Any]={"embed":embed,"view":self}
        if file is not None: kwargs["attachments"]=[file]
        try: await interaction.response.edit_message(**kwargs)
        except (discord.HTTPException,TypeError):
            if not interaction.response.is_done(): await interaction.response.edit_message(embed=embed,view=self)
            else: await interaction.followup.send(embed=embed,ephemeral=True)
        _ACTIVE_USERS.discard(self.owner_id)

    async def on_timeout(self) -> None:
        for item in self.children: item.disabled=True
        _ACTIVE_USERS.discard(self.owner_id)
        if self.message is not None:
            try: await self.message.edit(view=self)
            except (discord.Forbidden,discord.HTTPException,AttributeError): pass


async def maybe_encounter(ctx: commands.Context, activity: str, user: Dict[str, Any], save_data: Callable[[], None]) -> Optional[discord.Message]:
    activity=ACTIVITY_ALIASES.get(activity,activity)
    if activity not in ACTIVITY_LABELS or int(ctx.author.id) in _ACTIVE_USERS: return None
    profile=_ensure_profile(user)
    if int(profile.get("daily_count",0))>=ENCOUNTER_DAILY_LIMIT or random.random()>=ENCOUNTER_CHANCE: return None
    candidates=[e for e in ENCOUNTERS if e.activity==activity]; recent=list(profile.get("recent",[]))[-2:]
    candidates=[e for e in candidates if e.encounter_id not in recent] or candidates
    weights=[5 if e.rarity=="common" else 3 if e.rarity=="danger" else 2 for e in candidates]
    encounter=random.choices(candidates,weights=weights,k=1)[0]
    profile["daily_count"]=int(profile.get("daily_count",0))+1; profile["total"]=int(profile.get("total",0))+1
    if encounter.encounter_id not in profile["seen"]: profile["seen"].append(encounter.encounter_id)
    profile["recent"].append(encounter.encounter_id); del profile["recent"][:-5]; save_data(); _ACTIVE_USERS.add(int(ctx.author.id))
    emoji,label=ACTIVITY_LABELS[activity]; rarity={"common":"일반","rare":"희귀","danger":"위험"}[encounter.rarity]
    embed=discord.Embed(title=f"{emoji} 랜덤 상황 · {encounter.title}",description=f"**{label} 도중 예상치 못한 상황이 발생했습니다.**\n\n{encounter.description}",color=discord.Color.gold() if encounter.rarity=="rare" else discord.Color.red() if encounter.rarity=="danger" else discord.Color.blurple(),timestamp=datetime.now(timezone.utc))
    embed.add_field(name="희귀도",value=f"**{rarity}**",inline=True); embed.add_field(name="오늘 남은 조우",value=f"**{ENCOUNTER_DAILY_LIMIT-int(profile['daily_count'])}회**",inline=True); embed.add_field(name="선택 제한",value="**150초**",inline=True); embed.add_field(name="💡 TIP",value=random_tip(activity),inline=False)
    view=EncounterView(owner_id=ctx.author.id,encounter=encounter,user=user,save_data=save_data)
    try: message=await send_visual(ctx,embed,f"activities/{activity}/encounter",view=view)
    except Exception:
        _ACTIVE_USERS.discard(int(ctx.author.id)); raise
    view.message=message; return message


def register_v632_life_visuals(bot: commands.Bot, get_user: Callable[[int], Dict[str, Any]], check_registered: Callable[..., Any], save_data: Callable[[], None]) -> None:
    setattr(bot,"v632_send_visual",send_visual)
    setattr(bot,"v632_edit_visual",edit_visual)
    setattr(bot,"v632_tip",random_tip)
    setattr(bot,"v632_maybe_encounter",lambda ctx,activity,user: maybe_encounter(ctx,activity,user,save_data))
    setattr(bot,"v632_visual_version",VERSION)
