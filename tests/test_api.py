from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test_sukan.db"
    app = create_app(str(db_path))
    return TestClient(app)


def test_health(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        res = client.get('/health')
    assert res.status_code == 200
    assert res.json()['status'] == 'ok'


def test_create_property_and_contract_flow(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        prop_res = client.post(
            '/properties',
            json={'title': 'Olaya Shared House', 'city': 'Riyadh', 'total_rooms': 2},
        )
        assert prop_res.status_code == 201
        assert prop_res.json()['id'] == 1

        contract_res = client.post(
            '/contracts',
            json={
                'property_id': 1,
                'tenant_name': 'Ahmed Ali',
                'monthly_rent_sar': 2200,
                'start_date': '2026-05-01',
                'end_date': '2026-11-01',
            },
        )
        assert contract_res.status_code == 201
        assert contract_res.json()['status'] == 'active'

        dashboard_res = client.get('/dashboard')
        assert dashboard_res.status_code == 200
        assert dashboard_res.json()['occupied_rooms'] == 1


def test_contract_requires_existing_property(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        res = client.post(
            '/contracts',
            json={
                'property_id': 99,
                'tenant_name': 'Sara',
                'monthly_rent_sar': 1800,
                'start_date': '2026-06-01',
                'end_date': '2026-12-01',
            },
        )
    assert res.status_code == 404


def test_frontend_is_served(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        res = client.get('/')
    assert res.status_code == 200
    assert 'لوحة تشغيل كاملة' in res.text
