import {ModelCenter} from './ModelCenter';
import React,{useEffect,useState,useRef} from 'react';
import {ActionButton,Button,Text,Picker,PickerItem,StatusLight,DialogContainer,Dialog,Heading,Content,ButtonGroup} from '@react-spectrum/s2';
import {style} from '@react-spectrum/s2/style' with {type:'macro'};
import {type State} from './api';
import {useI18n} from './i18n';

const full=style({width:'full'});
export function FeatureCenter({state,busy,onAction}:{state:State|null;busy:boolean;onAction:(route:string,data?:unknown)=>void}) {
    const {t}=useI18n();
    const [profile,setProfile]=useState<Record<string,string>>({vision:'auto',face:'auto'});
    const [remove,setRemove]=useState<string|null>(null);
    const requested=useRef(false);
    const runtime=state?.runtimes, hardware=runtime?.hardware;
    useEffect(()=>{if(state&&!hardware&&!busy&&!requested.current){requested.current=true;onAction('environment-detect');}},[!!state,!!hardware,busy]);
    return <div className="features-page"><section className="hardware-card">
      <div className="feature-heading"><div><h2>{t('让功能按需生长')}</h2><p className="muted">{t('保留轻量主界面，需要时再安装独立 AI 引擎。')}</p></div><ActionButton isDisabled={busy} onPress={()=>onAction('environment-detect')}>{t('重新检测')}</ActionButton></div>
      {hardware?<><div className="hardware-facts"><span>{hardware.os} · {hardware.architecture}</span><span>Python {hardware.python}</span><span>{t('可用磁盘 {0} GB',[hardware.free_gb])}</span></div>
        {hardware.gpus.map((gpu,i)=><div className="gpu-detail" key={i}><strong>{gpu.name}</strong><span>{(gpu.memory_mb/1024).toFixed(1)} GB · {t('驱动 {0}',[gpu.driver])}</span></div>)}
        <p className="microcopy">{hardware.cuda_candidate?t('推荐 NVIDIA 方案；安装后还会验证真实 GPU 运算。'):t('当前未满足已配置的 GPU 方案，推荐 CPU。')}</p>
      </>:<p className="muted">{t('正在读取系统与显卡信息…')}</p>}
    </section><div className="engine-grid">{(['vision','face'] as const).map(id=>{
      const engine=runtime?.engines.find(e=>e.id===id);
      const installed=!!engine?.available;
      return <article className="engine-card" key={id}>
        <div className="feature-heading"><h3>{id==='vision'?t('视觉 AI 引擎'):t('人物识别引擎')}</h3><StatusLight variant={installed?'positive':engine?.state==='failed'?'negative':'neutral'}>{installed?t('已就绪'):engine?.state==='installing'?t('安装中'):engine?.state==='failed'?t('需要修复'):t('未安装')}</StatusLight></div>
        <p className="muted">{id==='vision'?t('YOLO 检测与 SAM3 抠图共用一套环境，避免重复安装。'):t('SCRFD 与 LVFace / ArcFace 的本地人脸匹配环境。')}</p>
        <div className="engine-detail"><span>{id==='vision'?'PyTorch + Ultralytics':'ONNX Runtime + InsightFace'}</span>{installed&&<span>{engine?.profile==='cu128'?'NVIDIA · CUDA 12.8':'CPU'} · {((engine?.bytes||0)/1024**3).toFixed(2)} GB</span>}</div>
        {!installed&&<Picker label={t('安装方案')} value={profile[id]} onChange={key=>setProfile(p=>({...p,[id]:String(key)}))} isDisabled={busy} styles={full}><PickerItem id="auto">{t('自动选择（推荐）')}</PickerItem><PickerItem id="cpu">CPU</PickerItem>{hardware?.cuda_candidate&&<PickerItem id="cu128">NVIDIA · CUDA 12.8</PickerItem>}</Picker>}
        <p className="microcopy">{id==='vision'?t('CPU 约 1–3 GB，NVIDIA 约 4–10 GB；均为估算，不含模型。'):t('支持 CPU 与 NVIDIA CUDA 12.8；自动方案根据显卡与驱动选择，安装后验证实际计算。')}</p>
        <p className="microcopy">{t('安装后请在设置中选择执行设备：CPU 或 NVIDIA CUDA。')}</p>
        {id==='face'&&<p className="microcopy">{t('模型权重与引擎分开安装；部分电脑需要 Microsoft C++ 构建工具。')}</p>}
        {engine?.state==='failed'&&<p className="engine-error" role="alert">{t(engine.error||'安装未完成，请查看诊断日志后重试。')}</p>}
        <div className="engine-actions"><Button variant={installed?'secondary':'accent'} isDisabled={busy||!hardware} onPress={()=>installed?setRemove(id):onAction('engine-install',{feature:id,profile:profile[id]})}>{installed?t('卸载引擎'):engine?.state==='failed'?t('重试安装'):t('安装引擎')}</Button>{!installed&&engine?.state==='failed'&&<ActionButton isDisabled={busy} onPress={()=>setRemove(id)}>{t('清理未完成环境')}</ActionButton>}</div>
      </article>;
    })}</div>{state&&<ModelCenter state={state} busy={busy} onAction={onAction}/>}<section className="feature-notes"><h3>{t('你的数据独立保存')}</h3><p>{t('安装需要联网下载依赖。模型权重另行选择；卸载只移除本程序创建的引擎环境，保留照片、标注、模型和项目。')}</p><p>{t('暂不自动安装显卡驱动、系统 Python 或完整 CUDA Toolkit；不兼容时提供原因，可改用 CPU。')}</p><p>{t('安装引擎后，可在训练工作台使用已确认的数据集版本。')}</p></section>
      <details className="engine-logs"><summary>{t('诊断日志')}</summary><p className="microcopy">{runtime?.root}</p><pre aria-live="polite">{runtime?.logs.length?runtime.logs.join('\n'):t('安装与推理诊断将在这里显示。')}</pre></details>
      <DialogContainer onDismiss={()=>setRemove(null)}>{remove&&<Dialog><Heading slot="title">{t('卸载可选引擎')}</Heading><Content><p>{remove==='vision'?t('YOLO 与 SAM3 共用此引擎，卸载后两者都需要重新安装才能使用。'):t('卸载后人物识别需要重新安装引擎。')}</p><p>{t('照片、模型权重与项目数据保留。')}</p></Content><ButtonGroup><Button variant="secondary" onPress={()=>setRemove(null)}>{t('取消')}</Button><Button variant="negative" isDisabled={busy} onPress={()=>{onAction('engine-uninstall',{feature:remove});setRemove(null);}}>{t('卸载引擎')}</Button></ButtonGroup></Dialog>}</DialogContainer>
    </div>;
}
