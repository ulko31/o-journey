"""Assemble a dated lodging shortlist with price provenance.

Only explicit calls to this endpoint consume StayAPI credits. Never construct
a complete trip price when flights or activities are unknown.
"""
from datetime import date,datetime,timezone
from decimal import Decimal,InvalidOperation
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
try:
    from .stayapi import hotels as stay_search
except ImportError:
    from stayapi import hotels as stay_search

router=APIRouter(prefix='/api/agent',tags=['agent'])

class AssembleInput(BaseModel):
    city:str=Field(min_length=2,max_length=120)
    checkin:date
    checkout:date
    travelers:int=Field(default=2,ge=1,le=30)
    rooms:int=Field(default=1,ge=1,le=10)
    currency:str=Field(default='USD',pattern=r'^[A-Z]{3}$')
    budget_per_person:Decimal|None=Field(default=None,ge=0)
    # The user must supply a comparable budget currency; never silently convert RUB to USD.
    budget_currency:str=Field(default='RUB',pattern=r'^[A-Z]{3}$')

def numeric(value):
    try:
        result=Decimal(str(value))
        if not result.is_finite() or result < 0:return None
        return result
    except (TypeError,ValueError,InvalidOperation):return None

def assemble(req:AssembleInput, search=stay_search):
    if req.checkout<=req.checkin:raise HTTPException(422,'Дата выезда должна быть позже заезда')
    if req.checkin<date.today():raise HTTPException(422,'Дата заезда уже прошла')
    # A provider search happens once, only after explicit user action.
    provider=search(city=req.city,checkin=req.checkin,checkout=req.checkout,
        adults=req.travelers,rooms=req.rooms,currency=req.currency)
    offers=[]
    for h in provider.get('hotels',[]):
        if h.get('is_sold_out'):continue
        price=h.get('price') or {}
        amount=numeric(price.get('amount'))
        if amount is None:continue
        actual_currency=price.get('currency') or req.currency
        if actual_currency!=req.currency:continue
        offers.append({'id':h.get('id'),'name':h.get('name'),
          'room_name':h.get('room_name'),'address':h.get('address'),
          'price':str(amount),'currency':actual_currency,
          'price_basis':'provider_reported_unverified_total_basis',
          'per_person_if_total_stay':str(round(amount/req.travelers,2)),
          'price_display':price.get('display'),'source':'StayAPI',
          'checked_at':provider.get('checked_at'),
          'availability':'provider_observation_not_prebooked'})
    offers.sort(key=lambda o:Decimal(o['price']))
    comparable=req.budget_per_person is not None and req.budget_currency==req.currency
    for o in offers:
        o['budget_fit_if_total_stay']=(Decimal(o['price'])<=req.budget_per_person*req.travelers) if comparable else None
    return {'stage':'lodging_results','city':req.city,'dates':{'checkin':req.checkin.isoformat(),'checkout':req.checkout.isoformat()},
      'travelers':req.travelers,'source':'StayAPI','checked_at':provider.get('checked_at'),
      'lodging_options':offers[:10],'budget_comparable':comparable,
      'known_trip_total':None,'full_trip_budget_verified':False,
      'missing_costs':['междугородний транспорт','местный транспорт','питание','экскурсии','возможные сборы отеля'],
      'warnings':['Тариф может включать оплату за ночь либо за весь период: подтверждение состава цены требуется перед итоговым расчётом.',
                  'Никаких студенческих и других скидок без подтверждения тарифа.'],
      'message':'Не найдено тарифов по выбранным условиям.' if not offers else 'Подбор отелей получен. Общая цена поездки пока не подтверждена.'}

@router.post('/assemble')
def assemble_endpoint(req:AssembleInput):
    return assemble(req)
