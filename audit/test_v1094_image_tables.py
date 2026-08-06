from __future__ import annotations

import io
import json
import pathlib
import sys
from types import SimpleNamespace

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from apocalypse_bot.commands.v1094_visual_core import font_status
from apocalypse_bot.commands.v1094_card_table_images import render_private_hand, render_session_table


def _png_info(buffer: io.BytesIO) -> tuple[int, int, str]:
    buffer.seek(0)
    with Image.open(buffer) as image:
        image.load()
        return image.width, image.height, image.format or ""


def fake_base(class_name: str = "GenericSession"):
    cls = type(class_name, (), {})
    obj = cls()
    obj.locale = "ko"
    obj.variant = "테스트 게임"
    obj.player_ids = [1, 2]
    obj.names = {1: "생존자-긴닉네임-레이아웃검사", 2: "ABADDON"}
    obj.current_uid = 1
    obj.hands = {1: [(14, "♠"), (13, "♥")], 2: [(9, "♣"), (8, "♦")]}
    obj.pot = 123456789
    obj.last_action = "아주 긴 한국어 설명도 이미지 박스 안에서 자동으로 줄바꿈되고 잘리지 않아야 합니다."
    obj.done = False
    return obj


def run() -> dict[str, object]:
    checks: list[dict[str, object]] = []

    def check(name: str, ok: bool, detail: object) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    status = font_status()
    check("한글 regular font", "missing" not in status["regular"], status["regular"])
    check("한글 bold font", "missing" not in status["bold"], status["bold"])

    poker = fake_base("TexasPokerSession")
    poker.variant = "텍사스홀덤"
    poker.board = [(14, "♠"), (10, "♥"), (7, "♣")]
    poker.stage = "플랍"
    poker.betting = SimpleNamespace(current_bet=40000, round_bets={1: 40000, 2: 40000}, folded=set())
    pbuf = render_session_table(poker)
    check("포커 공개 테이블 PNG", pbuf is not None and _png_info(pbuf) == (1280, 720, "PNG"), _png_info(pbuf) if pbuf else None)

    hwatu_card = lambda m, c="junk": SimpleNamespace(month=m, category=c, name=f"{m}월패")
    hwatu = fake_base("GoStopSession")
    hwatu.variant = "고스톱"
    hwatu.engine = SimpleNamespace(
        floor=[hwatu_card(i) for i in range(1, 9)],
        captured={1: [hwatu_card(1)], 2: [hwatu_card(2)]},
        stock=[hwatu_card(i) for i in range(1, 12)],
        current_uid=1,
    )
    hwatu.score = lambda uid: SimpleNamespace(score=5 if uid == 1 else 2, junk_points=7 if uid == 1 else 4)
    hwatu.go_counts = {1: 1, 2: 0}
    hbuf = render_session_table(hwatu)
    check("화투 공개 테이블 PNG", hbuf is not None and _png_info(hbuf) == (1280, 720, "PNG"), _png_info(hbuf) if hbuf else None)

    for class_name, label in [
        ("BlackjackSession", "블랙잭"), ("BaccaratSession", "바카라"),
        ("SeotdaSession", "섯다"), ("OneCardSession", "원카드"),
        ("OldMaidSession", "조커잡기"), ("HoolaSession", "훌라"),
    ]:
        session = fake_base(class_name)
        session.variant = label
        if "Blackjack" in class_name:
            session.dealer = [(10, "♠"), (7, "♥")]
            session.value = lambda cards: sum(min(int(c[0]), 10) for c in cards)
        elif "Baccarat" in class_name:
            session.choices = {1: "플레이어", 2: "뱅커"}
            session.result = ([(8, "♠"), (2, "♥")], [(7, "♣"), (3, "♦")], "타이")
        elif "Seotda" in class_name:
            session.street = 2
            session.betting = SimpleNamespace(round_bets={1: 50000, 2: 50000}, folded=set())
            session.hands = {1: [hwatu_card(1), hwatu_card(3)], 2: [hwatu_card(2), hwatu_card(8)]}
        elif "OneCard" in class_name:
            session.discard = [(7, "♥")]
            session.penalty = 2
        buffer = render_session_table(session)
        check(f"{label} 공개 테이블 PNG", buffer is not None and _png_info(buffer) == (1280, 720, "PNG"), class_name)

    many_cards = [(2 + i % 13, "♠♥♦♣"[i % 4]) for i in range(50)]
    private = render_private_hand(locale="ko", title="매우 긴 비공개 손패 제목 자동 축소 검사", cards=many_cards, note="50장일 때도 이미지 밖으로 넘치지 않고 나머지 장수를 안내합니다.")
    check("대량 비공개 손패 PNG", _png_info(private) == (1280, 720, "PNG"), _png_info(private))

    v651 = (ROOT / "apocalypse_bot/commands/v651_card_games.py").read_text("utf-8")
    v1060 = (ROOT / "apocalypse_bot/commands/v1060_authentic_card_games.py").read_text("utf-8")
    core = (ROOT / "apocalypse_bot/core/bot.py").read_text("utf-8")
    patch = (ROOT / "apocalypse_bot/commands/v1094_image_table_patch.py").read_text("utf-8")
    check("공개 메시지 PNG 교체 연결", "attachments=[file]" in v651, "message.edit attachments")
    check("핵심 6계열 비공개 PNG", all(token in v651 + v1060 for token in ["abaddon_onecard_hand.png", "abaddon_oldmaid_hand.png", "abaddon_poker_private_hand.png", "abaddon_hwatu_private_hand.png", "abaddon_blackjack_private_hand.png", "abaddon_seotda_private_hand.png"]), "six private families")
    check("최종 등록 순서", core.index("register_v1094_image_table_patch") < core.index("synchronize_all_english_aliases"), "v1094 before final alias sync")
    check("최신 테스트·패치노트", "v1094_test" in patch and "v1094_patch_notes" in patch and "이미지검수" in patch, "latest-only checks")

    website = ROOT.parent / "site"
    active_pages = [website / "index.html", website / "commands.html", website / "updates.html", website / "en/index.html", website / "en/commands.html", website / "en/updates.html"]
    check("홈페이지 v10.9.4", all("10.9.4" in p.read_text("utf-8") for p in active_pages), [p.name for p in active_pages])
    check("홈페이지 미리보기 3종", all((website / "assets/v1094" / name).is_file() for name in ["ABADDON_v10.9.4_POKER_TABLE_PREVIEW.png", "ABADDON_v10.9.4_HWATU_TABLE_PREVIEW.png", "ABADDON_v10.9.4_PRIVATE_HAND_PREVIEW.png"]), "assets/v1094")
    check("홈페이지 간단 문구", "카드게임 화면을 더 쉽게 봅니다" in (website / "index.html").read_text("utf-8") and "Card games are easier to read" in (website / "en/index.html").read_text("utf-8"), "short home copy")

    failed = [row for row in checks if not row["ok"]]
    return {"version": "10.9.4", "scope": "card-table images, Korean font layout, private hands and simplified website copy", "checks": checks, "passed": len(checks)-len(failed), "failed": len(failed)}


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(1 if report["failed"] else 0)
