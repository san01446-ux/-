from apocalypse_bot.commands.v1090_rules import (
    ai_risk, dashboard_health, dice_card_score, dori_rank, greedy_melds,
    hwatu_capture_points, is_run, is_set, league_points, president_play_valid,
    sambong_rank, yukbaek_round_valid,
)


def run():
    checks = []
    checks.append(("rummy set", is_set([(7,"S"),(7,"H"),(7,"D")]) and not is_set([(7,"S"),(7,"S"),(7,"D")])))
    checks.append(("rummy run", is_run([(14,"S"),(2,"S"),(3,"S")]) and is_run([(9,"H"),(10,"H"),(11,"H")]) and not is_run([(9,"H"),(10,"S"),(11,"H")])))
    checks.append(("greedy meld", bool(greedy_melds([(3,"S"),(4,"S"),(5,"S"),(9,"H"),(9,"D"),(9,"C")]))))
    checks.append(("president", president_play_valid([10,10], 9, 2) and not president_play_valid([10], 9, 2)))
    checks.append(("dice card", dice_card_score([(7,"S"),(7,"H")],[6,6,6])[0] >= 4))
    checks.append(("sambong", sambong_rank([3,3,3])[0] > sambong_rank([10,10,2])[0] > sambong_rank([1,2,6])[0]))
    checks.append(("dori", dori_rank([1,9,3,3,3])[2] is not None))
    checks.append(("hwatu", hwatu_capture_points(["bright","animal","ribbon"],[1,2,3]) == 70))
    checks.append(("yukbaek", yukbaek_round_valid([31,45,80]) and not yukbaek_round_valid([30,45,80])))
    checks.append(("ai", ai_risk("악몽","도박형") > ai_risk("쉬움","안정형")))
    checks.append(("league", league_points(10,2,1,500000) > league_points(5,0,4,-500000)))
    checks.append(("dashboard", dashboard_health({"a":True,"b":True}) == (2,2,"green")))
    failed = [name for name, ok in checks if not ok]
    if failed:
        raise AssertionError(f"v10.9 rules failed: {failed}")
    print(f"v10.9 rules: {len(checks)}/{len(checks)} PASS")


def test_v1090_rules():
    run()


if __name__ == "__main__":
    run()
