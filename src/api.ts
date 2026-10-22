export type Role = 'player' | 'coach' | 'both';
export interface User { id:string; name:string; contact_method:string; contact:string; requested_role:Role; coach_approved:boolean; is_admin:boolean }
export interface Auth { user:User; csrf_token:string }
export interface CalendarSlot { availability_id:string; coach_id:string; coach_name:string; starts_at:string; ends_at:string; booked:boolean; equipment_available:boolean }
export interface Calendar { timezone:string; slots:CalendarSlot[] }
export interface Window { id:string; coach_id:string; starts_at:string; ends_at:string }
export interface Reservation { id:string; coach_id:string; coach_name:string; player_id:string; player_name:string; training_type_id:string; training_type:string; starts_at:string; ends_at:string; status:'active'|'canceled'; equipment:{id:string;name:string}[] }
export interface Training { id:string; name:string; equipment_ids:string[]; available:boolean; reason:string|null }
export interface Options { slot_available:boolean; training_types:Training[] }
export class ApiError extends Error { constructor(public status:number,message:string){super(message);} }
let csrf='';
export function setSession(auth:Auth|null){csrf=auth?.csrf_token??'';}
const base=(import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/,'');
async function request<T>(path:string,method='GET',body?:unknown):Promise<T>{
 let response:Response;
 try{response=await fetch(base+path,{method,credentials:'include',cache:'no-store',headers:{...(body!==undefined?{'Content-Type':'application/json'}:{}),...(method!=='GET'?{'X-CSRF-Token':csrf}:{})},...(body!==undefined?{body:JSON.stringify(body)}:{})});}
 catch{throw new ApiError(0,'Could not reach Rally. Check your connection and try again.');}
 if(!response.ok){let message=response.status===429?'Too many sign-in attempts. Please wait a minute and try again.':'Something went wrong. Please try again.';try{const data=await response.json();message=typeof data.detail==='string'?data.detail:Array.isArray(data.detail)?data.detail.map((e:{msg:string})=>e.msg).join(' '):message;}catch{/* Keep a useful error for proxy failures. */}
 if(response.status===401&&!['/auth/login','/auth/register'].includes(path))window.dispatchEvent(new Event('rally-session-expired'));
 throw new ApiError(response.status,message);}
 if(response.status===204)return undefined as T;
 try{return await response.json();}catch{throw new ApiError(0,'Rally returned an unexpected response. Check the API connection.');}
}
const query=(values:Record<string,string>)=>new URLSearchParams(values).toString();
export const api={
 me:()=>request<Auth>('/auth/me'),
 login:(body:unknown)=>request<Auth>('/auth/login','POST',body),
 register:(body:unknown)=>request<Auth>('/auth/register','POST',body),
 logout:()=>request<void>('/auth/logout','POST'),
 calendar:(start:string,end:string)=>request<Calendar>('/calendar?'+query({start,end})),
 reservations:()=>request<Reservation[]>('/reservations'),
 coachReservations:(start:string,end:string)=>request<Reservation[]>('/coach/reservations?'+query({start,end})),
 windows:(start:string,end:string)=>request<Window[]>('/coach/availability?'+query({start,end})),
 saveWeek:(week_start:string,windows:{starts_at:string;ends_at:string}[])=>request<Window[]>('/coach/availability/week','PUT',{week_start,windows}),
 options:(slot:CalendarSlot)=>request<Options>('/booking-options?'+query({coach_id:slot.coach_id,starts_at:slot.starts_at})),
 book:(slot:CalendarSlot,training_type_id:string)=>request<Reservation>('/reservations','POST',{coach_id:slot.coach_id,starts_at:slot.starts_at,training_type_id}),
 cancel:(id:string)=>request<Reservation>('/reservations/'+encodeURIComponent(id),'DELETE'),
 requests:()=>request<User[]>('/admin/coach-requests'),
 approve:(id:string)=>request<User>('/admin/coaches/'+encodeURIComponent(id)+'/approve','POST'),
};
