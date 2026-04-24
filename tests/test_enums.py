from autoref.enums import WinCondition, MapState, Step


def test_win_condition_values():
    # native bancho values — must stay aligned with BanchoLobbyWinConditions
    assert WinCondition.SCORE_V1.value == 0
    assert WinCondition.ACCURACY.value == 1
    assert WinCondition.COMBO.value == 2
    assert WinCondition.SCORE_V2.value == 3
    # sentinel / custom
    assert WinCondition.INHERIT.value == -1
    assert WinCondition.OTHER.value == 11


def test_map_state_values():
    assert MapState.INHERIT.value == -1
    assert MapState.PICKABLE.value == 0
    assert MapState.PROTECTED.value == 1
    assert MapState.BANNED.value == 2
    assert MapState.OTHER.value == 11


def test_step_values():
    assert Step.PICK.value == 0
    assert Step.BAN.value == 1
    assert Step.PROTECT.value == 2
    assert Step.WIN.value == 3
    assert Step.OTHER.value == 11


def test_step_name_roundtrip():
    for step in Step:
        assert Step[step.name] is step
