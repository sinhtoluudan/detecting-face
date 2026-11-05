let csrf = '';
export function setCsrf(value: string) { csrf = value; }
export async function api(path: string, options: RequestInit = {}) {
  const response = await fetch('/api'+path, { signal: AbortSignal.timeout(path.startsWith('/faces/') ? 90000 : 15000), ...options, credentials: 'include', cache: 'no-store',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf, ...options.headers } });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(body.detail) ? body.detail.map((x: {msg:string})=>x.msg).join('; ') : body.detail;
    const error = new Error(detail || 'Không thể xử lý yêu cầu. Vui lòng thử lại.') as Error & {status:number};
    error.status=response.status;
    throw error;
  }
  return body;
}
export const write = (path:string, data:unknown, method='POST') => api(path,{method,body:JSON.stringify(data)});
export type Row = Record<string, any>;
export const roles:Record<string,string> = {admin:'Quản trị viên',hr:'Nhân sự',manager:'Quản lý',employee:'Nhân viên'};
export const statusLabels:Record<string,string> = {present:'Đủ công',late:'Đi trễ',early:'Về sớm',absent:'Vắng mặt',leave:'Nghỉ phép',scheduled:'Chưa đến ca',working:'Đang làm',missing_out:'Thiếu lượt ra',pending:'Chờ duyệt',approved:'Đã duyệt',rejected:'Từ chối',cancelled:'Đã hủy'};
export const requestLabels:Record<string,string> = {leave:'Nghỉ phép',correction:'Bổ sung / sửa công',overtime:'Tăng ca',remote:'Làm từ xa',business:'Công tác',late_early:'Đi trễ / về sớm'};
export const vnDate=(v:string)=>v ? new Date(v.length===10?v+'T12:00:00+07:00':v).toLocaleDateString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'}):'—';
export const vnTime=(v:string)=>v ? new Date(v).toLocaleTimeString('vi-VN',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Ho_Chi_Minh'}):'—';
export const todayVN=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Ho_Chi_Minh',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
export const hours=(m:number)=>new Intl.NumberFormat('vi-VN',{maximumFractionDigits:1}).format((m||0)/60);
export const initials=(name:string)=>name.split(' ').slice(-2).map(v=>v[0]).join('');
