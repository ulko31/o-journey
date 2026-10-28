import React,{useMemo,useState,useEffect} from 'react';
import {feature} from 'topojson-client';
import {geoNaturalEarth1,geoPath,geoCentroid} from 'd3-geo';
import atlas from 'world-atlas/countries-110m.json';

const read=()=>{try{return JSON.parse(localStorage.getItem('oj_world_v1')||'[]')}catch{return []}};
const countries=feature(atlas,atlas.objects.countries).features;
const projection=geoNaturalEarth1().fitSize([1100,560],{type:'Sphere'});
const path=geoPath(projection);
const safe=s=>String(s||'').trim();
export default function WorldMap(){
 const [entries,setEntries]=useState(read),[focus,setFocus]=useState(null),[query,setQuery]=useState(''),[results,setResults]=useState([]),[picked,setPicked]=useState(null),[kind,setKind]=useState('city'),[reaction,setReaction]=useState('liked'),[note,setNote]=useState(''),[searching,setSearching]=useState(false),[error,setError]=useState('');
 const [countryNames,setCountryNames]=useState({}),[zoom,setZoom]=useState({x:550,y:280,k:1});
 useEffect(()=>{localStorage.setItem('oj_world_v1',JSON.stringify(entries))},[entries]);
 const country=useMemo(()=>countries.find(c=>String(c.id)===String(focus)),[focus]);
 const countryTitle=countryNames[focus]||country?.properties?.name||'Выбранная страна';
 const points=useMemo(()=>entries.map((p,i)=>({...p,idx:i,xy:projection([p.lon,p.lat])})).filter(p=>p.xy),[entries]);
 function selectCountry(item){const b=path.bounds(item);const w=b[1][0]-b[0][0],h=b[1][1]-b[0][1],scale=Math.min(5,Math.max(1.4,Math.min(880/Math.max(w,1),420/Math.max(h,1))));setFocus(item.id);setZoom({x:(b[0][0]+b[1][0])/2,y:(b[0][1]+b[1][1])/2,k:scale})}
 function reset(){setFocus(null);setZoom({x:550,y:280,k:1});setPicked(null)}
 async function find(){if(query.trim().length<2)return;setSearching(true);setError('');try{const r=await fetch('/api/destinations/search?q='+encodeURIComponent(query));const j=await r.json();if(!r.ok)throw Error(typeof j.detail==='string'?j.detail:'Поиск временно недоступен');setResults(j.results||[]);if(!j.results?.length)setError('Ничего не найдено: попробуйте название города')}catch(e){setError(e.message)}finally{setSearching(false)}}
 function choosePlace(p){setPicked(p);setResults([]);const xy=projection([p.lon,p.lat]);if(xy)setZoom({x:xy[0],y:xy[1],k:Math.max(3,zoom.k)});setCountryNames(names=>({...names,[focus]:p.country}))}
 function save(){if(!picked)return;setEntries(list=>[{...picked,kind,reaction,note:safe(note),createdAt:Date.now()+Math.random()},...list]);setPicked(null);setNote('');setQuery('')}
 const transformed='translate(550 280) scale('+zoom.k+') translate('+(-zoom.x)+' '+(-zoom.y)+')';
 const grouped=Object.groupBy?Object.groupBy(entries,e=>e.country||'Другие'):entries.reduce((a,e)=>{(a[e.country||'Другие']??=[]).push(e);return a},{});
 return <section className="atlas-page">
 <div className="atlas-top"><div><span className="eyebrow">МОЙ МИР</span><h2>Карта ваших впечатлений</h2><p>Выберите страну на карте, найдите город и запишите любимые места. Ваши оценки сохраняются для будущих поездок.</p></div><div className="atlas-stats"><strong>{new Set(entries.filter(e=>e.reaction==='liked').map(e=>e.country)).size}</strong><span>стран с отметками</span></div></div>
 <div className="atlas-shell"><div className="atlas-actions"><span>{focus?'Исследуем: '+countryTitle:'Нажмите на страну, чтобы приблизить'}</span><button onClick={reset} type="button">↶ Весь мир</button></div>
 <svg className="atlas-svg" viewBox="0 0 1100 560" role="img" aria-label="Интерактивная карта мира: нажмите на страну, чтобы приблизить"><rect width="1100" height="560" rx="14" fill="#f6f8fb"/>
 <g transform={transformed}>{countries.map(c=><path key={c.id} d={path(c)||''} className={'atlas-country '+(String(focus)===String(c.id)?'focused':'')} onClick={()=>selectCountry(c)} tabIndex={0} role="button" aria-label={'Выбрать страну '+(c.properties?.name||c.id)} onKeyDown={e=>{if(e.key==='Enter')selectCountry(c)}} />)}{points.map(p=><g key={p.createdAt} transform={'translate('+p.xy[0]+' '+p.xy[1]+')'}><circle r={Math.max(2.5,7/zoom.k)} fill={p.reaction==='liked'?'#d8f168':p.reaction==='disliked'?'#ecb5bb':'#fff'} stroke="#2145a9" strokeWidth={Math.max(1,2/zoom.k)}/></g>)}</g></svg>
 <div className="atlas-bottom">Контуры государств: Natural Earth / world-atlas · отметки сохраняются в этом браузере · карта без дорожных тайлов</div></div>
 <div className="atlas-content"><section className="surface atlas-add"><span className="eyebrow">ДОБАВИТЬ В МОЙ МИР</span><h3>Что вам запомнилось?</h3><label>Поиск города<div className="search-control"><input placeholder="Например, Рим или Киото" value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();find()}}}/><button className="primary" onClick={find} disabled={searching||query.trim().length<2}>{searching?'Поиск…':'Найти'}</button></div></label>{error&&<p className="error">{error}</p>}
 {results.map(p=><button className="atlas-result" key={p.id} onClick={()=>choosePlace(p)}>{p.name}, {p.country} <span>Выбрать →</span></button>)}
 {picked&&<div className="atlas-editor"><strong>{picked.name}, {picked.country}</strong><label>Уровень<select value={kind} onChange={e=>setKind(e.target.value)}><option value="city">Город</option><option value="place">Кафе, жильё или достопримечательность</option><option value="country">Страна</option></select></label><label>Впечатление<select value={reaction} onChange={e=>setReaction(e.target.value)}><option value="liked">Понравилось</option><option value="disliked">Не подошло</option><option value="saved">Хочу посетить</option></select></label><label>Название места и что вам понравилось<textarea rows={3} value={note} onChange={e=>setNote(e.target.value)} placeholder="Например: уютное кафе у площади, хорошее обслуживание"/></label><button className="primary" onClick={save}>Сохранить отметку</button></div>}</section>
 <section className="surface atlas-memory"><span className="eyebrow">МОИ ЗАПИСИ</span><h3>Страны → города → места</h3>{entries.length===0?<p className="sub">Здесь появятся ваши впечатления. Начните с поиска города.</p>:Object.entries(grouped).sort(([a],[b])=>a.localeCompare(b,'ru')).map(([nation,rows])=><div className="atlas-nation" key={nation}><h4>{nation} <small>· {rows.length}</small></h4>{rows.map(e=><div className="atlas-entry" key={e.createdAt}><button onClick={()=>{const xy=projection([e.lon,e.lat]);if(xy)setZoom({x:xy[0],y:xy[1],k:4})}}><b>{e.name}</b><span>{e.kind==='place'?'Место':e.kind==='country'?'Страна':'Город'} · {e.reaction==='liked'?'♥ понравилось':e.reaction==='disliked'?'− не подошло':'☆ хочу посетить'}</span><small>{e.note||'Без заметки'}</small></button><button aria-label="Удалить отметку" onClick={()=>setEntries(a=>a.filter(x=>x.createdAt!==e.createdAt))}>×</button></div>)}</div>)}</section></div>
 </section>
}
