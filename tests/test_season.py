from sww3bot import season as season_mod


def test_summarize_reads_scores():
    out = season_mod.summarize({'overallScore': '117', 'militaryScore': 43,
                                'economicScore': 74.9, 'globalRank': 4635289,
                                'currentRankLevel': 5})
    assert out == {'overall': 117, 'military': 43, 'economic': 74,
                   'global_rank': 4635289, 'military_rank': 0, 'economic_rank': 0,
                   'level': 5}
    assert season_mod.summarize(None)['overall'] == 0
    assert season_mod.summarize({'overallScore': True})['overall'] == 0


def test_delta_against_baseline():
    current = {'overall': 150, 'military': 50, 'economic': 100}
    assert season_mod.delta({'overall': 117, 'military': 43, 'economic': 74}, current) == {
        'overall': 33, 'military': 7, 'economic': 26}
    assert season_mod.delta(None, current)['overall'] == 150
    assert isinstance(season_mod.today(), str) and len(season_mod.today()) == 10


def test_parse_season_date_handles_shapes():
    assert season_mod.parse_season_date('2026-08-19 10:15:00') > 0
    assert season_mod.parse_season_date('2026-08-19') > 0
    assert season_mod.parse_season_date(1791811798) == 1791811798
    assert season_mod.parse_season_date(1791811798109) == 1791811798.109
    assert season_mod.parse_season_date(None) == 0
    assert season_mod.parse_season_date(True) == 0
    assert season_mod.parse_season_date('kapan?') == 0


def test_active_season_picks_running_window():
    seasons = {
        '51': {'id': 51, 'name': 'Season 20', 'scoreType': 'military',
               'requiredScore': 4000, 'visible': True,
               'fromDate': '2026-04-23 10:00:00', 'toDate': '2026-08-18 13:00:00'},
        '60': {'id': 60, 'name': 'Season 21', 'scoreType': 'military',
               'requiredScore': 2000, 'visible': True,
               'fromDate': '2026-08-19 10:15:00', 'toDate': '2026-10-19 13:00:00'},
        '61': {'id': 61, 'name': 'Hidden', 'scoreType': 'military', 'visible': False,
               'fromDate': '2026-08-19 10:15:00', 'toDate': '2026-10-19 13:00:00'},
        'rusak': 'bukan-dict',
    }
    now = season_mod.parse_season_date('2026-10-12 12:00:00')
    active = season_mod.active_season(seasons, now)
    assert active['id'] == 60 and active['name'] == 'Season 21'
    assert active['required_score'] == 2000
    assert season_mod.active_season({}, now) == {}
    assert season_mod.active_season(None, now) == {}
    past = season_mod.parse_season_date('2027-01-01 00:00:00')
    assert season_mod.active_season(seasons, past) == {}


def test_summarize_season_user_defaults():
    out = season_mod.summarize_season_user({'score': '150', 'position': 12,
                                            'unlockStatus': {'unlocked': True}})
    assert out == {'score': 150, 'position': 12, 'unlocked': True}
    assert season_mod.summarize_season_user(None) == {'score': 0, 'position': 0, 'unlocked': False}
    assert season_mod.summarize_season_user({})['unlocked'] is False
