from fastapi.testclient import TestClient

from roambot.main import create_app


def test_guest_can_read_versioned_regions_without_provider_startup():
    # The anonymous endpoint must not need provider calls or credentials.
    app = create_app()
    # Do not enter the lifespan: this public static endpoint has no runtime dependency.
    response = TestClient(app).get('/api/v1/regions')
    assert response.status_code == 200
    body = response.json()
    assert body['version']
    assert body['data_date'] == '2023-06-30'
    assert body['regions']
    assert {row['level'] for row in body['regions']} == {'province', 'city'}
    assert all(set(row) == {'adcode', 'name', 'level', 'province_adcode'}
               for row in body['regions'])
