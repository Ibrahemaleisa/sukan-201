from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(str(tmp_path / 'test_sukan.db'))
    return TestClient(app)


def admin_token(client: TestClient) -> str:
    res = client.post('/auth/login', json={'username': 'admin', 'password': 'admin123'})
    assert res.status_code == 200
    return res.json()['token']


def test_health(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        res = client.get('/health')
    assert res.status_code == 200


def test_final_fullstack_flow(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        token = admin_token(client)
        h = {'x-api-token': token}

        user = client.post('/auth/users', json={'username': 'ops1', 'password': 'ops12345', 'role': 'operator'}, headers=h)
        assert user.status_code == 201

        prop = client.post('/properties', json={'title': 'Olaya Premium', 'city': 'Riyadh', 'district': 'Olaya', 'total_rooms': 4, 'monthly_base_rent_sar': 3000}, headers=h)
        assert prop.status_code == 201

        tenant = client.post('/tenants', json={'full_name': 'Ahmed Ali', 'email': 'ahmed@x.com', 'work_or_study': 'Engineer', 'interests': ['gym','reading'], 'sleep_schedule': 'early', 'cleanliness_level': 8}, headers=h)
        assert tenant.status_code == 201

        contract = client.post('/contracts', json={'property_id': 1, 'tenant_id': 1, 'monthly_rent_sar': 2800, 'security_deposit_sar': 1200, 'start_date': '2026-05-01', 'end_date': '2026-11-01'}, headers=h)
        assert contract.status_code == 201

        payment = client.post('/payments', json={'contract_id': 1, 'amount_sar': 2800, 'due_date': '2026-05-03'}, headers=h)
        assert payment.status_code == 201
        mark = client.post('/payments/1/mark-paid', headers=h)
        assert mark.status_code == 200

        expense = client.post('/expenses', json={'property_id': 1, 'category': 'maintenance', 'amount_sar': 400, 'spent_on': '2026-05-02', 'notes': 'fix AC'}, headers=h)
        assert expense.status_code == 201

        ticket = client.post('/tickets', json={'property_id': 1, 'tenant_id': 1, 'title': 'Water leak in kitchen', 'priority': 'high'}, headers=h)
        assert ticket.status_code == 201

        dash = client.get('/dashboard')
        assert dash.status_code == 200
        assert dash.json()['net_cash_sar'] == 2400.0
        assert dash.json()['open_tickets'] == 1

        audit = client.get('/audit/logs', headers=h)
        assert audit.status_code == 200
        assert len(audit.json()['items']) >= 8

        csv = client.get('/reports/finance.csv', headers=h)
        assert csv.status_code == 200
        assert 'metric,value' in csv.text


def test_permissions_enforced(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        res = client.post('/properties', json={'title': 'Unit X', 'city': 'Riyadh', 'district': '', 'total_rooms': 2, 'monthly_base_rent_sar': 1000})
    assert res.status_code == 401


def test_frontend_served(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        res = client.get('/')
    assert res.status_code == 200
    assert 'High-End Final Console' in res.text
