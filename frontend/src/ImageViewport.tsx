import React, {useEffect, useRef, useState} from 'react';
import {ActionButton} from '@react-spectrum/s2';
import {useI18n} from './i18n';

type View = {zoom:number;x:number;y:number};
type Props = {imageKey:string;src:string;alt:string;width?:number;height?:number;
    children?:React.ReactNode;mode?:'pan'|'annotate';checker?:boolean};

/** Geometry and overlays share a single transform; pointer coordinates stay in image space. */
export function ImageViewport({imageKey,src,alt,width,height,children,mode='pan',checker=false}:Props) {
    const {t}=useI18n();
    const viewport=useRef<HTMLDivElement>(null);
    const [size,setSize]=useState({width:1,height:1});
    const [natural,setNatural]=useState({width:1,height:1});
    const [view,setView]=useState<View>({zoom:1,x:0,y:0});
    const viewRef=useRef(view);viewRef.current=view;
    const space=useRef(false);
    const drag=useRef<{id:number;clientX:number;clientY:number;x:number;y:number}|null>(null);
    const [dragging,setDragging]=useState(false);
    const reset=()=>setView({zoom:1,x:0,y:0});
    useEffect(()=>{reset();setNatural({width:1,height:1});drag.current=null;setDragging(false);},[imageKey]);
    useEffect(()=>{
        const node=viewport.current;if(!node)return;
        const observer=new ResizeObserver(([entry])=>{
            setSize({width:entry.contentRect.width,height:entry.contentRect.height});
        });observer.observe(node);
        const wheel=(event:WheelEvent)=>{
            event.preventDefault();
            const rect=node.getBoundingClientRect();
            const delta=event.deltaY*(event.deltaMode===1?16:event.deltaMode===2?rect.height:1);
            zoomAt(Math.exp(-Math.max(-500,Math.min(500,delta))*.002),
                   event.clientX-rect.left-rect.width/2,event.clientY-rect.top-rect.height/2);
        };
        node.addEventListener('wheel',wheel,{passive:false});
        return ()=>{observer.disconnect();node.removeEventListener('wheel',wheel);};
    },[]);
    function zoomAt(factor:number,anchorX=0,anchorY=0) {
        setView(previous=>{
            const zoom=Math.max(.1,Math.min(32,previous.zoom*factor)),ratio=zoom/previous.zoom;
            return {zoom,x:anchorX-(anchorX-previous.x)*ratio,y:anchorY-(anchorY-previous.y)*ratio};
        });
    }
    const imageWidth=width||natural.width,imageHeight=height||natural.height;
    const fit=Math.min(Math.max(1,size.width-32)/imageWidth,Math.max(1,size.height-32)/imageHeight,1);
    const displayWidth=imageWidth*fit*view.zoom,displayHeight=imageHeight*fit*view.zoom;
    const finish=(event:React.PointerEvent)=>{
        if(drag.current?.id!==event.pointerId)return;
        drag.current=null;setDragging(false);
        if(event.currentTarget.hasPointerCapture(event.pointerId))event.currentTarget.releasePointerCapture(event.pointerId);
        event.stopPropagation();
    };
    return <div className="image-viewer">
      <div ref={viewport} className={'image-viewport '+(mode==='pan'?'pan-mode ':'')+(dragging?'dragging ':'')+(checker?'checker':'')}
        role="region" aria-label={t('图片浏览画布')} tabIndex={0}
        onDragStart={event=>event.preventDefault()}
        onKeyDown={event=>{
            if(event.code==='Space'){space.current=true;event.preventDefault();}
            if(event.key==='0'){reset();event.preventDefault();}
            if(event.key==='+'||event.key==='='){zoomAt(1.25);event.preventDefault();}
            if(event.key==='-'){zoomAt(.8);event.preventDefault();}
        }} onKeyUp={event=>{if(event.code==='Space'){space.current=false;event.preventDefault();}}}
        onBlur={()=>{space.current=false;}}
        onPointerDownCapture={event=>{
            if(event.button!==0&&event.button!==1)return;
            viewport.current?.focus({preventScroll:true});
            const temporary=event.button===1||space.current;
            if(!temporary&&(mode==='annotate'||(event.target as Element).closest('[data-viewport-select]')))return;
            event.preventDefault();event.stopPropagation();viewport.current?.focus({preventScroll:true});
            const v=viewRef.current;
            drag.current={id:event.pointerId,clientX:event.clientX,clientY:event.clientY,x:v.x,y:v.y};
            setDragging(true);event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMoveCapture={event=>{
            const start=drag.current;if(!start||start.id!==event.pointerId)return;
            setView(v=>({...v,x:start.x+event.clientX-start.clientX,y:start.y+event.clientY-start.clientY}));
            event.stopPropagation();
        }} onPointerUpCapture={finish} onPointerCancelCapture={finish}
        onLostPointerCapture={()=>{drag.current=null;setDragging(false);}}>
        <div className="viewport-image" style={{width:displayWidth,height:displayHeight,
            '--image-scale':fit*view.zoom,
            left:size.width/2-displayWidth/2+view.x,top:size.height/2-displayHeight/2+view.y} as React.CSSProperties}>
          <img src={src} alt={alt} draggable={false} onLoad={event=>{
            setNatural({width:event.currentTarget.naturalWidth,height:event.currentTarget.naturalHeight});
          }}/>{children}
        </div>
      </div>
      <div className="image-viewer-tools"><div className="zoom-controls">
        <ActionButton aria-label={t('缩小图像')} isDisabled={view.zoom<=.1} onPress={()=>zoomAt(.8)}>−</ActionButton>
        <span className="zoom-value">{Math.round(fit*view.zoom*100)}%</span>
        <ActionButton aria-label={t('放大图像')} isDisabled={view.zoom>=32} onPress={()=>zoomAt(1.25)}>＋</ActionButton>
        <ActionButton onPress={reset}>{t('重置视角')}</ActionButton>
      </div><span className="viewer-help">{mode==='annotate'?t('滚轮缩放 · 空格或中键拖动平移'):t('滚轮缩放 · 拖动平移 · 0 重置')}</span></div>
    </div>;
}
