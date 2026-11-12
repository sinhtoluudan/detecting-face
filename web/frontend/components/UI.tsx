'use client';
import { useEffect, useRef, useState } from 'react';
import { X, Inbox, LoaderCircle } from 'lucide-react';
import { statusLabels } from '@/lib/api';
export function Badge({status}:{status:string}) { return <span className={'badge '+status}><i/>{statusLabels[status]||status}</span>; }
export function Empty({text='Chưa có dữ liệu',hint='Dữ liệu sẽ xuất hiện tại đây sau khi bạn tạo mới.'}:{text?:string,hint?:string}) { return <div className="empty"><Inbox size={32}/><h3>{text}</h3><p>{hint}</p></div>; }
export function Loading(){return <div className="empty"><LoaderCircle className="spin"/><p>Đang tải dữ liệu…</p></div>;}
export function Modal({title,children,onClose}:{title:string,children:React.ReactNode,onClose:()=>void}) {
  const ref=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    const previous=document.activeElement as HTMLElement;
    const el=ref.current;
    const focusables=()=>Array.from(el?.querySelectorAll<HTMLElement>('button,input,select,textarea,[tabindex="0"]')||[]).filter(x=>!x.hasAttribute('disabled'));
    focusables()[0]?.focus();
    const handler=(e:KeyboardEvent)=>{ if(e.key==='Escape') onClose(); if(e.key==='Tab'){const nodes=focusables();const first=nodes[0],last=nodes[nodes.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}} };
    document.addEventListener('keydown',handler); const overflow=document.body.style.overflow;document.body.style.overflow='hidden';
    return ()=>{document.removeEventListener('keydown',handler);document.body.style.overflow=overflow;previous?.focus();};
  },[onClose]);
  return <div className="modal-backdrop"><div className="modal" role="dialog" aria-modal="true" aria-label={title} ref={ref}><div className="modal-head"><h2>{title}</h2><button className="icon-btn" aria-label="Đóng" onClick={onClose}><X size={20}/></button></div>{children}</div></div>;
}
export type Field={name:string,label:string,type?:string,required?:boolean,options?:{value:string,label:string}[],hint?:string,min?:number,max?:number,step?:string};
function WeekdayPicker({name, initial}: {name: string, initial: number[]}) {
  const labels = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ nhật'];
  const [days, setDays] = useState(initial);
  return <fieldset className="wide">
    <legend>Áp dụng vào các thứ trong tuần</legend>
    <div className="weekday-picker">
      {labels.map((label, day) => <label key={day}>
        <input type="checkbox" name={name} value={day} checked={days.includes(day)}
          onChange={e => setDays(e.target.checked ? [...days, day] : days.filter(value => value !== day))}/>
        <span>{label}</span>
      </label>)}
      <label><input type="checkbox" checked={days.length === labels.length}
        onChange={e => setDays(e.target.checked ? labels.map((_, day) => day) : [])}/>
        <span>Áp dụng cho tất cả</span>
      </label>
    </div>
  </fieldset>;
}

export function Editor({fields,values={},busy,onSubmit,onClose,submit='Lưu thay đổi'}:{fields:Field[],values?:Record<string,any>,busy:boolean,onSubmit:(data:Record<string,any>)=>void,onClose:()=>void,submit?:string}){
  return <form onSubmit={e=>{e.preventDefault();const raw=new FormData(e.currentTarget); const d:Record<string,any>={};fields.forEach(f=>{const v=raw.get(f.name);d[f.name]=f.type==='weekdays'?raw.getAll(f.name).map(Number):f.type==='checkbox'?v==='on':f.type==='number'?Number(v):v;});onSubmit(d);}}>
    <div className="form-grid">{fields.map(f=>f.type==='weekdays'?<WeekdayPicker key={f.name} name={f.name} initial={values[f.name]}/>:<label className={f.type==='textarea'?'wide':''} key={f.name}><span>{f.label}{f.required&&' *'}</span>
      {f.options?<select name={f.name} defaultValue={values[f.name]??''} required={f.required}>{f.options.map(o=><option value={o.value} key={o.value}>{o.label}</option>)}</select>:
       f.type==='textarea'?<textarea name={f.name} defaultValue={values[f.name]||''} rows={3} required={f.required} maxLength={1000}/>:
       f.type==='checkbox'?<input className="checkbox" type="checkbox" name={f.name} defaultChecked={values[f.name]??true}/>:
       <input name={f.name} type={f.type||'text'} defaultValue={values[f.name]??''} required={f.required} min={f.min} max={f.max} step={f.step} maxLength={f.type==='password'?128:200} autoComplete={f.type==='password'?'new-password':undefined}/>}
       {f.hint&&<small>{f.hint}</small>}
    </label>)}</div><div className="modal-actions"><button type="button" className="btn secondary" onClick={onClose} disabled={busy}>Hủy</button><button className="btn primary" disabled={busy}>{busy?'Đang lưu…':submit}</button></div>
  </form>;
}
