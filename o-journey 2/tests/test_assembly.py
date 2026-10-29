from datetime import date,timedelta
from decimal import Decimal
from backend.assembly import AssembleInput,assemble

def test_assembly_sorts_and_does_not_invent_full_total():
    today=date.today()+timedelta(days=30)
    request=AssembleInput(city='Istanbul',checkin=today,checkout=today+timedelta(days=3),
        travelers=2,budget_per_person=Decimal('200'),currency='USD',budget_currency='USD')
    def provider(**kwargs):
        return {'checked_at':'2026-10-29T00:00:00Z','hotels':[
          {'id':'exp','name':'Expensive','price':{'amount':600,'currency':'USD'}},
          {'id':'cheap','name':'Affordable','price':{'amount':240,'currency':'USD'}},
          {'id':'sold','name':'Sold out','is_sold_out':True,'price':{'amount':50,'currency':'USD'}},
          {'id':'noprice','name':'No price','price':None}]}
    out=assemble(request,provider)
    assert len(out['lodging_options'])==2
    assert out['lodging_options'][0]['id']=='cheap'
    assert out['lodging_options'][0]['budget_fit_if_total_stay'] is True
    assert out['known_trip_total'] is None
    assert out['full_trip_budget_verified'] is False

def test_currency_mismatch_never_compares():
    today=date.today()+timedelta(days=30)
    request=AssembleInput(city='Tokyo',checkin=today,checkout=today+timedelta(days=2),
        travelers=1,budget_per_person=Decimal('45000'),budget_currency='RUB',currency='USD')
    out=assemble(request,lambda **kw:{'hotels':[{'id':'1','name':'A','price':{'amount':100,'currency':'USD'}}]})
    assert out['lodging_options'][0]['budget_fit_if_total_stay'] is None
