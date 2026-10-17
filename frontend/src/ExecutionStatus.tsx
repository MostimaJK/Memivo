import React from 'react';
import {type State} from './api';
import {useI18n} from './i18n';

export function ExecutionStatus({state}:{state:State|null}) {
  const {t}=useI18n();if(!state)return null;
  const execution=state.runtimes.execution;
  const actual=execution?.actual||'unknown';
  const label=actual.startsWith('cuda')?'GPU · CUDA':actual==='cpu'?'CPU':actual==='cache'?t('特征缓存'):execution?.evidence==='failed'?t('执行失败，未确认设备'):t('尚未验证');
  const operations:Record<string,string>={warmup_detect:'预热 YOLO',warmup_segment:'预热 SAM3',detect:'YOLO 检测',segment:'SAM3 分割',recognize:'人物识别',train:'模型训练',evaluate:'模型评估'};
  return <section className="execution-status" aria-label={t('执行设备状态')} role="status">
    <span>{t('全局设置')}：{state.config.device==='cuda'?'GPU · CUDA':'CPU'}</span>
    <strong className={actual.startsWith('cuda')?'verified-gpu':''}>{t('最近实际执行')}：{label}</strong>
    {execution&&<><span>{t(operations[execution.operation]||execution.operation)} · {execution.time}</span>
      {execution.gpu_name&&<span>{execution.gpu_name}</span>}
      {execution.requested!==state.config.device&&<span>{t('该任务请求')}：{execution.requested}</span>}
      {execution.evidence==='onnx_node_profile'&&<span>{t('已核对 ONNX 算子执行记录')}{execution.cpu_nodes?` · ${t('含 CPU 算子')}`:''}</span>}
      {execution.evidence==='tensor_device'&&<span>{t('已核对模型张量设备')}</span>}
      {execution.evidence==='pending'&&state.task.state==='running'&&<span>{t('等待执行证据，设置不代表实际设备。')}</span>}
    </>}
  </section>;
}
