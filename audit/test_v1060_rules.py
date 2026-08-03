from apocalypse_bot.commands.v1051_rules import (
    DebtBettingRound,
    GoStopEngine,
    HwatuCardLite,
    baccarat_deal,
    baccarat_outcome,
    baccarat_total,
    resolve_seotda,
    seotda_deck,
    seotda_rank,
    uncapped_extra_payment,
)


def hwatu_cards():
    cards=[]
    uid=0
    for month in range(1,13):
        cards.extend([
            HwatuCardLite(uid,month,'bright' if month in {1,3,8,11} else 'animal',f'{month}a',0),
            HwatuCardLite(uid+1,month,'ribbon',f'{month}b',0),
            HwatuCardLite(uid+2,month,'junk',f'{month}c',1),
            HwatuCardLite(uid+3,month,'junk',f'{month}d',1),
        ])
        uid += 4
    return cards


def test_uncapped_payment():
    assert uncapped_extra_payment(10_000, 1_000_000) == 9_999_990_000


def test_debt_betting_has_no_stack_cap():
    round_ = DebtBettingRound([1,2], min_raise=10_000)
    action, paid = round_.raise_to(1, 10**18)
    assert action == 'raise' and paid == 10**18
    action, paid = round_.check_or_call(2)
    assert action == 'call' and paid == 10**18
    assert round_.complete()


def test_baccarat_third_card_and_total():
    # Deterministic deck order: pop from end.
    deck=[(2,'S'),(3,'H'),(4,'D'),(5,'C'),(6,'S'),(7,'H'),(8,'D'),(9,'C')]
    p,b=baccarat_deal(deck)
    assert len(p) in {2,3} and len(b) in {2,3}
    assert baccarat_outcome(p,b) in {'player','banker','tie'}
    assert 0 <= baccarat_total(p) <= 9


def test_seotda_core_ranks():
    deck=seotda_deck()
    c3=next(c for c in deck if c.month==3 and c.kind=='bright')
    c8=next(c for c in deck if c.month==8 and c.kind=='bright')
    assert seotda_rank([c3,c8]).name == '삼팔광땡'
    status,winners,ranks=resolve_seotda({1:[c3,c8],2:[deck[0],deck[1]]})
    assert status == 'win' and winners == [1]


def test_gostop_real_deal_sizes():
    matgo=GoStopEngine([1,2],hwatu_cards(),matgo=True)
    assert all(len(hand)==10 for hand in matgo.hands.values())
    assert len(matgo.floor)==8 and len(matgo.stock)==20
    gostop=GoStopEngine([1,2,3],hwatu_cards(),matgo=False)
    assert all(len(hand)==7 for hand in gostop.hands.values())
    assert len(gostop.floor)==6 and len(gostop.stock)==21


def test_gostop_turn_reduces_hand_and_stock():
    game=GoStopEngine([1,2],hwatu_cards(),matgo=True)
    uid=game.current_uid
    before_hand=len(game.hands[uid]); before_stock=len(game.stock)
    card=game.hands[uid][0]
    matches=game.matching_floor_indices(card.month)
    result=game.play(uid,0,match_index=(matches[0] if len(matches)==2 else None),flip_match_index=0 if False else None)
    if result.needs_choice:
        phase,indices=result.needs_choice
        kwargs={'match_index':matches[0] if len(matches)==2 else None,'flip_match_index':indices[0] if phase=='flip' else None}
        if phase=='hand': kwargs['match_index']=indices[0]
        result=game.play(uid,0,**kwargs)
    assert len(game.hands[uid]) == before_hand-1
    assert len(game.stock) == before_stock-1


def test_debt_blinds_are_uncapped_and_live():
    round_ = DebtBettingRound([1, 2, 3], min_raise=10_000)
    assert round_.post(1, 5_000) == 5_000
    assert round_.post(2, 10_000) == 10_000
    assert round_.current_bet == 10_000
    assert round_.to_call(1) == 5_000
    assert round_.to_call(3) == 10_000
    assert round_.raise_to(3, 10**30)[1] == 10**30


def test_three_player_gostop_supports_two_ai_seats():
    game = GoStopEngine([1, -1060, -1061], hwatu_cards(), matgo=False)
    assert list(game.hands) == [1, -1060, -1061]
    assert all(len(hand) == 7 for hand in game.hands.values())
    assert len(game.floor) == 6 and len(game.stock) == 21


def test_gostop_ambiguous_floor_choice_is_transactional():
    cards = hwatu_cards()
    game = GoStopEngine([1, 2], cards, matgo=True)
    hand_card = next(c for c in cards if c.month == 1)
    floor_cards = [c for c in cards if c.month == 1 and c.uid != hand_card.uid][:2]
    stock_card = next(c for c in cards if c.month == 12)
    game.hands[1] = [hand_card]
    game.hands[2] = []
    game.floor = list(floor_cards)
    game.stock = [stock_card]
    before = (list(game.hands[1]), list(game.floor), list(game.stock))
    pending = game.play(1, 0)
    assert pending.needs_choice and pending.needs_choice[0] == 'hand'
    assert game.hands[1] == before[0]
    assert game.floor == before[1]
    assert game.stock == before[2]
    resolved = game.play(1, 0, match_index=pending.needs_choice[1][0])
    assert not resolved.needs_choice
    assert len(game.hands[1]) == 0
    assert len(game.stock) == 0
