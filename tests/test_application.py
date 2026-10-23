import io
import json
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.domain import Account, Layout
from backend.fixtures import demo_layout
from backend.storage import Store, now
from backend.workers import Manager, command
from backend.optimization import propose


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path, workers=False)) as client:
        yield client


def test_account_creation_import_and_persistence(client, tmp_path):
    result = client.post('/api/accounts', json=Account(name='My saved account').model_dump())
    assert result.status_code == 200
    assert len(client.get('/api/accounts').json()) == 2
    imported = client.post('/api/accounts/import', json={"player": {"name": "Imported", "townHallLevel": 14,
        "troops": [{"name": "Giant", "level": 7, "village": "home"}], "spells": [], "heroes": []}})
    assert imported.status_code == 200
    assert imported.json()['troops'] == {'giant': 7}
    assert imported.json()['housing'] == 1  # unknown, never silently inferred
    assert len(Store(tmp_path/'war.sqlite3').list('accounts')) == 3


def test_screenshot_review_match_solve_and_export(client, request_model):
    fixture = client.get('/api/fixtures/synthetic-base.png')
    result = client.post('/api/bases/analyze', files={'file': ('base.png', fixture.content, 'image/png')}, data={'mode': 'synthetic'})
    assert result.status_code == 200, result.text
    layout = result.json()['layout']
    assert len(layout['structures']) == len(demo_layout().structures)
    payload = request_model.model_dump(mode='json'); payload['base_id'] = layout['id']
    assert client.post('/api/optimizations', json=payload).status_code == 422
    for s in layout['structures']: s['reviewed'] = True
    saved = client.post('/api/bases', json=layout)
    assert saved.status_code == 200
    matches = client.get(f"/api/bases/{layout['id']}/matches").json()
    assert matches[0]['classification'] == 'visible_layout_exact'
    result = client.post('/api/optimizations', json=payload)
    assert result.status_code == 200, result.text
    key = result.json()['id']
    snapshot = client.get(f'/api/optimizations/{key}/results').json()
    assert snapshot['inputs']['layout']['revision'] == 2
    assert snapshot['inputs']['sha256']
    assert client.get(f'/api/optimizations/{key}/report').status_code == 200
    assert client.post(f'/api/optimizations/{key}/control', json={'action':'cancel'}).json()['status'] == 'cancelled'
    assert client.get(f'/api/attack-plans/{key}').status_code == 200


def test_stale_revision_and_undo_history(client):
    layout = client.get('/api/bases/demo-layout').json()
    original = dict(layout)
    layout['name'] = 'Changed'
    saved = client.post('/api/bases', json=layout)
    assert saved.status_code == 200
    assert client.post('/api/bases', json=original).status_code == 409
    history = client.get('/api/bases/demo-layout/revisions').json()
    assert len(history) == 2
    history[1]['revision'] = saved.json()['revision']
    assert client.post('/api/bases', json=history[1]).json()['name'] == original['name']


def test_immutable_packs_and_discrepancies(client):
    pack = client.get('/api/game-data').json()[0]
    pack['definitions']['giant']['stats']['hp']['value'] += 1
    assert client.post('/api/game-data', json=pack).status_code == 409
    pack['id'] = 'synthetic-v2'
    assert client.post('/api/game-data', json=pack).status_code == 200
    diff = client.get('/api/game-data/discrepancies?left=synthetic-v1&right=synthetic-v2').json()
    assert diff[0]['object'] == 'giant' and diff[0]['parameter'] == 'hp'


def test_loopback_origin_and_host_guard(client):
    assert client.post('/api/accounts', json=Account(name='bad').model_dump(), headers={'origin':'https://evil.example'}).status_code == 403
    assert client.get('/api/system/status', headers={'host':'evil.example'}).status_code == 400
    assert client.get('/api/assets/not-a-path').status_code == 404


def test_backup_contains_sqlite_and_uploaded_assets(client):
    fixture = client.get('/api/fixtures/synthetic-base.png').content
    result = client.post('/api/bases/analyze', files={'file':('base.png',fixture,'image/png')})
    assert result.status_code == 200
    backup = client.get('/api/backup')
    with zipfile.ZipFile(io.BytesIO(backup.content)) as z:
        assert 'war.sqlite3' in z.namelist()
        assert any(name.startswith('assets/') for name in z.namelist())


def test_calibration_observations(client):
    data = {'source':'permitted replay: abc', 'pack_id':'synthetic-v1', 'observed_stars':2,
            'predicted_stars':2.5,'observed_destruction':80,'predicted_destruction':90}
    assert client.post('/api/calibration',json=data).status_code == 200
    assert client.get('/api/calibration').json()['stars_mae'] == .5


def test_diagnostic_simulation_is_persisted(client, request_model, account, pack):
    strategy = propose(request_model, account, pack, 0, [])
    response = client.post('/api/simulations', json={"base_id":"demo-layout", "account_id":"demo-account", "strategy":strategy.model_dump(mode='json')})
    assert response.status_code == 200, response.text
    assert response.json()['outcome']['events']
    assert client.get('/api/simulations').json()[0]['id'] == response.json()['id']


def wait_until(client, key, predicate, timeout=15):
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        job = client.get(f'/api/optimizations/{key}/results').json()
        if predicate(job): return job
        time.sleep(.1)
    pytest.fail(f'Worker did not reach expected state: {job}')


def test_worker_progress_pause_resume_cancel_and_reopen(tmp_path, request_model):
    with TestClient(create_app(tmp_path)) as client:
        payload = request_model.model_dump(mode='json'); payload['budget_seconds'] = 30
        key = client.post('/api/optimizations', json=payload).json()['id']
        initial = wait_until(client,key,lambda j:j['checkpoint']['simulations'] >= 2)
        assert initial['status'] == 'running'
        assert client.get('/api/system/status').status_code == 200
        client.post(f'/api/optimizations/{key}/control',json={'action':'pause'})
        paused = wait_until(client,key,lambda j:j['status']=='paused')
        assert paused['checkpoint']['leaders']
        spent = paused['active_seconds']
        client.post(f'/api/optimizations/{key}/control',json={'action':'resume'})
        wait_until(client,key,lambda j:j['status']=='running' and j['active_seconds']>spent)
        client.post(f'/api/optimizations/{key}/control',json={'action':'cancel'})
        cancelled = wait_until(client,key,lambda j:j['status']=='cancelled')
        assert cancelled['checkpoint']['simulations'] >= paused['checkpoint']['simulations']
    with TestClient(create_app(tmp_path,workers=False)) as client:
        assert client.get(f'/api/optimizations/{key}/results').json()['checkpoint']['leaders']


def test_worker_time_limit_includes_process_start(tmp_path, request_model):
    with TestClient(create_app(tmp_path)) as client:
        payload = request_model.model_dump(mode='json'); payload['budget_seconds'] = 4
        key = client.post('/api/optimizations',json=payload).json()['id']
        final = wait_until(client,key,lambda j:j['status'] in {'completed','failed'},timeout=10)
        assert final['status'] == 'completed', final['error']
        assert final['active_seconds'] <= 4
        assert final['checkpoint']['leaders']


def test_crash_recovery_charges_downtime_and_preserves_checkpoint(tmp_path, request_model):
    app = create_app(tmp_path,workers=False)
    store = app.state.store
    inputs = {'request':request_model.model_dump(mode='json')}
    store.create_job('recovery',inputs)
    with store.connection() as db:
        db.execute("UPDATE jobs SET status='running',segment_started=?,active_seconds=2 WHERE id='recovery'",(now()-3,))
    manager = Manager(store)
    try:
        manager.start()
        job = store.job('recovery')
        assert job['status'] == 'paused'
        assert job['active_seconds'] >= 5
        assert job['checkpoint']['iteration'] == 0
    finally:
        manager.stop()
