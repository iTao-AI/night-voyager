from scripts.seed_demo import ACTORS, CASE_ID


def test_m3b_seed_uses_only_three_stable_synthetic_participants() -> None:
    assert CASE_ID.hex == "40000000000000000000000000000001"
    assert tuple(role for role, _, _ in ACTORS) == ("advisor", "student", "parent")
