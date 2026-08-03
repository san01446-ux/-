from apocalypse_bot.commands.v1050_rules import (
    HwatuSummary, ace_to_five_low, baccarat_value, badugi_score,
    best_short_deck, blackjack_value, build_single_elimination,
    capped_extra_payment, claimable_season_rewards, ensure_game_stats,
    ensure_season_profile, hwatu_multiplier, pineapple_best,
    record_game_result, short_deck_score, advance_season,
)

def poker_score(hand):
    # Small deterministic evaluator sufficient to verify pineapple discard search.
    ranks=sorted((r for r,_ in hand), reverse=True)
    return (tuple(ranks), 'test')

def run():
    assert blackjack_value([(14,'S'),(9,'H')]) == (20, True)
    assert blackjack_value([(14,'S'),(9,'H'),(5,'D')]) == (15, False)
    assert baccarat_value([(14,'S'),(13,'H'),(8,'D')]) == 9
    low=ace_to_five_low([(14,'S'),(2,'H'),(3,'D'),(4,'C'),(5,'S'),(13,'H')])
    assert low == (0,5,4,3,2,1)
    count,key,hand=badugi_score([(14,'S'),(2,'H'),(3,'D'),(4,'C')])
    assert count == 4 and key == (4,3,2,1) and len(hand)==4
    flush=short_deck_score([(14,'S'),(12,'S'),(10,'S'),(8,'S'),(6,'S')])[0]
    full=short_deck_score([(14,'S'),(14,'H'),(14,'D'),(13,'S'),(13,'H')])[0]
    assert flush > full
    wheel=short_deck_score([(14,'S'),(9,'H'),(8,'D'),(7,'C'),(6,'S')])[0]
    assert wheel[0] == 4 and wheel[1] == 9
    assert len(best_short_deck([(14,'S'),(9,'H'),(8,'D'),(7,'C'),(6,'S'),(13,'D')])[2]) == 5
    p=pineapple_best([(14,'S'),(2,'H'),(3,'D')],[(13,'C'),(12,'C'),(11,'C'),(10,'C'),(9,'C')],poker_score)
    assert len(p[2])==5 and p[3] in {(14,'S'),(2,'H'),(3,'D')}
    w=HwatuSummary(10,3,7,5,10)
    l=HwatuSummary(2,0,2,1,5)
    mult,reasons=hwatu_multiplier(w,l,go_count=4,shakes=2,bombs=1,loser_declared_go=True,nagari_multiplier=2)
    assert mult == 1024 and len(reasons) >= 7
    assert capped_extra_payment(1_000_000,10_000,mult)==160_000
    assert capped_extra_payment(5_000,10_000,mult)==5_000
    bracket=build_single_elimination(['A','B','C'])
    assert len(bracket)==2 and bracket[0][1][1] is None
    u={}
    record_game_result(u,'포커','win',earnings=100,versus_ai=True)
    total=ensure_game_stats(u)['total']
    assert total['wins']==1 and total['ai_plays']==1 and total['earnings']==100
    profile=ensure_season_profile(u)
    for _ in range(10): advance_season(u,'play_games')
    assert profile['points']==20 and 'play_games' in profile['completed']
    assert claimable_season_rewards(u)[0][0]==20
    print('V1050_RULE_TESTS=PASS')

if __name__=='__main__': run()
