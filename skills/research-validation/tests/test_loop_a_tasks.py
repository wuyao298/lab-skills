import importlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


@pytest.fixture
def loop():
    return importlib.import_module('loop_a_tasks')


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def get(path):
    return json.loads(path.read_text(encoding='utf-8'))


@pytest.fixture
def project(tmp_path):
    v = tmp_path / 'validation'
    v.mkdir()
    index = {f'ACU-{i:03d}': {'query': f'TITLE-ABS-KEY(test{i})', 'source_objects': [f'obj{i}']}
             for i in (1, 2)}
    put(v / 'acu_index.json', index)
    put(v / 'loop_state.json', {'round': 0, 'max_rounds': 10, 'acus': {
        acu: {'query': x['query'], 'status': 'open', 'consecutive_fails': 0}
        for acu, x in index.items()}})
    put(v / 'per_ACU_summary.json', {acu: {'source_objects': x['source_objects']} for acu, x in index.items()})
    put(v / 'metadata.json', {'objects': ['obj1', 'obj2'], 'gate3_pending': False, 'last_step': 'step4'})
    for i in (1, 2):
        (v / f'obj{i}').mkdir()
        (v / f'obj{i}/mve_paths.md').write_text(f'MVE OBJECT {i}', encoding='utf-8')
    return v


def raw(query, zero=False):
    return {'search-results': {'opensearch:totalResults': '0' if zero else '1',
            'opensearch:Query': {'@searchTerms': query},
            'entry': [{'error': 'ZERO_RESULTS'}] if zero else [
                {'eid': '2-s2.0-123', 'dc:title': 'A title', 'dc:description': '120 C gives 95% yield'}]}}


@pytest.fixture
def fetch(loop, monkeypatch):
    calls = []
    def fake(query, env_file=None):
        calls.append(query)
        return raw(query)
    monkeypatch.setattr(loop, 'search', fake)
    return calls


def reply(v, acu='ACU-001', level='高', **changes):
    folder = v / f'scopus_runs/{acu}/round_01'
    task = get(folder / 'task.json')
    result = {'task_id': task['task_id'], 'verdict': [
        {'paper_id': 'EID:2-s2.0-123', 'level': level,
         'key_steps': '120 C → 95% yield (H2)', 'integration': 'path A, step 1'}]}
    result.update(changes)
    put(folder / 'verdict_result.json', result)
    return result


def test_dry_no_credentials_no_writes(loop, project, monkeypatch):
    monkeypatch.setattr(loop, 'search', lambda *a, **k: pytest.fail('dry accessed network'))
    before = {str(p.relative_to(project)): p.read_bytes() for p in project.rglob('*') if p.is_file()}
    plan = loop.prepare(project, dry=True)
    assert plan['round'] == 1
    assert before == {str(p.relative_to(project)): p.read_bytes() for p in project.rglob('*') if p.is_file()}


def test_prepare_scopes_context_and_resume(loop, project, fetch):
    first = loop.prepare(project, workers=12)
    assert first['pending'] == 2 and len(fetch) == 2
    for i in (1, 2):
        prompt = (project / f'scopus_runs/ACU-{i:03d}/round_01/verdict_prompt.md').read_text(encoding='utf-8')
        assert f'MVE OBJECT {i}' in prompt and f'MVE OBJECT {3-i}' not in prompt
        assert '120 C gives 95% yield' in prompt
    loop.prepare(project)
    assert len(fetch) == 2
    assert get(project / 'loop_state.json')['round'] == 0


def test_partial_collect_idempotent_then_complete(loop, project, fetch):
    loop.prepare(project)
    reply(project)
    result = loop.collect(project)
    assert result['pending'] == 1
    state = get(project / 'loop_state.json')
    assert state['acus']['ACU-001']['status'] == 'covered' and state['round'] == 0
    summary = (project / 'per_ACU_summary.json').read_bytes()
    loop.collect(project)
    assert summary == (project / 'per_ACU_summary.json').read_bytes()
    reply(project, 'ACU-002', '中')
    assert loop.collect(project)['pending'] == 0
    state = get(project / 'loop_state.json')
    assert state['round'] == 1 and state['acus']['ACU-002']['consecutive_fails'] == 1
    assert get(project / 'per_ACU_summary.json')['ACU-002']['fail_rounds'] == [1]
    loop.collect(project)
    assert get(project / 'per_ACU_summary.json')['ACU-002']['fail_rounds'] == [1]


@pytest.mark.parametrize('bad', [
    {'task_id': 'stale'},
    {'verdict': []},
    {'verdict': [{'paper_id': 'EID:invented', 'level': '高', 'key_steps': 'x', 'integration': 'y'}]},
    {'verdict': [{'paper_id': '1', 'level': '高（H2）', 'key_steps': 'x', 'integration': 'y'}]},
])
def test_invalid_result_not_a_scientific_failure(loop, project, fetch, bad):
    loop.prepare(project)
    reply(project, **bad)
    result = loop.collect(project)
    assert result['errors']
    assert get(project / 'loop_state.json')['acus']['ACU-001']['consecutive_fails'] == 0
    assert not (project / 'scopus_runs/ACU-001/round_01/verdict.md').exists()


def test_network_error_retry_only_failed_task(loop, project, monkeypatch):
    calls = []
    def flaky(query, env_file=None):
        calls.append(query)
        if query.endswith('test2)') and calls.count(query) == 1:
            raise TimeoutError('network timeout')
        return raw(query)
    monkeypatch.setattr(loop, 'search', flaky)
    assert loop.prepare(project)['errors']
    assert get(project / 'loop_state.json')['round'] == 0
    loop.prepare(project)
    assert calls.count('TITLE-ABS-KEY(test1)') == 1
    assert calls.count('TITLE-ABS-KEY(test2)') == 2
    assert get(project / 'loop_state.json')['acus']['ACU-002']['consecutive_fails'] == 0


def test_zero_results_no_agent_task(loop, project, monkeypatch):
    monkeypatch.setattr(loop, 'search', lambda query, env_file=None: raw(query, zero=True))
    assert loop.prepare(project)['pending'] == 0
    loop.collect(project)
    assert get(project / 'loop_state.json')['round'] == 1
    assert (project / 'scopus_runs/ACU-001/round_01/verdict.md').exists()


def test_gate3_blocks_before_network(loop, project, monkeypatch):
    state = get(project / 'loop_state.json')
    state['acus']['ACU-001']['consecutive_fails'] = 2
    put(project / 'loop_state.json', state)
    monkeypatch.setattr(loop, 'search', lambda *a, **k: pytest.fail('gate bypass'))
    result = loop.prepare(project)
    assert result['gate3_pending']


def test_wrong_query_rejected_not_reused(loop, project, monkeypatch):
    monkeypatch.setattr(loop, 'search', lambda *a, **k: raw('TITLE-ABS-KEY(wrong)'))
    assert loop.prepare(project)['errors']
    assert not list(project.rglob('task.json'))


def test_input_change_rejects_stale_tasks(loop, project, fetch):
    loop.prepare(project)
    reply(project)
    (project / 'obj1/mve_paths.md').write_text('changed scope', encoding='utf-8')
    with pytest.raises(ValueError, match='input|输入'):
        loop.collect(project)


def test_shared_query_one_fetch_distinct_tasks(loop, project, fetch):
    index = get(project / 'acu_index.json')
    state = get(project / 'loop_state.json')
    index['ACU-002']['query'] = state['acus']['ACU-002']['query'] = index['ACU-001']['query']
    put(project / 'acu_index.json', index)
    put(project / 'loop_state.json', state)
    loop.prepare(project)
    assert len(fetch) == 1
    tasks = [get(p) for p in sorted(project.rglob('task.json'))]
    assert tasks[0]['task_id'] != tasks[1]['task_id']


def test_multi_object_acu_includes_all_sources(loop, project, fetch):
    index = get(project / 'acu_index.json')
    index['ACU-001']['source_objects'] = ['obj1', 'obj2']
    put(project / 'acu_index.json', index)
    loop.prepare(project)
    prompt = (project / 'scopus_runs/ACU-001/round_01/verdict_prompt.md').read_text(encoding='utf-8')
    assert 'MVE OBJECT 1' in prompt and 'MVE OBJECT 2' in prompt


def test_missing_context_fails_before_search(loop, project, monkeypatch):
    (project / 'obj2/mve_paths.md').unlink()
    monkeypatch.setattr(loop, 'search', lambda *a, **k: pytest.fail('invalid inputs queried'))
    with pytest.raises((ValueError, FileNotFoundError)):
        loop.prepare(project)


def test_raw_tamper_rejects_result(loop, project, fetch):
    loop.prepare(project)
    reply(project)
    put(project / 'scopus_runs/ACU-001/round_01/results_raw.json', raw('tampered'))
    assert loop.collect(project)['errors']
    assert get(project / 'loop_state.json')['acus']['ACU-001']['status'] == 'open'


def test_covered_and_skipped_not_scheduled(loop, project, fetch):
    state = get(project / 'loop_state.json')
    state['acus']['ACU-001'].update(status='covered', pass_round=1)
    state['acus']['ACU-002']['status'] = 'skipped'
    put(project / 'loop_state.json', state)
    assert loop.prepare(project)['pending'] == 0
    assert not fetch


def test_second_failure_batches_gate3(loop, project, monkeypatch):
    monkeypatch.setattr(loop, 'search', lambda query, env_file=None: raw(query, zero=True))
    for rn in (1, 2):
        loop.prepare(project)
        result = loop.collect(project)
        assert get(project / 'loop_state.json')['round'] == rn
    assert result['gate3_pending'] and result['gate3_acus'] == ['ACU-001', 'ACU-002']
    assert get(project / 'metadata.json')['last_step'] == 'step5'
    assert get(project / 'per_ACU_summary.json')['ACU-001']['fail_rounds'] == [1, 2]
    assert len(get(project / 'loop_state.json')['gate_history']) == 1
    monkeypatch.setattr(loop, 'search', lambda *a, **k: pytest.fail('queried through gate'))
    assert loop.prepare(project)['gate3_pending']


def test_max_round_guard_even_after_fail_counter_reset(loop, project, monkeypatch):
    state = get(project / 'loop_state.json')
    state['round'] = 10
    put(project / 'loop_state.json', state)
    monkeypatch.setattr(loop, 'search', lambda *a, **k: pytest.fail('eleventh round'))
    assert loop.prepare(project)['gate3_pending']


def test_recover_interrupted_multi_file_commit(loop, project, fetch, monkeypatch):
    loop.prepare(project)
    reply(project)
    reply(project, 'ACU-002')
    original = loop.recover
    def crash(root):
        journal = root / 'loop_a/transaction.json'
        if journal.exists():
            name, text = next(iter(get(journal).items()))
            loop.atomic_text(root / name, text)
            raise OSError('simulated power loss between state files')
        original(root)
    with monkeypatch.context() as m:
        m.setattr(loop, 'recover', crash)
        with pytest.raises(OSError, match='power loss'):
            loop.collect(project)
    assert loop.status(project)['recovery_needed']
    result = loop.collect(project)
    assert result['phase'] == 'complete' and result['pending'] == 0
    assert get(project / 'loop_state.json')['round'] == 1
    assert get(project / 'per_ACU_summary.json')['_meta']['round'] == 1
    assert not (project / 'loop_a/transaction.json').exists()


def test_coordinator_lock_rejects_concurrent_writer(loop, project):
    with loop.writer_lock(project):
        with pytest.raises(RuntimeError, match='coordinator'):
            loop.prepare(project)
    # OS lock releases without deleting or manually unlocking the lock file.
    with loop.writer_lock(project):
        pass


def test_query_edit_survives_stale_index(loop, project, fetch):
    state = get(project / 'loop_state.json')
    state['acus']['ACU-001']['query'] = 'TITLE-ABS-KEY(user-approved-new)'
    put(project / 'loop_state.json', state)
    loop.prepare(project)
    assert 'TITLE-ABS-KEY(user-approved-new)' in fetch
    assert 'TITLE-ABS-KEY(test1)' not in fetch


def test_shared_state_external_edit_detected(loop, project, fetch):
    loop.prepare(project)
    reply(project)
    meta = get(project / 'metadata.json')
    meta['objects'].append('obj3')
    put(project / 'metadata.json', meta)
    with pytest.raises(ValueError, match='shared state'):
        loop.collect(project)


def test_legacy_files_not_overwritten(loop, project, fetch):
    path = project / 'scopus_runs/ACU-001/round_01/results_raw.json'
    put(path, raw('legacy'))
    with pytest.raises(ValueError, match='legacy'):
        loop.prepare(project)
    assert get(path) == raw('legacy') and not fetch


def test_reordered_rows_keep_identity_no_positional_repair(loop):
    entries = [{'eid': 'a'}, {'eid': 'b'}]
    rows = [{'paper_id': 'EID:b', 'level': '高', 'key_steps': 'b evidence', 'integration': 'b use'},
            {'paper_id': 'EID:a', 'level': '中', 'key_steps': 'a evidence', 'integration': 'a use'}]
    accepted = loop.validate_result({'task_id': 't', 'verdict': rows}, 't', entries)
    assert accepted[0]['paper_id'] == 'EID:b' and accepted[0]['level'] == '高'
    rows[1]['paper_id'] = '2'  # Another alias for b, not a new paper.
    with pytest.raises(ValueError, match='duplicate'):
        loop.validate_result({'task_id': 't', 'verdict': rows}, 't', entries)


def test_native_output_builds_knowledge_base(loop, project, fetch):
    import build_knowledge_base as kb
    loop.prepare(project)
    reply(project)
    reply(project, 'ACU-002')
    loop.collect(project)
    result = kb.main_argv(['--validation', str(project)])
    assert result == 0
    index = get(project / 'reproducibility_index.json')
    assert len(index['entries']) == 1  # Shared EID retains both source ACUs.
    assert sorted(index['entries'][0]['source_acus']) == ['ACU-001', 'ACU-002']
    for obj in ('obj1', 'obj2'):
        assert 'XE001' in (project / f'knowledge_base/{obj}.txt').read_text(encoding='utf-8')


def test_concurrency_can_exceed_old_cap(loop, project, monkeypatch):
    import threading
    import time
    index = get(project / 'acu_index.json')
    state = get(project / 'loop_state.json')
    for i in range(3, 13):
        acu = f'ACU-{i:03d}'
        index[acu] = {'query': f'TITLE-ABS-KEY(test{i})', 'source_objects': ['obj1']}
        state['acus'][acu] = {'query': index[acu]['query'], 'status': 'open', 'consecutive_fails': 0}
    put(project / 'acu_index.json', index)
    put(project / 'loop_state.json', state)
    lock, barrier = threading.Lock(), threading.Barrier(12)
    concurrent = {'active': 0, 'peak': 0}
    def slow(query, env_file=None):
        with lock:
            concurrent['active'] += 1
            concurrent['peak'] = max(concurrent['peak'], concurrent['active'])
        barrier.wait(timeout=3)
        time.sleep(0.01)
        with lock:
            concurrent['active'] -= 1
        return raw(query)
    monkeypatch.setattr(loop, 'search', slow)
    result = loop.prepare(project, workers=12)
    assert not result['errors'] and concurrent['peak'] == 12


def test_cli_dry_is_provider_independent(project, monkeypatch):
    import subprocess
    env = dict(__import__('os').environ)
    for name in ('OPENCODE_GO_KEY', 'SCOPUS_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY'):
        env.pop(name, None)
    runner = Path(__file__).resolve().parents[1] / 'scripts/loop_a_runner.py'
    result = subprocess.run([sys.executable, str(runner), 'round', '--validation', str(project), '--dry'],
                            env=env, capture_output=True, encoding='utf-8', timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['dry']
    assert get(project / 'loop_state.json')['round'] == 0


def test_partial_second_fail_defers_gate_until_round_complete(loop, project, fetch):
    state = get(project / 'loop_state.json')
    state['acus']['ACU-001']['consecutive_fails'] = 1
    put(project / 'loop_state.json', state)
    loop.prepare(project)
    reply(project, level='中')
    result = loop.collect(project)
    assert result['pending'] == 1 and not result['gate3_pending']
    assert not get(project / 'metadata.json')['gate3_pending']
    reply(project, 'ACU-002')
    assert loop.collect(project)['gate3_pending']


def test_accepts_one_byte_snapshot_despite_late_worker_replace(loop, project, fetch, monkeypatch):
    loop.prepare(project)
    reply(project)
    response = project / 'scopus_runs/ACU-001/round_01/verdict_result.json'
    original_hash = loop.file_hash(response)
    original_validate = loop.validate_result
    def swap_after_parse(result, task_id, entries):
        rows = original_validate(result, task_id, entries)
        reply(project, level='中')
        return rows
    monkeypatch.setattr(loop, 'validate_result', swap_after_parse)
    loop.collect(project)
    task = get(project / 'loop_a/active.json')['tasks']['ACU-001']
    assert task.get('source_result_sha', task['result_sha']) == original_hash


def test_rebuilds_missing_accepted_verdict_before_finishing(loop, project, fetch):
    loop.prepare(project)
    reply(project)
    loop.collect(project)
    verdict = project / 'scopus_runs/ACU-001/round_01/verdict.md'
    verdict.unlink()
    reply(project, 'ACU-002')
    assert loop.collect(project)['pending'] == 0
    assert verdict.exists() and '| 高 |' in verdict.read_text(encoding='utf-8')


def test_partial_round_cannot_enter_knowledge_base(loop, project, fetch):
    import build_knowledge_base as kb
    loop.prepare(project)
    reply(project)
    loop.collect(project)
    with pytest.raises(SystemExit, match='LOOP|未决|活动'):
        kb.main_argv(['--validation', str(project)])
    assert not (project / 'reproducibility_filter.md').exists()


def test_native_round_passes_existing_final_checker(loop, tmp_path, monkeypatch):
    import build_knowledge_base as kb
    import check_validation as cv
    from test_check_validation import write_mini_project
    p, slug, v = write_mini_project(tmp_path)
    saved = v / 'fixture_saved_round'
    (v / 'scopus_runs/ACU-001/round_01').rename(saved)
    index = get(v / 'acu_index.json')
    query = index['ACU-001']['query']
    put(v / 'loop_state.json', {'round': 0, 'max_rounds': 10,
        'acus': {'ACU-001': {'status': 'open', 'query': query, 'consecutive_fails': 0}}})
    put(v / 'per_ACU_summary.json', {'ACU-001': {}})
    data = get(saved / 'results_raw.json')
    data['search-results']['opensearch:Query'] = {'@searchTerms': query}
    monkeypatch.setattr(loop, 'search', lambda *a, **k: data)
    loop.prepare(v)
    folder = v / 'scopus_runs/ACU-001/round_01'
    task = get(folder / 'task.json')
    put(folder / 'verdict_result.json', {'task_id': task['task_id'], 'verdict': [
        {'paper_id': 'EID:2-s2.0-85000000001', 'level': '高', 'key_steps': 'H2 参数与结果', 'integration': '路径 A 步骤1'},
        {'paper_id': 'EID:2-s2.0-85000000002', 'level': '建议排除', 'key_steps': '无操作依据', 'integration': '不适用'}]})
    assert loop.collect(v)['phase'] == 'complete'
    assert kb.main_argv(['--validation', str(v), '--db', str(p / 'reports/literature_db.csv')]) == 0
    cv.issues.clear()
    assert cv.main_argv(['--validation', str(v), '--project', str(p), '--slug', slug]) == 0, cv.issues
