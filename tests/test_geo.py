"""Phase 13C tests: state codes for the map."""

from salesinsight.geo import STATE_CODES, state_code


def test_all_states_and_dc():
    assert len(STATE_CODES) == 51
    assert len(set(STATE_CODES.values())) == 51


def test_lookups():
    assert state_code("New York") == "NY"
    assert state_code(" District of Columbia ") == "DC"
    assert state_code("Ontario") is None


def test_every_sample_state_has_a_code(sales_data):
    assert all(state_code(s) for s in sales_data["state"].unique())
