"""Unit tests for deterministic single-elimination bracket layout."""

import pytest
from app.services.bracket import bracket_round_sizes, first_round_pairings


@pytest.mark.parametrize(
    ("entrant_count", "round_sizes"),
    [
        (2, (1,)),
        (3, (2, 1)),
        (4, (2, 1)),
        (5, (4, 2, 1)),
        (8, (4, 2, 1)),
        (9, (8, 4, 2, 1)),
    ],
)
def test_round_sizes(entrant_count: int, round_sizes: tuple[int, ...]):
    assert bracket_round_sizes(entrant_count) == round_sizes


@pytest.mark.parametrize("entrant_count", [2, 3, 4, 5, 6, 7, 8, 9])
def test_first_round_pairings_include_each_entrant_once(entrant_count: int):
    registration_ids = list(range(101, 101 + entrant_count))

    pairings = first_round_pairings(registration_ids)

    assert [pairing.match_number for pairing in pairings] == list(
        range(1, len(pairings) + 1)
    )
    assert sorted(
        registration_id
        for pairing in pairings
        for registration_id in pairing.registration_ids
    ) == registration_ids
    assert all(
        len(pairing.registration_ids) == (1 if pairing.is_bye else 2)
        for pairing in pairings
    )
    expected_byes = (1 << (entrant_count - 1).bit_length()) - entrant_count
    assert sum(pairing.is_bye for pairing in pairings) == expected_byes


def test_byes_are_assigned_to_earliest_registration_order():
    pairings = first_round_pairings([31, 32, 33, 34, 35])

    assert [(pairing.registration_ids, pairing.is_bye) for pairing in pairings] == [
        ((31,), True),
        ((32,), True),
        ((33,), True),
        ((34, 35), False),
    ]


def test_bracket_size_rejects_fewer_than_two_entrants():
    with pytest.raises(ValueError, match="at least two"):
        bracket_round_sizes(1)
