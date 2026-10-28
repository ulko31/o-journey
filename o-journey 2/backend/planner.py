"""Structured trip planning core. Explicitly no invented live travel offers.

LLM is optional and restricted to parsing user intent. Rules validate costs and
real offer status separately. Destination suggestions are examples, not bookings.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal
import json, os, re
from urllib.request import Request, urlopen
from pydantic import BaseModel, Field

class Traveler(BaseModel):
    age: int | None = Field(default=None, ge=0, le=120)
    student: bool = False
    needs_accessibility: bool = False
    interests: list[str] = []

class PlanningRequest(BaseModel):
    message: str = Field(min_length=3, max_length=4000)
    origin: str | None = None
    departure_date: date | None = None
    days: int = Field(default=5, ge=1, le=31)
    budget_per_person: Decimal | None = Field(default=None, ge=0)
    currency: Literal['RUB'] = 'RUB'
    travelers: list[Traveler] = Field(default_factory=lambda: [Traveler()])
    previous_likes: list[str] = []
    previous_dislikes: list[str] = []
    novelty: Literal['similar','balanced','new'] = 'balanced'
    preferred_destinations: list[str] = []

DESTINATIONS = [
  {'id':'kazan','name':'Казань','tags':['еда','архитектура','история','город','культура'],'country':'Россия'},
  {'id':'kaliningrad','name':'Калининград','tags':['море','история','архитектура','природа','город'],'country':'Россия'},
  {'id':'moscow','name':'Москва','tags':['искусство','музеи','еда','город','архитектура'],'country':'Россия'},
  {'id':'ossetia','name':'Владикавказ','tags':['горы','природа','приключения','еда','история'],'country':'Россия'},
  {'id':'armenia','name':'Ереван','tags':['еда','архитектура','история','культура','город'],'country':'Армения'},
  {'id':'uzbekistan','name':'Самарканд','tags':['архитектура','культура','история','еда'],'country':'Узбекистан'},
  {'id':'georgia','name':'Тбилиси','tags':['еда','история','архитектура','город','культура'],'country':'Грузия'},
  {'id':'karelia','name':'Петрозаводск','tags':['природа','приключения','вода','история'],'country':'Россия'},
]
# Additional destinations broaden discovery. No unverified hotel/ticket claims.
EXTRA_DESTINATIONS = [
 {'id':'sochi','name':'Сочи','tags':['море','горы','природа','приключения'],'country':'Россия'},
 {'id':'dagestan','name':'Махачкала','tags':['море','горы','природа','еда','приключения'],'country':'Россия'},
 {'id':'murmansk','name':'Мурманск','tags':['природа','приключения','море'],'country':'Россия'},
 {'id':'novgorod','name':'Великий Новгород','tags':['история','культура','архитектура'],'country':'Россия'},
 {'id':'minsk','name':'Минск','tags':['город','культура','архитектура','еда'],'country':'Беларусь'},
 {'id':'almaty','name':'Алматы','tags':['горы','природа','город','еда','приключения'],'country':'Казахстан'},
 {'id':'bishkek','name':'Бишкек','tags':['горы','природа','еда','приключения'],'country':'Кыргызстан'},
 {'id':'baku','name':'Баку','tags':['море','еда','архитектура','культура'],'country':'Азербайджан'},
 {'id':'istanbul','name':'Стамбул','tags':['море','еда','архитектура','история','культура'],'country':'Турция'},
 {'id':'belgrade','name':'Белград','tags':['еда','город','культура','история'],'country':'Сербия'},
 {'id':'tashkent','name':'Ташкент','tags':['город','еда','культура','архитектура'],'country':'Узбекистан'},
 {'id':'dilijan','name':'Дилижан','tags':['горы','природа','история'],'country':'Армения'},
]
DESTINATIONS.extend(EXTRA_DESTINATIONS)
TOPICS = {
 'еда':['еда','кухн','гастрон','ресторан','кафе'],
 'искусство':['искусств','музе','галере','выстав'],
 'архитектура':['архитектур','здани','старый город'],
 'море':['море','пляж','побереж','океан'],
 'горы':['гор','альп','трекин','поход'],
 'природа':['природ','лес','озер','озёр','водопад'],
 'история':['истори','замк','крепост'],
 'город':['город','урбан','шопинг'],
 'приключения':['приключ','адреналин','активн','необычн'],
 'культура':['культур','местн','традиц','новую стран','новое'],
 'спокойствие':['спокойн','расслаб','релакс','тихий отдых'],
 'уединение':['уедин','без людей','без толп','тишин'],
}

def parse_interests(message: str) -> list[str]:
    m=message.casefold()
    return [tag for tag,patterns in TOPICS.items() if any(p in m for p in patterns)]

def extract_budget(message: str) -> Decimal | None:
    m = message.casefold().replace('\u202f',' ').replace('\xa0',' ')
    match = re.search(r'(?:до|бюджет|около|примерно)\s*(\d[\d\s]{2,8})\s*(тыс(?:яч)?|к|руб|₽)',m)
    if not match: return None
    value=Decimal(match.group(1).replace(' ',''))
    if match.group(2).startswith(('тыс','к')): value*=1000
    return value

def llm_extract(message: str) -> dict:
    """Local Ollama extraction. Never generate prices, hotels or availability."""
    base=os.getenv('OLLAMA_BASE_URL','http://host.docker.internal:11434').rstrip('/')
    model=os.getenv('OLLAMA_MODEL','qwen3:4b')
    prompt=('Верни ТОЛЬКО JSON с полями interests (массив из: еда, искусство, архитектура, море, горы, природа, история, город, приключения, культура, спокойствие, уединение), destinations (названия упомянутых направлений). '
            'Учитывай отрицания. Не придумывай цены, гостиницы и географию. Запрос: '+message)
    try:
      payload={'model':model,'stream':False,'format':'json','messages':[{'role':'user','content':prompt}],'options':{'temperature':0,'num_predict':260}}
      req=Request(base+'/api/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
      with urlopen(req,timeout=28) as resp:result=json.load(resp)
      parsed=json.loads(result['message']['content'])
      return {'enabled':True,'provider':'ollama','interests':parsed.get('interests',[]),'destinations':parsed.get('destinations',[])}
    except Exception:
      return {'enabled':False,'provider':'rules','message':'Ollama недоступна, используется поиск по интересам'}

def plan(req: PlanningRequest, use_llm: bool=False) -> dict:
    text=req.message.casefold()
    interests=parse_interests(req.message)
    # Crosswalk mood preferences onto travel features for the fixed catalog.
    if 'спокойствие' in interests or 'уединение' in interests:interests.append('природа')
    # Don't treat clearly negated topics as positive wishes.
    for tag,patterns in TOPICS.items():
      if any(re.search(r'(?:не\\s+хочу|без|никаких|не\\s+люблю)\\s+[^,.!?]{0,18}'+re.escape(p),text) for p in patterns):
        interests=[v for v in interests if v!=tag]
    for t in req.travelers:
      interests.extend(t.interests)
    llm=llm_extract(req.message) if use_llm else {'enabled':False,'message':'Локальный разбор; LLM не запрашивалась'}
    # LLM extracts intent; deterministic scoring and source validation remain server-side.
    if llm.get('enabled'):
      for item in llm.get('interests',[]):
        if isinstance(item,str):
          word=item.casefold().strip()
          if word in TOPICS and word not in interests:interests.append(word)
    interests=list(dict.fromkeys(interests))
    budget=req.budget_per_person or extract_budget(req.message)
    llm_countries=[str(x).casefold() for x in llm.get('destinations',[]) if isinstance(x,str)] if llm.get('enabled') else []
    named=[d for d in DESTINATIONS if d['name'].casefold() in text or d['country'].casefold() in text or d['name'].casefold() in [v.casefold() for v in req.preferred_destinations] or d['name'].casefold() in llm_countries or d['country'].casefold() in llm_countries]
    # No supplier tariff is known here. Budget cannot be used to rank destinations as affordable.
    # Typical international trips cannot be promised within an arbitrary low budget.
    scored=[]
    # Non-price travel friction tiers: these only diversify choices, NEVER promise affordability.
    nearby={'kazan','moscow','novgorod','karelia','kaliningrad','minsk'}
    premium_distance={'istanbul','belgrade','baku','tashkent','bishkek','almaty','armenia','georgia','dilijan'}
    low_budget=budget is not None and budget<=30000
    high_budget=budget is not None and budget>=120000
    for d in DESTINATIONS:
      overlap=len(set(d['tags']) & set(interests))
      history_like=any(d['name'].casefold() in v.casefold() for v in req.previous_likes)
      history_dislike=any(d['name'].casefold() in v.casefold() for v in req.previous_dislikes)
      score=overlap*3 + (8 if d in named else 0)
      if low_budget:
        score+=(5 if d['id'] in nearby else -3 if d['id'] in premium_distance else 0)
      elif high_budget:
        score+=(2 if d['id'] in premium_distance else 0)
      if req.novelty=='similar': score+=4 if history_like else 0
      elif req.novelty=='new': score-=5 if history_like else 0
      if history_dislike: score-=7
      scored.append((score,d))
    scored.sort(key=lambda x:(-x[0],x[1]['name']))
    if not interests and not named and budget is None:
      order=['kaliningrad','almaty','istanbul','karelia','minsk','dagestan','armenia']
      scored.sort(key=lambda x:order.index(x[1]['id']) if x[1]['id'] in order else 100)
    # Diversify countries when scores are similar.
    selected=[]
    for score,d in scored:
      if len(selected)>=3:break
      if not any(x['country']==d['country'] for x in selected) or len(scored)<4:
        selected.append(d)
    for score,d in scored:
      if len(selected)>=3:break
      if d not in selected:selected.append(d)
    scenarios=[]
    for index,d in enumerate(selected):
      scenarios.append({
       'id':f'scenario_{index+1}','destination':d,'rank_basis':{'interest_overlap':list(set(interests)&set(d['tags'])),'novelty':req.novelty,'budget_fit':'not_verified','indicative_cost_rub':None},
       'duration_days':req.days,'start_date':req.departure_date.isoformat() if req.departure_date else None,
       'lodging_options':[],'transport_options':[],'activities':[],
       'budget':{'per_person_limit':str(budget) if budget is not None else None,'total_price':None,'currency':'RUB','status':'not_quoted'},
       'availability':'not_checked','weather_status':'not_checked',
       'is_bookable':False,
       'required_actions':['Получить реальные предложения жилья с датами и составом гостей','Проверить транспорт и стыковки','Получить тарифы и часы работы экскурсий','Проверить погоду и сезонные ограничения']
      })
    needs=[]
    if not req.origin: needs.append('Город отправления для проверки транспорта')
    if not req.departure_date: needs.append('Даты поездки для проверки цен и прогноза')
    if budget is None: needs.append('Бюджет для проверки осуществимости')
    if any(t.student for t in req.travelers): needs.append('Подтверждение документов для студенческих льгот у поставщиков')
    return {'status':'discovery','intent':{'interests':interests,'origin':req.origin,'travelers':len(req.travelers),'student_travelers':sum(t.student for t in req.travelers),'budget_per_person':str(budget) if budget is not None else None,'novelty':req.novelty},'scenarios':scenarios,'needed_for_verification':needs,'llm':llm,'notice':'Направления — рекомендации по предпочтениям, а НЕ подтверждённые пакеты, цены или бронирования.'}

class Activity(BaseModel):
    id: str
    name: str
    start: datetime
    end: datetime
    source_url: str | None = None
    quoted_price: Decimal | None = Field(default=None, ge=0)
    tariff_status: Literal['verified','estimated','demo','unknown'] = 'unknown'

class ItineraryCheck(BaseModel):
    activities: list[Activity]
    transfer_minutes: int = Field(default=0,ge=0,le=1440)

def check_itinerary(req:ItineraryCheck)->dict:
    issues=[]
    activities=sorted(req.activities,key=lambda a:a.start)
    for i,a in enumerate(activities):
      if a.end<=a.start: issues.append({'item':a.id,'code':'invalid_interval'})
      if i and a.start < activities[i-1].end+timedelta(minutes=req.transfer_minutes):
        issues.append({'item':a.id,'code':'overlap_or_insufficient_transfer','previous':activities[i-1].id})
      if a.tariff_status=='verified' and not a.source_url:
        issues.append({'item':a.id,'code':'unsubstantiated_verified_tariff'})
    return {'valid':not issues,'issues':issues,'items_checked':len(activities),'note':'Проверены только переданные временные интервалы. Маршрутное время, часы работы и доступность поставщика требуют внешних проверок.'}
