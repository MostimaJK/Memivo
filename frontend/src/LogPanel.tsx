import React,{useRef,useState} from 'react';
import {ActionButton} from '@react-spectrum/s2';
import {useI18n} from './i18n';
import {type State} from './api';

export function diagnosticText(state:State|null) {
    if(!state)return '';
    const runtime=state.runtimes;
    return ['Memivo diagnostics',`Device setting: ${state.config.device}`,
        ...runtime.engines.map(e=>`Engine ${e.id}: ${e.state}; profile=${e.profile||'unknown'}`),
        `Task: ${state.task.kind}; state=${state.task.state}`,
        state.task.error||'',`Log file: ${state.task.log_file||runtime.log_file||''}`,
        '-- Recent subprocess output --',...runtime.logs,
        runtime.last_failure?`-- Last recorded failure (${runtime.last_failure.time}) --\n${runtime.last_failure.message}`:''
    ].filter(Boolean).join('\n');
}

export function LogPanel({text,compact=false}:{text:string;compact?:boolean}) {
    const {t}=useI18n();
    const field=useRef<HTMLTextAreaElement>(null);
    const disclosure=useRef<HTMLDetailsElement>(null);
    const [status,setStatus]=useState('');
    const select=()=>{if(disclosure.current)disclosure.current.open=true;field.current?.focus();field.current?.select();};
    const copy=async()=>{
        try {await navigator.clipboard.writeText(text);setStatus(t('日志已复制。'));}
        catch {
            select();
            let copied=false;
            try {copied=document.execCommand('copy');} catch {}
            setStatus(t(copied?'日志已复制。':'已全选日志，请按 Ctrl+C 复制。'));
        }
    };
    const log=<textarea ref={field} aria-label={t('诊断日志文本')} value={text} readOnly spellCheck={false} wrap="off" rows={8}/>;
    return <div className="log-panel"><div className="log-actions">
        <ActionButton onPress={copy} isDisabled={!text}>{t('复制日志')}</ActionButton>
        <ActionButton onPress={select} isDisabled={!text}>{t('全选日志')}</ActionButton>
        <span role="status">{status}</span>
      </div>{compact?<details ref={disclosure}><summary>{t('展开诊断日志')}</summary>{log}</details>:log}
    </div>;
}

export function TaskDiagnostics({state,kind,onFeatures,onOpen}:{state:State|null;kind:string;onFeatures:()=>void;onOpen:()=>void}) {
    const {t}=useI18n();
    if(!state||state.task.state!=='failed'||state.task.kind!==kind)return null;
    return <section className="task-diagnostics" role="alert"><div className="feature-heading">
      <strong>{t('运行失败，未生成新结果')}</strong><ActionButton onPress={onFeatures}>{t('查看引擎配置')}</ActionButton>
      {state.desktop&&<ActionButton onPress={onOpen}>{t('打开日志文件夹')}</ActionButton>}
      </div><LogPanel text={diagnosticText(state)} compact/></section>;
}
