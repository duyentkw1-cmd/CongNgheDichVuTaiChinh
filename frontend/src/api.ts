export class ApiError extends Error { constructor(message:string,public status:number){super(message);} }
export async function api<T>(path:string, init:RequestInit={}):Promise<T>{
  const headers:Record<string,string>={'X-Requested-With':'so-thu-chi',...(init.headers as Record<string,string>||{})};
  if(init.body && !(init.body instanceof FormData)) headers['Content-Type']='application/json';
  let response:Response;
  try{response=await fetch(path,{...init,headers,credentials:'same-origin'});}catch{throw new ApiError('Chưa kết nối được máy chủ. Kiểm tra cửa sổ chạy demo và thử lại.',0);}
  if(!response.ok){let message='Chưa thực hiện được thao tác.';try{const data=await response.json();message=typeof data.detail==='string'?data.detail:data.detail?.map((x:{msg:string})=>x.msg.replace('Value error, ','')).join(' · ')||message;}catch{}throw new ApiError(message,response.status);}
  return response.json();
}
export const post=<T,>(path:string,body:unknown)=>api<T>(path,{method:'POST',body:JSON.stringify(body)});
export const money=(amount:number)=>new Intl.NumberFormat('vi-VN').format(amount)+' ₫';
export const shortMoney=(amount:number)=>amount>=1000000?(amount/1000000).toLocaleString('vi-VN',{maximumFractionDigits:1})+'tr':amount>=1000?(amount/1000).toLocaleString('vi-VN',{maximumFractionDigits:0})+'k':String(amount);
export const prettyDate=(date:string)=>date.split('-').reverse().join('/');

// Request IDs prevent duplicate saves; no authentication secret is derived here.
export function newRequestId(){
  if(typeof crypto.randomUUID==='function')return crypto.randomUUID();
  const bytes=new Uint8Array(16);crypto.getRandomValues(bytes);
  return Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');
}
