from datetime import datetime
from backend.planner import PlanningRequest, Traveler, plan, check_itinerary, ItineraryCheck, Activity, extract_budget

def test_no_mountains_bias():
    r=plan(PlanningRequest(message='Хочу искусство, еду и архитектуру',travelers=[Traveler()]))
    assert 'горы' not in r['intent']['interests']
    assert r['scenarios'][0]['destination']['id'] != 'ossetia'

def test_missing_prices_are_null():
    r=plan(PlanningRequest(message='Необычное путешествие на пять дней'))
    assert all(s['budget']['total_price'] is None and not s['is_bookable'] for s in r['scenarios'])

def test_student_not_automatically_discounted():
    r=plan(PlanningRequest(message='Музеи и еда',travelers=[Traveler(student=True),Traveler(student=True)]))
    assert r['intent']['student_travelers']==2
    assert all(s['budget']['total_price'] is None for s in r['scenarios'])

def test_budget_extraction():
    assert extract_budget('до 45 тыс рублей') == 45000

def test_itinerary_overlap():
    r=check_itinerary(ItineraryCheck(activities=[Activity(id='a',name='A',start=datetime(2026,11,1,10),end=datetime(2026,11,1,12)), Activity(id='b',name='B',start=datetime(2026,11,1,11),end=datetime(2026,11,1,13))]))
    assert not r['valid']

def test_verified_without_source_rejected():
    r=check_itinerary(ItineraryCheck(activities=[Activity(id='a',name='A',start=datetime(2026,11,1,10),end=datetime(2026,11,1,12),tariff_status='verified')]))
    assert r['issues'][0]['code']=='unsubstantiated_verified_tariff'
