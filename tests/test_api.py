from fastapi.testclient import TestClient

from apps.api.main import app, CONTRACTS, PROPERTIES

client = TestClient(app)


def setup_function() -> None:
    PROPERTIES.clear()
    CONTRACTS.clear()


def test_health() -> None:
    res = client.get('/health')
    assert res.status_code == 200
    assert res.json()['status'] == 'ok'


def test_create_property_and_contract_flow() -> None:
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


def test_contract_requires_existing_property() -> None:
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
