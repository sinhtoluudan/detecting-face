'use client';

import {useEffect, useState} from 'react';
import {api, Row, vnDate, vnTime} from '@/lib/api';
import FaceCamera from './Camera';

export default function ShiftCamera({onRecorded}: {onRecorded: () => void}) {
  const [status, setStatus] = useState<Row | null>(null);
  const [error, setError] = useState('');
  const [recordedId, setRecordedId] = useState<string>();

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const result = await api('/attendance/today');
        if (!cancelled) {
          setStatus(result);
          setError('');
        }
      } catch (err) {
        if (!cancelled) setError((err as Error).message);
      } finally {
        if (!cancelled) timer = setTimeout(refresh, 15000);
      }
    }
    refresh();
    return () => { cancelled = true; clearTimeout(timer); };
  }, []);

  const shift = status?.active_assignment;
  const attendance = shift?.attendance;
  const checkedAt = attendance?.check_in || attendance?.check_out;
  const source = attendance?.source;
  const recordedVia = source === 'face' ? 'bằng khuôn mặt'
    : source === 'manual' ? 'thủ công'
    : source === 'correction' ? 'qua đơn bổ sung'
    : '';
  const message = error || (!status ? 'Đang kiểm tra ca làm việc…'
    : !shift ? 'Chỉ có thể chấm công trong giờ của ca đã được phân.'
    : shift.id === recordedId ? 'Chấm công thành công.'
    : checkedAt ? `Ca này đã có bản ghi chấm công${recordedVia ? ' ' + recordedVia : ''} lúc ${vnTime(checkedAt)} ngày ${vnDate(checkedAt)}.`
    : shift.attendance ? 'Ca này đã có bản ghi chấm công.'
    : !status.face_enabled ? 'Nhận diện khuôn mặt chưa được bật.'
    : status.face_samples < 5 ? 'Cần đăng ký ít nhất 5 mẫu khuôn mặt trước khi chấm công.'
    : '');

  return <section className="card">
    <div className="card-head"><h3>Camera chấm công</h3></div>
    {message ? <p role="status">{message}</p> :
      <FaceCamera key={shift.id} assignmentId={shift.id} action="in" onDone={() => {
        setRecordedId(shift.id);
        onRecorded();
      }}/>}
  </section>;
}
