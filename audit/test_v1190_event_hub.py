import importlib.util
from pathlib import Path

MODULE=Path(__file__).parents[1]/'apocalypse_bot/commands/v1190_event_broadcast_collection.py'
spec=importlib.util.spec_from_file_location('v1190',MODULE)
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

def test_event_type_aliases():
    assert m._normalize_event_type('race')=='경마'
    assert m._normalize_event_type('리그')=='챔피언십'

def test_parse_datetime():
    assert m._parse_dt('2026-08-05','21:00')>0

def test_public_state_has_no_private_hands():
    class S:
        player_ids=[1,-1]; names={1:'A',-1:'ABADDON'}; hands={1:['SECRET']}; pot=100; stage='flop'; board=['A♠']; channel_id=1
    row=m._public_session_state(S())
    assert 'hands' not in row and 'SECRET' not in str(row)

def test_achievement_scan():
    u={'casino_chips':-1,'v1050_game_stats':{'total':{'plays':10,'wins':2,'best_streak':1,'profit':100},'games':{}},'v1092_horse_racing':{'plays':5,'wins':1}}
    new,stats=m._scan_achievements(u)
    assert 'first_game' in u['v1190_collections']['unlocked']
    assert stats['races']==5

def test_images_render():
    assert m._png_calendar('ko','테스트 서버',[]).getbuffer().nbytes>1000
    assert m._png_collection('ko','테스터',{},{}).getbuffer().nbytes>1000
