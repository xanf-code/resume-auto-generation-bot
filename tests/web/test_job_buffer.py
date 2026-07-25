"""Phase 8 — EventBuffer: monotonic seq assignment + replay via since()."""
from types import SimpleNamespace


def _ev():
    return SimpleNamespace(seq=0)


def test_append_assigns_increasing_seq_and_stamps_event():
    from src.web.job import EventBuffer
    buf = EventBuffer(maxlen=10)
    e1, e2 = _ev(), _ev()
    assert buf.append(e1) == 1
    assert buf.append(e2) == 2
    assert e1.seq == 1 and e2.seq == 2


def test_since_returns_only_newer():
    from src.web.job import EventBuffer
    buf = EventBuffer(maxlen=10)
    for _ in range(5):
        buf.append(_ev())
    assert [e.seq for e in buf.since(3)] == [4, 5]


def test_since_survives_maxlen_eviction():
    from src.web.job import EventBuffer
    buf = EventBuffer(maxlen=3)
    for _ in range(5):
        buf.append(_ev())  # seqs 1..5; only 3,4,5 retained
    assert [e.seq for e in buf.since(0)] == [3, 4, 5]
    assert [e.seq for e in buf.since(4)] == [5]


def test_len_reflects_bounded_size():
    from src.web.job import EventBuffer
    buf = EventBuffer(maxlen=3)
    for _ in range(5):
        buf.append(_ev())
    assert len(buf) == 3
