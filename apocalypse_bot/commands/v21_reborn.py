import random
from datetime import datetime

import discord


OPTION_POOL = {
    "공격력": (1, 18),
    "방어력": (1, 18),
    "치명타": (1, 8),
    "회피": (1, 8),
    "감염저항": (1, 10),
    "행운": (1, 8),
}

SET_RULES = {
    "타이탄": {"keywords": ["타이탄", "중장갑"], "need": 2, "bonus": "공격력·방어력 +12", "power": 24},
    "심연": {"keywords": ["심연", "공허"], "need": 2, "bonus": "공격력 +18, 치명타 +4%", "power": 26},
    "천공": {"keywords": ["천공", "오메가"], "need": 2, "bonus": "방어력 +15, 회피 +4%", "power": 25},
    "종말": {"keywords": ["종말", "아포칼립스"], "need": 2, "bonus": "전투력 +35", "power": 35},
}

ROOMS = ["일반 전투", "함정", "보물방", "구조 신호", "정예 감염체", "오염 구역"]
HIDDEN_BOSSES = ["백색 포식자", "균열의 수문장", "지하왕 모르가나", "실험체 ZERO"]


def _ensure_user(u):
    u.setdefault("equipment_options", {})
    u.setdefault("dungeon_v21", {"max_floor": 1, "best_floor": 0, "clears": 0, "hidden_kills": 0})
    for key, value in {"max_floor": 1, "best_floor": 0, "clears": 0, "hidden_kills": 0}.items():
        u["dungeon_v21"].setdefault(key, value)
    u.setdefault("life_mastery", {"채집": 0, "낚시": 0, "벌목": 0, "광산": 0})
    for key in ["채집", "낚시", "벌목", "광산"]:
        u["life_mastery"].setdefault(key, 0)
    u.setdefault("worldboss_codex", {})
    u.setdefault("market_history", [])
    u.setdefault("materials", {})
    u["materials"].setdefault("강화석", 0)
    u["materials"].setdefault("강화보호권", 0)
    u["materials"].setdefault("옵션재설정권", 0)
    return u


def _option_count(tier):
    return {"일반": 1, "고급": 1, "희귀": 2, "영웅": 2, "전설": 3, "신화": 3, "유일": 4}.get(tier, 1)


def _roll_options(tier):
    result = {}
    keys = random.sample(list(OPTION_POOL), k=min(_option_count(tier), len(OPTION_POOL)))
    tier_mult = {"일반": 0.7, "고급": 0.9, "희귀": 1.1, "영웅": 1.35, "전설": 1.65, "신화": 2.0, "유일": 2.5}.get(tier, 1.0)
    for key in keys:
        low, high = OPTION_POOL[key]
        result[key] = max(1, int(random.randint(low, high) * tier_mult))
    return result


def _format_options(options):
    if not options:
        return "옵션 없음"
    return ", ".join(f"{k} +{v}{'%' if k in {'치명타', '회피', '감염저항'} else ''}" for k, v in options.items())


def _set_status(u):
    equipped = [x for x in u.get("equipment", {}).values() if x]
    lines = []
    total_power = 0
    for name, rule in SET_RULES.items():
        count = sum(1 for item in equipped if any(keyword in item for keyword in rule["keywords"]))
        active = count >= rule["need"]
        if active:
            total_power += rule["power"]
        lines.append(f"{'✅' if active else '⬜'} **{name} 세트** {count}/{rule['need']} — {rule['bonus']}")
    return lines, total_power


def register_v21_commands(
    bot,
    get_user,
    check_registered,
    save_data,
    send_pages,
    world_data,
    item_db,
    materials,
    find_item,
    calculate_user_power,
    spend_stamina,
    apply_damage,
    get_max_hp,
    add_season_points,
):
    for material in ["강화석", "강화보호권", "옵션재설정권"]:
        if material not in materials:
            materials.append(material)

    @bot.command(name="패치노트", aliases=["업데이트"])
    async def patch_notes(ctx):
        await ctx.send(
            "🔥 **V2.1 Apocalypse Reborn**\n"
            "• 상태 메시지 대폭 추가 및 실제 서버 데이터 연동\n"
            "• 심층 던전: 층 진행·함정·보물방·히든 보스\n"
            "• 강화석·강화보호권·강화 정보·강화 랭킹\n"
            "• 장비 랜덤 옵션·옵션 재설정·세트 효과\n"
            "• 월드보스 도감·광폭화·특수 패턴\n"
            "• 생활 숙련도·통합 랭킹\n"
            "• 기존 거래소 확장: 검색·경매·입찰·거래 기록"
        )

    @bot.command(name="강화정보")
    async def enhance_info(ctx, *, item_name: str):
        if not await check_registered(ctx):
            return
        u = _ensure_user(get_user(ctx.author.id))
        if item_name not in u.get("inventory", []):
            await ctx.send("⚠️ 해당 장비를 보유하고 있지 않습니다.")
            return
        _, info = find_item(item_name)
        current = u.get("enhancements", {}).get(item_name, 0)
        cost = int(info["price"] * (0.12 + current * 0.04))
        rate = max(15, 90 - current * 4)
        stone_need = 1 + current // 5
        await ctx.send(
            f"🔨 **[{item_name} 강화 정보]**\n"
            f"현재: **+{current}** / 다음 성공 확률: **{rate}%**\n"
            f"식량 비용: **{cost:,}개** / 강화석 권장: **{stone_need}개**\n"
            f"+10 이상 실패 시 단계 하락 가능\n"
            f"보호 강화: `!보호강화 {item_name}`"
        )

    @bot.command(name="보호강화")
    async def protected_enhance(ctx, *, item_name: str):
        if not await check_registered(ctx):
            return
        u = _ensure_user(get_user(ctx.author.id))
        if item_name not in u.get("inventory", []):
            await ctx.send("⚠️ 해당 장비를 보유하고 있지 않습니다.")
            return
        current = u["enhancements"].get(item_name, 0)
        if current >= 20:
            await ctx.send("⚠️ 이미 최대 강화 수치 +20입니다.")
            return
        _, info = find_item(item_name)
        cost = int(info["price"] * (0.18 + current * 0.05))
        stones = 1 + current // 5
        if u["materials"].get("강화보호권", 0) < 1:
            await ctx.send("⚠️ **강화보호권 1개**가 필요합니다. 심층 던전과 월드보스에서 획득할 수 있습니다.")
            return
        if u["materials"].get("강화석", 0) < stones:
            await ctx.send(f"⚠️ **강화석 {stones}개**가 필요합니다.")
            return
        if u.get("balance", 0) < cost:
            await ctx.send(f"⚠️ 식량 **{cost:,}개**가 필요합니다.")
            return
        u["balance"] -= cost
        u["materials"]["강화보호권"] -= 1
        u["materials"]["강화석"] -= stones
        rate = min(95, max(25, 95 - current * 3))
        if random.randint(1, 100) <= rate:
            u["enhancements"][item_name] = current + 1
            u.setdefault("stats", {}).setdefault("enhance_success", 0)
            u["stats"]["enhance_success"] += 1
            text = f"✅ 보호 강화 성공! **{item_name} +{current + 1}**"
        else:
            text = "🛡️ 강화 실패! 보호권이 장비의 강화 하락을 막았습니다."
        save_data()
        await ctx.send(f"🔨 **[보호 강화]**\n{text}\n성공 확률: **{rate}%** / 비용: **{cost:,}개**")

    @bot.command(name="강화랭킹")
    async def enhance_ranking(ctx):
        rows = []
        for uid in list(getattr(world_data, "keys", lambda: [])()):
            pass
        # 등록 유저는 bot 모듈의 get_user를 통해 접근할 수 없어 world_data와 분리되어 있으므로 guild 멤버를 기준으로 조회한다.
        if not ctx.guild:
            await ctx.send("⚠️ 서버 안에서 사용해 주세요.")
            return
        for member in ctx.guild.members:
            u = get_user(member.id)
            if not u:
                continue
            best = max(u.get("enhancements", {}).values(), default=0)
            total = sum(u.get("enhancements", {}).values())
            rows.append((best, total, member.id))
        rows.sort(reverse=True)
        lines = [f"{i}. <@{uid}> — 최고 **+{best}** / 총합 **{total}**" for i, (best, total, uid) in enumerate(rows[:20], 1)]
        await ctx.send("🏆 **[강화 랭킹]**\n" + ("\n".join(lines) if lines else "기록 없음"))

    @bot.command(name="장비옵션")
    async def equipment_option(ctx, *, item_name: str):
        if not await check_registered(ctx):
            return
        u = _ensure_user(get_user(ctx.author.id))
        if item_name not in u.get("inventory", []) and item_name not in u.get("equipment", {}).values():
            await ctx.send("⚠️ 해당 장비를 보유하고 있지 않습니다.")
            return
        tier, _ = find_item(item_name)
        if item_name not in u["equipment_options"]:
            u["equipment_options"][item_name] = _roll_options(tier)
            save_data()
        await ctx.send(f"💎 **[{item_name} 랜덤 옵션]**\n{_format_options(u['equipment_options'][item_name])}\n재설정: `!옵션재설정 {item_name}`")

    @bot.command(name="옵션재설정")
    async def reroll_option(ctx, *, item_name: str):
        if not await check_registered(ctx):
            return
        u = _ensure_user(get_user(ctx.author.id))
        if item_name not in u.get("inventory", []) and item_name not in u.get("equipment", {}).values():
            await ctx.send("⚠️ 해당 장비를 보유하고 있지 않습니다.")
            return
        tier, info = find_item(item_name)
        ticket = u["materials"].get("옵션재설정권", 0)
        cost = max(1500, info["price"] // 8)
        if ticket > 0:
            u["materials"]["옵션재설정권"] -= 1
            paid = "옵션재설정권 1개"
        elif u.get("balance", 0) >= cost:
            u["balance"] -= cost
            paid = f"식량 {cost:,}개"
        else:
            await ctx.send(f"⚠️ 옵션재설정권 또는 식량 **{cost:,}개**가 필요합니다.")
            return
        u["equipment_options"][item_name] = _roll_options(tier)
        save_data()
        await ctx.send(f"✨ **옵션 재설정 완료** ({paid})\n{item_name}: {_format_options(u['equipment_options'][item_name])}")

    @bot.command(name="세트효과")
    async def set_effect(ctx):
        if not await check_registered(ctx):
            return
        u = _ensure_user(get_user(ctx.author.id))
        lines, power = _set_status(u)
        await ctx.send("🧬 **[장비 세트 효과]**\n" + "\n".join(lines) + f"\n\n활성 세트 추가 전투력: **+{power}**")

    @bot.command(name="심층던전", aliases=["층던전"])
    async def deep_dungeon(ctx, floor: int = None):
        if not await check_registered(ctx):
            return
        u = _ensure_user(get_user(ctx.author.id))
        state = u["dungeon_v21"]
        floor = floor or state["max_floor"]
        if floor < 1 or floor > 100:
            await ctx.send("⚠️ 층은 1~100 사이로 입력하세요.")
            return
        if floor > state["max_floor"]:
            await ctx.send(f"🔒 현재 입장 가능한 최고 층은 **{state['max_floor']}층**입니다.")
            return
        stamina_cost = min(45, 12 + floor // 4)
        if not spend_stamina(u, stamina_cost):
            await ctx.send(f"⚠️ 스태미나가 부족합니다. 필요: **{stamina_cost}**")
            return
        room = random.choice(ROOMS)
        enemy_power = 12 + floor * 5 + random.randint(0, floor * 2 + 5)
        user_power = calculate_user_power(u)
        event_bonus = 0
        damage = 0
        details = []
        hidden = floor % 10 == 0 and random.random() < 0.45
        if hidden:
            room = f"히든 보스: {random.choice(HIDDEN_BOSSES)}"
            enemy_power = int(enemy_power * 1.7)
        if room == "함정":
            damage = random.randint(4, 10 + floor // 3)
            apply_damage(u, damage)
            event_bonus = -5
            details.append(f"🪤 함정 피해 **{damage}**")
        elif room == "보물방":
            event_bonus = 25
            details.append("💰 보물방 발견: 보상 증가")
        elif room == "구조 신호":
            heal = min(20, get_max_hp(u) - u.get("hp", 0))
            u["hp"] = min(get_max_hp(u), u.get("hp", 0) + heal)
            event_bonus = 10
            details.append(f"🚑 생존자 구조: HP **{heal} 회복**")
        elif room == "오염 구역":
            u["infection"] = min(100, u.get("infection", 0) + random.randint(2, 6))
            event_bonus = -3
            details.append("☣️ 감염도가 상승했습니다.")
        roll = user_power + random.randint(0, max(10, user_power // 2)) + event_bonus
        win = roll >= enemy_power
        if win:
            reward = 700 + floor * 260
            exp = 70 + floor * 24
            if room == "보물방":
                reward = int(reward * 1.8)
            if hidden:
                reward *= 3
                exp *= 2
                state["hidden_kills"] += 1
            u["balance"] += reward
            u["exp"] += exp
            state["clears"] += 1
            state["best_floor"] = max(state["best_floor"], floor)
            if floor == state["max_floor"] and floor < 100:
                state["max_floor"] += 1
            stone = 1 + floor // 20
            u["materials"]["강화석"] += stone
            drops = [f"강화석 {stone}개"]
            if random.random() < 0.05 + floor / 1000:
                u["materials"]["강화보호권"] += 1
                drops.append("강화보호권 1개")
            if random.random() < 0.04 + floor / 1500:
                u["materials"]["옵션재설정권"] += 1
                drops.append("옵션재설정권 1개")
            add_season_points(u, 8 + floor // 5)
            result = f"✅ **{floor}층 돌파 성공!** 식량 {reward:,} · 경험치 {exp:,}\n🎁 " + ", ".join(drops)
        else:
            loss = random.randint(8, 18 + floor // 2)
            apply_damage(u, loss)
            result = f"❌ **{floor}층 공략 실패** · HP 피해 **{loss}**"
        save_data()
        await ctx.send(
            f"🏰 **[심층 던전 {floor}층]**\n방: **{room}**\n"
            f"내 전투력 판정 **{roll}** vs 적 전투력 **{enemy_power}**\n"
            + ("\n".join(details) + "\n" if details else "") + result
        )

    @bot.command(name="던전기록")
    async def dungeon_record(ctx):
        if not await check_registered(ctx):
            return
        u = _ensure_user(get_user(ctx.author.id))
        d = u["dungeon_v21"]
        await ctx.send(
            f"🏰 **[{ctx.author.display_name}의 심층 던전 기록]**\n"
            f"입장 가능: **{d['max_floor']}층** / 최고 기록: **{d['best_floor']}층**\n"
            f"누적 클리어: **{d['clears']}회** / 히든 보스 처치: **{d['hidden_kills']}회**"
        )

    @bot.command(name="보스도감")
    async def boss_codex(ctx):
        if not await check_registered(ctx):
            return
        u = _ensure_user(get_user(ctx.author.id))
        if not u["worldboss_codex"]:
            await ctx.send("📕 아직 기록된 월드보스가 없습니다. 월드보스 전투에 참가해 보세요.")
            return
        lines = []
        for name, rec in sorted(u["worldboss_codex"].items(), key=lambda x: x[1].get("damage", 0), reverse=True):
            lines.append(f"• **{name}** — 피해 {rec.get('damage', 0):,} / 공격 {rec.get('attacks', 0)}회 / 처치 참여 {rec.get('kills', 0)}회")
        await send_pages(ctx.channel, "📕 **[월드보스 도감]**\n" + "\n".join(lines))

    @bot.command(name="생활숙련도")
    async def life_mastery(ctx):
        if not await check_registered(ctx):
            return
        u = _ensure_user(get_user(ctx.author.id))
        lines = []
        for name, exp in u["life_mastery"].items():
            level = 1 + exp // 20
            bonus = min(30, (level - 1) * 2)
            lines.append(f"• {name}: **Lv.{level}** ({exp % 20}/20) · 추가 획득 확률 **+{bonus}%**")
        await ctx.send("🎣 **[생활 숙련도]**\n" + "\n".join(lines))

    @bot.command(name="종합랭킹")
    async def total_ranking(ctx):
        if not ctx.guild:
            await ctx.send("⚠️ 서버 안에서 사용해 주세요.")
            return
        rows = []
        for member in ctx.guild.members:
            u = get_user(member.id)
            if not u:
                continue
            _ensure_user(u)
            score = calculate_user_power(u) * 10 + u.get("level", 1) * 50 + u.get("stats", {}).get("worldboss_damage", 0) // 100 + u["dungeon_v21"]["best_floor"] * 100
            rows.append((score, member.id, calculate_user_power(u), u["dungeon_v21"]["best_floor"]))
        rows.sort(reverse=True)
        lines = [f"{i}. <@{uid}> — 종합 **{score:,}점** · 전투력 {power:,} · 심층 {floor}층" for i, (score, uid, power, floor) in enumerate(rows[:20], 1)]
        await ctx.send("🏆 **[종합 생존자 랭킹]**\n" + ("\n".join(lines) if lines else "기록 없음"))

    @bot.command(name="거래검색")
    async def market_search(ctx, *, keyword: str):
        if not await check_registered(ctx):
            return
        listings = world_data.setdefault("market", {})
        lines = []
        for listing_id, listing in sorted(listings.items(), key=lambda x: int(x[0])):
            if keyword.lower() not in listing.get("item", "").lower():
                continue
            kind = "경매" if listing.get("auction") else "즉시구매"
            price = listing.get("highest_bid", listing.get("price", 0))
            lines.append(f"`#{listing_id}` **{listing.get('item')} +{listing.get('enhance', 0)}** | {kind} **{price:,}개**")
        await send_pages(ctx.channel, f"🔎 **[거래소 검색: {keyword}]**\n" + ("\n".join(lines[:50]) if lines else "검색 결과 없음"))

    @bot.command(name="경매등록")
    async def auction_register(ctx, item_name: str, start_price: int):
        if not await check_registered(ctx):
            return
        u = _ensure_user(get_user(ctx.author.id))
        if item_name not in u.get("inventory", []):
            await ctx.send("⚠️ 보유하지 않은 장비입니다.")
            return
        if start_price < 100:
            await ctx.send("⚠️ 시작가는 100 이상이어야 합니다.")
            return
        listing_id = str(world_data.setdefault("market_next_id", 1))
        world_data["market_next_id"] += 1
        enhance = u["enhancements"].get(item_name, 0)
        options = u["equipment_options"].pop(item_name, None)
        u["inventory"].remove(item_name)
        u["enhancements"].pop(item_name, None)
        world_data.setdefault("market", {})[listing_id] = {
            "seller": str(ctx.author.id), "item": item_name, "enhance": enhance,
            "price": start_price, "auction": True, "highest_bid": 0,
            "highest_bidder": None, "options": options, "created": datetime.now().isoformat(),
        }
        save_data()
        await ctx.send(f"🔨 경매 등록 완료 `#{listing_id}` — **{item_name} +{enhance}**, 시작가 **{start_price:,}개**")

    @bot.command(name="입찰")
    async def bid(ctx, listing_number: int, amount: int):
        if not await check_registered(ctx):
            return
        u = _ensure_user(get_user(ctx.author.id))
        listing = world_data.setdefault("market", {}).get(str(listing_number))
        if not listing or not listing.get("auction"):
            await ctx.send("⚠️ 해당 번호는 진행 중인 경매가 아닙니다.")
            return
        if listing["seller"] == str(ctx.author.id):
            await ctx.send("⚠️ 자신의 경매에는 입찰할 수 없습니다.")
            return
        minimum = max(listing.get("price", 0), listing.get("highest_bid", 0) + 100)
        if amount < minimum:
            await ctx.send(f"⚠️ 최소 입찰가는 **{minimum:,}개**입니다.")
            return
        if u.get("balance", 0) < amount:
            await ctx.send("⚠️ 보유 식량이 부족합니다.")
            return
        previous_uid = listing.get("highest_bidder")
        previous_bid = listing.get("highest_bid", 0)
        if previous_uid:
            previous = get_user(previous_uid)
            if previous:
                previous["balance"] += previous_bid
        u["balance"] -= amount
        listing["highest_bid"] = amount
        listing["highest_bidder"] = str(ctx.author.id)
        save_data()
        await ctx.send(f"🔨 <@{ctx.author.id}> 입찰 완료! `#{listing_number}` 현재 최고가 **{amount:,}개**")

    @bot.command(name="경매마감")
    async def auction_close(ctx, listing_number: int):
        if not await check_registered(ctx):
            return
        listing_id = str(listing_number)
        listing = world_data.setdefault("market", {}).get(listing_id)
        if not listing or not listing.get("auction"):
            await ctx.send("⚠️ 해당 번호는 진행 중인 경매가 아닙니다.")
            return
        is_admin = bool(ctx.guild and ctx.author.guild_permissions.administrator)
        if listing["seller"] != str(ctx.author.id) and not is_admin:
            await ctx.send("⚠️ 판매자 또는 관리자만 경매를 마감할 수 있습니다.")
            return
        seller = get_user(listing["seller"])
        bidder_id = listing.get("highest_bidder")
        if not bidder_id:
            if seller:
                seller["inventory"].append(listing["item"])
                seller["enhancements"][listing["item"]] = listing.get("enhance", 0)
                if listing.get("options"):
                    _ensure_user(seller)["equipment_options"][listing["item"]] = listing["options"]
            del world_data["market"][listing_id]
            save_data()
            await ctx.send("📦 입찰자가 없어 장비가 판매자에게 반환됐습니다.")
            return
        bidder = _ensure_user(get_user(bidder_id))
        bidder["inventory"].append(listing["item"])
        bidder["enhancements"][listing["item"]] = listing.get("enhance", 0)
        if listing.get("options"):
            bidder["equipment_options"][listing["item"]] = listing["options"]
        fee = max(1, int(listing["highest_bid"] * 0.05))
        payout = listing["highest_bid"] - fee
        if seller:
            seller["balance"] += payout
            _ensure_user(seller)["market_history"].append({"type": "판매", "item": listing["item"], "price": listing["highest_bid"], "date": datetime.now().isoformat()})
        bidder["market_history"].append({"type": "구매", "item": listing["item"], "price": listing["highest_bid"], "date": datetime.now().isoformat()})
        del world_data["market"][listing_id]
        save_data()
        await ctx.send(f"✅ 경매 마감! <@{bidder_id}> 낙찰 **{listing['highest_bid']:,}개** · 판매자 수령 **{payout:,}개** (수수료 5%)")

    @bot.command(name="거래기록")
    async def market_history(ctx):
        if not await check_registered(ctx):
            return
        u = _ensure_user(get_user(ctx.author.id))
        rows = u["market_history"][-15:]
        if not rows:
            await ctx.send("📭 저장된 거래 기록이 없습니다.")
            return
        lines = [f"• {r.get('type')} **{r.get('item')}** — {r.get('price', 0):,}개" for r in reversed(rows)]
        await ctx.send("📒 **[최근 거래 기록]**\n" + "\n".join(lines))
