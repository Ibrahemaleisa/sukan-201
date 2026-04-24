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


def test_end_to_end_flow_property_tenant_contract_payment(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        prop = client.post('/properties', json={
            'title': 'Olaya Residence',
            'city': 'Riyadh',
            'district': 'Olaya',
            'total_rooms': 3,
            'monthly_base_rent_sar': 2500,
        })
        assert prop.status_code == 201

        tenant = client.post('/tenants', json={
            'full_name': 'Ahmed Ali',
            'email': 'ahmed@example.com',
            'work_or_study': 'Engineer',
            'interests': ['gym', 'reading'],
            'sleep_schedule': 'early',
            'cleanliness_level': 8,
        })
        assert tenant.status_code == 201

        contract = client.post('/contracts', json={
            'property_id': 1,
            'tenant_id': 1,
            'monthly_rent_sar': 2400,
            'security_deposit_sar': 1000,
            'start_date': '2026-05-01',
            'end_date': '2026-11-01',
        })
        assert contract.status_code == 201

        payment = client.post('/payments', json={
            'contract_id': 1,
            'amount_sar': 2400,
            'due_date': '2026-05-05',
        })
        assert payment.status_code == 201

        paid = client.post('/payments/1/mark-paid')
        assert paid.status_code == 200
        assert paid.json()['status'] == 'paid'

        dash = client.get('/dashboard')
        assert dash.status_code == 200
        assert dash.json()['properties'] == 1
        assert dash.json()['tenants'] == 1
        assert dash.json()['active_contracts'] == 1


def test_matching_recommendations(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        client.post('/tenants', json={
            'full_name': 'A',
            'email': 'a@example.com',
            'work_or_study': 'Student',
            'interests': ['reading', 'tech'],
            'sleep_schedule': 'early',
            'cleanliness_level': 8,
        })
        client.post('/tenants', json={
            'full_name': 'B',
            'email': 'b@example.com',
            'work_or_study': 'Engineer',
            'interests': ['tech', 'music'],
            'sleep_schedule': 'early',
            'cleanliness_level': 7,
        })
        client.post('/tenants', json={
            'full_name': 'C',
            'email': 'c@example.com',
            'work_or_study': 'Designer',
            'interests': ['travel'],
            'sleep_schedule': 'late',
            'cleanliness_level': 2,
        })

        res = client.get('/matching/recommendations/1')
        assert res.status_code == 200
        recommendations = res.json()['recommendations']
        assert len(recommendations) == 2
        assert recommendations[0]['full_name'] == 'B'


def test_frontend_is_served(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        res = client.get('/')
    assert res.status_code == 200
    assert 'منصة إدارة Co-living متقدمة' in res.text
