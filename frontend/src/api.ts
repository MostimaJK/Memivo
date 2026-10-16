export const token = new URLSearchParams(location.hash.slice(1)).get('token') || sessionStorage.getItem('sf-token') || '';
if (token) sessionStorage.setItem('sf-token', token);
export async function api<T=any>(route: string, payload?: unknown): Promise<T> {
  const response = await fetch('/api/' + route, {method: payload === undefined ? 'GET' : 'POST', headers: {'Content-Type':'application/json','X-Memivo-Token': token}, body: payload === undefined ? undefined : JSON.stringify(payload)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || '操作失败');
  return data;
}
export function asset(id: string, size = 'thumb') {return `/api/image?id=${encodeURIComponent(id)}&size=${size}&token=${encodeURIComponent(token)}`;}
export type UploadedImages={paths:string[];folder:string};
export async function uploadImages(files:File[]):Promise<UploadedImages> {
  if(!files.length||files.some(file=>! /\.(jpe?g|png|webp|bmp|tiff?)$/i.test(file.name)))throw new Error('请拖入支持的图片文件。');
  if(files.some(file=>!file.size||file.size>64*1024*1024))throw new Error('单张拖入图片不能超过 64 MB。');
  const batch=crypto.randomUUID(),paths:string[]=[];let folder='';
  for(const file of files){
    const response=await fetch(`/api/upload-image?batch=${batch}&name=${encodeURIComponent(file.name)}`,{
      method:'POST',headers:{'X-Memivo-Token':token,'Content-Type':'application/octet-stream'},body:file});
    const result=await response.json();if(!response.ok)throw new Error(result.error||'操作失败');
    paths.push(result.path);folder=result.folder;
  }
  return {paths,folder};
}
export type Face = {bbox:number[]; identity:string|null; status:string; candidates:{name:string;score:number}[]};
export type Photo = {id:string;name:string;path:string;faces:Face[];error:string|null;processed:boolean;width?:number;height?:number};
export type Detection = {photo:string;source:string;model:string;conf:number;iou:number;width:number;height:number;detections:{class_id:number;name:string;confidence:number;bbox:number[]}[];counts:{class_id:number;name:string;count:number}[];total:number};
export type Segment = {photo:string;count:number;width:number;height:number;directory:string;mask:string;cutout:string;crop:string;overlay:string;instances:{cutout:string;crop:string;mask:string;bbox:number[]}[]};
export type Annotation = {id:string;class_id:number;type:'box'|'polygon';bbox?:number[];points?:number[][];source?:string};
export type DatasetImage = {id:string;file_id:string;name:string;width:number;height:number;group:string;split:string;reviewed:boolean;negative:boolean;annotations:Annotation[];revision:number};
export type Dataset = {id:string;name:string;task:'detect'|'segment';revision:number;classes:{id:number;name:string}[];images:DatasetImage[]};
export type DatasetState = {items:{id:string;name:string;task:string;count:number}[];active:Dataset|null;versions:{id:string;created:string;task:string;counts:Record<string,number>;revision:number;excluded:number}[]};
export type TrainingRun = {id:string;dataset:string;version:string;task:string;state:string;created:string;updated:string;options:{epochs:number;imgsz:number;batch:number;device:string};metrics:Record<string,number>[];best:string;error:string;can_resume:boolean;evaluation:null|{metrics:Record<string,number>;count_mae:number;images:number;count_conf:number}};
export type Runtimes = {hardware:null|{os:string;architecture:string;python:string;free_gb:number;gpus:{name:string;driver:string;memory_mb:number;capability:number}[];cuda_candidate:boolean;recommended:string;checked:boolean;driver_cuda_max?:string;diagnostic?:string};engines:{id:string;feature?:string;state:string;profile?:string;available:boolean;bytes?:number;error?:string}[];logs:string[];root:string;last_feature:string;log_root?:string;log_file?:string;last_failure?:{message:string;time:string;log_file:string}|null};
export type Config = {source:string;workspace:string;detector:string;recognition:string;sam:string;yolo:string;device:string;threshold:number;margin:number;references:Record<string,string[]>};
export type ModelEntry = {id:string;family:string;variant:string;task:string;role:string;label:string;relative:string;page:string;license:string;mode:'download'|'official';size?:number;sha256?:string;installed:boolean};
export type ModelLibrary = {root:string;checked:string;items:Record<string,{path:string;name:string;relative:string;bytes:number}[]>;models:ModelEntry[]};
export type State = {models:ModelLibrary;preferences:{language:string};config:Config;photos:Photo[];task:{state:string;kind:string;done:number;total:number;message:string;error?:string;log_file?:string};history:any[];dependencies:Record<string,boolean>;desktop:boolean;detection:Detection|null;segment:Segment|null;runtimes:Runtimes;datasets:DatasetState;training:TrainingRun[]};
