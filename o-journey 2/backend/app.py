"""O! Journey verification API. No invented offer prices or discounts."""
from __future__ import annotations
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode
from urllib.request import urlopen
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

app = FastAPI(title='O! Journey verification API', version='0.4.0')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=False, allow_methods=['GET','POST'], allow_headers=['*'])
ROOT = Path(__file__).resolve().parent.parent

CITIES = {
 'kazan':(55.7961,49.1064,'Казань'), 'kaliningrad':(54.7104,20.4522,'Калининград'),
 'moscow':(55.7558,37.6173,'Москва'), 'ossetia':(43.0259,44.6818,'Владикавказ'),
 'armenia':(40.1792,44.4991,'Ереван'), 'uzbekistan':(39.6542,66.9597,'Самарканд'),
 'georgia':(41.7151,44.8271,'Тбилиси'), 'karelia':(61.7849,34.3469,'Петрозаводск')
}

def get_json(url: str, params: dict) -> dict:
    request_url = url + '?' + urlencode(params)
    with urlopen(request_url,timeout=9) as response:
        return json.load(response)

@app.get('/')
def index():
    return FileResponse(ROOT/'index.html')

@app.get('/api/health')
def health():
    return {'status':'ok','external_weather':'open-meteo','prices':'not_connected','ai':'not_connected'}

@app.get('/api/weather/{destination_id}')
def weather(destination_id: str, departure: date | None = None):
    if destination_id not in CITIES:
        raise HTTPException(404,'Unknown destination')
    lat,lon,city=CITIES[destination_id]
    today=datetime.now(timezone.utc).date()
    when=departure or today
    days_ahead=(when-today).days
    if days_ahead < 0:
        raise HTTPException(422,'Date is in the past')
    try:
        if days_ahead <= 15:
            data=get_json('https://api.open-meteo.com/v1/forecast',{
                'latitude':lat,'longitude':lon,'daily':'temperature_2m_max,temperature_2m_min,precipitation_sum,snowfall_sum,wind_speed_10m_max',
                'timezone':'auto','forecast_days':16})
            day=data['daily']; dates=day['time']
            if when.isoformat() not in dates:
                raise ValueError('Forecast does not include selected day')
            i=dates.index(when.isoformat())
            metrics={k:day[k][i] for k in ['temperature_2m_max','temperature_2m_min','precipitation_sum','snowfall_sum','wind_speed_10m_max']}
            mode='forecast'; verified=True
            explanation='Прогноз на выбранный день. Перед выездом условия могут измениться.'
        else:
            # Historical averages are NOT a forecast; sample same calendar period for recent completed years.
            samples=[]
            for year in range(today.year-3,today.year):
                try:
                    historical=date(year,when.month, min(when.day,28))
                    x=get_json('https://archive-api.open-meteo.com/v1/archive',{
                        'latitude':lat,'longitude':lon,'start_date':historical.isoformat(), 'end_date':historical.isoformat(),
                        'daily':'temperature_2m_max,temperature_2m_min,precipitation_sum,snowfall_sum,wind_speed_10m_max','timezone':'auto'})
                    samples.append({k:x['daily'][k][0] for k in ['temperature_2m_max','temperature_2m_min','precipitation_sum','snowfall_sum','wind_speed_10m_max']})
                except Exception:
                    continue
            if not samples: raise ValueError('Historical data unavailable')
            metrics={k:round(sum(x[k] for x in samples if x[k] is not None)/len([x for x in samples if x[k] is not None]),1) for k in samples[0]}
            mode='historical_sample'; verified=False
            explanation='Среднее по тому же дню за последние доступные годы; это НЕ прогноз и не климатическая норма месяца.'
        return {'destination_id':destination_id,'city':city,'date':when.isoformat(),'mode':mode,'metrics':metrics,
            'verified_forecast':verified,'source':'Open-Meteo','source_url':'https://open-meteo.com/',
            'checked_at':datetime.now(timezone.utc).isoformat(),'explanation':explanation}
    except Exception as exc:
        raise HTTPException(503,detail='Не удалось получить погодные данные от провайдера. Повторите проверку позднее.') from exc

class Offer(BaseModel):
    title: str
    unit_price: Decimal = Field(ge=0)
    quantity: int = Field(ge=1)
    source_type: Literal['verified','estimated','demo']
    source_url: str | None = None
    checked_at: datetime | None = None
    discount: Decimal = Field(default=Decimal('0'),ge=0)
    discount_verified: bool = False

class QuoteRequest(BaseModel):
    travelers: int = Field(ge=1,le=30)
    budget_per_person: Decimal = Field(ge=0)
    offers: list[Offer]

@app.post('/api/quote')
def quote(request: QuoteRequest):
    line_items=[]; total=Decimal('0')
    for o in request.offers:
        accepted_discount=o.discount if o.discount_verified and o.source_type=='verified' and o.source_url and o.checked_at else Decimal('0')
        if accepted_discount>o.unit_price:
            raise HTTPException(422,'Discount exceeds unit price')
        cost=(o.unit_price-accepted_discount)*o.quantity
        total+=cost
        line_items.append({'title':o.title,'total':str(cost),'discount_applied':str(accepted_discount*o.quantity),
                           'source_type':o.source_type,'requires_recheck':o.source_type!='verified' or not o.source_url})
    return {'total':str(total),'per_person':str((total/request.travelers).quantize(Decimal('0.01'))),
            'within_budget':total<=request.budget_per_person*request.travelers,
            'is_bookable':bool(request.offers) and all(o.source_type=='verified' and o.source_url and o.checked_at for o in request.offers),
            'lines':line_items,'currency':'RUB'}

# Phase 6: transparent travel discovery and itinerary checks.
try:
    from .planner import PlanningRequest, ItineraryCheck, plan, check_itinerary
except ImportError as exc:
    if 'no known parent package' not in str(exc):
        raise
    from planner import PlanningRequest, ItineraryCheck, plan, check_itinerary

@app.post('/api/plan')
def create_plan(request: PlanningRequest, use_llm: bool=False):
    return plan(request,use_llm=use_llm)

@app.post('/api/itinerary/check')
def validate_itinerary(request: ItineraryCheck):
    return check_itinerary(request)
