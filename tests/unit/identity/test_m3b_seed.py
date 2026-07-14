from pathlib import Path

from night_voyager.identity.demo_seed import CONNECTED_DEMO_CASE_ID


def test_m3b_seed_uses_only_three_stable_synthetic_participants() -> None:
    source = Path("scripts/seed_demo.py").read_text(encoding="utf-8")
    assert 'CASE_ID = UUID("40000000-0000-0000-0000-000000000001")' in source
    assert CONNECTED_DEMO_CASE_ID.hex == "40000000000000000000000000000002"
    assert tuple(source.count(f'(\"{role}\",') for role in ("advisor", "student", "parent")) == (
        1,
        1,
        1,
    )
