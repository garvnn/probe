"""Control: with every leak mechanism off, the blind-leak attack must be at chance.

If it isn't, that's a bug in the simulator or the view export, not a finding.
"""

import pytest


@pytest.mark.skip(reason="mechanisms off -> blind accuracy at chance (needs simulator + blind_leak)")
def test_mechanisms_off_blind_at_chance() -> None:
    raise NotImplementedError("owner: Ajay")
