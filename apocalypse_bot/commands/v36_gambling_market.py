from __future__ import annotations

import asyncio
import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional, Tuple

import discord
from discord.ext import commands, tasks


KST = timezone(timedelta(hours=9))
MARKET_TICK_SECONDS = 60
TRADE_FEE_RATE = 0.02
TRADE_COOLDOWN_SECONDS = 10
MAX_TRADE_HISTORY = 20
MAX_PRICE_HISTORY = 30


MARKET_ASSETS: Dict[str, Dict[str, Any]] = {
    "보급권": {
        "name": "일반 보급권",
        "emoji": "🟢",
        "base_price": 750,
        "min_price": 100,
        "max_price": 20_000,
        "volatility": 0.018,
        "aliases": ["일반", "일반보급권", "보급", "보급권"],
        "desc": "폐허 암시장에서 가장 자주 거래되는 기본 보급 증서",
    },
    "군수권": {
        "name": "군용 보급권",
        "emoji": "🔵",
        "base_price": 55_000,
        "min_price": 5_000,
        "max_price": 1_500_000,
        "volatility": 0.026,
        "aliases": ["군용", "군수", "군용보급권", "군수권"],
        "desc": "군수 창고 물자 우선 배급권",
    },
    "혈청": {
        "name": "붉은 변이 혈청",
        "emoji": "🟠",
        "base_price": 1_800_000,
        "min_price": 100_000,
        "max_price": 80_000_000,
        "volatility": 0.038,
        "aliases": ["혈청", "붉은혈청", "변이혈청", "붉은변이혈청"],
        "desc": "효능과 부작용이 모두 불명확한 고위험 실험 물질",
    },
    "유물": {
        "name": "천상 유물",
        "emoji": "🌸",
        "base_price": 58_000_000,
        "min_price": 1_000_000,
        "max_price": 2_000_000_000,
        "volatility": 0.052,
        "aliases": ["유물", "천상", "천상유물"],
        "desc": "종말 이전 문명의 흔적이 담긴 희귀 유물",
    },
    "코어": {
        "name": "아바돈 코어",
        "emoji": "💠",
        "base_price": 2_000_000_000,
        "min_price": 50_000_000,
        "max_price": 100_000_000_000,
        "volatility": 0.072,
        "aliases": ["코어", "아바돈", "아바돈코어"],
        "desc": "공허 에너지가 응축된 최상위 투기 자산",
    },
}


MARKET_EVENTS = [
    ("📦 대형 보급 수송대 발견", 0.04),
    ("🧟 감염체 습격으로 공급망 붕괴", -0.05),
    ("📡 구조 신호 포착으로 매수세 유입", 0.035),
    ("☣️ 혈청 부작용 소문 확산", -0.065),
    ("🏚️ 암시장 단속 소식", -0.04),
    ("🛰️ 군수 위성 데이터 복구", 0.055),
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def _clean_asset_name(value: str) -> str:
    return str(value or "").replace(" ", "").lower()


def resolve_asset(value: str) -> Optional[str]:
    target = _clean_asset_name(value)
    if not target:
        return None
    for key, info in MARKET_ASSETS.items():
        candidates = [key, info["name"], *info.get("aliases", [])]
        if target in {_clean_asset_name(candidate) for candidate in candidates}:
            return key
    return None


def ensure_market(world_data: Dict[str, Any]) -> Dict[str, Any]:
    market = world_data.setdefault("gambling_market", {})
    if not isinstance(market, dict):
        market = {}
        world_data["gambling_market"] = market

    assets = market.setdefault("assets", {})
    if not isinstance(assets, dict):
        assets = {}
        market["assets"] = assets

    for key, info in MARKET_ASSETS.items():
        entry = assets.setdefault(key, {})
        if not isinstance(entry, dict):
            entry = {}
            assets[key] = entry
        initial = int(info["base_price"])
        entry.setdefault("price", initial)
        entry.setdefault("previous_price", initial)
        entry.setdefault("open_price", initial)
        entry.setdefault("high_price", initial)
        entry.setdefault("low_price", initial)
        entry.setdefault("history", [initial])
        entry["price"] = max(int(info["min_price"]), min(int(info["max_price"]), int(entry.get("price", initial) or initial)))
        if not isinstance(entry.get("history"), list):
            entry["history"] = [entry["price"]]

    market.setdefault("last_update", _utc_now().isoformat())
    market.setdefault("tick", 0)
    market.setdefault("event", "")
    market.setdefault("event_expires_tick", 0)
    return market


def ensure_user_market(user: Dict[str, Any]) -> Dict[str, Any]:
    account = user.setdefault("gambling_market", {})
    if not isinstance(account, dict):
        account = {}
        user["gambling_market"] = account

    holdings = account.setdefault("holdings", {})
    if not isinstance(holdings, dict):
        holdings = {}
        account["holdings"] = holdings

    for key in MARKET_ASSETS:
        position = holdings.setdefault(key, {})
        if not isinstance(position, dict):
            position = {}
            holdings[key] = position
        position.setdefault("quantity", 0)
        position.setdefault("avg_price", 0)
        position["quantity"] = max(0, int(position.get("quantity", 0) or 0))
        position["avg_price"] = max(0, int(position.get("avg_price", 0) or 0))

    trades = account.setdefault("trades", [])
    if not isinstance(trades, list):
        account["trades"] = []
    account.setdefault("realized_profit", 0)
    account.setdefault("fees_paid", 0)
    account.setdefault("last_trade", "")
    return account


def _single_market_tick(market: Dict[str, Any]) -> None:
    market["tick"] = int(market.get("tick", 0) or 0) + 1
    global_event_shift = 0.0

    if random.random() < 0.035:
        event_name, global_event_shift = random.choice(MARKET_EVENTS)
        market["event"] = event_name
        market["event_expires_tick"] = market["tick"] + random.randint(2, 5)
    elif market.get("event") and market["tick"] >= int(market.get("event_expires_tick", 0) or 0):
        market["event"] = ""

    for key, info in MARKET_ASSETS.items():
        entry = market["assets"][key]
        old_price = max(1, int(entry.get("price", info["base_price"])))
        entry["previous_price"] = old_price

        base_price = float(info["base_price"])
        volatility = float(info["volatility"])
        mean_reversion = ((base_price - old_price) / max(base_price, 1.0)) * 0.0025
        random_move = random.gauss(0.0, volatility)
        asset_event = 0.0

        if random.random() < 0.012:
            asset_event = random.choice([-1, 1]) * random.uniform(volatility * 2.5, volatility * 5.5)

        total_change = max(-0.35, min(0.35, random_move + mean_reversion + global_event_shift + asset_event))
        new_price = int(round(old_price * (1.0 + total_change)))
        new_price = max(int(info["min_price"]), min(int(info["max_price"]), new_price))

        entry["price"] = new_price
        entry["high_price"] = max(int(entry.get("high_price", new_price) or new_price), new_price)
        entry["low_price"] = min(int(entry.get("low_price", new_price) or new_price), new_price)
        history = entry.setdefault("history", [])
        history.append(new_price)
        del history[:-MAX_PRICE_HISTORY]


def update_market(world_data: Dict[str, Any], force: bool = False) -> bool:
    market = ensure_market(world_data)
    now = _utc_now()
    last_update = _parse_time(market.get("last_update")) or now
    elapsed = max(0.0, (now - last_update).total_seconds())

    ticks = int(elapsed // MARKET_TICK_SECONDS)
    if force and ticks <= 0:
        ticks = 1
    if ticks <= 0:
        return False

    # 장시간 오프라인 후 한 번에 과도하게 움직이지 않도록 최대 120분만 보정합니다.
    ticks = min(ticks, 120)
    for _ in range(ticks):
        _single_market_tick(market)
    market["last_update"] = now.isoformat()
    return True


def _price_change(entry: Dict[str, Any]) -> Tuple[int, float]:
    current = int(entry.get("price", 0) or 0)
    previous = int(entry.get("previous_price", current) or current)
    difference = current - previous
    percent = difference / max(previous, 1) * 100
    return difference, percent


def _format_change(entry: Dict[str, Any]) -> str:
    difference, percent = _price_change(entry)
    if difference > 0:
        return f"📈 +{percent:.2f}%"
    if difference < 0:
        return f"📉 {percent:.2f}%"
    return "➖ 0.00%"


def _market_embed(world_data: Dict[str, Any]) -> discord.Embed:
    market = ensure_market(world_data)
    now_kst = _utc_now().astimezone(KST)
    embed = discord.Embed(
        title="📊 폐허 암시장 실시간 시세",
        description=(
            f"**{now_kst:%Y-%m-%d %H시 %M분 %S초} 기준**\n"
            "시세는 모든 서버에서 공유되며 **1분마다 자동 변동**합니다."
        ),
        color=discord.Color.purple(),
    )

    for key, info in MARKET_ASSETS.items():
        entry = market["assets"][key]
        embed.add_field(
            name=f"{info['emoji']} {info['name']}",
            value=(
                f"**{int(entry['price']):,} 식량**  {_format_change(entry)}\n"
                f"고가 {int(entry['high_price']):,} · 저가 {int(entry['low_price']):,}"
            ),
            inline=False,
        )

    if market.get("event"):
        embed.add_field(name="⚠️ 현재 시장 소식", value=str(market["event"]), inline=False)

    embed.set_footer(text="거래 수수료 2% · 인게임 식량 전용 · 현금 환전 불가")
    return embed


def _record_trade(account: Dict[str, Any], action: str, asset_key: str, quantity: int, price: int, fee: int, total: int) -> None:
    account.setdefault("trades", []).append(
        {
            "time": _utc_now().isoformat(),
            "action": action,
            "asset": asset_key,
            "quantity": int(quantity),
            "price": int(price),
            "fee": int(fee),
            "total": int(total),
        }
    )
    del account["trades"][:-MAX_TRADE_HISTORY]
    account["last_trade"] = _utc_now().isoformat()


def _trade_cooldown_remaining(account: Dict[str, Any]) -> int:
    last = _parse_time(account.get("last_trade"))
    if not last:
        return 0
    remaining = int((last + timedelta(seconds=TRADE_COOLDOWN_SECONDS) - _utc_now()).total_seconds())
    return max(0, remaining)


def _parse_quantity(value: Any, owned: int = 0) -> Optional[int]:
    text = str(value or "").strip().lower().replace(",", "")
    if text in {"전부", "all", "전체"}:
        return owned if owned > 0 else None
    try:
        quantity = int(text)
    except (TypeError, ValueError):
        return None
    return quantity if quantity > 0 else None


def register_v36_commands(
    bot: commands.Bot,
    get_user: Callable[[int], Dict[str, Any]],
    check_registered: Callable[..., Any],
    save_data: Callable[[], None],
    world_data: Dict[str, Any],
    progress_quest: Optional[Callable[[Dict[str, Any], str], None]] = None,
) -> None:
    """V3.6 실시간 암시장과 도박 안내 명령어를 등록합니다."""
    ensure_market(world_data)
    save_data()

    user_locks: Dict[int, asyncio.Lock] = {}

    def get_lock(user_id: int) -> asyncio.Lock:
        return user_locks.setdefault(int(user_id), asyncio.Lock())

    async def sync_market(force: bool = False) -> None:
        if update_market(world_data, force=force):
            save_data()

    async def show_prices(ctx: commands.Context) -> None:
        if not await check_registered(ctx):
            return
        await sync_market()
        await ctx.send(embed=_market_embed(world_data))

    async def show_help(ctx: commands.Context) -> None:
        if not await check_registered(ctx):
            return
        await ctx.send(
            "🎰 **[ABADDON 도박·암시장 안내]**\n"
            "배팅 범위: **최소 100 ~ 최대 10,000,000 식량**\n\n"
            "🎲 **도박 콘텐츠**\n"
            "`!탐색 왼쪽/오른쪽 금액` · `/탐색` — 갈림길 방향 도박\n"
            "`!주파수 금액` · `/주파수` — 신호 슬롯 도박\n"
            "`!룰렛 금액` · `/룰렛` — 탄환 확률이 1/6→1/5→1/4로 올라가는 생존 룰렛\n"
            "`!도박잔액` · `/도박잔액` — 현재 식량과 최근·오늘·누적 손익\n"
            "`!파산신청` · `/파산신청` — 빚 일부 탕감\n\n"
            "🧰 **식량 획득 콘텐츠**\n"
            "`!알바` · `/알바` — 하루 50회 알바, 레벨이 높을수록 사고 확률 감소\n"
            "`!코인` · `/코인` — 3분마다 희귀 암시장 자산 탐색(하루 30회)\n"
            "확률: 실패 35% · 일반 48% · 군용 12% · 혈청 3.8% · 유물 1.1% · 코어 0.1%\n\n"
            "📊 **실시간 암시장**\n"
            "`!시세` · `/암시장 시세` — 현재 종목별 시세\n"
            "`!매수 일반 10` · `/암시장 매수` — 종목 구매\n"
            "`!매도 일반 전부` · `/암시장 매도` — 보유 종목 판매\n"
            "`!자산` · `/암시장 자산` — 평가금과 손익 확인\n"
            "`!암시장기록` · `/암시장 기록` — 최근 거래 확인\n"
            "`!암시장알림설정 [@역할]` · `/암시장 알림설정` — 급등락·시장 사건 자동 알림\n"
            "`!암시장알림상태` · `/암시장 알림상태`\n"
            "`!암시장알림해제` · `/암시장 알림해제`\n\n"
            "종목 별칭: `일반`, `군용`, `혈청`, `유물`, `코어`\n"
            "⚠️ 모든 기능은 **게임 내 식량만 사용**하며 현금 가치나 환전 기능이 없습니다."
        )

    async def buy_asset(ctx: commands.Context, asset_name: str, quantity_value: Any) -> None:
        if not await check_registered(ctx):
            return
        await sync_market()
        asset_key = resolve_asset(asset_name)
        quantity = _parse_quantity(quantity_value)
        if not asset_key or not quantity:
            await ctx.send("⚠️ 사용법: `!매수 일반 10`\n종목: 일반 / 군용 / 혈청 / 유물 / 코어")
            return

        async with get_lock(ctx.author.id):
            user = get_user(ctx.author.id)
            account = ensure_user_market(user)
            remaining = _trade_cooldown_remaining(account)
            if remaining > 0:
                await ctx.send(f"⏳ 연속 거래 방지를 위해 **{remaining}초** 뒤 다시 거래하세요.")
                return

            market = ensure_market(world_data)
            price = int(market["assets"][asset_key]["price"])
            subtotal = price * quantity
            fee = max(1, math.ceil(subtotal * TRADE_FEE_RATE))
            total_cost = subtotal + fee
            if user.get("balance", 0) < total_cost:
                await ctx.send(
                    f"⚠️ 식량이 부족합니다.\n필요: **{total_cost:,}개** · 보유: **{int(user.get('balance', 0)):,}개**"
                )
                return

            position = account["holdings"][asset_key]
            old_quantity = int(position["quantity"])
            old_avg = int(position["avg_price"])
            new_quantity = old_quantity + quantity
            new_avg = int(round(((old_quantity * old_avg) + (quantity * price)) / max(new_quantity, 1)))

            user["balance"] -= total_cost
            position["quantity"] = new_quantity
            position["avg_price"] = new_avg
            account["fees_paid"] = int(account.get("fees_paid", 0)) + fee
            _record_trade(account, "매수", asset_key, quantity, price, fee, total_cost)
            user.setdefault("stats", {}).setdefault("gambles", 0)
            user["stats"]["gambles"] += 1
            if progress_quest:
                progress_quest(user, "도박 참여")
            save_data()

            info = MARKET_ASSETS[asset_key]
            await ctx.send(
                f"✅ **[암시장 매수 완료]**\n"
                f"{info['emoji']} {info['name']} **{quantity:,}개**\n"
                f"체결가 **{price:,}** · 수수료 **{fee:,}** · 총 지출 **{total_cost:,} 식량**\n"
                f"보유 수량 **{new_quantity:,}개** · 평균 단가 **{new_avg:,}**"
            )

    async def sell_asset(ctx: commands.Context, asset_name: str, quantity_value: Any) -> None:
        if not await check_registered(ctx):
            return
        await sync_market()
        asset_key = resolve_asset(asset_name)
        if not asset_key:
            await ctx.send("⚠️ 사용법: `!매도 일반 10` 또는 `!매도 일반 전부`")
            return

        async with get_lock(ctx.author.id):
            user = get_user(ctx.author.id)
            account = ensure_user_market(user)
            position = account["holdings"][asset_key]
            owned = int(position["quantity"])
            quantity = _parse_quantity(quantity_value, owned=owned)
            if not quantity or quantity > owned:
                await ctx.send(f"⚠️ 판매 수량이 올바르지 않습니다. 현재 보유: **{owned:,}개**")
                return

            remaining = _trade_cooldown_remaining(account)
            if remaining > 0:
                await ctx.send(f"⏳ 연속 거래 방지를 위해 **{remaining}초** 뒤 다시 거래하세요.")
                return

            market = ensure_market(world_data)
            price = int(market["assets"][asset_key]["price"])
            gross = price * quantity
            fee = max(1, math.ceil(gross * TRADE_FEE_RATE))
            net = max(0, gross - fee)
            avg_price = int(position["avg_price"])
            realized = net - (avg_price * quantity)

            user["balance"] += net
            position["quantity"] = owned - quantity
            if position["quantity"] <= 0:
                position["quantity"] = 0
                position["avg_price"] = 0
            account["realized_profit"] = int(account.get("realized_profit", 0)) + realized
            account["fees_paid"] = int(account.get("fees_paid", 0)) + fee
            _record_trade(account, "매도", asset_key, quantity, price, fee, net)
            user.setdefault("stats", {}).setdefault("gambles", 0)
            user["stats"]["gambles"] += 1
            if realized > 0:
                user["stats"].setdefault("earned", 0)
                user["stats"]["earned"] += realized
            if progress_quest:
                progress_quest(user, "도박 참여")
            save_data()

            sign = "+" if realized >= 0 else ""
            info = MARKET_ASSETS[asset_key]
            await ctx.send(
                f"💱 **[암시장 매도 완료]**\n"
                f"{info['emoji']} {info['name']} **{quantity:,}개**\n"
                f"체결가 **{price:,}** · 수수료 **{fee:,}** · 순수령 **{net:,} 식량**\n"
                f"실현 손익 **{sign}{realized:,} 식량** · 남은 수량 **{position['quantity']:,}개**"
            )

    async def show_assets(ctx: commands.Context) -> None:
        if not await check_registered(ctx):
            return
        await sync_market()
        user = get_user(ctx.author.id)
        account = ensure_user_market(user)
        market = ensure_market(world_data)

        lines = []
        total_cost = 0
        total_value = 0
        for key, info in MARKET_ASSETS.items():
            position = account["holdings"][key]
            quantity = int(position["quantity"])
            if quantity <= 0:
                continue
            avg_price = int(position["avg_price"])
            current_price = int(market["assets"][key]["price"])
            cost = avg_price * quantity
            value = current_price * quantity
            profit = value - cost
            total_cost += cost
            total_value += value
            sign = "+" if profit >= 0 else ""
            lines.append(
                f"{info['emoji']} **{info['name']}** {quantity:,}개\n"
                f"평단 {avg_price:,} · 현재 {current_price:,} · 평가손익 **{sign}{profit:,}**"
            )

        unrealized = total_value - total_cost
        realized = int(account.get("realized_profit", 0))
        sign_u = "+" if unrealized >= 0 else ""
        sign_r = "+" if realized >= 0 else ""
        body = "\n\n".join(lines) if lines else "보유 중인 암시장 자산이 없습니다."
        await ctx.send(
            f"💼 **[{ctx.author.display_name}의 암시장 자산]**\n"
            f"{body}\n\n"
            f"평가금 **{total_value:,} 식량** · 평가손익 **{sign_u}{unrealized:,}**\n"
            f"누적 실현손익 **{sign_r}{realized:,}** · 누적 수수료 **{int(account.get('fees_paid', 0)):,}**\n"
            f"현금성 식량 **{int(user.get('balance', 0)):,}개**"
        )

    async def show_history(ctx: commands.Context) -> None:
        if not await check_registered(ctx):
            return
        user = get_user(ctx.author.id)
        account = ensure_user_market(user)
        trades = list(account.get("trades", []))[-10:]
        if not trades:
            await ctx.send("📜 아직 암시장 거래 기록이 없습니다.")
            return

        lines = []
        for trade in reversed(trades):
            asset_key = trade.get("asset")
            info = MARKET_ASSETS.get(asset_key, {"emoji": "📦", "name": str(asset_key)})
            when = _parse_time(trade.get("time"))
            when_text = when.astimezone(KST).strftime("%m-%d %H:%M") if when else "시간 미상"
            lines.append(
                f"`{when_text}` {info['emoji']} **{trade.get('action', '?')}** "
                f"{info['name']} {int(trade.get('quantity', 0)):,}개 @ {int(trade.get('price', 0)):,}"
            )
        await ctx.send("📜 **[최근 암시장 거래 기록]**\n" + "\n".join(lines))

    # !명령어 호환
    @bot.command(name="시세", aliases=["암시장시세"])
    async def market_price_legacy(ctx: commands.Context) -> None:
        await show_prices(ctx)

    @bot.command(name="매수", aliases=["투자"])
    async def market_buy_legacy(ctx: commands.Context, 종목: str, 수량: str) -> None:
        await buy_asset(ctx, 종목, 수량)

    @bot.command(name="매도")
    async def market_sell_legacy(ctx: commands.Context, 종목: str, 수량: str) -> None:
        await sell_asset(ctx, 종목, 수량)

    @bot.command(name="자산", aliases=["투자자산"])
    async def market_assets_legacy(ctx: commands.Context) -> None:
        await show_assets(ctx)

    @bot.command(name="암시장기록", aliases=["투자기록"])
    async def market_history_legacy(ctx: commands.Context) -> None:
        await show_history(ctx)

    @bot.command(name="도박정보", aliases=["도박도움말"])
    async def gambling_help_legacy(ctx: commands.Context) -> None:
        await show_help(ctx)

    # /암시장 하위 명령어
    @bot.hybrid_group(
        name="암시장",
        aliases=["도박시장"],
        fallback="시세",
        invoke_without_command=True,
        description="실시간 시세를 확인하고 암시장 자산을 거래합니다.",
    )
    async def black_market_group(ctx: commands.Context) -> None:
        await show_prices(ctx)

    @black_market_group.command(name="매수", description="식량으로 암시장 종목을 구매합니다.")
    async def black_market_buy(ctx: commands.Context, 종목: str, 수량: int) -> None:
        await buy_asset(ctx, 종목, 수량)

    @black_market_group.command(name="매도", description="보유한 암시장 종목을 판매합니다.")
    async def black_market_sell(ctx: commands.Context, 종목: str, 수량: str) -> None:
        await sell_asset(ctx, 종목, 수량)

    @black_market_group.command(name="자산", description="보유 종목의 평가금과 손익을 확인합니다.")
    async def black_market_assets(ctx: commands.Context) -> None:
        await show_assets(ctx)

    @black_market_group.command(name="기록", description="최근 암시장 매수·매도 기록을 확인합니다.")
    async def black_market_history(ctx: commands.Context) -> None:
        await show_history(ctx)

    @black_market_group.command(name="도움말", description="기존 도박과 실시간 암시장 명령어를 확인합니다.")
    async def black_market_help(ctx: commands.Context) -> None:
        await show_help(ctx)

    @tasks.loop(seconds=MARKET_TICK_SECONDS)
    async def market_price_loop() -> None:
        if update_market(world_data, force=True):
            save_data()

    @bot.listen("on_ready")
    async def start_v36_market_loop() -> None:
        if not market_price_loop.is_running():
            market_price_loop.start()
