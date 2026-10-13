"""Deterministic single-elimination bracket layout helpers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FirstRoundPairing:
    match_number: int
    registration_ids: tuple[int, ...]
    is_bye: bool


def bracket_round_sizes(entrant_count: int) -> tuple[int, ...]:
    """Return match counts by round for a complete power-of-two bracket."""
    if entrant_count < 2:
        raise ValueError("A bracket requires at least two entrants.")

    bracket_size = 1 << (entrant_count - 1).bit_length()
    round_count = bracket_size.bit_length() - 1
    return tuple(bracket_size >> round_number for round_number in range(1, round_count + 1))


def first_round_pairings(
    registration_ids: list[int],
) -> tuple[FirstRoundPairing, ...]:
    """Place earliest approved registrations in byes, then pair the rest in order."""
    round_sizes = bracket_round_sizes(len(registration_ids))
    first_round_match_count = round_sizes[0]
    bye_count = first_round_match_count * 2 - len(registration_ids)

    pairings = [
        FirstRoundPairing(match_number=index + 1, registration_ids=(registration_id,), is_bye=True)
        for index, registration_id in enumerate(registration_ids[:bye_count])
    ]

    remaining = registration_ids[bye_count:]
    for offset in range(0, len(remaining), 2):
        pairings.append(
            FirstRoundPairing(
                match_number=len(pairings) + 1,
                registration_ids=(remaining[offset], remaining[offset + 1]),
                is_bye=False,
            )
        )

    return tuple(pairings)
