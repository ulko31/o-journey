from fastapi.testclient import TestClient
from backend.app import app
client=TestClient(app)
def test_health():
    assert client.get('/api/health').json()['prices']=='not_connected'
def test_demo_discount_not_applied():
    data={'travelers':2,'budget_per_person':'5000','offers':[{'title':'Museum','unit_price':'1200','quantity':2,'source_type':'demo','discount':'500','discount_verified':True}]}
    r=client.post('/api/quote',json=data)
    assert r.status_code==200 and r.json()['total']=='2400' and r.json()['is_bookable'] is False
def test_verified_discount():
    data={'travelers':2,'budget_per_person':'5000','offers':[{'title':'Museum','unit_price':'1200','quantity':2,'source_type':'verified','source_url':'https://example.org/rates','checked_at':'2026-10-28T00:00:00Z','discount':'200','discount_verified':True}]}
    assert client.post('/api/quote',json=data).json()['total']=='2000'
def test_invalid_offer():
    data={'travelers':2,'budget_per_person':'5000','offers':[{'title':'Museum','unit_price':'100','quantity':1,'source_type':'verified','discount':'200','discount_verified':True,'source_url':'https://example.org','checked_at':'2026-10-28T00:00:00Z'}]}
    assert client.post('/api/quote',json=data).status_code==422
def test_weather_unknown():
    assert client.get('/api/weather/unknown').status_code==404
def test_weather_forecast_mock(monkeypatch):
    from backend import app as module
    from datetime import datetime,timezone
    today=datetime.now(timezone.utc).date().isoformat()
    def fake(url,params):
        assert 'forecast' in url
        return {'daily':{'time':[today], 'temperature_2m_max':[10.0], 'temperature_2m_min':[3.0], 'precipitation_sum':[1.2], 'snowfall_sum':[0.0], 'wind_speed_10m_max':[16.0]}}
    monkeypatch.setattr(module,'get_json',fake)
    r=client.get('/api/weather/kazan?departure='+today)
    assert r.status_code==200 and r.json()['verified_forecast'] is True and r.json()['metrics']['temperature_2m_max']==10.0
