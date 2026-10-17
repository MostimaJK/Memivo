import React from 'react';
import {ActionButton,Button} from '@react-spectrum/s2';
import {type State} from './api';
import {useI18n} from './i18n';

export function EngineControls({state,target,mode='geometry',onAction}:{state:State|null;target:'detect'|'segment';mode?:string;onAction:(route:string,data?:unknown)=>void}) {
  const {t}=useI18n();if(!state)return null;
  const name=target==='detect'?'YOLO':'SAM3';
  const resident=state.runtimes.residents?.[target];
  const weights=target==='detect'?state.config.yolo:state.config.sam;
  const matching=resident?.state==='ready'&&resident.weights===weights&&resident.requested===state.config.device&&(target==='detect'||resident.mode===mode);
  const busy=state.task.state==='running';
  const warming=busy&&state.task.kind===`预热 ${name}`;
  const started=resident&&!['stopped','failed'].includes(resident.state);
  return <section className="engine-control" aria-label={t('模型预热控制')+' '+name}>
    <div className="engine-control-status"><strong>{name}</strong><span>{warming?t('正在预热…'):resident?.state==='stopping'?t('正在关闭…'):resident?.state==='loading'?t('正在加载模型…'):matching?(resident.pinned?t('已预热 · 手动保持'):t('自动缓存')):started?t('配置已变化，需重新预热'):t('未启动')}</span></div>
    {target==='segment'&&<p className="microcopy">{mode==='text'?t('文字分割模式'):t('点／框分割模式')} · {weights.split(/[\\/]/).pop()||t('尚未选择权重')}</p>}
    {matching&&<p className="microcopy">{resident.gpu_name||resident.actual||t('尚未验证')}{typeof resident.allocated_mb==='number'?` · ${t('预热后张量显存约 {0} MB',[resident.allocated_mb.toFixed(0)])}`:''}</p>}
    <div className="engine-control-actions"><Button variant="secondary" isDisabled={busy||!weights||!!matching&&!!resident?.pinned} onPress={()=>onAction('vision-warmup',{target,mode})}>{t('预热模型')}</Button>
      {warming?<ActionButton onPress={()=>onAction('cancel')}>{t('取消预热')}</ActionButton>:<ActionButton isDisabled={busy||!started} onPress={()=>onAction('vision-release',{target})}>{t('关闭并释放')}</ActionButton>}</div>
    <p className="microcopy">{t('手动预热会保持就绪；可同时预热两种模型，显存不足时先关闭另一模型。训练等任务会自动释放。')}</p>
  </section>;
}
