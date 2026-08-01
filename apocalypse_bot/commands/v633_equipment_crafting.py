from __future__ import annotations

import asyncio
import io
import json
import math
import random
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from apocalypse_bot.commands import v432_forge_live as forge

VERSION = "6.3.3"
ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets" / "v633"


def _load_manifest(filename: str) -> Dict[str, str]:
    path = ASSET_ROOT / filename
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}


EQUIPMENT_ASSETS = _load_manifest("equipment_manifest.json")
TREASURE_ASSETS = _load_manifest("treasure_manifest.json")

STAGE_LABELS = (
    (20, "공허 초월"),
    (18, "경계 돌파"),
    (15, "아바돈 각성"),
    (12, "심연 개방"),
    (10, "종말 개조"),
    (7, "광휘 증폭"),
    (5, "단련 완료"),
    (0, "기본 형상"),
)

GRADE_TO_TIER = {
    "E": "일반",
    "D": "고급",
    "C": "희귀",
    "B": "영웅",
    "A": "전설",
}

MODE_LABELS = {
    "acquire": ("📦 장비 획득", "새 장비가 인벤토리에 등록되었습니다."),
    "equip": ("⚔️ 장비 장착", "장비가 전투 슬롯에 연결되었습니다."),
    "status": ("🛡️ 장비 현황", "현재 장착 장비의 강화 외형입니다."),
    "identify": ("🔍 장비 감정", "장비의 능력치와 구조 분석을 완료했습니다."),
    "preview": ("✨ 장비 외형", "현재 강화 단계의 외형 진화를 확인합니다."),
}


def enhancement_stage(level: int) -> str:
    level = max(0, int(level))
    for minimum, label in STAGE_LABELS:
        if level >= minimum:
            return label
    return "기본 형상"


def next_visual_stage(level: int) -> str:
    level = max(0, int(level))
    targets = [(5, "단련 완료"), (7, "광휘 증폭"), (10, "종말 개조"), (12, "심연 개방"), (15, "아바돈 각성"), (18, "경계 돌파"), (20, "공허 초월")]
    for target, label in targets:
        if level < target:
            return f"+{target} {label}"
    return "최종 단계 도달"


def _safe_filename(prefix: str) -> str:
    return f"abaddon_v633_{prefix}.png"


def _asset_path(mapping: Mapping[str, str], name: str) -> Optional[Path]:
    relative = mapping.get(str(name))
    if not relative:
        return None
    path = ASSET_ROOT / relative
    return path if path.is_file() else None


def _decorate_named_image(path: Path, *, tier: str, level: int, success: bool, discovered: bool = False) -> bytes:
    image = Image.open(path).convert("RGBA").resize((1280, 720), Image.Resampling.LANCZOS)
    accent_hex = forge.TIER_COLORS.get(tier, 0xAAB0BC)
    accent = ((accent_hex >> 16) & 255, (accent_hex >> 8) & 255, accent_hex & 255)

    if discovered:
        image = ImageEnhance.Brightness(image).enhance(0.34).filter(ImageFilter.GaussianBlur(3.0))
        veil = Image.new("RGBA", image.size, (4, 5, 10, 120))
        image = Image.alpha_composite(image, veil)
        draw = ImageDraw.Draw(image, "RGBA")
        draw.ellipse((500, 150, 780, 430), outline=(*accent, 180), width=10)
        draw.arc((555, 195, 725, 355), 205, 520, fill=(238, 230, 205, 220), width=18)
        draw.ellipse((626, 382, 654, 410), fill=(238, 230, 205, 220))
        return _encode_webp(image)

    level = max(0, int(level))
    stage = sum(level >= threshold for threshold in (5, 7, 10, 12, 15, 18, 20))
    if stage:
        aura = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(aura, "RGBA")
        for idx in range(stage):
            inset = 30 + idx * 12
            alpha = min(210, 65 + idx * 22)
            draw.rounded_rectangle((inset, inset, 1280-inset, 720-inset), radius=30, outline=(*accent, alpha), width=3 + idx // 2)
        rng = random.Random(f"{path.name}:{level}:{tier}")
        for _ in range(20 + stage * 14):
            x = rng.randint(70, 1210)
            y = rng.randint(65, 655)
            r = rng.randint(1, 5)
            draw.ellipse((x-r, y-r, x+r, y+r), fill=(*accent, rng.randint(80, 210)))
        if level >= 10:
            for x in (470, 520, 760, 810):
                draw.line((x, 110, x + rng.randint(-55, 55), 610), fill=(*accent, 90), width=4)
        if level >= 15:
            draw.arc((300, 70, 980, 650), 190, 350, fill=(*accent, 150), width=8)
            draw.arc((340, 90, 940, 630), 10, 170, fill=(*accent, 120), width=6)
        aura = aura.filter(ImageFilter.GaussianBlur(2.2))
        image = Image.alpha_composite(image, aura)

    if not success:
        red = Image.new("RGBA", image.size, (155, 10, 25, 58))
        image = Image.alpha_composite(image, red)
        cracks = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(cracks, "RGBA")
        rng = random.Random(f"failure:{path.name}")
        for _ in range(11):
            x, y = rng.randint(180, 1100), rng.randint(110, 610)
            points = [(x, y)]
            for _ in range(rng.randint(2, 5)):
                x += rng.randint(-75, 75)
                y += rng.randint(25, 75)
                points.append((x, y))
            draw.line(points, fill=(255, 70, 85, 210), width=5)
        image = Image.alpha_composite(image, cracks.filter(ImageFilter.GaussianBlur(0.6)))
    return _encode_webp(image)


def _encode_webp(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="WEBP", quality=89, method=6)
    return buffer.getvalue()


async def _equipment_file(item_name: str, tier: str, slot: str, success: bool, level: int, prefix: str) -> discord.File:
    path = _asset_path(EQUIPMENT_ASSETS, item_name)
    if path is not None:
        image = await asyncio.to_thread(_decorate_named_image, path, tier=tier or "일반", level=level, success=success, discovered=False)
        return discord.File(io.BytesIO(image), filename=f"abaddon_v633_{prefix}.webp")
    image = await asyncio.to_thread(forge.build_forge_card_png, tier or "일반", slot or "무기", success, max(0, int(level)))
    return discord.File(io.BytesIO(image), filename=_safe_filename(prefix))


async def _treasure_file(treasure_name: str, grade: str, discovered: bool, prefix: str) -> Optional[discord.File]:
    path = _asset_path(TREASURE_ASSETS, treasure_name)
    if path is None:
        return None
    tier = GRADE_TO_TIER.get(str(grade), "일반")
    image = await asyncio.to_thread(_decorate_named_image, path, tier=tier, level={"E":1,"D":4,"C":8,"B":13,"A":18}.get(str(grade), 1), success=True, discovered=discovered)
    return discord.File(io.BytesIO(image), filename=f"abaddon_v633_{prefix}.webp")


async def send_equipment_visual(
    ctx: commands.Context,
    *,
    item_name: str,
    tier: str,
    slot: str,
    level: int,
    mode: str,
    description: str = "",
    stats_text: str = "",
) -> Optional[discord.Message]:
    title, fallback = MODE_LABELS.get(mode, MODE_LABELS["preview"])
    level = max(0, int(level))
    file = await _equipment_file(item_name, tier, slot, True, level, f"equipment_{mode}")
    embed = discord.Embed(
        title=title,
        description=f"**{forge.forge_display_name(item_name, level)}**\n{description or fallback}",
        color=forge.TIER_COLORS.get(tier, 0xAAB0BC),
    )
    embed.add_field(name="등급 · 슬롯", value=f"**{tier or '일반'} · {slot or '기타'}**", inline=True)
    embed.add_field(name="강화 단계", value=f"**+{level} · {enhancement_stage(level)}**", inline=True)
    embed.add_field(name="다음 외형 변화", value=f"**{next_visual_stage(level)}**", inline=True)
    if stats_text:
        embed.add_field(name="능력치", value=stats_text[:1024], inline=False)
    embed.set_image(url=f"attachment://{file.filename}")
    embed.set_footer(text="ABADDON EQUIPMENT VISUALS v6.3.3 · 강화할수록 문양·광원·오라·실루엣이 확장됩니다")
    return await ctx.send(embed=embed, file=file)


async def edit_craft_visual(
    message: discord.Message,
    embed: discord.Embed,
    *,
    item_name: str,
    tier: str,
    slot: str,
    success: bool,
) -> None:
    file = await _equipment_file(item_name, tier, slot, success, 0 if success else 3, "craft_result")
    embed.set_image(url=f"attachment://{file.filename}")
    embed.add_field(
        name="🎬 제작 연출",
        value=("설계 문양과 결합부가 안정적으로 점등되었습니다." if success else "접합부의 균열과 불안정한 에너지 역류가 확인됐습니다."),
        inline=False,
    )
    embed.set_footer(text="ABADDON CRAFTING v6.3.3 · 제작 결과에 따라 성공/실패 외형이 분리됩니다")
    try:
        await message.edit(content=None, embed=embed, attachments=[file])
    except TypeError:
        await message.edit(content=None, embed=embed)
    except (discord.Forbidden, discord.HTTPException, AttributeError):
        return


async def edit_relic_visual(
    message: discord.Message,
    embed: discord.Embed,
    *,
    grade: str,
    treasure_name: str,
    upgraded: bool,
    discovered: bool = False,
) -> None:
    tier = GRADE_TO_TIER.get(str(grade), "일반")
    file = await _treasure_file(treasure_name, str(grade), discovered, "relic")
    if file is None:
        level = {"E": 1, "D": 4, "C": 8, "B": 13, "A": 18}.get(str(grade), 1)
        fallback = await asyncio.to_thread(forge.build_forge_card_png, tier, "목걸이", not discovered, level)
        file = discord.File(io.BytesIO(fallback), filename=_safe_filename("relic"))
    embed.set_image(url=f"attachment://{file.filename}")
    if discovered:
        embed.add_field(name="🕯️ 봉인 상태", value="감정 전에는 실제 가치와 등급 보정 결과가 공개되지 않습니다.", inline=False)
    elif upgraded:
        embed.add_field(name="🌟 감정 반응", value="감정사의 보정으로 유물 문양과 가치 등급이 상승했습니다.", inline=False)
    else:
        embed.add_field(name="🔎 감정 반응", value=f"**{treasure_name}**의 문양과 보존 상태가 확정됐습니다.", inline=False)
    embed.set_footer(text="ABADDON RELIC APPRAISAL v6.3.3 · 기존 감정사 확률과 매입 배율은 유지됩니다")
    try:
        await message.edit(content=None, embed=embed, attachments=[file])
    except TypeError:
        await message.edit(content=None, embed=embed)
    except (discord.Forbidden, discord.HTTPException, AttributeError):
        return


def register_v633_equipment_crafting(
    bot: commands.Bot,
    get_user: Callable[[int], Dict[str, Any]],
    check_registered: Callable[..., Any],
    find_item: Callable[[str], Any],
    get_item_slot: Callable[[str], str],
    get_item_stats: Callable[[str], Mapping[str, Any]],
) -> None:
    setattr(bot, "v633_send_equipment_visual", send_equipment_visual)
    setattr(bot, "v633_edit_craft_visual", edit_craft_visual)
    setattr(bot, "v633_edit_relic_visual", edit_relic_visual)
    setattr(bot, "v633_build_named_equipment_file", _equipment_file)
    setattr(bot, "v633_visual_version", VERSION)

    existing_guide = bot.get_command("강화연출")
    if existing_guide is not None:
        async def v633_forge_guide(ctx: commands.Context) -> None:
            await ctx.send(
                "✨ **[ABADDON 장비 외형 진화 v6.3.3]**\n"
                "강화 단계가 높아질수록 장비 실루엣·룬 문양·광원·오라·에너지 날개가 순서대로 확장됩니다.\n"
                "외형 변화: **+5 단련 · +7 광휘 · +10 종말 · +12 심연 · +15 아바돈 · +18 경계 · +20 공허 초월**\n"
                "성공·실패·단계 하락은 서로 다른 균열과 광원으로 표시됩니다.\n"
                "현재 장비 미리보기: `!장비외형 아이템명`"
            )
        existing_guide.callback = v633_forge_guide
        existing_guide.help = "강화 단계별 장비 외형 변화와 현재 외형 확인법을 안내합니다."
        existing_guide.description = existing_guide.help

    existing_patch_notes = bot.get_command("패치노트")
    if existing_patch_notes is not None:
        async def v633_patch_notes(ctx: commands.Context) -> None:
            await ctx.send(
                "⚒️ **ABADDON v6.3.3 — 장비·제작 비주얼 패치**\n"
                "• 장비 획득·장착·현황·감정에 슬롯별 장비 카드 적용\n"
                "• 강화 단계가 높을수록 실루엣과 오라가 더 화려하게 변화\n"
                "• 제작 성공·실패 장면 분리, 유물 발견·감정 카드 추가\n"
                "• 기존 강화 확률·비용·하락, 제작 재료·실패 수리비, 감정사 확률·배율은 유지\n"
                "• `!장비외형 아이템명` 명령 추가"
            )
        existing_patch_notes.callback = v633_patch_notes
        existing_patch_notes.help = "ABADDON 최신 통합 패치 내용을 확인합니다."
        existing_patch_notes.description = existing_patch_notes.help

    @bot.command(name="장비외형", aliases=["장비비주얼", "강화외형"])
    async def equipment_visual_preview(ctx: commands.Context, *, 아이템이름: str) -> None:
        if not await check_registered(ctx):
            return
        user = get_user(ctx.author.id)
        if 아이템이름 not in user.get("inventory", []):
            await ctx.send("⚠️ 해당 장비를 보유하고 있지 않습니다.")
            return
        tier, info = find_item(아이템이름)
        if not info:
            await ctx.send("⚠️ 장비 정보를 찾지 못했습니다.")
            return
        level = int(user.get("enhancements", {}).get(아이템이름, 0))
        stats = get_item_stats(아이템이름)
        stat_text = " · ".join(
            f"{key} +{value}{'%' if key in {'치명타', '회피', '감염저항'} else ''}"
            for key, value in stats.items()
            if value
        )
        await send_equipment_visual(
            ctx,
            item_name=아이템이름,
            tier=tier or "일반",
            slot=get_item_slot(아이템이름),
            level=level,
            mode="preview",
            description=str(info.get("desc", "")),
            stats_text=stat_text,
        )
