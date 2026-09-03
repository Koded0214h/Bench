from __future__ import annotations

import json
import threading

from bench.audit import AuditLog, InMemoryAuditStore, JsonlAuditStore
from bench.audit.config import AuditConfig


def test_jsonl_persists_across_instances(tmp_path):
    path = tmp_path / "audit.jsonl"
    log1 = AuditLog(JsonlAuditStore(path))
    log1.note("first", task_id="t1")
    log1.note("second", task_id="t1")

    log2 = AuditLog(JsonlAuditStore(path))
    assert len(log2) == 2
    assert [e.payload["text"] for e in log2] == ["first", "second"]
    assert log2.verify().ok


def test_jsonl_is_one_object_per_line(tmp_path):
    path = tmp_path / "a.jsonl"
    log = AuditLog(JsonlAuditStore(path))
    for i in range(5):
        log.note(f"n{i}")
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 5
    assert all(json.loads(line)["kind"] == "note" for line in lines)


def test_from_config_memory_vs_jsonl(tmp_path):
    mem = AuditLog.from_config(AuditConfig(backend="memory"))
    assert isinstance(mem.store, InMemoryAuditStore)
    disk = AuditLog.from_config(AuditConfig(backend="jsonl", path=str(tmp_path / "x.jsonl")))
    assert isinstance(disk.store, JsonlAuditStore)


def test_concurrent_appends_keep_chain_intact(tmp_path):
    log = AuditLog(JsonlAuditStore(tmp_path / "c.jsonl"))

    def worker(n: int) -> None:
        for i in range(25):
            log.note(f"w{n}-{i}", task_id=f"t{n}")

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(log) == 100
    result = log.verify()
    assert result.ok, result
    seqs = [e.seq for e in log]
    assert seqs == list(range(100))
