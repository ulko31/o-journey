"""Live public map providers. Discover accommodation names, not rooms or tariffs."""
from __future__ import annotations
from datetime import datetime, timezone
from functools import lru_cache
import json, logging, ssl
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
 'georgia':(41.7151,44.8271,'Тбилиси'),'karelia':(61.7849,34.3469,'Петрозаводск')
}
def fetch(url, timeout=12):
    request=Request(url,headers={'User-Agent':'OJourneyHackathonDemo/0.8 (public OSM data; educational demo)','Accept':'application/json'})
    with urlopen(request,timeout=timeout,context=ssl.create_default_context(cafile=certifi.where())) as resp:
        return json.load(resp)

@router.get('/lodging/{destination_id}')
def lodging(destination_id:str):
    """OSM lodging catalog results only; prices, availability, photos are NOT checked."""
    if destination_id not in CITIES: raise HTTPException(404,'Unknown destination')
    lat,lon,city=CITIES[destination_id]
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
