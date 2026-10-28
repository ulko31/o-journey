"""O! Journey verification API. No invented offer prices or discounts."""
from __future__ import annotations
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode
from urllib.request import urlopen
import json
import ssl
import certifi
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field

app = FastAPI(title='O! Journey verification API', version='0.4.0')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=False, allow_methods=['GET','POST'], allow_headers=['*'])
ROOT = Path(__file__).resolve().parent.parent

CITIES = {
 'kazan':(55.7961,49.1064,'Казань'), 'kaliningrad':(54.7104,20.4522,'Калининград'),
 'moscow':(55.7558,37.6173,'Москва'), 'ossetia':(43.0259,44.6818,'Владикавказ'),
 'armenia':(40.1792,44.4991,'Ереван'), 'uzbekistan':(39.6542,66.9597,'Самарканд'),
 'georgia':(41.7151,44.8271,'Тбилиси'), 'karelia':(61.7849,34.3469,'Петрозаводск'),
 'sochi':(43.5855,39.7231,'Сочи'),
 'dagestan':(42.9849,47.5047,'Махачкала'),
 'murmansk':(68.9707,33.0749,'Мурманск'),
 'novgorod':(58.5215,31.2755,'Великий Новгород'),
 'minsk':(53.9006,27.559,'Минск'),
 'almaty':(43.2389,76.8897,'Алматы'),
 'bishkek':(42.8746,74.5698,'Бишкек'),
 'baku':(40.4093,49.8671,'Баку'),
 'istanbul':(41.0082,28.9784,'Стамбул'),
 'belgrade':(44.7866,20.4489,'Белград'),
 'tashkent':(41.2995,69.2401,'Ташкент'),
 'dilijan':(40.7407,44.8631,'Дилижан')
}

def get_json(url: str, params: dict) -> dict:
    request_url = url + '?' + urlencode(params)
    with urlopen(request_url,timeout=9,context=ssl.create_default_context(cafile=certifi.where())) as response:
        return json.load(response)

@app.get('/')
def index():
    return RedirectResponse(url='http://localhost:5188/',status_code=307)

@app.get('/api/health')
def health():
    return {'status':'ok','external_weather':'open-meteo','hotel_provider':'stayapi_if_configured','ai':'ollama_if_available'}

SEASON_GUIDANCE = {
 'kazan':'Континентальный климат: зимой морозно, летом бывает тепло.',
 'kaliningrad':'Морской климат: переменчивая погода и ветер в течение года.',
 'moscow':'Зима обычно холодная, лето умеренно тёплое.',
 'ossetia':'Погода в горах быстро меняется; условия зависят от высоты.',
 'armenia':'Лето в Ереване часто жаркое, зимой прохладнее; горные районы отличаются.',
 'uzbekistan':'Лето обычно очень жаркое, весна и осень часто комфортнее для прогулок.',
 'georgia':'В Тбилиси лето жаркое; в горах погода существенно отличается.',
 'karelia':'Влажный северный климат: прохладнее летом, зимой возможен снег.'
}
METRICS = ('temperature_2m_max','temperature_2m_min','precipitation_sum','snowfall_sum','wind_speed_10m_max')

@app.get('/api/weather/coordinates')
def weather_coordinates(lat:float,lon:float,departure:date|None=None):
    if not (-90<=lat<=90 and -180<=lon<=180):raise HTTPException(422,'Invalid coordinates')
    if departure is None:return {'mode':'seasonal_guidance','metrics':None,'explanation':'Без даты невозможно дать конкретный прогноз. Выберите дату для погоды в этой точке.','source':'Open-Meteo','date':None}
    today=datetime.now(timezone.utc).date()
    if departure<today:raise HTTPException(422,'Дата в прошлом')
    if (departure-today).days>15:return {'mode':'seasonal_guidance','metrics':None,'explanation':'До поездки больше 15 дней: точного прогноза ещё нет.','source':'Open-Meteo','date':departure.isoformat()}
    try:
        data=get_json('https://api.open-meteo.com/v1/forecast',{'latitude':lat,'longitude':lon,'daily':','.join(METRICS),'timezone':'auto','forecast_days':16})
        days=data['daily']['time'];idx=days.index(departure.isoformat())
        return {'mode':'forecast','metrics':{k:data['daily'][k][idx] for k in METRICS},'explanation':'Прогноз Open-Meteo','source':'Open-Meteo','date':departure.isoformat()}
    except Exception as exc:
        raise HTTPException(503,detail={'message':'Не удалось получить прогноз для выбранной точки','type':type(exc).__name__}) from exc

@app.get('/api/weather/{destination_id}')
def weather(destination_id: str, departure: date | None = None, month: int | None = None):
    if destination_id not in CITIES:
        raise HTTPException(404,'Unknown destination')
    if month is not None and not 1 <= month <= 12:
        raise HTTPException(422,'Month must be from 1 to 12')
    lat,lon,city=CITIES[destination_id]
    today=datetime.now(timezone.utc).date()
    # No specific date = useful season notes, not a misleading today's forecast.
    if departure is None:
        return {'destination_id':destination_id,'city':city,'date':None,'month':month,
                'mode':'seasonal_guidance','metrics':None,'verified_forecast':False,
                'source':'General seasonal guidance','source_url':None,
                'checked_at':datetime.now(timezone.utc).isoformat(),
                'explanation':SEASON_GUIDANCE[destination_id]+' Это качественная оценка, не прогноз.',
                'availability':'date_required_for_forecast'}
    days_ahead=(departure-today).days
    if days_ahead < 0:
        raise HTTPException(422,'Date is in the past')
    try:
        if days_ahead <= 15:
            data=get_json('https://api.open-meteo.com/v1/forecast',{
                'latitude':lat,'longitude':lon,'daily':','.join(METRICS),
                'timezone':'auto','forecast_days':16})
            daily=data.get('daily',{})
            dates=daily.get('time',[])
            if departure.isoformat() not in dates:
                raise ValueError('Forecast does not include requested date')
            idx=dates.index(departure.isoformat())
            metrics={k:daily[k][idx] for k in METRICS}
            mode='forecast'
            explanation='Прогноз на выбранную дату; условия могут измениться.'
        else:
            # A dated historical sample is never represented as a future forecast.
            samples=[]
            for year in range(today.year-3,today.year):
                sample_day=date(year,departure.month,min(departure.day,28))
                try:
                    data=get_json('https://archive-api.open-meteo.com/v1/archive',{
                        'latitude':lat,'longitude':lon,'start_date':sample_day.isoformat(),
                        'end_date':sample_day.isoformat(),'daily':','.join(METRICS),'timezone':'auto'})
                    sample={k:data['daily'][k][0] for k in METRICS}
                    if all(isinstance(v,(int,float)) for v in sample.values()):
                        samples.append(sample)
                except Exception:
                    continue
            if not samples:
                raise ValueError('Historical samples unavailable')
            metrics={k:round(sum(v[k] for v in samples)/len(samples),1) for k in METRICS}
            mode='historical_sample'
            explanation='Выборка аналогичного календарного дня за прошлые годы. Это НЕ прогноз.'
        return {'destination_id':destination_id,'city':city,'date':departure.isoformat(),
                'mode':mode,'metrics':metrics,'verified_forecast':mode=='forecast',
                'source':'Open-Meteo','source_url':'https://open-meteo.com/',
                'checked_at':datetime.now(timezone.utc).isoformat(),'explanation':explanation}
    except Exception as exc:
        # Do not pretend provider values were received. Surface diagnostic category.
        import logging
        logging.getLogger(__name__).warning('Weather provider error for %s (%s): %s',destination_id,type(exc).__name__,exc)
        raise HTTPException(503,detail={'message':'Open-Meteo не ответил корректными данными. Можно планировать поездку без прогноза.',
                                        'provider':'Open-Meteo','error_type':type(exc).__name__}) from exc

@app.get('/api/places/search')
def search_places(q: str):
    """Live city search via Open-Meteo geocoding, without pretending it is a POI database."""
    if not 2 <= len(q.strip()) <= 100:
        raise HTTPException(422,'Search query must contain 2-100 characters')
    try:
        data=get_json('https://geocoding-api.open-meteo.com/v1/search',
                      {'name':q.strip(),'count':8,'language':'ru','format':'json'})
        return {'source':'Open-Meteo Geocoding','results':[{
            'name':x.get('name'),'country':x.get('country'),
            'latitude':x.get('latitude'),'longitude':x.get('longitude')}
            for x in data.get('results',[])], 'live':True}
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning('Geocoding error: %s',exc)
        raise HTTPException(503,detail='Геокодинг временно недоступен') from exc

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

try:
    from .travel_sources import router as travel_router
except ImportError as exc:
    if 'no known parent package' not in str(exc):
        raise
    from travel_sources import router as travel_router
app.include_router(travel_router)
try:
    from .demo_catalog import router as demo_router
except ImportError as exc:
    if 'no known parent package' not in str(exc):raise
    from demo_catalog import router as demo_router
app.include_router(demo_router)

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

try:
    from .agent import router as agent_router
except ImportError as exc:
    if 'no known parent package' not in str(exc):raise
    from agent import router as agent_router
app.include_router(agent_router)

try:
    from .stayapi import router as hotels_router
except ImportError as exc:
    if 'no known parent package' not in str(exc):raise
    from stayapi import router as hotels_router
app.include_router(hotels_router)

@app.get('/api/agent/diagnostics')
def agent_diagnostics():
    """Check local Ollama without using a token-generating request or exposing secrets."""
    import os
    from urllib.request import Request, urlopen
    from urllib.error import URLError, HTTPError
    base=os.getenv('OLLAMA_BASE_URL','http://host.docker.internal:11434').rstrip('/')
    model=os.getenv('OLLAMA_MODEL','qwen3:4b')
    report={'ollama':{'configured_model':model,'connected':False,'model_installed':False},
            'stayapi':{'configured':bool(os.getenv('STAYAPI_KEY','').strip()),'live_search_tested':False}}
    try:
        with urlopen(Request(base+'/api/tags'),timeout=5) as response:
            tags=json.load(response)
        names=[m.get('name','') for m in tags.get('models',[])]
        report['ollama'].update({'connected':True,'model_installed':model in names,'installed_models':names[:12]})
    except Exception as exc:
        report['ollama']['error_type']=type(exc).__name__
        report['ollama']['hint']='Проверьте Ollama на Mac и OLLAMA_BASE_URL; сервис должен быть доступен контейнеру.'
    return report
