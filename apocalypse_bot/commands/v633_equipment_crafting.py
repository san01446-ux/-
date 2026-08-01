from __future__ import annotations

import asyncio
import io
import json
import hashlib
import math
import math
import random
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

import discord
from discord.ext import commands
try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
    PIL_AVAILABLE = True
except ModuleNotFoundError:
    Image = ImageDraw = ImageEnhance = ImageFilter = None
    PIL_AVAILABLE = False

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

V641A_SAFE_ENHANCEMENT_FX = True

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



def _emoji_bar(percent: float, width: int = 10, filled: str = "🟨", empty: str = "⬛") -> str:
    pct = max(0.0, min(100.0, float(percent)))
    count = max(0, min(width, int(round(pct / 100 * width))))
    return filled * count + empty * (width - count)


def _enhancement_progress(level: int) -> str:
    level = max(0, min(20, int(level)))
    percent = level / 20 * 100
    return f"{_emoji_bar(percent)} **{level}/20 · {percent:.0f}%**"


def _safe_filename(prefix: str) -> str:
    return f"abaddon_v633_{prefix}.png"


def _asset_path(mapping: Mapping[str, str], name: str) -> Optional[Path]:
    relative = mapping.get(str(name))
    if not relative:
        return None
    path = ASSET_ROOT / relative
    return path if path.is_file() else None


def _effect_profile(item_name: str) -> str:
    name = str(item_name or "")
    groups = (
        ("electric", ("전기", "EMP", "플라즈마", "레일", "썬더", "천벌", "절대영도", "오메가", "차원")),
        ("fire", ("화염", "드래곤", "불사조", "신호탄", "폭발")),
        ("void", ("공허", "심연", "루시퍼", "판도라", "종말", "심판")),
        ("bio", ("감염", "재생", "생체", "혈청", "유전자", "나무", "약초")),
        ("defense", ("방패", "갑옷", "방탄", "전술복", "보호대", "헬멧", "우의", "가방", "장갑", "가면", "왕관")),
        ("precision", ("권총", "소총", "샷건", "캐논", "포", "조준", "스코프", "탐지", "드론", "장치", "코어", "통제키")),
        ("blade", ("검", "칼", "나이프", "도끼", "낫", "창", "석궁", "파이프", "몽둥이", "철근")),
    )
    for profile, keywords in groups:
        if any(word in name for word in keywords):
            return profile
    return "rune"


def _unique_accent(item_name: str, base: tuple[int, int, int]) -> tuple[int, int, int]:
    digest = hashlib.sha256(str(item_name).encode("utf-8")).digest()
    shift = tuple((digest[i] - 128) // 4 for i in range(3))
    return tuple(max(40, min(255, base[i] + shift[i])) for i in range(3))


def _draw_equipment_effects(image: Image.Image, *, item_name: str, level: int, tier: str, accent: tuple[int, int, int]) -> Image.Image:
    """강화 단계가 높을수록 장비 주변만 밝아지는 안전한 후처리.

    카드 전체를 가로지르는 사선/레이저는 사용하지 않습니다. +0~+4는 원본 그대로,
    +5부터 테두리, +10부터 오라, +15부터 속성 입자, +20에서 초월 효과를 표시합니다.
    """
    level = max(0, int(level))
    if level < 5:
        return image

    profile = _effect_profile(item_name)
    phase = 1 if level < 10 else 2 if level < 15 else 3 if level < 20 else 4
    rng = random.Random(f"v641a-safe-fx:{item_name}:{level}:{tier}")
    palette = {
        "electric": (80, 210, 255),
        "fire": (255, 118, 48),
        "void": (174, 92, 255),
        "bio": (108, 220, 132),
        "defense": (170, 205, 235),
        "precision": (92, 170, 255),
        "blade": (235, 196, 118),
        "rune": (200, 150, 255),
    }
    profile_color = palette.get(profile, palette["rune"])
    # 등급색은 20%만 섞어, 일반 근접 장비가 초록 레이저처럼 보이지 않게 합니다.
    color = tuple(int(profile_color[i] * 0.8 + accent[i] * 0.2) for i in range(3))
    width, height = image.size
    cx, cy = width // 2, int(height * 0.47)

    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow, "RGBA")
    rx, ry = int(width * 0.24), int(height * 0.35)
    for i in range(phase + 1):
        pad = i * 18
        alpha = 38 + phase * 14 - i * 5
        gdraw.ellipse((cx-rx-pad, cy-ry-pad, cx+rx+pad, cy+ry+pad), outline=(*color, max(20, alpha)), width=6)
    glow = glow.filter(ImageFilter.GaussianBlur(18 + phase * 3))
    result = Image.alpha_composite(image, glow)

    fx = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(fx, "RGBA")

    # +5: 얇은 프레임만. 강화 전 원본과 명확히 구분되되 장비를 가리지 않습니다.
    for i in range(phase):
        inset = 18 + i * 9
        draw.rounded_rectangle(
            (inset, inset, width-inset, height-inset),
            radius=26,
            outline=(*color, 70 + i * 24),
            width=2 + i,
        )

    # +10: 장비 중심 주변의 짧은 광점. 화면을 가로지르는 선은 금지합니다.
    if phase >= 2:
        for _ in range(16 + phase * 5):
            angle = rng.random() * math.tau
            radius_x = rng.randint(int(rx * 0.75), int(rx * 1.12))
            radius_y = rng.randint(int(ry * 0.68), int(ry * 1.05))
            x = cx + int(math.cos(angle) * radius_x)
            y = cy + int(math.sin(angle) * radius_y)
            r = rng.randint(1, 4)
            draw.ellipse((x-r, y-r, x+r, y+r), fill=(*color, rng.randint(90, 205)))

    # +15: 장비 종류별 짧고 국소적인 심볼 효과.
    if phase >= 3:
        if profile == "electric":
            for _ in range(7):
                x = rng.randint(cx-rx, cx+rx)
                y = rng.randint(cy-ry, cy+ry)
                pts = [(x, y), (x+rng.randint(-14, 14), y+18), (x+rng.randint(-12, 12), y+35)]
                draw.line(pts, fill=(*color, 170), width=3)
        elif profile == "fire":
            for _ in range(18):
                x = rng.randint(cx-rx, cx+rx)
                y = rng.randint(cy+ry//4, cy+ry)
                r = rng.randint(2, 6)
                draw.ellipse((x-r, y-r*2, x+r, y+r), fill=(*color, rng.randint(90, 190)))
        elif profile == "void":
            for i in range(3):
                r = 90 + i * 42
                draw.arc((cx-r, cy-r, cx+r, cy+r), 210+i*15, 510-i*10, fill=(*color, 140+i*18), width=4)
        elif profile == "bio":
            for _ in range(13):
                x = rng.randint(cx-rx, cx+rx)
                y = rng.randint(cy-ry, cy+ry)
                r = rng.randint(3, 8)
                draw.ellipse((x-r, y-r, x+r, y+r), outline=(*color, 145), width=2)
        elif profile == "defense":
            shield = [(cx, cy-180), (cx+145, cy-85), (cx+120, cy+120), (cx, cy+190), (cx-120, cy+120), (cx-145, cy-85)]
            draw.line(shield + [shield[0]], fill=(*color, 145), width=5)
        elif profile == "precision":
            r = 105
            draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline=(*color, 145), width=4)
            for dx, dy in ((0,-145), (145,0), (0,145), (-145,0)):
                draw.line((cx+dx*0.72, cy+dy*0.72, cx+dx, cy+dy), fill=(*color, 150), width=4)
        elif profile == "blade":
            # 몽둥이·칼·도끼는 짧은 금속 반짝임만 사용합니다.
            for _ in range(11):
                x = rng.randint(cx-rx, cx+rx)
                y = rng.randint(cy-ry, cy+ry)
                length = rng.randint(8, 18)
                draw.line((x-length, y, x+length, y), fill=(*color, 155), width=2)
                draw.line((x, y-length, x, y+length), fill=(*color, 155), width=2)
        else:
            for i in range(10):
                angle = i / 10 * math.tau
                x = cx + int(math.cos(angle) * 205)
                y = cy + int(math.sin(angle) * 165)
                draw.polygon([(x, y-6), (x+5, y), (x, y+6), (x-5, y)], fill=(*color, 155))

    # +20: 초월 단계는 외곽 별빛을 추가하되 원본 피사체 위를 덮지 않습니다.
    if phase >= 4:
        for _ in range(24):
            edge = rng.choice(("top", "bottom", "left", "right"))
            if edge in {"top", "bottom"}:
                x = rng.randint(55, width-55)
                y = rng.randint(35, 95) if edge == "top" else rng.randint(height-95, height-35)
            else:
                x = rng.randint(35, 95) if edge == "left" else rng.randint(width-95, width-35)
                y = rng.randint(55, height-55)
            r = rng.randint(2, 5)
            draw.ellipse((x-r, y-r, x+r, y+r), fill=(*color, rng.randint(140, 230)))

    return Image.alpha_composite(result, fx.filter(ImageFilter.GaussianBlur(0.45)))


def _decorate_named_image(path: Path, *, tier: str, level: int, success: bool, discovered: bool = False, item_name: str = "") -> bytes:
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

    image = _draw_equipment_effects(image, item_name=item_name or path.stem, level=level, tier=tier, accent=accent)

    if not success:
        red = Image.new("RGBA", image.size, (155, 10, 25, 58))
        image = Image.alpha_composite(image, red)
        cracks = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(cracks, "RGBA")
        rng = random.Random(f"failure:{item_name}:{path.name}")
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
        if PIL_AVAILABLE:
            image = await asyncio.to_thread(_decorate_named_image, path, tier=tier or "일반", level=level, success=success, discovered=False, item_name=item_name)
            return discord.File(io.BytesIO(image), filename=f"abaddon_v633_{prefix}.webp")
        # Pillow가 설치되지 않은 환경에서도 봇이 중단되지 않도록 원본 장비 이미지를 직접 첨부합니다.
        return discord.File(str(path), filename=f"abaddon_v633_{prefix}{path.suffix.lower() or '.webp'}")
    image = await asyncio.to_thread(forge.build_forge_card_png, tier or "일반", slot or "무기", success, max(0, int(level)))
    return discord.File(io.BytesIO(image), filename=_safe_filename(prefix))


async def _treasure_file(treasure_name: str, grade: str, discovered: bool, prefix: str) -> Optional[discord.File]:
    path = _asset_path(TREASURE_ASSETS, treasure_name)
    if path is None:
        return None
    tier = GRADE_TO_TIER.get(str(grade), "일반")
    if PIL_AVAILABLE:
        image = await asyncio.to_thread(_decorate_named_image, path, tier=tier, level={"E":1,"D":4,"C":8,"B":13,"A":18}.get(str(grade), 1), success=True, discovered=discovered, item_name=treasure_name)
        return discord.File(io.BytesIO(image), filename=f"abaddon_v633_{prefix}.webp")
    # Pillow가 없는 경우에도 감정 결과의 실제 보물 이미지를 그대로 표시합니다.
    return discord.File(str(path), filename=f"abaddon_v633_{prefix}{path.suffix.lower() or '.webp'}")


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
    embed.add_field(name="✨ 강화 진행도", value=_enhancement_progress(level), inline=False)
    if stats_text:
        embed.add_field(name="능력치", value=stats_text[:1024], inline=False)
    embed.set_image(url=f"attachment://{file.filename}")
    embed.set_footer(text="ABADDON EQUIPMENT VISUALS v6.4.1a · 강화할수록 문양·광원·오라·실루엣이 확장됩니다")
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
    setattr(bot, "v633_pillow_available", PIL_AVAILABLE)

    existing_guide = bot.get_command("강화연출")
    if existing_guide is not None:
        async def v633_forge_guide(ctx: commands.Context) -> None:
            await ctx.send(
                "✨ **[ABADDON 장비 외형 진화 v6.4.1a]**\n"
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
