from autoref.enums import WinCondition, MapState, Step


def test_win_condition_values():
    assert WinCondition.INHERIT.value == 0
    assert WinCondition.SCORE_V2.value == 1
    assert WinCondition.OTHER.value == 11


def test_map_state_values():
    assert MapState.INHERIT.value == 0
    assert MapState.PICKABLE.value == 1
    assert MapState.BANNED.value == 3
    assert MapState.OTHER.value == 11


def test_step_values():
    assert Step.PICK.value == 1
    assert Step.BAN.value == 2
    assert Step.PROTECT.value == 3
    assert Step.WIN.value == 4
    assert Step.OTHER.value == 11


def test_step_name_roundtrip():
    for step in Step:
        assert Step[step.name] is step
