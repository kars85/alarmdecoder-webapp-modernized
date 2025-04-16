def test_index(client):
    response = client.get('/', follow_redirects=True)
    assert response.status_code == 200
    assert b"AlarmDecoder Status" in response.data
