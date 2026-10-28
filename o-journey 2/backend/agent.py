"""O! Journey agent orchestration v1: requirements gate + grounded existing tools.

No hotel inventory or live price is invented. LLM may parse intent in planner,
but tools remain deterministic and explicitly identify missing provider access.
"""
from datetime import date,datetime,timezone
import re
from decimal import Decimal
from fastapi import APIRouter,HTTPException
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
    novelty:str='balanced'
    preferred_destinations:list[str]=Field(default_factory=list)

@router.post('/next')
def agent_next(req:AgentInput):
    """Ask the next meaningful question before ranking travel options."""
    missing=[]
    if not req.origin:missing.append({'field':'origin','question':'Из какого города будете отправляться?'})
    # Flexible travel dates are valid for destination discovery; live quotes require exact dates.
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
        travelers=[Traveler(student=(req.is_student or bool(re.search(r'\\bстудент(?:ка|ом|у)?\\b',req.message,re.I)))) for _ in range(req.travelers)],
        preferred_destinations=req.preferred_destinations,novelty=req.novelty if req.novelty in ('similar','balanced','new') else 'balanced')
    result=plan(request,use_llm=True)
    return {'stage':'discovery','result':result,
      'tool_status':{'llm_intent':result['llm'],'hotel_rates':'stayapi_available_if_configured',
        'flight_fares':'requires_verified_live_fare','visa':'needs_verified_official_country_rules'},
      'notice':'Это предварительный выбор направления. Реальные тарифы и визы ещё не проверены.'}

@router.post('/inspect')
def agent_inspect(req:AgentInput):
    """One call for user intent + real provider status. Hotel searches are deliberately
    separate to avoid consuming scarce credits for three speculative destinations."""
    partial=agent_next(req)
    if partial['stage']=='clarify':
        return partial
    result=partial['result']
    return {**result,'stage':'recommend','intent':result.get('intent'),
      'llm':result.get('llm'),
      'scenarios':result.get('scenarios',[]),
      'budget_verification':'not_possible_without_live_transport_and_lodging_quotes',
      'visa':{'status':'requires_official_verification','citizenship':req.citizenship},
      'discount':{'status':'requires_provider_eligibility_check',
                  'student_declared':bool(req.is_student or re.search(r'\\bстудент(?:ка|ом|у)?\\b',req.message,re.I)),'applied_amount':0},
      'next_step':'Pick a destination and dates, then call /api/hotels/search for actual rates.',
      'notice':'Destination ranking is preliminary; no hotel, transport or discount prices invented.'}

@router.get('/self-test')
def agent_self_test():
    try:
        from .planner import llm_extract
    except ImportError:
        from planner import llm_extract
    result=llm_extract('Мне нужны спокойный отдых и новая культура, но не экскурсии по памятникам.')
    return {'model_responded':bool(result.get('enabled')),'provider':result.get('provider'),
            'detected_interests':result.get('interests',[]),'error_type':result.get('error_type'),
            'diagnostic':result.get('diagnostic')}
