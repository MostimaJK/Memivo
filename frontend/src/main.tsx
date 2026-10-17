import {EngineControls} from './EngineControls';
import {ExecutionStatus} from './ExecutionStatus';
import {ImageDropZone} from './ImageDropZone';
import {TaskDiagnostics} from './LogPanel';
import {ImageViewport} from './ImageViewport';
import {ModelSettings} from './ModelSettings';
import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Provider, Button, ActionButton, Text, SearchField, Picker, PickerItem, TextField, NumberField, ProgressBar, ProgressCircle, DialogContainer, Dialog, Heading, Content, ButtonGroup, Divider, StatusLight, Slider, SegmentedControl, SegmentedControlItem, CardView, AssetCard, CardPreview, Image as SpectrumImage } from '@react-spectrum/s2';
import FolderOpen from '@react-spectrum/s2/icons/FolderOpen';
import ImageIcon from '@react-spectrum/s2/icons/Image';
import People from '@react-spectrum/s2/icons/PeopleGroup';
import Settings from '@react-spectrum/s2/icons/Settings';
import Play from '@react-spectrum/s2/icons/Play';
import Add from '@react-spectrum/s2/icons/Add';
import Export from '@react-spectrum/s2/icons/Export';
import Checkmark from '@react-spectrum/s2/icons/Checkmark';
import Close from '@react-spectrum/s2/icons/Close';
import Undo from '@react-spectrum/s2/icons/Undo';
import MagicWand from '@react-spectrum/s2/icons/MagicWand';
import Clock from '@react-spectrum/s2/icons/Clock';
import ChevronLeft from '@react-spectrum/s2/icons/ChevronLeft';
import ChevronRight from '@react-spectrum/s2/icons/ChevronRight';
import { api, asset, type State, type Config } from './api';
import { style } from '@react-spectrum/s2/style' with { type: 'macro' };
import './style.css';
import {DatasetWorkspace} from './DatasetWorkspace';
import {TrainingWorkspace} from './TrainingWorkspace';
import {FeatureCenter} from './FeatureCenter';
import {DetectionWorkspace} from './DetectionWorkspace';
import {LanguageProvider, useI18n, languages, isLocale, type Locale} from './i18n';
const fullWidth = style({ width: 'full' });
const fullWidthSpaced = style({ width: 'full', marginTop: 16 });
const galleryStyle = style({ position: 'absolute', inset: 0, width: 'full', height: 'full' });
const dividerSpacing = style({ marginY: 20 });
const labels: Record<string, string> = { matched: '自动匹配', confirmed: '已确认', rejected: '不归档', review: '待审核', unknown: '未知人物' };
const emptyTask = { state: 'idle', kind: '', done: 0, total: 0, message: '准备就绪' };
type Modal = 'import' | 'person' | 'settings' | 'export' | 'open' | 'save-segment' | 'save-detection' | 'image' | null;
type Mark = {
    type: 'point' | 'box';
    values: number[];
    label: number;
};
function App() {
    const {locale, setLocale, t} = useI18n();
    const [state, setState] = useState<State | null>(null);
    const [tab, setTab] = useState('library');
    const [modal, setModalState] = useState<Modal>(null);
    const [modalVersion, setModalVersion] = useState(0);
    const setModal = (next: Modal) => {
        if (next) setModalVersion(version => version + 1);
        setModalState(next);
    };
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [query, setQuery] = useState('');
    const [filter, setFilter] = useState('all');
    const [person, setPerson] = useState('');
    const [selected, setSelected] = useState('');
    const [faceIndex, setFaceIndex] = useState(0);
    const [identity, setIdentity] = useState('');
    const [page, setPage] = useState(0);
    const [dark, setDark] = useState(localStorage.getItem('sf-theme') === 'dark');
    const [refreshing, setRefreshing] = useState(false);
    const [marks, setMarks] = useState<Mark[]>([]);
    const markUndo=useRef<Mark[][]>([]),markRedo=useRef<Mark[][]>([]);
    const changeMarks=(next:Mark[])=>{markUndo.current=[...markUndo.current.slice(-49),marks];markRedo.current=[];setMarks(next);};
    const undoMarks=()=>{const previous=markUndo.current.pop();if(previous){markRedo.current.push(marks);setMarks(previous);}};
    const redoMarks=()=>{const next=markRedo.current.pop();if(next){markUndo.current.push(marks);setMarks(next);}};
    const pendingDrop=useRef<Set<string>|null>(null);
    const [mode, setMode] = useState('point');
    const [prompt, setPrompt] = useState('');
    const [opacity, setOpacity] = useState(.8);
    const [samConf, setSamConf] = useState(.3);
    const [samIou, setSamIou] = useState(.7);
    const [segmentView,setSegmentView]=useState('overlay');
    const [dimensions, setDimensions] = useState([1, 1]);
    const drag = useRef<number[] | null>(null);
    const [draftBox, setDraftBox] = useState<number[] | null>(null);
    const busy = state?.task.state === 'running';
    const task = state?.task || emptyTask;
    const photos = state?.photos || [];
    const config = state?.config;
    const names = Object.keys(config?.references || {});
    const photo = photos.find(p => p.id === selected);
    useEffect(() => { if (!photos.some(p => p.id === selected)) setSelected(photos[0]?.id || ''); }, [state?.config.source]);
    useEffect(()=>{if(pendingDrop.current&&state?.task.state!=='running'){const added=photos.find(p=>!pendingDrop.current!.has(p.id));if(added)setSelected(added.id);pendingDrop.current=null;}},[state]);
    const refresh = async () => { const next = await api<State>('state'); setState(next); if(isLocale(next.preferences?.language)) setLocale(next.preferences.language); };
    useEffect(() => { refresh().catch(e => setError(e.message)); }, []);
    useEffect(() => { if (!busy)
        return; const id = setInterval(() => refresh().catch(e => setError(e.message)), state?.task.kind==='目标检测'?150:900); return () => clearInterval(id); }, [busy,state?.task.kind]);
    useEffect(() => { setPage(0); }, [filter, person, query]);
    useEffect(()=>{if(state?.task.state==='failed')setError(state.task.error||state.task.message);},[state?.task.state,state?.task.error]);
    useEffect(() => { setMarks([]); markUndo.current=[];markRedo.current=[];drag.current=null;setDraftBox(null); setFaceIndex(0); setIdentity(''); setPrompt(''); setDimensions([photo?.width||1,photo?.height||1]); }, [selected]);
    useEffect(() => { setIdentity(photo?.faces[faceIndex]?.identity || ''); }, [faceIndex, selected]);
    useEffect(() => { localStorage.setItem('sf-theme', dark ? 'dark' : 'light'); }, [dark]);
    const act = async (route: string, data: unknown = {}, message = '') => {
        setError('');
        if(route==='import-drop')pendingDrop.current=new Set(photos.map(p=>p.id));
        if(route==='segment'||route==='detect')setNotice('');
        setRefreshing(true);
        try {
            const result = await api(route, data);
            await refresh();
            if (result?.path) setNotice(t('已保存到：{0}',[result.path]));
            else if (message) setNotice(message);
            return result;
        }
        catch (e) {
            setError((e as Error).message);
            if(route==='import-drop')pendingDrop.current=null;
            throw e;
        }
        finally {
            setRefreshing(false);
        }
    };
    const trigger = (route: string, data: unknown = {}, message = '') => { void act(route, data, message).catch(() => { }); };
    const processed = photos.filter(p => p.processed).length;
    const reviewCount = photos.filter(p => p.faces.some(f => ['review', 'unknown'].includes(f.status))).length;
    const matched = photos.filter(p => p.faces.some(f => f.identity)).length;
    const filtered = photos.filter(p => p.name.toLowerCase().includes(query.toLowerCase()) && (!person || p.faces.some(f => f.identity === person)) && (filter === 'all' || filter === 'review' && p.faces.some(f => ['review', 'unknown'].includes(f.status)) || filter === 'matched' && p.faces.some(f => f.identity) || filter === 'unprocessed' && !p.processed || filter === 'empty' && p.processed && !p.faces.length && !p.error || filter === 'failed' && !!p.error));
    const totalPages = Math.max(1, Math.ceil(filtered.length / 48));
    const currentPage = Math.min(page, totalPages - 1);
    const getPoint = (e: React.PointerEvent<SVGSVGElement>) => {
        const rect = e.currentTarget.getBoundingClientRect();
        return [Math.max(0, Math.min(dimensions[0] - 1, (e.clientX - rect.left) / rect.width * dimensions[0])), Math.max(0, Math.min(dimensions[1] - 1, (e.clientY - rect.top) / rect.height * dimensions[1]))];
    };
    const drawStart = (e: React.PointerEvent<SVGSVGElement>) => {
        if (busy || mode === 'text')
            return;
        if (e.button !== 0 || mode === 'view') return;
        const values = getPoint(e);
        if (mode === 'box') {
            drag.current = values;
            e.currentTarget.setPointerCapture(e.pointerId);
            setDraftBox([...values, ...values]);
        }
        else
            changeMarks([...marks, { type: 'point', values, label: mode === 'negative' ? 0 : 1 }]);
    };
    const drawEnd = (e: React.PointerEvent<SVGSVGElement>) => {
        if (e.button!==0 || !drag.current)
            return;
        const [x, y] = getPoint(e), [a, b] = drag.current;
        if (Math.abs(x - a) > 2 && Math.abs(y - b) > 2)
            changeMarks([...marks, { type: 'box', values: [Math.min(x, a), Math.min(y, b), Math.max(x, a), Math.max(y, b)], label: 1 }]);
        drag.current = null;
        setDraftBox(null);
    };
    const renderBox = (values: number[], key: number | string, color: string) => <rect key={key} x={values[0]} y={values[1]} width={values[2] - values[0]} height={values[3] - values[1]} stroke={color} strokeWidth={2} vectorEffect="non-scaling-stroke" fill="none"/>;
    const segment=state?.segment?.photo===selected?state.segment:null;
    useEffect(()=>{if(segment)setSegmentView('overlay');},[segment?.overlay]);
    const markLayer=<svg className="image-overlay annotation-overlay" viewBox={`0 0 ${dimensions[0]} ${dimensions[1]}`} aria-label={t('图像标记画布')}
      onContextMenu={event=>{
        event.preventDefault();if(busy)return;
        if(drag.current){drag.current=null;setDraftBox(null);return;}
        const rect=event.currentTarget.getBoundingClientRect();
        const px=(event.clientX-rect.left)/rect.width*dimensions[0],py=(event.clientY-rect.top)/rect.height*dimensions[1];
        let target=-1,distance=13;
        marks.forEach((mark,index)=>{if(mark.type==='point'){const d=Math.hypot((px-mark.values[0])*rect.width/dimensions[0],(py-mark.values[1])*rect.height/dimensions[1]);if(d<distance){distance=d;target=index;}}});
        if(target<0)for(let i=marks.length-1;i>=0;i--){const m=marks[i],v=m.values;if(m.type==='box'&&px>=v[0]&&px<=v[2]&&py>=v[1]&&py<=v[3]){target=i;break;}}
        if(target>=0)changeMarks(marks.filter((_,i)=>i!==target));
      }} onPointerDown={drawStart} onPointerUp={drawEnd} onPointerCancel={()=>{drag.current=null;setDraftBox(null);}}
      onPointerMove={event=>{if(drag.current)setDraftBox([...drag.current,...getPoint(event)]);}}>
      {marks.map((m,i)=>m.type==='box'?renderBox(m.values,i,'#8bc9ff'):<circle key={i} cx={m.values[0]} cy={m.values[1]} r="calc(5px / var(--image-scale, 1))" fill={m.label?'#59dca2':'#ff8181'} stroke="white" strokeWidth="1.5" vectorEffect="non-scaling-stroke"/>)}
      {draftBox&&renderBox([Math.min(draftBox[0],draftBox[2]),Math.min(draftBox[1],draftBox[3]),Math.max(draftBox[0],draftBox[2]),Math.max(draftBox[1],draftBox[3])],'draft','#8bc9ff')}
    </svg>;
    const imageStage=()=>photo&&<div className="image-stage"><img className="main-photo" src={asset(photo.id,'preview')} alt={photo.name}/>
      <svg className="image-overlay" viewBox={`0 0 ${photo.width||dimensions[0]} ${photo.height||dimensions[1]}`} aria-label={t('人脸位置')}>
      {photo.faces.map((f,i)=><g key={i}>{renderBox(f.bbox,i,i===faceIndex?'#7bb9ff':'#ffd580')}<text x={f.bbox[0]} y={Math.max(24,f.bbox[1]-8)} fill="white" fontSize={Math.max(18,(photo.width||dimensions[0])/65)}>{i+1}</text></g>)}</svg></div>;
    return <Provider colorScheme={dark ? 'dark' : 'light'} locale={locale}><div className={'app ' + (dark ? 'dark' : 'light')}>
    <header className="topbar"><div className="brand"><img className="brand-mark" src="/memivo.svg" alt="" aria-hidden="true"/><strong>Memivo</strong><span className="product-tag">{t("影像工作台")}</span></div><div className="global-search"><SearchField aria-label={t("搜索照片名称")} placeholder={t("搜索你的照片…")} value={query} onChange={v => { setQuery(v); setTab('library'); }} styles={fullWidth}/></div><div className="topbar-right"><StatusLight variant={busy ? 'informative' : 'positive'}>{busy ? t("任务进行中") : t("本地工作区")}</StatusLight><ActionButton isQuiet aria-label={t("切换明暗主题")} onPress={() => setDark(v => !v)}><span>{dark ? '☀' : '◐'}</span></ActionButton><ActionButton isQuiet aria-label={t("模型与项目设置")} onPress={() => setModal('settings')}><Settings /></ActionButton></div></header>
    <div className="shell"><aside className="sidebar"><div className="workspace-label">{t("工作空间")}</div><nav aria-label={t("主导航")}>{[
            ['library', t("照片图库"), ImageIcon], ['people', t("人物相册"), People], ['detect', t("检测与计数"), ImageIcon], ['segment', t("分割工作台"), MagicWand], ['datasets', t('标注与数据集'), ImageIcon], ['training', t('训练工作台'), Play], ['features', t('功能中心'), Settings], ['tasks', t("任务记录"), Clock]
        ].map(([key, label, Icon]) => <button key={key as string} aria-label={label as string} className={'nav-item ' + (tab === key ? 'active' : '')} onClick={() => setTab(key as string)}><Icon /><span>{label as string}</span>{key === 'library' && photos.length > 0 && <em>{photos.length}</em>}</button>)}</nav>
      <div className="sidebar-divider"/><div className="workspace-label section-label"><span>{t("我的朋友")}</span><ActionButton isQuiet aria-label={t("登记朋友")} isDisabled={busy} onPress={() => setModal('person')}><Add /></ActionButton></div>
      <div className="people-nav">{names.length ? names.map((name, i) => <button key={name} aria-label={t("查看 ") + name + t(" 的相册")} title={name} className={'person-nav ' + (person === name ? 'selected' : '')} onClick={() => { setPerson(person === name ? '' : name); setTab('library'); }}><span className={'avatar avatar-' + i % 5}>{name.slice(0, 1)}</span><span>{name}</span><em>{photos.filter(p => p.faces.some(f => f.identity === name)).length}</em></button>) : <p className="side-hint">{t("登记一张参考照，")}<br />{t("开始寻找朋友的照片。")}</p>}</div>
      <div className="sidebar-bottom"><div className="privacy-line"><Checkmark /><span>{t("照片保留在本机")}</span></div><ActionButton isQuiet aria-label={t("打开已有项目")} onPress={() => setModal('open')} isDisabled={busy}><FolderOpen /></ActionButton></div>
    </aside><ImageDropZone className="workspace" disabled={busy||refreshing||!['library','people','detect','segment'].includes(tab)} onImages={async({folder})=>{pendingDrop.current=new Set(photos.map(p=>p.id));try{await act('import-drop',{path:folder});}catch(e){pendingDrop.current=null;throw e;}}}>
      {(error || notice) && <div className={'message ' + (error ? 'error' : 'success')} role={error ? 'alert' : 'status'}><span>{t(error || notice)}</span><ActionButton isQuiet aria-label={t("关闭提示")} onPress={() => { setError(''); setNotice(''); }}><Close /></ActionButton></div>}
      <div className="page-heading"><div><div className="eyebrow">{tab === 'datasets' ? 'DATASET STUDIO' : tab === 'training' ? 'MODEL LAB' : tab === 'features' ? 'MAKE IT YOURS' : tab === 'detect' ? 'OBJECT WORKSPACE' : tab === 'segment' ? 'PRECISION WORKSPACE' : tab === 'tasks' ? 'ACTIVITY' : tab === 'people' ? 'PEOPLE & MEMORIES' : 'YOUR PHOTO LIBRARY'}</div><h1>{tab === 'datasets' ? t('标注与数据集') : tab === 'training' ? t('训练工作台') : tab === 'features' ? t('功能中心') : tab === 'detect' ? t('检测与计数') : tab === 'segment' ? t("分割工作台") : tab === 'tasks' ? t("任务记录") : tab === 'people' ? t("人物相册") : person ? t("{0}的相册", [person]) : t("照片图库")}</h1><p>{tab === 'datasets' ? t('从人工确认的标签，到可复现的数据版本。') : tab === 'training' ? t('训练、评估并应用属于你的模型。') : tab === 'features' ? t('按需安装，让每一台电脑找到合适的 AI 能力。') : tab === 'detect' ? t('找到图像中的目标，让数量一目了然。') : tab === 'segment' ? t("用点、框和文字提取目标，让每一次选择更精准。") : tab === 'tasks' ? t("查看处理进度与结果，每一步都有迹可循。") : tab === 'people' ? t("用少量参考照片，建立属于这次旅行的人物库。") : config?.source ? config.source.split(/[\\/]/).filter(Boolean).pop() + t(" · 浏览、识别与审核，在一个空间完成。") : t("把一趟旅行的照片，整理成每个人的回忆。")}</p></div><div className="heading-actions">{(tab === 'segment' || tab === 'detect') && <Button variant="secondary" onPress={() => setModal('image')} isDisabled={busy}><Add/><Text>{t('导入单张图像')}</Text></Button>}{tab === 'library' && <><Button variant="secondary" onPress={() => setModal('import')} isDisabled={busy}><Add /><Text>{t("导入照片")}</Text></Button><Button variant="accent" onPress={() => trigger('recognize')} isDisabled={busy || !photos.length}><Play /><Text>{t("开始整理")}</Text></Button></>}{tab === 'people' && <Button variant="accent" onPress={() => setModal('person')} isDisabled={busy}><Add /><Text>{t("登记朋友")}</Text></Button>}</div></div>
      <ExecutionStatus state={state}/>
      {tab === 'library' && <><div className="collection-bar"><SegmentedControl aria-label={t("照片状态")} selectedKey={['all', 'review', 'matched'].includes(filter) ? filter : null} onSelectionChange={k => setFilter(String(k))}>{[['all', t("全部照片"), photos.length], ['review', t("待审核"), reviewCount], ['matched', t("已归档"), matched]].map(([key, label, count]) => <SegmentedControlItem id={String(key)} key={key}><Text>{label} · {count}</Text></SegmentedControlItem>)}</SegmentedControl><div className="collection-actions"><ActionButton aria-label={t("导出人物相册")} isDisabled={busy || !matched} onPress={() => setModal('export')}><Export /></ActionButton></div></div>
      <div className={'library-layout ' + (photo ? 'with-inspector' : '')}><section className="gallery-region" aria-label={t("照片集合")}>
        {!photos.length ? <div className="empty-library"><div className="empty-art"><div className="art-back"/><div className="art-photo"><ImageIcon /><span className="art-sun"/></div><span className="art-check"><Checkmark /></span></div><div className="eyebrow">{t("每一次相聚，都值得好好收藏")}</div><h2>{t("从一份旅行相册开始")}</h2><p>{t("导入照片，登记朋友。让系统寻找相同的人，")}<br />{t("你只需确认那些不确定的瞬间。")}</p><Button variant="accent" onPress={() => setModal('import')} isDisabled={busy}><FolderOpen /><Text>{t("导入照片文件夹")}</Text></Button><div className="empty-details"><span>{t("原图保留")}</span><i /><span>{t("合照多人归档")}</span><i /><span>{t("本地处理")}</span></div></div> : <>
          <div className="gallery-info"><span>{filtered.length}{t("张照片")}{person ? ' · ' + person : ''}</span><Picker aria-label={t("更多状态筛选")} value={filter} onChange={k => setFilter(String(k))}><PickerItem id="all">{t("全部状态")}</PickerItem><PickerItem id="review">{t("待审核")}</PickerItem><PickerItem id="matched">{t("已归档")}</PickerItem><PickerItem id="unprocessed">{t("尚未识别")}</PickerItem><PickerItem id="empty">{t("未检测到人脸")}</PickerItem><PickerItem id="failed">{t("处理失败")}</PickerItem></Picker>{person && <ActionButton isQuiet onPress={() => setPerson('')}>{t("清除人物筛选")}</ActionButton>}</div>
          {!filtered.length ? <div className="no-results"><ImageIcon /><h3>{t("没有符合条件的照片")}</h3><p>{t("尝试其他状态、人物或搜索关键词。")}</p><Button variant="secondary" onPress={() => { setFilter('all'); setQuery(''); setPerson(''); }}>{t("重置筛选")}</Button></div> : <div className="photo-collection"><CardView aria-label={t("照片卡片")} layout="waterfall" size="L" variant="quiet" selectionMode="single" selectionStyle="highlight" selectedKeys={selected ? [selected] : []} onSelectionChange={keys => { if (keys !== 'all') {
                const id = Array.from(keys)[0];
                if (id)
                    setSelected(String(id));
            } }} onAction={key => setSelected(String(key))} styles={galleryStyle} items={filtered.slice(currentPage * 48, (currentPage + 1) * 48)}>{p => { const assigned = Array.from(new Set(p.faces.filter(f => f.identity).map(f => f.identity))); return <AssetCard id={p.id} textValue={p.name} aria-label={t("查看 ") + p.name}><CardPreview><SpectrumImage src={asset(p.id)} alt={p.name} width={p.width || 600} height={p.height || 450}/></CardPreview><Content><Text slot="title">{p.name}</Text><Text slot="description">{p.error ? t("处理失败") : !p.processed ? t("尚未识别") : assigned.join('、') || (!p.faces.length ? t("未检测到人脸") : t("等待确认"))}</Text></Content></AssetCard>; }}</CardView></div>}

          <div className="pagination"><span>{t("每页最多 48 张 · 缩略图按需加载")}</span><ActionButton aria-label={t("上一页")} isDisabled={currentPage === 0} onPress={() => setPage(p => p - 1)}><ChevronLeft /></ActionButton><span>{currentPage + 1} / {totalPages}</span><ActionButton aria-label={t("下一页")} isDisabled={currentPage + 1 >= totalPages} onPress={() => setPage(p => p + 1)}><ChevronRight /></ActionButton></div>
        </>}
      </section>{photo && <aside className="inspector"><div className="inspector-title"><h3>{t("照片详情")}</h3><ActionButton isQuiet aria-label={t("关闭照片详情")} onPress={() => setSelected('')}><Close /></ActionButton></div><div className="review-preview">{imageStage()}</div><h4 className="file-title">{photo.name}</h4><p className="muted">{photo.faces.length ? t("{0} 张人脸 · 点击下方人物核对身份", [photo.faces.length]) : photo.processed ? t("此照片未检测到人脸。") : t("照片尚未识别，开始整理后在这里审核人物。")}</p>
        <div className="face-list">{photo.faces.map((f, i) => <button key={i} className={'face-row ' + (faceIndex === i ? 'active' : '')} onClick={() => setFaceIndex(i)}><span className="face-number">{i + 1}</span><span><strong>{f.identity || t("身份待确认")}</strong><small>{t(labels[f.status] || f.status)}</small></span>{f.status === 'confirmed' && <Checkmark />}</button>)}</div>
        {photo.faces[faceIndex] && <><Divider size="S"/><h4>{t("匹配候选")}</h4><div className="candidate-list">{photo.faces[faceIndex].candidates.map(c => <div key={c.name}><span>{c.name}</span><strong>{c.score.toFixed(3)}</strong></div>)}</div><p className="microcopy">{t("相似度用于比较候选，不代表正确概率。")}</p><Picker label={t("确认人物身份")} value={identity || '_unknown'} onChange={k => setIdentity(k === '_unknown' ? '' : String(k))} styles={fullWidth} isDisabled={busy}>{['_unknown', ...names].map(n => <PickerItem id={n}>{n === '_unknown' ? t("未知人物 / 不归档") : n}</PickerItem>)}</Picker><Button variant="accent" styles={fullWidthSpaced} isDisabled={busy} onPress={() => trigger('review', { id: photo.id, face: faceIndex, identity }, t("身份修改已保存。"))}><Checkmark /><Text>{t("保存身份")}</Text></Button><ActionButton styles={fullWidthSpaced} isDisabled={busy || !(state as any)?.canUndo} onPress={() => trigger('undo', {}, t("已撤销身份修改。"))}><Undo /><Text>{t("撤销修改")}</Text></ActionButton></>}
        <div className="inspector-footer"><Button variant="secondary" styles={fullWidth} onPress={() => setTab('segment')}>{t("在分割工作台打开")}</Button></div></aside>}</div></>}
      {tab === 'people' && <div className="people-page">{!names.length ? <div className="people-empty"><People /><h2>{t("先认识这次旅行的朋友")}</h2><p>{t("每个人从一张清晰的单人参考照开始。")}<br />{t("后续可以补充不同角度，让匹配更可靠。")}</p><Button variant="accent" onPress={() => setModal('person')}><Add /><Text>{t("登记第一位朋友")}</Text></Button></div> : <div className="person-grid">{names.map((name, i) => { const count = photos.filter(p => p.faces.some(f => f.identity === name)).length; return <article className="person-card" key={name}><span className={'avatar large avatar-' + i % 5}>{name.slice(0, 1)}</span><h2>{name}</h2><p>{config!.references[name].length}{t("张参考照 ·")}{count}{t("张关联照片")}</p><Button variant="secondary" onPress={() => { setPerson(name); setFilter('all'); setTab('library'); }}>{t("查看相册")}</Button></article>; })}</div>}<div className="info-note"><span>{t("关于参考照片")}</span><p>{t("请选择仅含一张清晰人脸的照片。侧脸、夜景与背影可能需要人工审核；确认结果不会自动加入参考库。")}</p></div></div>}
      {state && <div className="learning-container" hidden={tab!=='datasets'}><DatasetWorkspace state={state} busy={busy} onAction={act} onTrain={()=>setTab('training')}/></div>}
      {tab === 'training' && state && <TrainingWorkspace state={state} busy={busy} onAction={act} onFeatures={()=>setTab('features')} onDataset={()=>setTab('datasets')}/>}
      {tab === 'features' && <FeatureCenter state={state} busy={busy} onAction={trigger}/>}
      {tab === 'detect' && <DetectionWorkspace onAction={trigger} state={state} selected={selected} busy={busy} onSelect={setSelected} onImport={()=>setModal('image')} onSettings={()=>setModal('settings')} onExport={()=>setModal('save-detection')} onFeatures={()=>setTab('features')} onOpenLogs={()=>trigger('diagnostics-open')} onDetect={options=>trigger('detect',options)} onSegment={bbox=>{changeMarks([{type:'box',values:bbox,label:1}]);setMode('box');setTab('segment');}}/>}
      {tab === 'segment' && <div className="segment-layout" onKeyDownCapture={event=>{
        if(busy||(event.target as Element).closest('input,textarea,select,[contenteditable=true]'))return;
        if(event.key==='Escape'){drag.current=null;setDraftBox(null);event.preventDefault();}
        if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='z'){event.preventDefault();event.shiftKey?redoMarks():undoMarks();}
        if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='y'){event.preventDefault();redoMarks();}
      }}><div className="segment-main"><div className="editor-toolbar"><Picker aria-label={t("选择照片")} value={selected || null} onChange={k => setSelected(String(k))} placeholder={t("选择一张照片")}>{photos.map(p => <PickerItem id={p.id}>{p.name}</PickerItem>)}</Picker><Button variant={mode==='view'?'accent':'secondary'} aria-pressed={mode==='view'} onPress={()=>setMode(mode==='view'?'point':'view')}>{t('拖动')}</Button><SegmentedControl aria-label={t("标记工具")} selectedKey={mode==='view'?'none':mode} onSelectionChange={k => setMode(String(k))}>{[['point', t("正点")], ['negative', t("负点")], ['box', t("框选")], ['text', t("文字")]].map(([key, label]) => <SegmentedControlItem id={key} key={key}>{label}</SegmentedControlItem>)}</SegmentedControl><Button variant={segment&&segmentView!=='original'?'accent':'secondary'} aria-pressed={!!segment&&segmentView!=='original'} isDisabled={!segment} onPress={()=>setSegmentView(segmentView==='original'?'overlay':'original')}>{segment&&segmentView!=='original'?'Result':t('原图')}</Button><ActionButton aria-pressed={segmentView==='mask'} isDisabled={!segment} onPress={()=>setSegmentView('mask')}>{t('黑白掩码')}</ActionButton><ActionButton aria-pressed={segmentView==='cutout'} isDisabled={!segment} onPress={()=>setSegmentView('cutout')}>{t('透明抠图')}</ActionButton><ActionButton aria-label={t("撤销标记")} isDisabled={!markUndo.current.length || busy} onPress={undoMarks}><Undo /></ActionButton><ActionButton isDisabled={!markRedo.current.length||busy} onPress={redoMarks}>{t('重做')}</ActionButton><ActionButton isDisabled={!marks.length || busy} onPress={() => changeMarks([])}>{t("清空")}</ActionButton></div><TaskDiagnostics state={state} kind="SAM3 分割" onFeatures={()=>setTab('features')} onOpen={()=>trigger('diagnostics-open')}/><div className="editor-canvas">{photo ? <ImageViewport imageKey={photo.id} src={asset(segment&&(segmentView==='mask'||segmentView==='cutout')?segment[segmentView]:photo.id,segment&&(segmentView==='mask'||segmentView==='cutout')?'download':'full')} alt={photo.name} width={photo.width} height={photo.height} mode={mode==='view'||mode==='text'?'pan':'annotate'} checker={!!segment&&segmentView==='cutout'}>
      {segment&&segmentView==='overlay'&&<img className="result-overlay" style={{opacity}} src={asset(segment.overlay,'download')} alt={t('分割结果')}/>}{markLayer}</ImageViewport> : <div className="canvas-empty"><MagicWand /><h3>{t("给你的选择，多一点精准")}</h3><p>{t('拖入图片，或从图库选择。')}</p><Button variant="secondary" onPress={() => setModal('import')}>{t("导入照片")}</Button></div>}</div><div className="canvas-caption"><span>{photo ? photo.name : t("尚未选择图像")}</span><span>{marks.length}{t("个标记 ·")}{mode === 'view' ? t('拖动平移图像') : mode === 'box' ? t("拖动绘制矩形") : mode === 'text' ? t("右侧输入概念提示") : mode === 'negative' ? t("点击排除目标") : t("点击选择目标")}</span></div></div><aside className="segment-controls"><div className="panel-heading"><MagicWand /><h3>{t("提示与结果")}</h3></div><EngineControls state={state} target="segment" mode={mode==='text'?'text':'geometry'} onAction={trigger}/>{segment&&<section className="result-summary" aria-live="polite"><strong>{t(task.kind==='SAM3 分割'&&task.state!=='completed'?'上次分割结果 · {0} 个目标':'分割成功 · {0} 个目标',[segment.count])}</strong><p>{t('已自动保存掩码、透明抠图和预览。')}</p><label>{t('结果保存目录')}</label><code>{segment.directory}</code><Button variant="accent" styles={fullWidth} isDisabled={busy} onPress={()=>setModal('save-segment')}>{t('导出抠图或掩码')}</Button><ActionButton isDisabled={!state?.desktop} onPress={()=>trigger('segment-open',{id:selected})}>{t('打开结果文件夹')}</ActionButton></section>}<p className="muted">{t("用视觉标记选择具体目标，或用文字寻找图像中的概念。")}</p><TextField label={t("文本提示")} placeholder={t("例如：person、red bag")} value={prompt} onChange={setPrompt} isDisabled={busy || mode !== 'text'} styles={fullWidth}/><p className="microcopy">{t("文字模式使用概念提示；点与框模式使用画布标记。")}</p><Divider size="S" styles={dividerSpacing}/><div className="sam-thresholds"><NumberField label={t("置信阈值")} value={samConf} onChange={setSamConf} minValue={0} maxValue={1} step={.05} isDisabled={busy} styles={fullWidth}/><NumberField label={t("IoU 阈值")} value={samIou} onChange={setSamIou} minValue={0} maxValue={1} step={.05} isDisabled={busy} styles={fullWidth}/></div><p className="microcopy">{t('右键删除标记 · Ctrl+Z 撤销 · Esc 取消绘制')}</p><div className="mark-legend"><span><i className="positive"/>{t("正点：包含")}</span><span><i className="negative"/>{t("负点：排除")}</span></div><Button variant="accent" styles={fullWidthSpaced} isDisabled={busy || !photo || (mode === 'text' ? !prompt.trim() : !marks.length)} onPress={() => trigger('segment', { id: selected, conf: samConf, iou: samIou, text: mode === 'text' ? prompt : '', points: marks.filter(m => m.type === 'point').map(m => m.values), labels: marks.filter(m => m.type === 'point').map(m => m.label), boxes: marks.filter(m => m.type === 'box').map(m => m.values) })}><MagicWand /><Text>{t("生成分割")}</Text></Button><Divider size="S" styles={dividerSpacing}/>
<Slider label={t("结果叠加透明度")} value={Math.round(opacity * 100)} onChange={v => setOpacity(Number(v) / 100)} isDisabled={!segment||segmentView!=='overlay'} minValue={0} maxValue={100} styles={fullWidth}/><div className="info-note compact"><span>{t("保留你的原图")}</span><p>{t("分割结果独立保存，原始照片不会被修改。")}</p></div></aside></div>}
      {tab === 'tasks' && <div className="tasks-page"><div className="task-overview"><Clock /><div><h3>{task.state === 'idle' ? t("还没有处理任务") : t(task.kind)}</h3><p>{t(task.message)}</p></div>{busy && <Button variant="secondary" onPress={() => trigger('cancel')}>{t("停止任务")}</Button>}</div><h3>{t("本次会话记录")}</h3>{!state?.history.length ? <div className="no-results"><p>{t("导入、识别、分割与导出记录将在这里显示。")}</p></div> : <div className="history-list">{[...state.history].reverse().map((h, i) => <article key={i}><span className={'task-dot ' + h.state}/><div><strong>{t(h.kind)}</strong><p>{t(h.message)}</p></div><span>{h.seconds}s</span><time>{h.time}</time></article>)}</div>}</div>}
      <footer className={'statusbar ' + (busy ? 'running' : '')}><div>{busy ? <ProgressCircle aria-label={t("任务运行中")} size="S" isIndeterminate/> : <span className={'status-dot '+(task.state==='failed'?'failed':'')}/>}<span>{t(task.message)}</span></div><div>{busy && <><ProgressBar aria-label={t("当前任务进度")} value={task.done} maxValue={task.total || 1} isIndeterminate={!task.total} valueLabel=""/><span>{task.total ? task.kind==='下载官方模型'?`${(task.done/1048576).toFixed(1)} / ${(task.total/1048576).toFixed(1)} MB`:`${task.done} / ${task.total}` : t("处理中")}</span><ActionButton isQuiet onPress={() => trigger('cancel')}>{t("停止")}</ActionButton></>}{!busy && <span>{processed} / {photos.length}{t("张已处理")}</span>}</div></footer>
    </ImageDropZone></div>
    <DialogContainer onDismiss={() => setModal(null)}>{modal && state && <ProjectDialog key={`${modal}-${modalVersion}`} kind={modal} state={state} busy={refreshing} onClose={() => setModal(null)} onAction={act}/>}</DialogContainer>
  </div></Provider>;
}
function ProjectDialog({ kind, state, busy, onClose, onAction }: {
    kind: Exclude<Modal, null>;
    state: State;
    busy: boolean;
    onClose: () => void;
    onAction: (r: string, d?: unknown, m?: string) => Promise<any>;
}) {
    const {locale, t} = useI18n();
    const [draftLanguage, setDraftLanguage] = useState<Locale>(locale);
    const [path, setPath] = useState('');
    const [name, setName] = useState('');
    const [paths, setPaths] = useState<string[]>([]);
    const [draft, setDraft] = useState<Config>({ ...state.config });
    const [err, setErr] = useState('');
    const [pending, setPending] = useState(false);
    const [instance, setInstance] = useState('all');
    const [crop, setCrop] = useState('crop');
    const [output,setOutput]=useState('cutout');
    const title = { import: t("导入照片"), person: t("登记朋友"), settings: t("模型与项目设置"), export: t("导出人物相册"), open: t("打开已有项目"), 'save-segment': t("导出分割结果"), 'save-detection': t('导出检测 JSON'), image: t('导入单张图像') }[kind];
    const choose = async (type: string, field?: string) => { setErr(''); try {
        const result = await api('pick', { kind: type });
        if (result.paths.length) {
            if (field)
                setDraft(d => ({ ...d, [field]: result.paths[0] }));
            else if (type === 'references') {
                setPaths(result.paths);
                setPath(result.paths.join('\n'));
            }
            else
                setPath(result.paths[0]);
        }
    }
    catch (e) {
        setErr((e as Error).message);
    } };
    const submit = async () => {
        setPending(true);
        setErr('');
        try {
            if (kind === 'settings') {
                await onAction('config', { workspace: draft.workspace, detector: draft.detector, recognition: draft.recognition, sam: draft.sam, yolo: draft.yolo, device: draft.device, threshold: draft.threshold, margin: draft.margin });
                await onAction('preferences', {language: draftLanguage}, "设置已保存。");
            }
            else if (kind === 'person')
                await onAction('reference', { name, paths: paths.length ? paths : path.split(/\r?\n/).map(p => p.trim()).filter(Boolean) }, t("参考照片已登记。"));
            else
                await onAction(kind === 'import' || kind === 'image' ? 'scan' : kind, {path, instance, output, crop: output==='cutout'&&crop === 'crop', id: kind === 'save-segment' ? state.segment?.photo : state.detection?.photo}, kind === 'save-segment' ? t("透明 PNG 已导出。") : '');
            onClose();
        }
        catch (e) {
            setErr((e as Error).message);
        }
        finally {
            setPending(false);
        }
    };
    return <Dialog size={kind === 'settings' ? 'L' : 'M'}><Heading slot="title">{title}</Heading><Content><div className="dialog-body">
    {kind === 'settings' ? <><section className="language-settings"><h3>{t('外观与语言')}</h3><Picker label="Language" value={draftLanguage} onChange={value=>{if(isLocale(value))setDraftLanguage(value);}} styles={fullWidth}>{languages.map(language=><PickerItem id={language.id} key={language.id}>{language.name}</PickerItem>)}</Picker><p className="microcopy">{languages.find(language=>language.id===draftLanguage)?.font} · {t('字体随语言自动切换，离线可用。')}<br/>{t('保存后生效，下次启动自动恢复。')}</p></section><Divider size="S"/><div className="settings-intro"><StatusLight variant="informative">{t("模型在本地运行，照片不上传")}</StatusLight><p>{t("配置一次后会保存到当前项目。识别与分割可以分别使用不同模型。")}</p></div><ModelSettings state={state} draft={draft} busy={busy} onAction={onAction} onChange={(key,value)=>setDraft(d=>({...d,[key]:value}))}/><div className="settings-grid"><Picker label={t("执行设备")} value={draft.device} onChange={k => setDraft(d => ({ ...d, device: String(k) }))}><PickerItem id="cpu">CPU</PickerItem><PickerItem id="cuda">NVIDIA CUDA</PickerItem></Picker><NumberField label={t("匹配阈值")} value={draft.threshold} onChange={threshold => setDraft(d => ({ ...d, threshold }))} minValue={0} maxValue={1} step={.01}/><NumberField label={t("候选差距")} value={draft.margin} onChange={margin => setDraft(d => ({ ...d, margin }))} minValue={0} maxValue={1} step={.01}/></div><p className="microcopy">{t("阈值为待校准起始值；更换识别模型后请重新评估匹配效果。")}</p><Divider size="S"/><h3>{t("项目存储")}</h3><TextField label={t("工作目录")} value={draft.workspace} onChange={workspace => setDraft(d => ({ ...d, workspace }))} styles={fullWidth} isReadOnly={!!state.photos.length}/><p className="microcopy">{t("缓存与审核结果保存在此目录。已有照片时请通过“打开已有项目”切换。")}</p><h3>{t('主界面环境依赖')}</h3><p className="microcopy">{t('下方仅检测主界面环境；独立 AI 引擎的安装状态请查看功能中心。')}</p><div className="dependency-list">{Object.entries(state.dependencies).map(([key, ok]) => <span key={key} className={ok ? 'ready' : 'missing'}>{ok ? '✓' : '○'} {key}</span>)}</div></> : <>
      <p className="dialog-description">{kind === 'image' ? t('选择一张图像建立独立项目，原图不会被修改。') : kind === 'save-detection' ? t('保存当前图像的检测框、类别、置信分数和计数。') : kind === 'import' ? t("选择照片文件夹，包含子文件夹。仅建立索引，原图不会被移动。") : kind === 'person' ? t("给朋友起一个名字，选择一张或多张仅含一张清晰人脸的参考照。") : kind === 'export' ? t("按人物复制原始照片。合照可同时进入多人的相册；请先审核自动匹配结果。") : kind === 'open' ? t("选择之前保存的 project.json，恢复照片与审核结果。") : t('选择保存目录，可导出透明抠图或原图尺寸的黑白掩码。')}</p>
      {kind === 'save-segment' && state.segment && <><Picker label={t('导出内容')} value={output} onChange={key=>setOutput(String(key))} styles={fullWidth}><PickerItem id="cutout">{t('透明抠图')}</PickerItem><PickerItem id="mask">{t('黑白掩码')}</PickerItem></Picker><Picker label={t('导出目标')} value={instance} onChange={key=>setInstance(String(key))} styles={fullWidth}><PickerItem id="all">{t('全部目标合并')}</PickerItem>{state.segment.instances.map((_,i)=><PickerItem id={String(i)} key={i}>{t('目标 {0}',[i+1])}</PickerItem>)}</Picker><Picker isDisabled={output==='mask'} label={t('图像尺寸')} value={output==='mask'?'original':crop} onChange={key=>setCrop(String(key))} styles={fullWidth}><PickerItem id="crop">{t('裁切到目标边界')}</PickerItem><PickerItem id="original">{t('保留原图尺寸')}</PickerItem></Picker><div className="cutout-preview"><img src={asset((instance === 'all' ? state.segment : state.segment.instances[Number(instance)])[output==='mask'?'mask':crop === 'crop' ? 'crop' : 'cutout'],'download')} alt={output==='mask'?t('黑白掩码'):t('透明背景预览')}/></div></>}
      {['person','image','import'].includes(kind)&&<ImageDropZone hint disabled={busy||pending} onImages={async({paths,folder})=>{if(kind==='person'){setPaths(paths);setPath(paths.join('\n'));}else{await onAction('import-drop',{path:folder});onClose();}}}/>}
      {kind === 'person' && <TextField label={t("朋友姓名")} value={name} onChange={setName} placeholder={t("例如：小明")} styles={fullWidth}/>}
      <div className="path-field"><TextField label={kind === 'person' ? t("参考照片路径（每行一张）") : kind === 'open' ? t("项目配置文件") : kind === 'image' ? t('图像文件路径') : t("文件夹路径")} value={path} onChange={v => { setPath(v); setPaths([]); }} placeholder={kind === 'open' ? 'D:\\PhotoProjects\\project.json' : t("粘贴本机路径，或使用右侧选择器")} styles={fullWidth}/><ActionButton aria-label={t("浏览本地文件")} onPress={() => choose(kind === 'person' ? 'references' : kind === 'open' || kind === 'image' ? 'file' : 'folder')}><FolderOpen /></ActionButton></div>
      {['import','image'].includes(kind)&&<p className="microcopy">{t('拖入图片会追加到当前图库；路径导入会打开独立项目。')}</p>}
      {!state.desktop && <p className="microcopy">{t('浏览器中可拖入图片或填写本机路径。')}</p>}
      {kind === 'person' && namesNotice(state, name, t)}
    </>}{err && <div className="dialog-error" role="alert">{t(err)}</div>}</div></Content><ButtonGroup><Button variant="secondary" onPress={onClose} isDisabled={pending}>{t("取消")}</Button><Button variant="accent" onPress={() => void submit()} isPending={pending} isDisabled={busy || kind !== 'settings' && (!path.trim() || kind === 'person' && !name.trim())}>{kind === 'settings' ? t("保存设置") : kind === 'import' || kind === 'image' ? t("导入照片") : kind === 'person' ? t("保存参考照") : kind === 'open' ? t("打开项目") : t("开始导出")}</Button></ButtonGroup></Dialog>;
}
function namesNotice(state: State, name: string, t:(text:string)=>string) { return name in state.config.references ? <p className="microcopy">{t("这位朋友已存在，本次将补充参考照。")}</p> : null; }
createRoot(document.getElementById('root')!).render(<LanguageProvider><App /></LanguageProvider>);
