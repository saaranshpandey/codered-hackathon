import json


def test_metrics_written_only_when_enabled(tmp_path, monkeypatch):
    from medbridge import metrics

    path = tmp_path / "m.jsonl"
    monkeypatch.setattr(metrics, "PATH", path)
    monkeypatch.setenv("METRICS_LOG", "0")
    metrics.log("caption.final", latency_ms=350)
    assert not path.exists()
    monkeypatch.setenv("METRICS_LOG", "1")
    metrics.log("caption.final", latency_ms=350)
    row = json.loads(path.read_text().splitlines()[0])
    assert row["event"] == "caption.final" and row["latency_ms"] == 350 and "t" in row
