'use client';
import { useEffect,useRef,useState } from 'react';
import { Camera, CheckCircle2, VideoOff } from 'lucide-react';
import { write } from '@/lib/api';
export default function FaceCamera({userId,assignmentId,action,onDone}:{userId?:string,assignmentId?:string,action?:'in'|'out',onDone:()=>void}){
  const video=useRef<HTMLVideoElement>(null),stream=useRef<MediaStream|null>(null),stopped=useRef(false);
  const [message,setMessage]=useState('Đang mở camera…'),[count,setCount]=useState(0),[done,setDone]=useState(false),[error,setError]=useState(false);
  useEffect(()=>{
    let cancelled=false,timer:ReturnType<typeof setTimeout>;
    const attempt=crypto.randomUUID(); const started=Date.now(); stopped.current=false;
    const stop=()=>{stopped.current=true;stream.current?.getTracks().forEach(t=>t.stop());};
    async function frame(){
      if(cancelled||stopped.current||!video.current) return;
      if(Date.now()-started>180000){setMessage('Đã hết thời gian camera. Đóng và mở lại để tiếp tục.');stop();return;}
      if(!video.current.videoWidth){timer=setTimeout(frame,500);return;}
      const canvas=document.createElement('canvas');canvas.width=640;canvas.height=Math.round(640*video.current.videoHeight/video.current.videoWidth);
      canvas.getContext('2d')!.drawImage(video.current,0,0,canvas.width,canvas.height);
      const image=canvas.toDataURL('image/jpeg',0.85);
      try{
        const result=userId?await write(`/faces/${userId}/enroll`,{image,consent:true}):await write('/faces/punch',{image,assignment_id:assignmentId,action,attempt_id:attempt});
        if(cancelled)return;
        setError(false);setCount(result.samples||result.count);setMessage(result.message);
        if(result.confirmed||(userId&&result.samples>=20)){setDone(true);stop();onDone();return;}
      }catch(e){
        if(cancelled)return;
        const err=e as Error & {status:number};setMessage(err.message);setError(true);
        if(!userId)setCount(0);
        if([401,403,503,429].includes(err.status)||(err.status===409&&!userId)){stop();return;}
      }
      if(!cancelled&&!stopped.current)timer=setTimeout(frame,userId?1300:800);
    }
    async function start(){
      try{
        if(!navigator.mediaDevices)throw new Error('Camera cần localhost hoặc HTTPS. Hãy mở web trên localhost:3000.');
        const media=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:640},height:{ideal:480},facingMode:'user'},audio:false});
        if(cancelled){media.getTracks().forEach(t=>t.stop());return;}
        stream.current=media;video.current!.srcObject=media;await video.current!.play();
        setMessage(userId?'Nhìn thẳng rồi xoay nhẹ. Hệ thống tự lưu các mẫu khác nhau.':'Đưa khuôn mặt vào khung. Hệ thống tự xác nhận 3 ảnh liên tiếp.');
        timer=setTimeout(frame,1200);
      }catch(e){if(!cancelled){setError(true);setMessage((e as Error).message);stop();}}
    }
    start();return ()=>{cancelled=true;clearTimeout(timer);stop();};
  // Camera session is intentionally fixed until this component is unmounted.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[]);
  return <div className="camera-panel"><div className="camera-stage"><video ref={video} playsInline muted/><div className={'face-guide '+(done?'success':'')}/><div className="camera-label">{done?<CheckCircle2 size={16}/>:<Camera size={16}/>} {userId?'Đăng ký mẫu':'Xác minh khuôn mặt'}</div></div>
    <div className={'camera-message '+(error?'error':'')} role="status">{done&&<CheckCircle2/>}<p>{message}</p></div>
    <div className="sample-progress"><div style={{width:`${Math.min(100,count/(userId?20:3)*100)}%`}}/></div><p className="muted small">{userId?`${count} mẫu · tối thiểu 5 · mục tiêu 20`:`${count}/3 ảnh được xác nhận`}</p>
    <div className="notice"><VideoOff size={17}/><span>Không lưu ảnh/video gốc. Bản này chưa có chống giả mạo bằng ảnh hoặc video.</span></div></div>;
}
