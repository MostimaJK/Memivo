import React,{useEffect,useState} from 'react';
import {Meter} from '@react-spectrum/s2';
import {style} from '@react-spectrum/s2/style' with {type:'macro'};
import {api} from './api';
import {useI18n} from './i18n';

type Memory={state:string;name?:string;index?:number;used_mb?:number;total_mb?:number;percent?:number;sampled_at?:number;error?:string};
const full=style({width:'full'});
export function GpuMemory({enabled}:{enabled:boolean}) {
  const {t}=useI18n();const [memory,setMemory]=useState<Memory|null>(null);
  useEffect(()=>{
    if(!enabled){setMemory(null);return;}
    let active=true,pending=false;
    const refresh=async()=>{
      if(pending||document.hidden)return;
      pending=true;
      try {const sample=await api<Memory>('gpu-memory');if(active)setMemory(sample);}
      catch {if(active)setMemory({state:'unavailable'});}
      finally {pending=false;}
    };
    refresh();const interval=setInterval(refresh,2000);
    document.addEventListener('visibilitychange',refresh);
    return()=>{active=false;clearInterval(interval);document.removeEventListener('visibilitychange',refresh);};
  },[enabled]);
  if(!enabled||memory?.state==='no_gpu')return null;
  const ready=memory?.state==='ready'&&typeof memory.used_mb==='number'&&typeof memory.total_mb==='number'&&typeof memory.percent==='number'&&!!memory.sampled_at&&Date.now()/1000-memory.sampled_at<=6;
  const percent=ready?memory.percent!:0;
  const value=ready?`${(memory.used_mb!/1024).toFixed(1)} / ${(memory.total_mb!/1024).toFixed(1)} GiB · ${percent.toFixed(0)}%`:memory?.state==='loading'||!memory?t('读取中…'):t('暂不可用');
  return <div className="gpu-memory" aria-live="off" title={`${memory?.name?`GPU ${memory.index??0} · ${memory.name}\n`:''}${t('整张显卡的显存占用，包含桌面和其他程序；每约 2 秒刷新，不代表 Memivo 独占。')}${memory?.error?`\n${memory.error}`:''}`}>
    <div className="gpu-memory-header"><span>{t('显卡总显存')}</span><span>{value}</span></div>
    {ready?<Meter aria-label={t('显卡总显存')} value={percent} valueLabel={`${t('显卡总显存')} ${value}`} size="S" variant={percent>=95?'negative':percent>=80?'notice':'informative'} styles={full}/>:<span className="gpu-memory-unavailable" aria-hidden="true"/>}
  </div>;
}
