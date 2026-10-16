import React,{useRef,useState} from 'react';
import {type Annotation} from './api';
type Props={src:string;width:number;height:number;labels:Annotation[];selected:string;mode:string;classId:number|null;disabled:boolean;
  onSelect:(id:string)=>void;onChange:(labels:Annotation[])=>void;names:Record<number,string>};
export function AnnotationCanvas({src,width,height,labels,selected,mode,classId,disabled,onSelect,onChange,names}:Props){
  const [draft,setDraft]=useState<number[]|null>(null),[polygon,setPolygon]=useState<number[][]>([]);
  const move=useRef<{id:string;index:number;start:number[];original:Annotation}|null>(null);
  const pointer=(event:React.PointerEvent<SVGSVGElement>)=>{const r=event.currentTarget.getBoundingClientRect();return [Math.max(0,Math.min(width,(event.clientX-r.left)/r.width*width)),Math.max(0,Math.min(height,(event.clientY-r.top)/r.height*height))];};
  const finishPolygon=()=>{if(!disabled&&polygon.length>=3&&classId!==null){onChange([...labels,{id:crypto.randomUUID(),type:'polygon',points:polygon,class_id:classId,source:'manual'}]);setPolygon([]);}};
  const startMove=(event:React.PointerEvent,id:string,index:number)=>{if(disabled||event.button!==0||mode!=='select')return;event.currentTarget.closest<HTMLElement>('.annotation-image')?.focus();event.stopPropagation();onSelect(id);const root=event.currentTarget.closest('svg')!;const r=root.getBoundingClientRect();const start=[(event.clientX-r.left)/r.width*width,(event.clientY-r.top)/r.height*height];move.current={id,index,start,original:structuredClone(labels.find(a=>a.id===id)!)};root.setPointerCapture(event.pointerId);};
  return <div className="annotation-image" tabIndex={0} onKeyDown={event=>{if(event.key==='Escape'){setPolygon([]);setDraft(null);move.current=null;}if(event.key==='Enter')finishPolygon();if(!disabled&&(event.key==='Delete'||event.key==='Backspace')&&selected){event.preventDefault();onChange(labels.filter(a=>a.id!==selected));onSelect('');}}}>
    <img src={src} alt="" draggable={false}/><svg viewBox={`0 0 ${width} ${height}`} className="annotation-overlay"
      onPointerDown={event=>{if(disabled||event.button!==0)return;event.currentTarget.closest<HTMLElement>('.annotation-image')?.focus();const point=pointer(event);if(mode==='box'&&classId!==null){setDraft([...point,...point]);event.currentTarget.setPointerCapture(event.pointerId);}else if(mode==='polygon'&&classId!==null)setPolygon(p=>[...p,point]);else if(mode==='select')onSelect('');}}
      onContextMenu={event=>{event.preventDefault();if(!disabled){setPolygon(p=>p.slice(0,-1));setDraft(null);move.current=null;}}}
      onDoubleClick={()=>{if(mode==='polygon')finishPolygon();}}
      onPointerMove={event=>{const point=pointer(event);if(draft)setDraft([draft[0],draft[1],...point]);if(move.current){const drag=move.current;const original=drag.original;let updated:Annotation=structuredClone(original);
        if(original.type==='box'){let [a,b,c,d]=original.bbox!;if(drag.index<0){const dx=Math.max(-a,Math.min(width-c,point[0]-drag.start[0])),dy=Math.max(-b,Math.min(height-d,point[1]-drag.start[1]));updated.bbox=[a+dx,b+dy,c+dx,d+dy];}else{if(drag.index===0||drag.index===3)a=Math.min(c-1,point[0]);else c=Math.max(a+1,point[0]);if(drag.index<2)b=Math.min(d-1,point[1]);else d=Math.max(b+1,point[1]);updated.bbox=[Math.max(0,a),Math.max(0,b),Math.min(width,c),Math.min(height,d)];}}
        else if(drag.index>=0)updated.points=original.points!.map((p,i)=>i===drag.index?point:p);
        else{const xs=original.points!.map(p=>p[0]),ys=original.points!.map(p=>p[1]);const dx=Math.max(-Math.min(...xs),Math.min(width-Math.max(...xs),point[0]-drag.start[0])),dy=Math.max(-Math.min(...ys),Math.min(height-Math.max(...ys),point[1]-drag.start[1]));updated.points=original.points!.map(p=>[p[0]+dx,p[1]+dy]);}
        onChange(labels.map(a=>a.id===drag.id?updated:a));}}}
      onPointerUp={event=>{if(event.button!==0){setDraft(null);move.current=null;return;}if(draft&&classId!==null){let [a,b,c,d]=draft;const box=[Math.min(a,c),Math.min(b,d),Math.max(a,c),Math.max(b,d)];if(box[2]-box[0]>=2&&box[3]-box[1]>=2){const id=crypto.randomUUID();onChange([...labels,{id,type:'box',bbox:box,class_id:classId,source:'manual'}]);onSelect(id);}setDraft(null);}move.current=null;}}
      onPointerCancel={()=>{move.current=null;setDraft(null);}}>
      {labels.map(label=>{const chosen=label.id===selected;const points=label.type==='box'?[[label.bbox![0],label.bbox![1]],[label.bbox![2],label.bbox![1]],[label.bbox![2],label.bbox![3]],[label.bbox![0],label.bbox![3]]]:label.points!;return <g key={label.id} onContextMenu={event=>{event.preventDefault();event.stopPropagation();if(!disabled&&polygon.length){setPolygon(p=>p.slice(0,-1));setDraft(null);move.current=null;}else if(!disabled){onChange(labels.filter(a=>a.id!==label.id));onSelect('');}}} onPointerDown={event=>startMove(event,label.id,-1)}>
        <polygon points={points.map(p=>p.join(',')).join(' ')} fill={chosen?'#ffd58033':'#8bc9ff22'} stroke={chosen?'#ffd580':'#8bc9ff'} strokeWidth="2" vectorEffect="non-scaling-stroke"/>
        <text x={points[0][0]} y={Math.max(height/35,points[0][1]-height/100)} fontSize={Math.max(10,width/65)} fill="white" stroke="#202124" strokeWidth="1" paintOrder="stroke">{names[label.class_id]||label.class_id}</text>
        {chosen&&mode==='select'&&points.map((point,index)=><circle key={index} cx={point[0]} cy={point[1]} r={Math.max(3,width/150)} fill="white" stroke="#3866e9" onPointerDown={event=>startMove(event,label.id,index)}/>)}
      </g>;})}
      {draft&&<rect x={Math.min(draft[0],draft[2])} y={Math.min(draft[1],draft[3])} width={Math.abs(draft[2]-draft[0])} height={Math.abs(draft[3]-draft[1])} fill="#8bc9ff22" stroke="#8bc9ff" strokeWidth="2" vectorEffect="non-scaling-stroke"/>}
      {polygon.length>0&&<polyline points={polygon.map(p=>p.join(',')).join(' ')} fill="#8bc9ff22" stroke="#8bc9ff" strokeWidth="2" vectorEffect="non-scaling-stroke"/>}
    </svg>
  </div>;
}
