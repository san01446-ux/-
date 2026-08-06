from apocalypse_bot.commands.v1092_horse_racing_rules import FINISH, HORSES, render_track_lane


def main() -> None:
    positions = [0, 5, 12, 20, 29, FINISH]
    lanes = [render_track_lane(pos) for pos in positions]
    assert len(HORSES) == 6
    assert all(lane.count('♞') == 1 for lane in lanes)
    assert all(lane.count('🏁') == 1 for lane in lanes)
    assert len({lane.index('🏁') for lane in lanes}) == 1
    assert lanes[-1].endswith('♞🏁]')
    assert all(len(lane) == len(lanes[0]) for lane in lanes)
    assert all(bool(str(horse.get('emoji') or '')) for horse in HORSES)
    print('v11.4.1 horse marker tests: 7/7 passed')


if __name__ == '__main__':
    main()
