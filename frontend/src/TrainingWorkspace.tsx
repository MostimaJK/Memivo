import React,{useEffect,useState,useRef} from 'react';
import {ActionButton,Button,TextField,Picker,PickerItem,NumberField,DialogContainer,Dialog,Heading,Content,ButtonGroup,StatusLight} from '@react-spectrum/s2';
import {style} from '@react-spectrum/s2/style' with {type:'macro'};
import {api,type State} from './api';
import {useI18n} from './i18n';
const full=style({width:'full'});
type Props={state:State;busy:boolean;onAction:(route:string,data?:unknown,message?:string)=>Promise<any>;onFeatures:()=>void;onDataset:()=>void};
export function TrainingWorkspace({state,busy,onAction,onFeatures,onDataset}:Props){
  const {t}=useI18n();const dataset=state.datasets.active;
  const [version,setVersion]=useState(''),[weights,setWeights]=useState(''),[epochs,setEpochs]=useState(50),[imgsz,setImgsz]=useState(640),[batch,setBatch]=useState(4),[device,setDevice]=useState(state.config.device);
  const [runId,setRunId]=useState(''),[metric,setMetric]=useState(''),[error,setError]=useState(''),[pending,setPending]=useState(false),[exporting,setExporting]=useState(false),[path,setPath]=useState('');
  const deviceEdited=useRef(false);
  useEffect(()=>{if(!deviceEdited.current)setDevice(state.config.device);},[state.config.device]);
  const previousCount=useRef(state.training.length);
  const engine=state.runtimes.engines.find(e=>e.id==='vision');const run=state.training.find(r=>r.id===runId);
  const stateNames:Record<string,string>={completed:t('已完成'),running:t('训练中'),failed:t('失败'),cancelled:t('已停止'),interrupted:t('已中断'),evaluating:t('评估中'),pending:t('准备中')};
  const disabled=busy||pending;
  useEffect(()=>{setVersion(state.datasets.versions[0]?.id||'');},[dataset?.id,state.datasets.versions.length]);
  useEffect(()=>{if((!runId||state.training.length>previousCount.current)&&state.training.length)setRunId(state.training[0].id);previousCount.current=state.training.length;},[state.training.length,runId]);
  const metrics=run?.metrics||[],keys=Object.keys(metrics[metrics.length-1]||{}).filter(k=>k!=='epoch');
  useEffect(()=>{if(keys.length&&!keys.includes(metric))setMetric(keys.find(k=>k.includes('mAP50('))||keys[0]);},[keys.join('|')]);
  const values=metrics.map(m=>m[metric]).filter(Number.isFinite),low=Math.min(0,...values),high=Math.max(1,...values);
  const act=async(route:string,data:unknown)=>{setPending(true);setError('');try{return await onAction(route,data,route==='training-apply'?t('模型已应用，可前往检测与计数。'):'');}catch(e){setError((e as Error).message);throw e;}finally{setPending(false);}};
  const trigger=(route:string,data:unknown)=>{void act(route,data).catch(()=>{});};
  const choose=async(kind:string)=>{try{const result=await api('pick',{kind});if(result.paths[0])kind==='folder'?setPath(result.paths[0]):setWeights(result.paths[0]);}catch(e){setError((e as Error).message);}};
  return <div className="learning-page"><div className="training-layout"><section className="training-setup"><div className="feature-heading"><h2>{t('训练配置')}</h2><StatusLight variant={engine?.available?'positive':'neutral'}>{engine?.available?t('引擎已就绪'):t('需要视觉引擎')}</StatusLight></div>
    {!engine?.available&&<Button variant="secondary" onPress={onFeatures}>{t('前往功能中心')}</Button>}
    <p className="muted">{dataset?dataset.name:t('请先创建数据集。')}</p><Picker label={t('固定数据集版本')} value={version||null} onChange={key=>setVersion(String(key))} styles={full} isDisabled={disabled}>{state.datasets.versions.map(v=><PickerItem id={v.id} key={v.id}>{`${v.id.slice(0,8)} · train ${v.counts.train} / val ${v.counts.val} / test ${v.counts.test}`}</PickerItem>)}</Picker>
    <ActionButton onPress={onDataset}>{t('返回标注与数据集')}</ActionButton>
    <div className="path-field" title={weights}><Picker label={t('初始模型权重 .pt')} value={weights||null} onChange={key=>setWeights(String(key))} styles={full} isDisabled={disabled}>{state.models.items.yolo.map(m=><PickerItem id={m.path} key={m.path}>{m.relative}</PickerItem>)}{weights&&!state.models.items.yolo.some(m=>m.path===weights)&&<PickerItem id={weights}>{weights.split(/[\\/]/).pop()||weights}</PickerItem>}</Picker><ActionButton aria-label={t('选择初始模型权重')} isDisabled={disabled} onPress={()=>void choose('file')}>{t('选择')}</ActionButton></div>
    <div className="training-fields"><NumberField label={t('训练轮数')} value={epochs} onChange={setEpochs} minValue={1} maxValue={1000} isDisabled={disabled}/><NumberField label={t('图像尺寸')} value={imgsz} onChange={setImgsz} minValue={320} maxValue={2048} step={32} isDisabled={disabled}/><NumberField label={t('批量大小')} value={batch} onChange={setBatch} minValue={1} maxValue={64} isDisabled={disabled}/><Picker label={t('执行设备')} value={device} onChange={key=>{deviceEdited.current=true;setDevice(String(key));}} isDisabled={disabled}><PickerItem id="cpu">CPU</PickerItem><PickerItem id="cuda">NVIDIA CUDA</PickerItem></Picker></div>
    <Button variant="accent" isDisabled={disabled||!engine?.available||!version||!weights.trim()} onPress={()=>{setRunId('');trigger('training-start',{dataset:dataset?.id,version,weights,epochs,imgsz,batch,device});}}>{t('开始训练')}</Button>
  </section><section className="training-results"><div className="feature-heading"><h2>{t('实验与模型')}</h2>{busy&&<Button variant="secondary" onPress={()=>trigger('cancel',{})}>{t('停止任务')}</Button>}</div>
    <Picker label={t('训练记录')} value={runId||null} onChange={key=>setRunId(String(key))} styles={full}>{state.training.map(r=><PickerItem id={r.id} key={r.id}>{r.id.slice(0,8)} · {stateNames[r.state]||r.state} · {r.created.slice(0,19)}</PickerItem>)}</Picker>
    {run?<><div className="run-facts"><span>{t('状态')}: {stateNames[run.state]||run.state}</span><span>{t('数据版本')}: {run.version.slice(0,8)}</span><span>{run.task} · {run.options.device} · {run.options.epochs} epochs</span></div>
      {run.error&&<div className="dialog-error" role="alert">{t(run.error)}</div>}
      <div className="run-actions"><Button variant="secondary" isDisabled={disabled||!run.can_resume} onPress={()=>trigger('training-start',{resume:run.id})}>{t('从断点恢复')}</Button><Button variant="secondary" isDisabled={disabled||!run.best} onPress={()=>trigger('training-evaluate',{run:run.id})}>{t('评估独立测试集')}</Button><Button variant="accent" isDisabled={disabled||!run.best} onPress={()=>trigger('training-apply',{run:run.id})}>{t('用于检测与计数')}</Button><ActionButton isDisabled={disabled||!run.best} onPress={()=>{setPath('');setExporting(true);}}>{t('导出模型与记录')}</ActionButton></div>
      {!!keys.length&&<Picker label={t('训练指标')} value={metric||null} onChange={key=>setMetric(String(key))}>{keys.map(key=><PickerItem id={key} key={key}>{key}</PickerItem>)}</Picker>}
      {values.length>0?<div className="metric-chart"><svg viewBox="0 0 600 180" role="img" aria-label={t('训练指标曲线')}><line x1="35" y1="150" x2="580" y2="150" stroke="currentColor" opacity=".2"/><polyline points={values.map((v,i)=>`${35+i/Math.max(1,values.length-1)*545},${150-(v-low)/(high-low)*120}`).join(' ')} fill="none" stroke="#5366e9" strokeWidth="3"/><text x="35" y="175" fontSize="12" fill="currentColor">epoch 1</text><text x="510" y="175" fontSize="12" fill="currentColor">{metrics[metrics.length-1]?.epoch}</text><text x="35" y="20" fontSize="12" fill="currentColor">{metric}: {values[values.length-1].toFixed(4)}</text></svg></div>:<p className="muted">{t('完成首轮后显示实际训练指标。')}</p>}
      <div className="epoch-table"><table><thead><tr><th>Epoch</th>{keys.slice(0,5).map(key=><th key={key}>{key}</th>)}</tr></thead><tbody>{metrics.map((m,i)=><tr key={i}><td>{m.epoch}</td>{keys.slice(0,5).map(key=><td key={key}>{Number.isFinite(m[key])?m[key].toFixed(4):'—'}</td>)}</tr>)}</tbody></table></div>
      <h3>{t('独立测试结果')}</h3>{run.evaluation?<><div className="evaluation-grid">{Object.entries(run.evaluation.metrics).map(([key,value])=><div key={key}><span>{key}</span><strong>{Number.isFinite(value)?value.toFixed(4):'—'}</strong></div>)}<div><span>{t('数量平均绝对误差')}</span><strong>{run.evaluation.count_mae.toFixed(3)}</strong></div></div><p className="microcopy">{t('测试图像 {0} 张；计数置信阈值 {1}。',[run.evaluation.images,run.evaluation.count_conf])}</p></>:<p className="muted">{t('训练完成后主动评估，查看检测指标与数量误差。')}</p>}
      <p className="microcopy">{run.best}</p>
    </>:<div className="learning-empty"><p>{t('选择版本并开始第一轮训练。')}</p></div>}
    {error&&<div className="dialog-error" role="alert">{t(error)}</div>}
    <details className="workspace-details"><summary>{t('训练说明')}</summary><p>{t('训练使用固定版本；后续修改标注不会改变已提交的实验。')}</p><p>{t('先选择与任务匹配的本地检测或分割权重；测试集不用于调参。')}</p><p className="microcopy">{t('新训练默认跟随全局设备，可单独更改；恢复训练沿用原记录的设备和参数。')}</p></details><details className="engine-logs"><summary>{t('诊断日志')}</summary><pre>{state.runtimes.logs.join('\n')}</pre></details>
  </section></div>
    <DialogContainer onDismiss={()=>setExporting(false)}>{exporting&&run&&<Dialog><Heading slot="title">{t('导出模型与记录')}</Heading><Content><div className="dialog-body"><TextField label={t('目标文件夹')} value={path} onChange={setPath} styles={full}/><ActionButton onPress={()=>void choose('folder')}>{t('选择文件夹')}</ActionButton>{error&&<p className="dialog-error">{t(error)}</p>}</div></Content><ButtonGroup><Button variant="secondary" onPress={()=>setExporting(false)}>{t('取消')}</Button><Button variant="accent" isDisabled={disabled||!path.trim()} onPress={()=>{void act('training-export',{run:run.id,path}).then(()=>setExporting(false)).catch(()=>{});}}>{t('导出')}</Button></ButtonGroup></Dialog>}</DialogContainer>
  </div>;
}
