import React,{useEffect,useState} from 'react';
import {Button} from '@react-spectrum/s2';
import {api,type State,type Resident} from './api';
import {useI18n} from './i18n';

export function EngineControls({state,target,mode='geometry',onAction}:{state:State|null;target:'detect'|'segment';mode?:string;onAction:(route:string,data?:unknown)=>void}) {
  const {t}=useI18n();
  const current=state?.runtimes.residents?.[target];
  const [live,setLive]=useState<Resident|undefined>(current);
  const busy=state?.task.state==='running';
  useEffect(()=>setLive(current),[current]);
  useEffect(()=>{
    if(busy)return;
    let active=true,pending=false;
    const refresh=async()=>{if(pending||document.hidden)return;pending=true;try{const status=await api<Record<string,Resident>>('vision-status');if(active)setLive(status[target]);}catch{/* Keep the last state; action failures still reach the task log. */}finally{pending=false;}};
    refresh();const interval=setInterval(refresh,2000);return()=>{active=false;clearInterval(interval);};
  },[target,busy]);
  if(!state)return null;
  const name=target==='detect'?'YOLO':'SAM3';
  const resident=live;
  const weights=target==='detect'?state.config.yolo:state.config.sam;
  const matching=resident?.state==='ready'&&resident.weights===weights&&resident.requested===state.config.device&&(target==='detect'||resident.mode===mode);
  const loading=busy&&state.task.kind===`加载 ${name}`;
  const started=!!resident&&!['stopped','failed'].includes(resident.state);
  const status=loading||resident?.state==='loading'?t('正在加载…'):resident?.state==='stopping'?t('正在卸载…'):matching?t('就绪'):resident?.state==='failed'?t('加载失败'):started?t('配置已更改'):t('未加载');
  const title=matching?`${resident.gpu_name||resident.actual||t('尚未验证')} · ${resident.pinned?t('保持就绪，直到手动卸载或运行训练等任务。'):t('自动缓存，闲置 5 分钟后释放。')}`:target==='segment'?t(mode==='text'?'文字分割模式':'点／框分割模式'):weights.split(/[\\/]/).pop()||t('尚未选择权重');
  return <section className="engine-control" aria-label={`${name} ${t('模型控制')}`} title={title}>
    <span className="engine-control-status"><strong>{name}</strong><span className={matching?'model-ready':''}><i aria-hidden="true"/>{status}</span></span>
    <Button variant="secondary" isDisabled={!loading&&(busy||!started&&!weights)} onPress={()=>onAction(loading?'cancel':started?'vision-release':'vision-warmup',{target,mode})}>{loading?t('取消加载'):started?t('卸载模型'):resident?.state==='failed'?t('重新加载'):t('加载模型')}</Button>
  </section>;
}
