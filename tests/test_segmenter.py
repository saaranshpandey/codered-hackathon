def make(**kw):
    from medbridge.segmenter import SignSegmenter
    args = dict(start_frames=3, end_frames=10, preroll=4, postroll=3, min_frames=12, max_frames=60)
    args.update(kw)
    return SignSegmenter(**args)


def run(seg, pattern):
    """pattern: string of '.' (no hands) and 'H' (hands); frame i carries value i."""
    events = []
    for i, ch in enumerate(pattern):
        events += seg.push(i, ch == "H")
    return events


def test_start_needs_consecutive_hand_frames():
    seg = make()
    assert run(seg, "..HH.HH.") == []
    assert seg.state == "idle"
    seg = make()
    assert run(seg, "..HHH") == [("start",)]
    assert seg.state == "signing"


def test_clip_has_preroll_sign_and_postroll():
    seg = make()
    events = run(seg, "......" + "H" * 20 + "." * 10)
    kind, clip = events[-1]
    assert kind == "end"
    assert clip[0] == 6 - 4             # 4 frames of preroll before the first hand frame (6)
    assert clip[-1] == 6 + 20 + 3 - 1   # 3 frames of postroll after the last hand frame


def test_brief_dropout_does_not_end_sign():
    seg = make()
    events = run(seg, "HHHHHHHH....HHHHHHHH")
    assert events == [("start",)]


def test_short_clip_is_discarded():
    seg = make()
    events = run(seg, "HHHH" + "." * 10)
    assert events == [("start",), ("discard",)]
    assert seg.state == "idle"


def test_max_frames_forces_end():
    seg = make()
    events = run(seg, "H" * 70)
    ends = [e for e in events if e[0] == "end"]
    assert len(ends) == 1 and len(ends[0][1]) == 60


def test_force_end_returns_clip_only_while_signing():
    seg = make()
    assert seg.force_end() is None
    run(seg, "H" * 15)
    clip = seg.force_end()
    assert clip is not None and len(clip) == 15
    assert seg.state == "idle"
