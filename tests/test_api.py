from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(str(tmp_path / 'test_sukan.db'))
    return TestClient(app)


def login(client: TestClient, role: str = 'admin') -> str:
    res = client.post('/auth/login', json={'username': 'tester', 'role': role})
    assert res.status_code == 200
    return res.json()['token']


def test_health(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        res = client.get('/health')
    assert res.status_code == 200


def test_advanced_end_to_end_and_audit(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        token = login(client, 'admin')
        headers = {'x-api-token': token}

        prop = client.post('/properties', json={
            'title': 'Olaya Residence', 'city': 'Riyadh', 'district': 'Olaya', 'total_rooms': 3, 'monthly_base_rent_sar': 2500,
        }, headers=headers)
        assert prop.status_code == 201

        tenant = client.post('/tenants', json={
            'full_name': 'Ahmed Ali', 'email': 'ahmed@example.com', 'work_or_study': 'Engineer',
            'interests': ['gym', 'reading'], 'sleep_schedule': 'early', 'cleanliness_level': 8,
        }, headers=headers)
        assert tenant.status_code == 201

        contract = client.post('/contracts', json={
            'property_id': 1, 'tenant_id': 1, 'monthly_rent_sar': 2400, 'security_deposit_sar': 1000,
            'start_date': '2026-05-01', 'end_date': '2026-11-01',
        }, headers=headers)
        assert contract.status_code == 201

        payment = client.post('/payments', json={'contract_id': 1, 'amount_sar': 2400, 'due_date': '2026-05-05'}, headers=headers)
        assert payment.status_code == 201

        expense = client.post('/expenses', json={'property_id': 1, 'category': 'utilities', 'amount_sar': 350, 'spent_on': '2026-05-02', 'notes': 'internet'}, headers=headers)
        assert expense.status_code == 201

        mark = client.post('/payments/1/mark-paid', headers=headers)
        assert mark.status_code == 200
        assert mark.json()['status'] == 'paid'

        dashboard = client.get('/dashboard')
        assert dashboard.status_code == 200
        assert dashboard.json()['net_cash_sar'] == 2050.0

        audit = client.get('/audit/logs', headers=headers)
        assert audit.status_code == 200
        assert len(audit.json()['items']) >= 5


def test_permissions_enforced(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        res = client.post('/properties', json={
            'title': 'Unit X', 'city': 'Riyadh', 'district': '', 'total_rooms': 2, 'monthly_base_rent_sar': 1000,
        })
    assert res.status_code == 401


def test_frontend_served(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        res = client.get('/')
    assert res.status_code == 200
    assert 'Advanced Operating Console' in res.text
