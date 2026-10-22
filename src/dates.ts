// Calendar date objects represent club-local dates, never appointment instants.
export const dayKey=(d:Date)=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
export const dateOf=(key:string)=>new Date(key+'T12:00:00');
const formatters=new Map<string,Intl.DateTimeFormat>();
export function parts(iso:string,zone:string){let formatter=formatters.get(zone);if(!formatter){formatter=new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});formatters.set(zone,formatter);}const p=formatter.formatToParts(new Date(iso));const get=(t:string)=>p.find(x=>x.type===t)!.value;return {day:`${get('year')}-${get('month')}-${get('day')}`,minutes:Number(get('hour'))*60+Number(get('minute'))};}
export const today=(zone:string)=>dateOf(parts(new Date().toISOString(),zone).day);
export const clock=(iso:string,zone:string)=>new Date(iso).toLocaleTimeString('en-US',{timeZone:zone,hour:'numeric',minute:'2-digit'});
export const fullDate=(d:Date)=>d.toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric'});
export const time=(m:number)=>`${Math.floor(m/60)%12||12}:${String(m%60).padStart(2,'0')} ${m>=720?'PM':'AM'}`;
export function addDays(d:Date,n:number){const next=new Date(d);next.setDate(next.getDate()+n);return next;}
export function monday(d:Date){return addDays(d,-(d.getDay()+6)%7);}
export function instant(day:string,minute:number,zone:string){
 // Resolve the offset for the actual practice date, including DST changes.
 const desired=Date.parse(`${day}T${String(Math.floor(minute/60)).padStart(2,'0')}:${String(minute%60).padStart(2,'0')}:00Z`);
 let guess=desired;
 for(let i=0;i<3;i++){const p=parts(new Date(guess).toISOString(),zone);const rendered=Date.parse(`${p.day}T${String(Math.floor(p.minutes/60)).padStart(2,'0')}:${String(p.minutes%60).padStart(2,'0')}:00Z`);guess+=desired-rendered;}
 return new Date(guess).toISOString();
}
