import {ImageViewport} from './ImageViewport';
import React, {useEffect, useState} from 'react';
import {ActionButton, Button, Text, Picker, PickerItem, NumberField, Divider, SegmentedControl, SegmentedControlItem} from '@react-spectrum/s2';
import {style} from '@react-spectrum/s2/style' with {type:'macro'};
import ImageIcon from '@react-spectrum/s2/icons/Image';
import Play from '@react-spectrum/s2/icons/Play';
import Export from '@react-spectrum/s2/icons/Export';
import {asset, type State} from './api';
import {useI18n} from './i18n';

const full = style({width:'full'});
type Props = {state:State|null; selected:string; busy:boolean; onSelect:(id:string)=>void;
    onImport:()=>void; onSettings:()=>void; onExport:()=>void;
    onDetect:(options:unknown)=>void; onSegment:(bbox:number[])=>void};

export function DetectionWorkspace({state,selected,busy,onSelect,onImport,onSettings,onExport,onDetect,onSegment}:Props) {
    const {t}=useI18n();
    const [conf,setConf]=useState(.25), [iou,setIou]=useState(.7);
    const [showResult,setShowResult]=useState(true);
    const [category,setCategory]=useState('all'), [active,setActive]=useState<number|null>(null);
    const photo=state?.photos.find(p=>p.id===selected);
    const result=state?.detection?.photo===selected ? state.detection : null;
    const visible=result?.detections.map((item,index)=>({...item,index})).filter(item=>category==='all'||String(item.class_id)===category)||[];
    const resultKey=JSON.stringify(result);
    useEffect(()=>{setActive(null);setCategory('all');setShowResult(true);},[selected,resultKey]);
    const width=result?.width||photo?.width||1, height=result?.height||photo?.height||1;
    const chosen=active===null?null:result?.detections[active];
    return <div className="segment-layout detection-layout"><div className="segment-main">
      <div className="editor-toolbar"><Picker aria-label={t('选择图像')} value={selected||null} onChange={key=>onSelect(String(key))} placeholder={t('选择一张照片')}>
        {(state?.photos||[]).map(p=><PickerItem id={p.id} key={p.id}>{p.name}</PickerItem>)}</Picker>
        <ActionButton onPress={onImport} isDisabled={busy}>{t('导入单张图像')}</ActionButton>
        <SegmentedControl aria-label={t('检测显示方式')} selectedKey={showResult&&result?'result':'original'} onSelectionChange={key=>setShowResult(key==='result')} isDisabled={!result}>
          <SegmentedControlItem id="original">{t('原图')}</SegmentedControlItem><SegmentedControlItem id="result">{t('检测结果')}</SegmentedControlItem></SegmentedControl>
        {result&&<span className="microcopy">{t('显示 {0} / {1} 个目标',[visible.length,result.total])}</span>}
      </div>
      <div className="editor-canvas detection-canvas">{photo?<ImageViewport imageKey={photo.id} src={asset(photo.id,'full')} alt={photo.name} width={width} height={height}>
        {showResult&&result&&<svg className="image-overlay detection-overlay" viewBox={`0 0 ${width} ${height}`} aria-label={t('目标检测框')}>
          {visible.map(item=><g data-viewport-select="true" key={item.index} className={'detection-box '+(active===item.index?'chosen':'')} onClick={()=>setActive(item.index)}>
            <rect x={item.bbox[0]} y={item.bbox[1]} width={item.bbox[2]-item.bbox[0]} height={item.bbox[3]-item.bbox[1]} stroke={active===item.index?'#ffd580':'#8bc9ff'} strokeWidth={2} vectorEffect="non-scaling-stroke" fill="transparent"/>
            <text x={item.bbox[0]} y={item.bbox[1]} dy="-0.35em" fill="white" stroke="#202124" paintOrder="stroke" style={{fontSize:'calc(12px / var(--image-scale))',strokeWidth:'calc(3px / var(--image-scale))'}}>{item.index+1} · {item.name} {Math.round(item.confidence*100)}%</text>
          </g>)}
        </svg>}
      </ImageViewport>:<div className="canvas-empty"><ImageIcon/><h3>{t('看见每一个目标')}</h3><p>{t('导入图像，检测位置，并按类别统计数量。')}</p><Button variant="secondary" onPress={onImport}>{t('导入单张图像')}</Button></div>}</div>
      {result&&<div className="result-strip" role="status"><strong>{t('检测完成 · {0} 个目标',[result.total])}</strong><span>{result.counts.map(c=>`${c.name} × ${c.count}`).join(' · ')||t('未检测到目标，可调整阈值或更换模型。')}</span></div>}
      <div className="canvas-caption"><span>{photo?.name||t('尚未选择图像')}</span><span>{result?t('检测结果仅代表当前图像'):t('尚未运行检测')}</span></div>
    </div><aside className="segment-controls detection-controls"><div className="panel-heading"><ImageIcon/><h3>{t('检测与计数')}</h3></div>
      <p className="muted">{t('通用模型识别人等已有类别；自定义权重识别你训练的物品。')}</p>
      <div className="model-summary"><strong>YOLO</strong><span title={state?.config.yolo}>{state?.config.yolo?.split(/[\\/]/).pop()||t('尚未选择权重')}</span><ActionButton onPress={onSettings} isDisabled={busy}>{t('选择模型')}</ActionButton></div>
      <div className="sam-thresholds"><NumberField label={t('置信阈值')} value={conf} onChange={setConf} minValue={0} maxValue={1} step={.05} isDisabled={busy}/><NumberField label={t('IoU 阈值')} value={iou} onChange={setIou} minValue={0} maxValue={1} step={.05} isDisabled={busy}/></div>
      <Button variant="accent" styles={full} isDisabled={busy||!photo} onPress={()=>onDetect({id:selected,conf,iou})}><Play/><Text>{t('检测当前图像')}</Text></Button>
      <p className="microcopy">{t('数量来自保留的检测框，漏检、重复框和阈值都会影响计数。')}</p><Divider size="S"/>
      {result?<><div className="detection-total"><strong>{result.total}</strong><span>{t('个检测目标')}</span></div>
        <p className="microcopy">{t('结果阈值：{0} · IoU：{1}',[result.conf,result.iou])}</p>
        <Picker label={t('类别筛选')} value={category} onChange={key=>{setCategory(String(key));setActive(null);}} styles={full}>
          <PickerItem id="all">{t('全部类别')}</PickerItem>{result.counts.map(c=><PickerItem id={String(c.class_id)} key={c.class_id}>{c.name} · {c.count}</PickerItem>)}
        </Picker>
        {!result.total&&<p className="muted">{t('未检测到目标，可调整阈值或更换模型。')}</p>}
        <div className="detection-list">{visible.map(item=><button key={item.index} aria-pressed={active===item.index} className={'detection-row '+(active===item.index?'active':'')} onClick={()=>setActive(item.index)}><span>{item.index+1} · {item.name}</span><strong>{(item.confidence*100).toFixed(1)}%</strong></button>)}</div>
        <Button variant="secondary" styles={full} isDisabled={busy||!chosen} onPress={()=>chosen&&onSegment(chosen.bbox)}>{t('用 SAM3 提取选中目标')}</Button>
        <Button variant="secondary" styles={full} isDisabled={busy} onPress={onExport}><Export/><Text>{t('导出检测 JSON')}</Text></Button>
      </>:<p className="microcopy">{t('运行后查看类别数量、检测框和置信分数。')}</p>}
      <div className="info-note compact"><span>{t('使用你训练的模型')}</span><p>{t('选择本地 best.pt，类别名自动读取。当前支持检测或分割权重的框选计数。')}</p></div>
    </aside></div>;
}
