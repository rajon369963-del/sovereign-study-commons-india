"""Exercise the real daemon on 100 temporary tasks; no workspace/account writes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3


def test_100_tasks_preserve_unverified_receipts(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setenv('SOVEREIGN_COMMONS_ROOT', str(tmp_path))
    monkeypatch.setenv('AIR1_HOME', str(tmp_path / 'state'))
    monkeypatch.setenv('SPARK_TRANSACTION_DB', str(tmp_path / 'ledger.sqlite'))
    monkeypatch.setenv('WORKSPACE_POOL_DB', str(tmp_path / 'absent-pool.sqlite'))
    monkeypatch.setenv('AIR1_RECEIPT_DIR', str(tmp_path / 'receipts'))
    spec = importlib.util.spec_from_file_location('isolated_daemon', root / 'scripts/gemini_spark_daemon.py')
    daemon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(daemon)
    with sqlite3.connect(daemon.SPARK_DB) as con:
        con.execute('CREATE TABLE transactions (task_id TEXT PRIMARY KEY, effect_id, account_id, service, object_id, started_at, committed_at, verifier, result, retry_condition, receipt_path)')
    daemon.ensure_directories()
    for i in range(100):
        (daemon.QUEUE_DIR / f'task-{i}.md').write_text('Draft a review plan for a calculation mistake.')
    daemon.run_cycle()
    assert not list(daemon.QUEUE_DIR.iterdir())
    assert len(list(daemon.COMPLETED_DIR.glob('*'))) == 100
    for i in range(100):
        body = (daemon.COMPLETED_DIR / f'task-{i}_SOLUTION.md').read_bytes()
        receipt = json.loads((tmp_path / 'receipts' / f'task-{i}_receipt.json').read_text())
        assert receipt['artifact_sha256'] == hashlib.sha256(body).hexdigest()
        assert receipt['status'] == 'SYNTHESIZED_UNVERIFIED'
        assert receipt['verification']['executed'] is False
        assert receipt['promotion']['git_commit_attempted'] is False
    with sqlite3.connect(daemon.SPARK_DB) as con:
        assert con.execute('SELECT COUNT(*) FROM transactions WHERE result=? AND verifier=?', ('SYNTHESIZED_UNVERIFIED', 'UNVERIFIED')).fetchone()[0] == 100
    assert not (tmp_path / '.git').exists()
