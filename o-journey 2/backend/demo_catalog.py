"""Synthetic test catalog for demo flows. All values fictitious: not actual offers."""
from fastapi import APIRouter
from pydantic import BaseModel,Field
router=APIRouter(prefix='/api/demo',tags=['synthetic demo'])

class QuoteIn(BaseModel):
    days:int=Field(ge=1,le=31)
    travelers:int=Field(ge=1,le=30)
    group_type:str='regular'
    destination:str=''
    budget_per_person:int|None=Field(default=None,ge=0)

@router.post('/packages')
def packages(req:QuoteIn):
    nights=max(0,req.days-1)
    # Intentionally fictional figures for full workflow demonstrations.
    choices=[('Эконом',2300,700,1400,650),
             ('Комфорт',5200,1500,2200,1350),
             ('Премиум',9800,2800,3600,2600)]
    result=[]
    for index,(label,night,transport,food,activity) in enumerate(choices):
        stay=night*nights
        journey=transport*req.travelers
        meals=food*req.days*req.travelers
        excursions=activity*req.travelers
        subtotal=stay+journey+meals+excursions
        # Only example eligibility discount; no actual supplier program was verified.
        demonstration_discount=round(excursions*0.1) if req.group_type in ('student','senior') else 0
        total=subtotal-demonstration_discount
        result.append({'id':f'demo_{index+1}','name':label,
          'status':'synthetic_unverified','hotel_type':['хостел / бюджетное жильё','отель среднего класса','отель повышенного комфорта'][index],
          'lodging':stay,'transport':journey,'food':meals,'activities':excursions,
          'illustrative_discount':demonstration_discount,
          'total':total,'per_person':round(total/req.travelers),
          'within_budget':req.budget_per_person is not None and total<=req.budget_per_person*req.travelers,
          'price_source':'FICTIONAL_TEST_VALUES','bookable':False})
    return {'status':'demo_only','destination':req.destination,'currency':'RUB',
      'packages':result,'notice':'ВСЕ цены и примерные льготы вымышлены только для демонстрации расчётов. Они не являются тарифами, акциями или предложениями Островка.'}
