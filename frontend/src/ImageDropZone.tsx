import React,{useRef,useState} from 'react';
import {uploadImages,type UploadedImages} from './api';
import {useI18n} from './i18n';

/** Native file drops and the accessible file picker share the same local upload path. */
export function ImageDropZone({children,className='',disabled=false,onImages,hint=false}:{
  children?:React.ReactNode;className?:string;disabled?:boolean;hint?:boolean;
  onImages:(images:UploadedImages)=>Promise<void>;
}) {
  const {t}=useI18n(),depth=useRef(0);
  const [over,setOver]=useState(false),[uploading,setUploading]=useState(false),[error,setError]=useState('');
  const locked=useRef(false);
  const receive=async(files:File[])=>{
    if(disabled||locked.current){setError(t('请等待当前任务完成后再导入。'));return;}
    locked.current=true;setUploading(true);setError('');
    try{await onImages(await uploadImages(files));}
    catch(e){setError(t((e as Error).message));}
    finally{locked.current=false;setUploading(false);}
  };
  return <div className={'image-drop-zone '+className+(over?' drop-active':'')}
    onDragEnter={e=>{if(e.dataTransfer.types.includes('Files')){e.preventDefault();e.stopPropagation();depth.current++;setOver(true);}}}
    onDragOver={e=>{if(e.dataTransfer.types.includes('Files')){e.preventDefault();e.stopPropagation();e.dataTransfer.dropEffect=disabled||uploading?'none':'copy';}}}
    onDragLeave={e=>{e.stopPropagation();if(--depth.current<=0){depth.current=0;setOver(false);}}}
    onDrop={e=>{e.preventDefault();e.stopPropagation();depth.current=0;setOver(false);void receive(Array.from(e.dataTransfer.files));}}>
    {children}
    {hint&&<label className="drop-picker">{t('拖入图片，或点击选择图片')}<input type="file" multiple accept=".jpg,.jpeg,.png,.webp,.bmp,.tif,.tiff" disabled={disabled||uploading}
      onChange={e=>{void receive(Array.from(e.target.files||[]));e.target.value='';}}/></label>}
    {(over||uploading)&&<div className="drop-indicator" role="status">{uploading?t('正在导入图片…'):t('松开以导入图片')}</div>}
    {error&&<div className="drop-error" role="alert">{error}<button aria-label={t('关闭')} onClick={()=>setError('')}>×</button></div>}
  </div>;
}
