from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apocalypse_bot.commands.v1095_visual_polish import (
    render_live_board,
    render_replay_timeline,
    render_session_media,
)


class PokerSession:
    locale = "ko"
    variant = "텍사스홀덤"
    game_id = "audit-1095"
    player_ids = [1, -1]
    names = {1: "아주 긴 생존자 닉네임 테스트", -1: "ABADDON"}
    current_uid = 1
    pot = 123456789
    board = [(14, "♠"), (10, "♥"), (7, "♣")]
    hands = {1: [(13, "♠"), (12, "♠")], -1: [(2, "♦"), (3, "♦")]}
    stage_label = "플랍 베팅"
    last_action = "ABADDON이 30,000칩으로 레이즈했고 생존자의 선택을 기다립니다."
    replay = ["[00:00:01] START", "[00:00:02] ABADDON RAISE 30000"]
    done = False

    class Betting:
        folded = set()
        round_bets = {1: 30000, -1: 30000}
        current_bet = 30000

    betting = Betting()


def assert_image(data: BytesIO, expected: str | None = None) -> Image.Image:
    data.seek(0)
    image = Image.open(data)
    if expected:
        assert image.format == expected, (image.format, expected)
    assert image.width >= 1200 and image.height >= 700
    return image


def test_active_table_gif() -> None:
    media, extension = render_session_media(PokerSession(), None)
    assert media is not None
    assert extension in {"gif", "png"}
    image = assert_image(media, extension.upper())
    if extension == "gif":
        assert getattr(image, "n_frames", 1) >= 3


def test_finished_table_png() -> None:
    session = PokerSession()
    session.done = True
    media, extension = render_session_media(session, None)
    assert media is not None and extension == "png"
    assert_image(media, "PNG")


def test_replay_timeline_long_korean() -> None:
    row = {
        "id": "g-1",
        "game": "고스톱",
        "stake": 10**30,
        "players": {"1": "긴 닉네임 생존자", "-1": "ABADDON"},
        "events": [f"[{i:02d}:00] 매우 긴 공개 행동 기록 {i} · 손패 내용은 포함하지 않음" for i in range(20)],
        "result": "생존자 승리 · 광박 · 피박 · 최종 배수 128배 · 잔액 음수 허용",
    }
    assert_image(render_replay_timeline(row, "ko"), "PNG")


def test_live_board() -> None:
    games = {123: PokerSession()}
    races = {
        1: {
            "selected_name": "검은 성가",
            "leader_name": "재의 질주",
            "tick": 8,
            "guild_id": 999,
        }
    }
    recent = [{"winner": "붉은 안개", "net": -10000}]
    assert_image(render_live_board(locale="ko", active_games=games, live_races=races, recent_races=recent), "PNG")


def test_source_recovery_and_registration() -> None:
    safe = (ROOT / "apocalypse_bot/commands/v651_card_games.py").read_text(encoding="utf-8")
    race = (ROOT / "apocalypse_bot/commands/v1092_visual_status_horserace.py").read_text(encoding="utf-8")
    core = (ROOT / "apocalypse_bot/core/bot.py").read_text(encoding="utf-8")
    assert "Final recovery path" in safe
    assert "_v1095_embed_fallbacks" in safe
    assert "LIVE_RACE_STATES" in race
    assert "register_v1095_gameplay_polish_patch" in core


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"PASS {len(tests)} tests")
