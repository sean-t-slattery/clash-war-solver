import {useRef,useState} from 'react';
import type {Action,Frame,Heat,Layout,Structure} from './types';
import {title} from './api';

const project=(x:number,y:number):[number,number]=>[480+(x-y)*8.5,55+(x+y)*4.25];
const color:Record<string,string>={town_hall:'#e2b35e',cannon:'#809cb4',archer_tower:'#b69acd',mortar:'#82b2a4',air_defense:'#d18e8d',storage:'#b9c4aa',wall:'#78847c',unknown:'#d47c49'};
const glyph:Record<string,string>={town_hall:'TH',cannon:'C',archer_tower:'AT',mortar:'M',air_defense:'AD',storage:'S',unknown:'?'};
export default function VillageMap({layout,selected,onSelect,onTile,actions=[],frame,heat=[],layers,calibrating,onAnchor,paths=[]}:{layout:Layout;selected?:string;onSelect?:(s:Structure)=>void;onTile?:(x:number,y:number)=>void;actions?:Action[];frame?:Frame;heat?:Heat[];layers:{grid:boolean;traps:boolean;actions:boolean;image:boolean};calibrating?:boolean;onAnchor?:(x:number,y:number)=>void;paths?:[number,number][][]}){
  const svg=useRef<SVGSVGElement>(null);const [zoom,setZoom]=useState(1);
  const polygon=(x:number,y:number,w:number,h:number)=>[[x,y],[x+w,y],[x+w,y+h],[x,y+h]].map(([a,b])=>project(a,b).join(',')).join(' ');
  function point(event:React.MouseEvent){const p=svg.current!.createSVGPoint();p.x=event.clientX;p.y=event.clientY;return p.matrixTransform(svg.current!.getScreenCTM()!.inverse());}
  function click(event:React.MouseEvent){const p=point(event);if(calibrating){onAnchor?.(p.x,p.y);return;} const dx=(p.x-480)/8.5,dy=(p.y-55)/4.25;onTile?.(Math.floor((dy+dx)/2),Math.floor((dy-dx)/2));}
  let imageTransform:string|undefined;
  if(layout.anchors){const [o,a,b]=layout.anchors;const det=(a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0]);if(Math.abs(det)>1){const ix=(b[1]-o[1])/det*44,iy=-(b[0]-o[0])/det*44,jx=-(a[1]-o[1])/det*44,jy=(a[0]-o[0])/det*44; const A=8.5*(ix-jx),C=8.5*(iy-jy),B=4.25*(ix+jx),D=4.25*(iy+jy); imageTransform=`matrix(${A} ${B} ${C} ${D} ${480-A*o[0]-C*o[1]} ${55-B*o[0]-D*o[1]})`;}}
  return <div className="map-shell"><div className="map-coordinate">44 × 44 <span>HOME VILLAGE GRID</span></div><div className="zoom-control"><label>Zoom <input aria-label="Map zoom" type="range" min="0.8" max="1.8" step=".1" value={zoom} onChange={e=>setZoom(+e.target.value)}/></label></div>
    <svg ref={svg} className="village-map" viewBox={`${480-480/zoom} ${235-235/zoom} ${960/zoom} ${470/zoom}`} onClick={click} role="img" aria-label="Interactive isometric village layout">
      <defs><filter id="shadow" x="-40%" y="-80%" width="180%" height="260%"><feDropShadow dx="0" dy="4" stdDeviation="2" floodColor="#0c211b" floodOpacity=".25"/></filter></defs>
      <polygon points={polygon(-3,-3,50,50)} fill="#c4d1bb" stroke="#a7b6a2"/>
      <polygon points={polygon(0,0,44,44)} fill="#d8e0cf" stroke="#aebda6"/>
      {layers.image&&layout.asset_id&&imageTransform&&<image href={`/api/assets/${layout.asset_id}`} width="4096" height="4096" transform={imageTransform} opacity=".6"/>}
      {layers.grid&&Array.from({length:45},(_,i)=><g key={i} stroke="#9aac96" strokeWidth={i%5===0?.7:.3} opacity=".6"><line x1={project(i,0)[0]} y1={project(i,0)[1]} x2={project(i,44)[0]} y2={project(i,44)[1]}/><line x1={project(0,i)[0]} y1={project(0,i)[1]} x2={project(44,i)[0]} y2={project(44,i)[1]}/></g>)}
      {layers.traps&&heat.filter(h=>h.weight>.65).map(h=><polygon key={`${h.x}-${h.y}`} points={polygon(h.x,h.y,1,1)} fill="#e67f47" opacity={(h.weight-.5)*.35}/>)}
      {[...layout.structures].sort((a,b)=>a.x+a.y-b.x-b.y).map(s=>{const [cx,cy]=project(s.x+s.width/2,s.y+s.height/2);const destroyed=frame?.destroyed.includes(s.id);return <g key={s.id} tabIndex={0} role="button" aria-label={`${title(s.type)} at ${s.x}, ${s.y}`} onKeyDown={e=>{if(e.key==='Enter')onSelect?.(s);}} onClick={e=>{if(!calibrating&&onSelect){e.stopPropagation();onSelect(s);}}} opacity={destroyed?.2:1} style={{cursor:onSelect?'pointer':'default'}}>
        <title>{title(s.type)} · Level {s.level} · ({s.x}, {s.y}){s.reviewed?'':' · review needed'}</title>
        <polygon filter={s.type!=='wall'?'url(#shadow)':undefined} points={polygon(s.x,s.y,s.width,s.height)} fill={color[s.type]||'#869f9f'} stroke={selected===s.id?'#132b2a':s.reviewed?'#f5f7ee':'#c25f27'} strokeWidth={selected===s.id?2:1} strokeDasharray={s.reviewed?undefined:'3 2'}/>
        {s.width>1&&<text x={cx} y={cy+3} textAnchor="middle" fontSize={s.type==='town_hall'?14:10} fontWeight="700" fill="#283e3a" pointerEvents="none">{glyph[s.type]||s.type.slice(0,2).toUpperCase()}</text>}
      </g>;})}
      {layers.traps&&layout.traps.map(t=>{const p=project(t.x+.5,t.y+.5);return <g key={t.id}><circle cx={p[0]} cy={p[1]} r="5" fill={t.status==='confirmed'?'#ba5143':'#dd9c53'} stroke="white"/><title>{t.status}: {t.evidence}</title></g>;})}
      {layers.actions&&paths.map((p,i)=><polyline key={i} points={p.map(([x,y])=>project(x,y).join(',')).join(' ')} fill="none" stroke="#2b7773" strokeWidth="1.6" opacity=".35" strokeDasharray="4 3"/>)}
      {frame?.spells.map((s,i)=>{const p=project(s.x,s.y);return <ellipse key={i} cx={p[0]} cy={p[1]} rx={s.radius*12} ry={s.radius*6} fill={s.type==='heal'?'#c8e27b':s.type==='freeze'?'#a0d7ef':'#c5a0dc'} opacity=".5"/>;})}
      {frame?.units.map(u=>{const p=project(u.x,u.y);return <circle key={u.id} cx={p[0]} cy={p[1]} r="2.5" fill={u.type==='barbarian_king'?'#754aa3':'#1e6865'} stroke="white" strokeWidth=".6"><title>{title(u.type)} · {Math.round(u.hp*100)}% HP</title></circle>;})}
      {layers.actions&&[...actions].sort((a,b)=>a.time-b.time).map((a,i)=>{const p=project(a.x,a.y);return <g key={i}><circle cx={p[0]} cy={p[1]} r="9" fill={a.kind==='spell'?'#ae7839':'#183e3d'} stroke="#fcf8e9" strokeWidth="2"/><text x={p[0]} y={p[1]+3.5} fontSize="10" textAnchor="middle" fill="white" fontWeight="700">{i+1}</text><title>{a.time.toFixed(1)}s: {a.kind} {a.quantity} {title(a.unit)}</title></g>;})}
      <text x="480" y="22" textAnchor="middle" className="map-direction">NORTH ENTRY</text><text x="890" y="245" textAnchor="middle" className="map-direction">EAST</text><text x="480" y="460" textAnchor="middle" className="map-direction">SOUTH ENTRY</text><text x="70" y="245" textAnchor="middle" className="map-direction">WEST</text>
    </svg><div className="map-legend"><span><i style={{background:'#e2b35e'}}/>Town Hall</span><span><i style={{background:'#809cb4'}}/>Defense</span><span><i style={{background:'#b9c4aa'}}/>Resource</span><span><i style={{background:'#dd9c53'}}/>Trap assumption</span></div></div>;
}
