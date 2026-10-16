import React,{useEffect,useRef,useState} from 'react';
import {Picker,PickerItem,ActionButton} from '@react-spectrum/s2';
import {style} from '@react-spectrum/s2/style' with {type:'macro'};
import {type Config,type State} from './api';
import {useI18n} from './i18n';
const full=style({width:'full'});
export function ModelSettings({state,draft,onChange,onAction,busy}:{state:State;draft:Config;onChange:(key:string,value:string)=>void;onAction:(route:string,data?:unknown)=>Promise<any>;busy:boolean}){
  const {t}=useI18n();const [pending,setPending]=useState(false),[error,setError]=useState('');const started=useRef(false);
  const scan=async()=>{setPending(true);setError('');try{const result=await onAction('models-scan',{});for(const [role,items] of Object.entries(result.models.items) as [keyof Config,State['models']['items'][string]][]){if(!draft[role]&&items.length===1)onChange(role,items[0].path);}}catch(e){setError((e as Error).message);}finally{setPending(false);}};
  useEffect(()=>{if(!started.current&&!busy){started.current=true;void scan();}},[]);
  return <section className="model-settings"><div className="feature-heading"><h3>{t('本地模型库')}</h3><ActionButton isDisabled={busy||pending} onPress={()=>void scan()}>{t('扫描模型')}</ActionButton></div><p className="microcopy">{t('将权重放入对应子文件夹；单个候选自动选择，多个候选由你选择。')}</p><code className="model-root">{state.models.root}</code><ActionButton isDisabled={!state.desktop||busy} onPress={()=>void onAction('models-open',{}).catch(e=>setError(e.message))}>{t('打开模型文件夹')}</ActionButton>
    {([['detector',t('SCRFD 人脸检测模型')],['recognition',t('LVFace / ArcFace 识别模型')],['sam',t('SAM3 分割模型（可选）')],['yolo',t('YOLO 检测模型（可选 .pt）')]] as const).map(([role,label])=>{
      const value=draft[role],items=[...state.models.items[role]];
      if(value&&!items.some(i=>i.path===value))items.push({path:value,name:value.split(/[\\/]/).pop()||value,relative:value,bytes:0});
      return <div className="model-choice" key={role}><div className="path-field"><Picker label={label} value={value||'none'} onChange={key=>onChange(role,key==='none'?'':String(key))} styles={full} isDisabled={busy||pending}><PickerItem id="none">{t('未选择模型')}</PickerItem>{items.map(item=><PickerItem key={item.path} id={item.path}>{item.relative}</PickerItem>)}</Picker><ActionButton isDisabled={busy||pending} aria-label={t('选择')+label} onPress={()=>{void onAction('pick',{kind:'file'}).then(result=>{if(result.paths[0])onChange(role,result.paths[0]);}).catch(e=>setError(e.message));}}>{t('外部文件')}</ActionButton></div>{value&&<p className="model-selected-path">{value}</p>}</div>;
    })}<p className="microcopy">{t('扫描按文件夹和扩展名分类，真正运行时才检查模型兼容性。官方权重入口在功能中心。')}</p>{error&&<p className="dialog-error" role="alert">{t(error)}</p>}</section>;
}
