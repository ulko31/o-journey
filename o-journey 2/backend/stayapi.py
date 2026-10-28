"""StayAPI dated hotel search. Uses only server-side secret; never returns it."""
import json
import os
from datetime import date,datetime,timezone
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from fastapi import APIRouter,HTTPException,Query
router=APIRouter(prefix="/api/hotels",tags=["hotels"])
BASE="https://api.stayapi.com/v1/booking/"
def request(path,params):
    key=os.getenv("STAYAPI_KEY","").strip()
    if not key:raise HTTPException(503,"STAYAPI_KEY not configured")
    url=BASE+path+"?"+urlencode(params)
    req=Request(url,headers={"x-api-key":key,"Accept":"application/json"})
    try:
        with urlopen(req,timeout=25) as response:
            return json.load(response)
    except HTTPError as e:
        # Do not expose upstream body, potentially revealing credentials or details.
        if e.code==429:raise HTTPException(429,"StayAPI quota or rate limit reached")
        raise HTTPException(502,f"StayAPI request failed (HTTP {e.code})")
    except (URLError,TimeoutError,ValueError) as e:
        raise HTTPException(503,f"StayAPI unavailable ({type(e).__name__})")
@router.get("/search")
def hotels(city:str=Query(min_length=2,max_length=120),checkin:date=None,checkout:date=None,
           adults:int=Query(default=2,ge=1,le=30),rooms:int=Query(default=1,ge=1,le=10),
           currency:str=Query(default="USD",pattern="^[A-Z]{3}$")):
    if not checkin or not checkout or checkout<=checkin or checkin<date.today():
        raise HTTPException(422,"Provide future checkin and later checkout dates")
    destination=request("destinations/lookup",{"query":city})
    destination_data=destination.get("data") or {}
    matches=destination_data.get("destinations") or destination_data.get("results") or destination_data.get("suggestions") or []
    chosen=matches[0] if matches and isinstance(matches[0],dict) else destination_data
    if not isinstance(chosen,dict):chosen={}
    dest_id=destination.get("dest_id") or chosen.get("dest_id")
    if not dest_id:
        return {"hotels":[],"message":"Destination not found","source":"StayAPI"}
    payload=request("search",{"dest_id":dest_id,"dest_type":destination.get("dest_type") or chosen.get("dest_type") or "CITY",
        "checkin":checkin.isoformat(),"checkout":checkout.isoformat(),"adults":adults,
        "rooms":rooms,"currency":currency,"rows_per_page":10})
    data=payload.get("data") or {}
    hotels=[]
    for h in data.get("hotels",[]):
        price=h.get("price") or {}
        hotels.append({"id":h.get("hotel_id"),"name":h.get("name"),"address":h.get("address"),
            "latitude":h.get("latitude"),"longitude":h.get("longitude"),
            "image_url":h.get("image_url"),"rating":h.get("rating"),
            "price": {"amount":price.get("amount"),"currency":price.get("currency"),
                "display":price.get("display"),"labels":price.get("labels",[]) } if price else None,
            "room_name":h.get("room_name"),"free_cancellation":h.get("free_cancellation"),
            "is_sold_out":h.get("is_sold_out")})
    return {"hotels":hotels,"city":city,"checkin":checkin,"checkout":checkout,
        "adults":adults,"rooms":rooms,"source":"StayAPI / Booking.com public quotes",
        "checked_at":payload.get("retrieved_at") or (data.get("metadata") or {}).get("scraped_at") or datetime.now(timezone.utc).isoformat(),
        "notice":"Displayed price may exclude taxes or charges; final availability and total must be rechecked.",
        "search_url":data.get("search_url") or payload.get("url"),"pagination":data.get("pagination")}
