import React,{useEffect,useMemo,useState} from 'react';

const fmt=n=>new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(Number(n)||0);

export default function TripTools({cityId,city,chosen,days,travelers,budgetLimit,customDestination,onRouteChange}){
 const [lodging,setLodging]=useState(null),[lodgingError,setLodgingError]=useState(''),[loadingHotels,setLoadingHotels]=useState(false),[hotelId,setHotelId]=useState('');
 const [road,setRoad]=useState(null),[roadError,setRoadError]=useState(''),[loadingRoad,setLoadingRoad]=useState(false);
 const [costs,setCosts]=useState({night:'',transport:'',meals:'',activities:'',extra:''});
 const hotel=lodging?.lodgings?.find(h=>h.id===hotelId);
 const nights=Math.max(0,Number(days||1)-1);
 const people=Math.max(1,Number(travelers||1));
 const num=k=>Math.max(0,Number(costs[k])||0);
 const totals=useMemo(()=>{
   const hotel=nights*num('night'),road=num('transport')*people,food=num('meals')*people*Math.max(1,Number(days)||1),activities=num('activities')*people,other=num('extra');
   return {hotel,road,food,activities,other,total:hotel+road+food+activities+other};
 },[costs,nights,people,days]);
 const remaining=(Number(budgetLimit)||0)*people-totals.total;
 const filled=Object.values(costs).every(v=>v!==''&&Number(v)>=0);
 useEffect(()=>{setLodging(null);setHotelId('');setLodgingError('');setRoad(null);setRoadError('');onRouteChange(null)},[cityId]);
 async function loadHotels(){setLoadingHotels(true);setLodgingError('');try{const res=await fetch('/api/lodging/'+cityId+(customDestination?'?lat='+customDestination.lat+'&lon='+customDestination.lon+'&city_name='+encodeURIComponent(customDestination.name):''));const j=await res.json();if(!res.ok)throw Error(typeof j.detail==='object'?j.detail.message:j.detail||'Ошибка каталога');setLodging(j)}catch(e){setLodgingError(e.message)}finally{setLoadingHotels(false)}}
 async function buildRoad(){setLoadingRoad(true);setRoadError('');setRoad(null);onRouteChange(null);const pts=chosen.map(i=>city.places[i]).filter(Boolean);if(pts.length<2){setRoadError('Выберите хотя бы две остановки');setLoadingRoad(false);return}
  try{const res=await fetch('/api/route',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({points:pts.map(p=>({title:p[0],lat:p[1],lon:p[2]}))})});const j=await res.json();if(!res.ok)throw Error(typeof j.detail==='object'?j.detail.message:j.detail||'Маршрут недоступен');setRoad(j);onRouteChange(j.geometry)}catch(e){setRoadError(e.message)}finally{setLoadingRoad(false)}
 }
 const change=(key,value)=>setCosts(v=>({...v,[key]:value}));
 return <section className="builder-tools">
 <div className="builder-heading"><div><span className="eyebrow">СОБИРАЕМ ПОЕЗДКУ</span><h2>Ваш план в деталях</h2><p>Три понятных шага: жильё → дорога → бюджет</p></div><span className="tool-label">Данные с источниками</span></div>
 <div className="tools-grid">
  <article className="surface tool-card"><div className="tool-no">01</div><h3>Где остановимся?</h3><p className="sub">Загрузим настоящие названия отелей, хостелов и гостевых домов из OpenStreetMap.</p>
  <button type="button" className="primary" onClick={loadHotels} disabled={loadingHotels}>{loadingHotels?'Ищем объекты…':'Найти варианты жилья'}</button>
  {lodgingError&&<div className="error" role="alert">{lodgingError}</div>}
  {lodging&&<><div className="source-note">Источник: OpenStreetMap · {lodging.lodgings.length} объектов · цены и наличие не проверены</div><div className="hotel-list">{lodging.lodgings.length===0?<p>Объекты в выбранном радиусе не найдены.</p>:lodging.lodgings.slice(0,10).map(h=><div className={'hotel-row '+(hotelId===h.id?'on':'')} key={h.id}><div><strong>{h.name}</strong><small>{({hotel:'Отель',hostel:'Хостел',guest_house:'Гостевой дом',apartment:'Апартаменты',motel:'Мотель'})[h.kind]||'Размещение'}</small><a href={h.source_url} target="_blank" rel="noopener noreferrer">Карточка на OSM</a></div><button type="button" className="ghost" onClick={()=>setHotelId(h.id)}>{hotelId===h.id?'✓ Выбрано':'Выбрать'}</button></div>)}</div></>}
  {hotel&&<p className="selected-hotel">Выбран объект: <b>{hotel.name}</b>. Номер и тариф ещё нужно проверить у поставщика.</p>}
  </article>
  <article className="surface tool-card"><div className="tool-no">02</div><h3>Сколько между точками?</h3><p className="sub">Реальный автомобильный маршрут по дорогам OpenStreetMap через OSRM, а не пунктир по прямой.</p>
  <button type="button" className="primary" onClick={buildRoad} disabled={loadingRoad||chosen.length<2}>{loadingRoad?'Строим маршрут…':'Рассчитать дорогу'}</button>
  {roadError&&<div className="error" role="alert">{roadError}</div>}
  {road&&<><div className="route-numbers"><strong>{road.distance_km} км</strong><strong>≈ {road.duration_minutes} мин</strong></div><div className="source-note">Автомобильный маршрут · OSRM demo · без учёта пробок и остановок. Для пересечения границ нужны отдельные проверки.</div>{road.legs?.map((leg,i)=><div className="road-leg" key={i}>{i+1} → {i+2}: {leg.distance_km} км · ~{leg.duration_minutes} мин</div>)}</>}
  </article>
  <article className="surface tool-card budget-card"><div className="tool-no">03</div><h3>Сколько получится?</h3><p className="sub">Введите ваши ориентировочные суммы. Это расчёт бюджета, а не найденные тарифы.</p>
  <div className="budget-fields"><label>Жильё за ночь, ₽ за всё размещение<input type="number" min="0" placeholder="Введите цену" value={costs.night} onChange={e=>change('night',e.target.value)}/></label><label>Транспорт, ₽ на человека за поездку<input type="number" min="0" placeholder="Введите сумму" value={costs.transport} onChange={e=>change('transport',e.target.value)}/></label><label>Питание, ₽ на человека в день<input type="number" min="0" placeholder="Введите сумму" value={costs.meals} onChange={e=>change('meals',e.target.value)}/></label><label>Активности, ₽ на человека за поездку<input type="number" min="0" placeholder="Введите сумму" value={costs.activities} onChange={e=>change('activities',e.target.value)}/></label><label>Запас и прочее, ₽ на группу<input type="number" min="0" placeholder="Введите сумму" value={costs.extra} onChange={e=>change('extra',e.target.value)}/></label></div>
  <div className="budget-summary"><div><span>Жильё · {nights} ночей</span><b>{fmt(totals.hotel)} ₽</b></div><div><span>Дорога</span><b>{fmt(totals.road)} ₽</b></div><div><span>Питание</span><b>{fmt(totals.food)} ₽</b></div><div><span>Активности</span><b>{fmt(totals.activities)} ₽</b></div><div><span>Прочее</span><b>{fmt(totals.other)} ₽</b></div><div className="budget-total"><span>Итого за {people} чел.</span><b>{fmt(totals.total)} ₽</b></div><div><span>На человека</span><b>{fmt(totals.total/people)} ₽</b></div></div>
  {!filled?<p className="source-note">Заполните все поля для оценки бюджета. Пустое значение пока считается нулём и не означает бесплатную услугу.</p>:Number(budgetLimit)>0?<div className={'budget-remaining '+(remaining<0?'over':'')}>{remaining>=0?'Остаток бюджета: ':'Превышение бюджета: '}{fmt(Math.abs(remaining))} ₽ на группу</div>:<p className="source-note">Лимит бюджета не задан.</p>}
  </article>
 </div></section>
}
