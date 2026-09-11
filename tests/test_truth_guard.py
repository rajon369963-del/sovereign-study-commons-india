import importlib.util
from pathlib import Path


def load_lint():
    spec = importlib.util.spec_from_file_location('truth_lint', Path(__file__).resolve().parents[1] / 'scripts/check_automation_truth_claims.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_negative_endpoint_guard_is_allowed_but_positive_claim_is_not(tmp_path, monkeypatch):
    lint = load_lint()
    path = tmp_path / 'workflow.yml'
    guard = '''if grep -Fq 'PASSED_PHYSICAL_VERIFICATION' "$body" || grep -Fq 'SUCCESS_PHYSICAL' "$body"; then
  echo 'stale unsafe verification marker detected on public endpoint' >&2
  exit 1
fi'''
    monkeypatch.setattr(lint, 'ROOT', tmp_path)
    monkeypatch.setattr(lint, 'REQUIRED', {})
    monkeypatch.setattr(lint, 'iter_surfaces', lambda: [path])
    monkeypatch.setattr(lint, 'load_manifest', lambda errors: ({}, {}))
    path.write_text(guard)
    assert lint.main() == 0
    path.write_text(guard + '\necho SUCCESS_PHYSICAL\n')
    assert lint.main() == 1
    path.write_text(guard.replace('exit 1', 'exit 0'))
    assert lint.main() == 1
