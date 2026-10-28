"""O! Journey agent orchestration v1: requirements gate + grounded existing tools.

No hotel inventory or live price is invented. LLM may parse intent in planner,
but tools remain deterministic and explicitly identify missing provider access.
"""
from datetime import date,datetime,timezone
from decimal import Decimal
from fastapi import APIRouter
from pydantic import BaseModel,Field
try:
    from .planner import PlanningRequest,Traveler,plan
except ImportError:
    from planner import PlanningRequest,Traveler,plan

router=APIRouter(prefix='/api/agent',tags=['agent'])

class AgentInput(BaseModel):
    message:str=Field(min_length=3,max_length=4000)
    origin:str|None=None
    departure_date:date|None=None
    days:int|None=Field(default=None,ge=1,le=31)
    budget_per_person:Decimal|None=Field(default=None,ge=0)
    travelers:int|None=Field(default=None,ge=1,le=30)
    citizenship:str|None=None
    residency:str|None=None
    is_student:bool=False
    preferred_destinations:list[str]=Field(default_factory=list)

@router.post('/next')
def agent_next(req:AgentInput):
    """Ask the next meaningful question before ranking travel options."""
    missing=[]
    if not req.origin:missing.append({'field':'origin','question':'Из какого города будете отправляться?'})
    if req.departure_date is None:missing.append({'field':'departure_date','question':'На какую дату планируете выезд? Можно выбрать приблизительную дату.'})
    if req.days is None:missing.append({'field':'days','question':'На сколько дней планируете поездку?'})
    if req.travelers is None:missing.append({'field':'travelers','question':'Сколько человек едет?'})
    if req.budget_per_person is None:missing.append({'field':'budget_per_person','question':'Какой максимальный бюджет на одного человека, в рублях?'})
    if not req.citizenship:missing.append({'field':'citizenship','question':'Какое гражданство у путешественника? Это нужно только для проверки визовых условий.'})
    if missing:
        return {'stage':'clarify','question':missing[0]['question'],'required_fields':missing,
                'facts':req.model_dump(mode='json'),
                'notice':'Пока недостаточно условий для проверки бюджета, визы и доступности.'}
    request=PlanningRequest(message=req.message,origin=req.origin,departure_date=req.departure_date,
        days=req.days,budget_per_person=req.budget_per_person,
        travelers=[Traveler(student=req.is_student) for _ in range(req.travelers)],
        preferred_destinations=req.preferred_destinations)
    result=plan(request,use_llm=True)
    return {'stage':'discovery','result':result,
      'tool_status':{'llm_intent':result['llm'],'hotel_rates':'stayapi_available_if_configured',
        'flight_fares':'requires_travelpayouts_token','visa':'needs_verified_official_country_rules'},
      'notice':'Это предварительный выбор направления. Реальные тарифы и визы ещё не проверены.'}
