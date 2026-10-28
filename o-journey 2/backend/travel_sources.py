"""Live public map providers. Discover accommodation names, not rooms or tariffs."""
from __future__ import annotations
from datetime import datetime, timezone
from functools import lru_cache
import json, logging, ssl, os
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import certifi
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router=APIRouter(prefix="/api")
LOG=logging.getLogger(__name__)
CITIES={
 'kazan':(55.7961,49.1064,'Казань'),'kaliningrad':(54.7104,20.4522,'Калининград'),
 'moscow':(55.7558,37.6173,'Москва'),'ossetia':(43.0259,44.6818,'Владикавказ'),
 'armenia':(40.1792,44.4991,'Ереван'),'uzbekistan':(39.6542,66.9597,'Самарканд'),
 'georgia':(41.7151,44.8271,'Тбилиси'),'karelia':(61.7849,34.3469,'Петрозаводск'),
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
def fetch(url, timeout=12):
    request=Request(url,headers={'User-Agent':'OJourneyHackathonDemo/0.8 (public OSM data; educational demo)','Accept':'application/json'})
    with urlopen(request,timeout=timeout,context=ssl.create_default_context(cafile=certifi.where())) as resp:
        return json.load(resp)

@router.get('/destinations/search')
def destination_search(q: str):
    if not 2 <= len(q.strip()) <= 100: raise HTTPException(422,'Введите название города (2–100 символов)')
    try:
        data=fetch('https://geocoding-api.open-meteo.com/v1/search?'+urlencode({'name':q.strip(),'count':10,'language':'ru','format':'json'}))
        return {'source':'Open-Meteo Geocoding','results':[{'id':'geo-'+str(x.get('id')),'name':x.get('name'),'country':x.get('country'),
                'lat':x.get('latitude'),'lon':x.get('longitude'),'admin1':x.get('admin1')} for x in data.get('results',[])
                if isinstance(x.get('latitude'),(int,float)) and isinstance(x.get('longitude'),(int,float))]}
    except Exception as exc:
        LOG.warning('Destination search failed: %s',exc)
        raise HTTPException(503,detail='Поиск городов временно недоступен') from exc


AIRPORT_CODES={'Санкт-Петербург':'LED','Москва':'MOW','Казань':'KZN','Ереван':'EVN','Баку':'BAK','Тбилиси':'TBS','Стамбул':'IST','Алматы':'ALA','Минск':'MSQ','Токио':'TYO','Киото':'KIX','Осака':'KIX','Париж':'PAR','Лондон':'LON','Рим':'ROM','Берлин':'BER','Дубай':'DXB','Бангкок':'BKK','Пекин':'BJS','Шанхай':'SHA','Сеул':'SEL','Белград':'BEG','Калининград':'KGD','Сочи':'AER','Махачкала':'MCX','Мурманск':'MMK','Ташкент':'TAS','Самарканд':'SKD','Бишкек':'FRU','Нью-Йорк':'NYC'}
@router.get('/flight-prices')
def flight_prices(origin:str,destination:str):
    """Travelpayouts cached observed flight prices; not bookable live quotations."""
    token=os.getenv('TRAVELPAYOUTS_TOKEN','')
    if not token:
        return {'status':'not_configured','source':'Travelpayouts','offers':[],'notice':'Для реальных наблюдаемых цен авиабилетов требуется TRAVELPAYOUTS_TOKEN. Подключение доступно, ключ не задан.'}
    src=AIRPORT_CODES.get(origin.strip(),origin.strip().upper() if len(origin.strip())==3 else None)
    dst=AIRPORT_CODES.get(destination.strip(),destination.strip().upper() if len(destination.strip())==3 else None)
    if not src or not dst:
        return {'status':'airport_unmapped','offers':[],'source':'Travelpayouts','notice':'Для этого города ещё не найден код аэропорта IATA. Не подставляем чужой город.'}
    try:
        url='https://api.travelpayouts.com/v2/prices/latest?'+urlencode({'origin':src,'destination':dst,'currency':'RUB','period_type':'year','limit':5,'sorting':'price'})
        req=Request(url,headers={'X-Access-Token':token,'Accept':'application/json','User-Agent':'OJourneyHackathonDemo/0.9'})
        with urlopen(req,timeout=10,context=ssl.create_default_context(cafile=certifi.where())) as response:
            data=json.load(response)
        quotes=[{'price_rub':v.get('value'),'depart_date':v.get('depart_date'),'return_date':v.get('return_date'),'found_at':v.get('found_at'),'expires_at':v.get('expires_at'),'origin':src,'destination':dst,'status':'cached_observation_not_bookable'} for v in data.get('data',[]) if isinstance(v,dict) and isinstance(v.get('value'),(int,float))]
        return {'status':'ok' if quotes else 'no_results','source':'Travelpayouts cached flight data','offers':quotes,'notice':'Цены из кэша прошлых поисков. НЕ подтверждают наличие билета, цену на ваши даты или стоимость поездки туда-обратно.'}
    except Exception as exc:
        LOG.warning('Travelpayouts: %s %s',type(exc).__name__,exc)
        return {'status':'provider_unavailable','source':'Travelpayouts','offers':[],'notice':'Источник цен сейчас недоступен. Не показываем неподтверждённые тарифы.'}

@router.get('/places/nearby')
def nearby_places(lat:float,lon:float,limit:int=25):
    if not (-90<=lat<=90 and -180<=lon<=180):raise HTTPException(422,'Invalid coordinates')
    limit=max(3,min(limit,45))
    query=f'[out:json][timeout:12];(nwr["tourism"~"^(attraction|museum|gallery|viewpoint|artwork)$"]["name"](around:8500,{lat},{lon});nwr["leisure"~"^(park|garden)$"]["name"](around:8500,{lat},{lon});nwr["historic"]["name"](around:8500,{lat},{lon}););out center {limit*3};'
    for base in ('https://overpass.kumi.systems/api/interpreter','https://overpass-api.de/api/interpreter'):
        try:
            response=fetch(base+'?'+urlencode({'data':query}),timeout=10)
            places=[];seen=set()
            for e in response.get('elements',[]):
                tags=e.get('tags') or {};point=e.get('center') or e
                name=tags.get('name')
                if not name or 'lat' not in point or 'lon' not in point:continue
                key=(name.lower(),round(point['lat'],3),round(point['lon'],3))
                if key in seen:continue
                seen.add(key)
                places.append({'id':str(e['type'])+'-'+str(e['id']),'name':name,'lat':point['lat'],'lon':point['lon'],
                               'type':tags.get('tourism') or tags.get('historic') or tags.get('leisure') or 'place',
                               'source_url':'https://www.openstreetmap.org/'+str(e['type'])+'/'+str(e['id'])})
                if len(places)>=limit:break
            return {'places':places,'provider_status':'ok','source':'OpenStreetMap'}
        except Exception as exc:
            LOG.warning('POI provider unavailable: %s %s',type(exc).__name__,exc)
    return {'places':[],'provider_status':'unavailable','source':'OpenStreetMap','notice':'Каталог мест временно недоступен; данные не выдуманы.'}

@router.get('/lodging/{destination_id}')
def lodging(destination_id:str, lat:float|None=None, lon:float|None=None, city_name:str|None=None):
    """OSM lodging catalog results only; prices, availability, photos are NOT checked."""
    if lat is not None and lon is not None:
        if not (-90<=lat<=90 and -180<=lon<=180):raise HTTPException(422,'Invalid coordinates')
        city=(city_name or destination_id)[:100]
    elif destination_id in CITIES:
        lat,lon,city=CITIES[destination_id]
    else: raise HTTPException(422,'Передайте lat и lon для произвольного города')
    query=f'[out:json][timeout:14];(nwr["tourism"~"^(hotel|hostel|guest_house|motel|apartment)$"]["name"](around:4500,{lat},{lon}););out center 35;'
    data=None
    failures=[]
    # Public Overpass mirrors are rate-limited; try independent endpoints.
    for base in ('https://overpass-api.de/api/interpreter','https://overpass.kumi.systems/api/interpreter','https://overpass.nchc.org.tw/api/interpreter'):
        try:
            data=fetch(base+'?'+urlencode({'data':query}),timeout=9)
            if isinstance(data.get('elements'),list):break
            data=None
        except Exception as exc:
            failures.append(type(exc).__name__)
            LOG.warning('Overpass mirror failure: %s %s',base,exc)
    if data is None:
        # Graceful empty state: not a fabricated hotel list.
        return {'destination_id':destination_id,'city':city,'source':'OpenStreetMap/Overpass',
                'checked_at':datetime.now(timezone.utc).isoformat(),
                'notice':'Каталог сейчас недоступен (публичные серверы перегружены). Объекты и цены не выдумываем.',
                'provider_status':'unavailable','lodgings':[]}
    items=[]
    seen=set()
    for x in data.get('elements',[]):
        tag=x.get('tags',{}); name=tag.get('name'); coords=x.get('center',x)
        if not name or coords.get('lat') is None or coords.get('lon') is None:continue
        key=(name.casefold(),round(coords['lat'],3),round(coords['lon'],3))
        if key in seen:continue
        seen.add(key)
        items.append({'id':f"{x.get('type','node')}-{x.get('id')}",'name':name,
             'kind':tag.get('tourism'),'lat':coords['lat'],'lon':coords['lon'],
             'website':tag.get('website') or tag.get('contact:website'),
             'source_url':f"https://www.openstreetmap.org/{x.get('type','node')}/{x.get('id')}",
             'price':None,'currency':None,'availability':'not_checked','source_type':'catalog_not_offer'})
    return {'destination_id':destination_id,'city':city,'source':'OpenStreetMap/Overpass',
            'checked_at':datetime.now(timezone.utc).isoformat(),
            'notice':'Это реальные названия из открытого каталога, но НЕ проверенные номера, тарифы или наличие.',
            'provider_status':'ok','lodgings':items[:18]}

class Waypoint(BaseModel):
    lat:float=Field(ge=-90,le=90)
    lon:float=Field(ge=-180,le=180)
    title:str=Field(default='',max_length=200)
class RouteRequest(BaseModel):
    points:list[Waypoint]=Field(min_length=2,max_length=12)

@router.post('/route')
def route(data:RouteRequest):
    """Real road routing using OSRM DEMO SERVER; no live traffic, not a navigation guarantee."""
    coords=';'.join(f'{p.lon:.6f},{p.lat:.6f}' for p in data.points)
    url='https://router.project-osrm.org/route/v1/driving/'+coords+'?'+urlencode({'overview':'full','geometries':'geojson','steps':'false'})
    try:
        result=fetch(url,timeout=12)
        if result.get('code')!='Ok' or not result.get('routes'):
            raise ValueError('No route returned')
        route=result['routes'][0]
        return {'status':'ok','provider':'OSRM demo / OpenStreetMap','mode':'driving',
            'distance_km':round(route['distance']/1000,1),
            'duration_minutes':round(route['duration']/60),
            'legs':[{'distance_km':round(leg['distance']/1000,1),'duration_minutes':round(leg['duration']/60)} for leg in route.get('legs',[])],
            'geometry':route.get('geometry',{}).get('coordinates',[]),
            'notice':'Расчёт по автомобильной сети без пробок и ограничений на даты. Время приблизительное; demo API может быть недоступен.'}
    except Exception as exc:
        LOG.warning('OSRM routing failed: %s: %s',type(exc).__name__,exc)
        raise HTTPException(503,detail={'message':'Сейчас не удалось построить дорожный маршрут. Линия по прямой не заменяет настоящий маршрут.','provider':'OSRM demo'}) from exc
