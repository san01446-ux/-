from __future__ import annotations

import asyncio
import random
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands


VERSION = "6.1.0"
KST = ZoneInfo("Asia/Seoul")
DIG_DAILY_LIMIT = 50
DIG_COOLDOWN_SECONDS = 60
TREASURE_CHANCE = 0.08
PENDING_LIMIT = 20

GRADE_ORDER: Tuple[str, ...] = ("E", "D", "C", "B", "A")
GRADE_WEIGHTS: Tuple[int, ...] = (500, 280, 140, 65, 15)
GRADE_COLORS: Mapping[str, int] = {
    "E": 0x7F8C8D,
    "D": 0x2ECC71,
    "C": 0x3498DB,
    "B": 0x9B59B6,
    "A": 0xF1C40F,
}
GRADE_VALUES: Mapping[str, Tuple[int, int]] = {
    "E": (150, 420),
    "D": (500, 1_250),
    "C": (1_600, 3_800),
    "B": (5_500, 13_500),
    "A": (22_000, 55_000),
}
TREASURE_NAMES: Mapping[str, Sequence[str]] = {
    "E": ("녹슨 생존자 배지", "금이 간 기념주화", "낡은 방공호 열쇠", "찌그러진 군번표"),
    "D": ("군용 나침반", "봉인된 탄피함", "오래된 회중시계", "구호대 완장"),
    "C": ("지휘관 인장", "감염 연구 표본", "은빛 데이터칩", "피난선 항로도"),
    "B": ("황금 방공호 열쇠", "왕좌의 파편", "푸른 핵 수정", "검은 통신 지휘봉"),
    "A": ("아바돈의 검은 성배", "종말 전쟁 깃발", "최초 생존자의 인장", "봉인된 왕좌 코어"),
}

APPRAISERS: Mapping[str, Dict[str, Any]] = {
    "마르코": {
        "label": "🧓 고철눈 마르코",
        "description": "무료 감정 · 가치 90% 매입 · 등급 상승 없음",
        "fee": 0,
        "multiplier": 0.90,
        "upgrade": 0.0,
        "emoji": "🧓",
    },
    "세라": {
        "label": "🧪 연구원 세라",
        "description": "300 식량 · 가치 105% 매입 · 3% 등급 상승",
        "fee": 300,
        "multiplier": 1.05,
        "upgrade": 0.03,
        "emoji": "🧪",
    },
    "라울": {
        "label": "🕶️ 암시장 라울",
        "description": "700 식량 · 가치 118% 매입 · 6% 등급 상승",
        "fee": 700,
        "multiplier": 1.18,
        "upgrade": 0.06,
        "emoji": "🕶️",
    },
    "이리스": {
        "label": "👁️ 왕좌 감정관 이리스",
        "description": "1,500 식량 · 가치 135% 매입 · 12% 등급 상승",
        "fee": 1500,
        "multiplier": 1.35,
        "upgrade": 0.12,
        "emoji": "👁️",
    },
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _kst_date() -> str:
    return _utc_now().astimezone(KST).strftime("%Y-%m-%d")


def _parse_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_seconds(seconds: int) -> str:
    seconds = max(0, int(seconds))
    minutes, remain = divmod(seconds, 60)
    return f"{minutes}분 {remain}초" if minutes else f"{remain}초"


async def _safe_reactions(message: Optional[discord.Message], emojis: Iterable[str]) -> None:
    if message is None:
        return
    for emoji in emojis:
        try:
            await message.add_reaction(emoji)
        except (discord.Forbidden, discord.HTTPException, AttributeError):
            return


def _ensure_profile(user: Dict[str, Any]) -> Dict[str, Any]:
    profile = user.setdefault("digging_v610", {})
    if not isinstance(profile, dict):
        profile = {}
        user["digging_v610"] = profile
    defaults: Dict[str, Any] = {
        "date": _kst_date(),
        "attempts": 0,
        "last_at": "",
        "total_attempts": 0,
        "empty_count": 0,
        "ordinary_count": 0,
        "treasure_count": 0,
        "appraised_count": 0,
        "total_treasure_value": 0,
        "pending": [],
        "grade_counts": {grade: 0 for grade in GRADE_ORDER},
        "codex": [],
    }
    for key, value in defaults.items():
        if key not in profile:
            if isinstance(value, dict):
                profile[key] = value.copy()
            elif isinstance(value, list):
                profile[key] = list(value)
            else:
                profile[key] = value
    if profile.get("date") != _kst_date():
        profile["date"] = _kst_date()
        profile["attempts"] = 0
    if not isinstance(profile.get("pending"), list):
        profile["pending"] = []
    if not isinstance(profile.get("grade_counts"), dict):
        profile["grade_counts"] = {grade: 0 for grade in GRADE_ORDER}
    for grade in GRADE_ORDER:
        profile["grade_counts"].setdefault(grade, 0)
    if not isinstance(profile.get("codex"), list):
        profile["codex"] = []
    return profile


def _cooldown_remaining(profile: Dict[str, Any]) -> int:
    last = _parse_time(profile.get("last_at"))
    if last is None:
        return 0
    elapsed = (_utc_now() - last).total_seconds()
    return max(0, int(DIG_COOLDOWN_SECONDS - elapsed + 0.999))


def _new_treasure() -> Dict[str, Any]:
    grade = random.choices(GRADE_ORDER, weights=GRADE_WEIGHTS, k=1)[0]
    return {
        "id": f"TR-{secrets.token_hex(3).upper()}",
        "grade": grade,
        "name": random.choice(tuple(TREASURE_NAMES[grade])),
        "base_value": random.randint(*GRADE_VALUES[grade]),
        "found_at": _utc_now().isoformat(),
    }


def _upgrade_grade(grade: str) -> str:
    try:
        index = GRADE_ORDER.index(grade)
    except ValueError:
        return "E"
    return GRADE_ORDER[min(index + 1, len(GRADE_ORDER) - 1)]


def _grade_reactions(grade: str) -> Tuple[str, ...]:
    return {
        "E": ("🪨", "📦", "✅"),
        "D": ("🟢", "🔎", "💰", "✅"),
        "C": ("🔵", "✨", "💎", "🎉"),
        "B": ("🟣", "🔥", "💎", "🎊", "🏆"),
        "A": ("🟡", "👑", "🌌", "💎", "🏆", "🎉"),
    }.get(grade, ("✅",))


def _ordinary_find(user: Dict[str, Any]) -> Tuple[str, Tuple[str, ...]]:
    roll = random.random()
    resources = user.setdefault("resources", {})
    if not isinstance(resources, dict):
        resources = {}
        user["resources"] = resources
    materials = user.setdefault("materials", {})
    if not isinstance(materials, dict):
        materials = {}
        user["materials"] = materials

    if roll < 0.28:
        return random.choice((
            "🕳️ 삽 끝에 걸린 건 깨진 콘크리트뿐입니다. 먼지만 한가득 날렸습니다.",
            "🪨 단단한 기반암입니다. 오늘은 땅이 입을 꾹 다물었습니다.",
            "🧟 오래된 감염체 발자국만 발견했습니다. 쓸 만한 물건은 없습니다.",
        )), ("🕳️", "🪨", "😵", "🧹")
    if roll < 0.55:
        amount = random.randint(1, 5)
        resources["고철"] = int(resources.get("고철", 0)) + amount
        return f"🔩 녹슨 배관 아래에서 **고철 {amount}개**를 캐냈습니다.", ("🔩", "⛏️", "📦", "✅")
    if roll < 0.72:
        amount = random.randint(1, 4)
        resources["광석"] = int(resources.get("광석", 0)) + amount
        return f"⛏️ 콘크리트 틈에서 **광석 {amount}개**가 반짝였습니다.", ("⛏️", "🪨", "✨", "✅")
    if roll < 0.88:
        amount = random.randint(35, 140)
        user["balance"] = int(user.get("balance", 0)) + amount
        user.setdefault("stats", {}).setdefault("earned", 0)
        user["stats"]["earned"] = int(user["stats"].get("earned", 0)) + amount
        return f"🥫 묻혀 있던 비상 식량 상자를 발견해 **식량 {amount}개**를 회수했습니다.", ("🥫", "💰", "📦", "👏")
    amount = random.randint(1, 3)
    materials["고대파편"] = int(materials.get("고대파편", 0)) + amount
    return f"🧩 정체불명의 금속 조각 **고대파편 {amount}개**를 찾았습니다.", ("🧩", "✨", "🔬", "✅")


def register_v610_digging_treasure(
    bot: commands.Bot,
    get_user: Any,
    check_registered: Any,
    save_data: Any,
) -> None:
    async def _appraise(ctx: commands.Context, appraiser_key: str) -> None:
        if not await check_registered(ctx):
            return
        user = get_user(ctx.author.id)
        profile = _ensure_profile(user)
        pending = profile["pending"]
        if not pending:
            message = await ctx.send("📭 미감정 보물이 없습니다. `!땅파기`로 보물을 찾아보세요.")
            await _safe_reactions(message, ("📭", "⛏️"))
            return
        info = APPRAISERS.get(appraiser_key)
        if info is None:
            await ctx.send("⚠️ 존재하지 않는 감정사입니다. `!감정사`를 확인하세요.")
            return
        fee = int(info["fee"])
        balance = int(user.get("balance", 0))
        if balance < fee:
            message = await ctx.send(
                f"⚠️ {info['label']}에게 맡기려면 식량 **{fee:,}개**가 필요합니다.\n"
                f"현재 보유 **{balance:,}개** · 무료 감정사는 **마르코**입니다."
            )
            await _safe_reactions(message, ("⚠️", "🥫", "🧓"))
            return

        treasure = pending.pop(0)
        original_grade = str(treasure.get("grade", "E"))
        final_grade = original_grade
        upgraded = False
        if original_grade != "A" and random.random() < float(info["upgrade"]):
            final_grade = _upgrade_grade(original_grade)
            upgraded = True

        if final_grade != original_grade:
            treasure["name"] = random.choice(tuple(TREASURE_NAMES[final_grade]))
            treasure["base_value"] = random.randint(*GRADE_VALUES[final_grade])
        base_value = max(1, int(treasure.get("base_value", 1)))
        payout = max(1, int(round(base_value * float(info["multiplier"]))))
        user["balance"] = balance - fee + payout
        profile["appraised_count"] = int(profile.get("appraised_count", 0)) + 1
        profile["total_treasure_value"] = int(profile.get("total_treasure_value", 0)) + payout
        profile["grade_counts"][final_grade] = int(profile["grade_counts"].get(final_grade, 0)) + 1
        codex = profile["codex"]
        if treasure["name"] not in codex:
            codex.append(treasure["name"])
        user.setdefault("stats", {}).setdefault("earned", 0)
        user["stats"]["earned"] = int(user["stats"].get("earned", 0)) + payout
        save_data()

        upgrade_text = f"\n🌟 감정 보정으로 **{original_grade} → {final_grade}등급** 상승!" if upgraded else ""
        embed = discord.Embed(
            title=f"{info['emoji']} 보물 감정 및 매입 완료",
            description=(
                f"감정사: **{info['label']}**\n"
                f"보물: **{treasure['name']}**\n"
                f"등급: **{final_grade}등급**{upgrade_text}"
            ),
            color=GRADE_COLORS.get(final_grade, 0x95A5A6),
            timestamp=_utc_now(),
        )
        embed.add_field(name="💎 감정 가치", value=f"**{base_value:,} 식량**", inline=True)
        embed.add_field(name="🤝 매입 지급", value=f"**+{payout:,} 식량**", inline=True)
        embed.add_field(name="🧾 감정 비용", value=f"**-{fee:,} 식량**", inline=True)
        embed.add_field(name="💰 현재 잔액", value=f"**{int(user['balance']):,} 식량**", inline=True)
        embed.add_field(name="📦 남은 미감정", value=f"**{len(pending)}개**", inline=True)
        embed.set_footer(text=f"ABADDON 보물 감정소 v{VERSION} · 감정과 동시에 식량으로 매입됩니다")
        message = await ctx.send(embed=embed)
        await _safe_reactions(message, _grade_reactions(final_grade))

    class AppraiserSelect(discord.ui.Select):
        def __init__(self, owner_id: int) -> None:
            self.owner_id = owner_id
            options = [
                discord.SelectOption(
                    label=str(info["label"]),
                    value=key,
                    description=str(info["description"])[:100],
                    emoji=str(info["emoji"]),
                )
                for key, info in APPRAISERS.items()
            ]
            super().__init__(placeholder="감정사를 선택하세요", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction) -> None:
            if interaction.user.id != self.owner_id:
                await interaction.response.send_message("이 감정 메뉴는 명령을 실행한 사용자만 사용할 수 있습니다.", ephemeral=True)
                return
            await interaction.response.defer()

            class InteractionContext:
                def __init__(self) -> None:
                    self.author = interaction.user
                    self.channel = interaction.channel
                    self.guild = interaction.guild

                async def send(self, *args: Any, **kwargs: Any) -> discord.Message:
                    kwargs.setdefault("wait", True)
                    return await interaction.followup.send(*args, **kwargs)

            await _appraise(InteractionContext(), self.values[0])
            await interaction.message.edit(view=None)

    class AppraiserView(discord.ui.View):
        def __init__(self, owner_id: int) -> None:
            super().__init__(timeout=180)
            self.add_item(AppraiserSelect(owner_id))

    @bot.command(name="땅파기", aliases=["굴착", "삽질"])
    async def digging(ctx: commands.Context) -> None:
        """하루 50회, 1분마다 폐허를 파서 물자와 미감정 보물을 찾습니다."""
        if not await check_registered(ctx):
            return
        user = get_user(ctx.author.id)
        profile = _ensure_profile(user)
        attempts = int(profile.get("attempts", 0))
        if attempts >= DIG_DAILY_LIMIT:
            message = await ctx.send(
                f"🛑 오늘의 땅파기 **{DIG_DAILY_LIMIT}회**를 모두 사용했습니다. 자정(KST)에 초기화됩니다.\n"
                "내일 다시 삽을 들거나 `!보물함`에서 오늘 찾은 보물을 확인하세요."
            )
            await _safe_reactions(message, ("🛑", "⛏️", "🌙"))
            return
        remaining_seconds = _cooldown_remaining(profile)
        if remaining_seconds > 0:
            message = await ctx.send(f"⏳ 땅이 아직 가라앉는 중입니다. 다음 굴착까지 **{_format_seconds(remaining_seconds)}** 남았습니다.")
            await _safe_reactions(message, ("⏳", "⛏️", "🪨"))
            return

        suspense = await ctx.send("⛏️ **폐허 굴착 시작!**\n삽날이 콘크리트 아래의 오래된 층을 긁어냅니다...")
        await _safe_reactions(suspense, ("⛏️", "🪨"))
        await asyncio.sleep(0.7)
        try:
            await suspense.edit(content="🧤 **잔해를 걷어내는 중...**\n금속성 소리와 함께 무언가가 모습을 드러냅니다.")
        except (discord.Forbidden, discord.HTTPException, AttributeError):
            pass
        await asyncio.sleep(0.7)

        profile["attempts"] = attempts + 1
        profile["last_at"] = _utc_now().isoformat()
        profile["total_attempts"] = int(profile.get("total_attempts", 0)) + 1
        remaining = DIG_DAILY_LIMIT - int(profile["attempts"])

        found_treasure = random.random() < TREASURE_CHANCE and len(profile["pending"]) < PENDING_LIMIT
        if found_treasure:
            treasure = _new_treasure()
            profile["pending"].append(treasure)
            profile["treasure_count"] = int(profile.get("treasure_count", 0)) + 1
            save_data()
            try:
                await suspense.edit(
                    content=(
                        "💥 **삽 끝에서 봉인된 상자가 튀어나왔습니다!**\n"
                        f"❓ **미감정 보물 1개** 획득 · 보물 ID `{treasure['id']}`\n"
                        f"📦 미감정 보물함 **{len(profile['pending'])}/{PENDING_LIMIT}**\n"
                        f"📅 오늘 남은 땅파기 **{remaining}회**\n\n"
                        "감정사를 선택하려면 `!보물감정`을 입력하세요."
                    )
                )
            except (discord.Forbidden, discord.HTTPException, AttributeError):
                pass
            await _safe_reactions(suspense, ("💥", "📦", "💎", "❓", "✨", "⛏️"))
            return

        text, reactions = _ordinary_find(user)
        profile["ordinary_count"] = int(profile.get("ordinary_count", 0)) + 1
        if text.startswith(("🕳️", "🪨", "🧟")):
            profile["empty_count"] = int(profile.get("empty_count", 0)) + 1
        save_data()
        full_note = "\n⚠️ 미감정 보물함이 가득 차 보물 발견 판정은 잠시 중단됩니다." if len(profile["pending"]) >= PENDING_LIMIT else ""
        try:
            await suspense.edit(
                content=(
                    f"{text}\n"
                    f"📅 오늘 남은 땅파기 **{remaining}회** · 다음 굴착 **1분 후**"
                    f"{full_note}"
                )
            )
        except (discord.Forbidden, discord.HTTPException, AttributeError):
            pass
        await _safe_reactions(suspense, reactions)

    @bot.command(name="보물감정", aliases=["보물감정소", "감정소"])
    async def appraise(ctx: commands.Context, *, 감정사: str = "") -> None:
        """미감정 보물의 감정사를 선택하고 즉시 식량으로 매입합니다."""
        if not await check_registered(ctx):
            return
        user = get_user(ctx.author.id)
        profile = _ensure_profile(user)
        if not profile["pending"]:
            message = await ctx.send("📭 미감정 보물이 없습니다. `!땅파기`로 보물을 찾아보세요.")
            await _safe_reactions(message, ("📭", "⛏️"))
            return
        key = 감정사.strip()
        if key:
            await _appraise(ctx, key)
            return
        treasure = profile["pending"][0]
        embed = discord.Embed(
            title="🔎 ABADDON 보물 감정소",
            description=(
                f"가장 오래된 미감정 보물 `{treasure.get('id', 'UNKNOWN')}`을 감정합니다.\n"
                f"현재 미감정 보물 **{len(profile['pending'])}개**\n\n"
                "감정사는 가치 배율과 등급 상승 확률이 다릅니다. 식량이 없다면 무료 감정사 **마르코**를 선택하세요."
            ),
            color=discord.Color.gold(),
        )
        for info in APPRAISERS.values():
            embed.add_field(name=str(info["label"]), value=str(info["description"]), inline=False)
        embed.set_footer(text="감정 완료 시 해당 보물은 감정사가 즉시 식량으로 매입합니다")
        message = await ctx.send(embed=embed, view=AppraiserView(ctx.author.id))
        await _safe_reactions(message, ("🔎", "💎", "🧾"))

    @bot.command(name="감정사", aliases=["감정사목록"])
    async def appraiser_list(ctx: commands.Context) -> None:
        lines = [f"{info['label']} — {info['description']}" for info in APPRAISERS.values()]
        message = await ctx.send("🔎 **[보물 감정사 목록]**\n" + "\n".join(lines) + "\n\n선택: `!보물감정` 또는 `!보물감정 감정사이름`")
        await _safe_reactions(message, ("🔎", "🧓", "🧪", "🕶️", "👁️"))

    @bot.command(name="보물함", aliases=["땅파기상태", "굴착상태"])
    async def treasure_box(ctx: commands.Context) -> None:
        if not await check_registered(ctx):
            return
        user = get_user(ctx.author.id)
        profile = _ensure_profile(user)
        remaining = max(0, DIG_DAILY_LIMIT - int(profile.get("attempts", 0)))
        grade_text = " · ".join(f"{grade} {int(profile['grade_counts'].get(grade, 0))}" for grade in reversed(GRADE_ORDER))
        pending_lines = []
        for item in profile["pending"][:5]:
            pending_lines.append(f"• `{item.get('id', 'UNKNOWN')}` · 발견 <t:{int((_parse_time(item.get('found_at')) or _utc_now()).timestamp())}:R>")
        pending_text = "\n".join(pending_lines) if pending_lines else "없음"
        embed = discord.Embed(
            title=f"📦 {ctx.author.display_name}의 굴착·보물 기록",
            color=discord.Color.dark_teal(),
        )
        embed.add_field(name="오늘 땅파기", value=f"{int(profile.get('attempts', 0))}/{DIG_DAILY_LIMIT} · 남음 **{remaining}회**", inline=False)
        embed.add_field(name="미감정 보물", value=f"**{len(profile['pending'])}개**\n{pending_text}", inline=False)
        embed.add_field(name="감정 등급 누계", value=grade_text, inline=False)
        embed.add_field(name="누적 감정 매입액", value=f"**{int(profile.get('total_treasure_value', 0)):,} 식량**", inline=True)
        embed.add_field(name="발견 도감", value=f"**{len(profile.get('codex', []))}종**", inline=True)
        embed.set_footer(text="수입 루트: !코인 → 소진 시 !알바 → 소진 시 !땅파기")
        message = await ctx.send(embed=embed)
        await _safe_reactions(message, ("📦", "⛏️", "💎", "📊"))
