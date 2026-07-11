from fastapi.testclient import TestClient

from mission_control_api.main import create_app


def test_mission_control_e2e_streams_demo_sequence():
    app = create_app(test_mode=True)
    client = TestClient(app)

    health = client.get('/health')
    assert health.status_code == 200
    assert health.json() == {'status': 'ok', 'service': 'mission-control-api'}

    scenario = client.get('/api/scenario')
    assert scenario.status_code == 200
    assert scenario.json()['name'] == 'Earthquake Response'
    assert scenario.json()['agents'] == ['Overwatch', 'Sentinel', 'Atlas', 'Pulse', 'Aegis']

    with client.websocket_connect('/ws') as ws:
        start = client.post('/api/simulations/demo/start')
        assert start.status_code == 202

        first = ws.receive_json()
        assert first['type'] == 'mission.started'
        assert first['data']['scenario']['name'] == 'Earthquake Response'

        event = ws.receive_json()
        assert event['type'] == 'event'
        assert event['data']['event_type'] == 'earthquake_detected'

        agent_responses = []
        while True:
            message = ws.receive_json()
            if message['type'] == 'agent_response':
                agent_responses.append(message)
                continue
            mission_plan = message
            break

        assert len(agent_responses) == 5
        assert {item['data']['callsign'] for item in agent_responses} == {'Overwatch', 'Sentinel', 'Atlas', 'Pulse', 'Aegis'}
        assert mission_plan['type'] == 'mission_plan'
        assert mission_plan['data']['version'] == 1
        assert mission_plan['data']['overall_risk'] in {'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'}

        last = mission_plan
        while last['type'] != 'mission_complete':
            last = ws.receive_json()

        assert last['type'] == 'mission_complete'
        assert last['data']['plan_version'] == 10

    status = client.get('/api/status')
    state = client.get('/api/state')
    assert status.status_code == 200
    assert state.status_code == 200
    assert status.json() == state.json()
    payload = state.json()
    assert payload['status'] == 'completed'
    assert payload['memory']['version'] == 10
    assert payload['memory']['current_risk'] in {'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'}
