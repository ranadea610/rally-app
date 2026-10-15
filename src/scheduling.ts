export type Role = 'player' | 'coach' | 'both';
export interface Profile { id: string; name: string; method: string; contact: string; role: Role }
export interface Slot { id: string; date: string; coachId: string; coach: string; start: number; bookedBy?: string; player?: string }
export const dateKey = (d: Date) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
export const time = (m: number) => `${Math.floor(m/60)%12 || 12}:${String(m%60).padStart(2,'0')} ${m>=720?'PM':'AM'}`;
export const slotId = (date: string, coach: string, start: number) => `${date}/${coach}/${start}`;
export function weekStart(date: Date) { const d = new Date(date); d.setDate(d.getDate() - (d.getDay()+6)%7); return d; }
export function seedSlots(today: Date): Slot[] {
  const slots: Slot[] = [];
  for(let offset=-35; offset<100; offset++) { const d = new Date(today); d.setDate(d.getDate()+offset); if(![1,2,4].includes(d.getDay())) continue;
    for(const [i,coach] of ['John','Joe'].entries()) for(let m=1110+i*30;m<1230+i*15;m+=15) { const date=dateKey(d); slots.push({id:slotId(date,coach.toLowerCase(),m), date, coachId:coach.toLowerCase(),coach,start:m,...(m===1170?{bookedBy:'sample',player:'Club member'}:{})}); }
  } return slots;
}
export function reserve(slots: Slot[], id: string, profile: Profile): Slot[] {
  const target=slots.find(s=>s.id===id);
  if(!target || target.bookedBy) throw new Error('This slot is no longer available.');
  if(slots.some(s=>s.date===target.date && s.start===target.start && s.bookedBy===profile.id)) throw new Error('You already have a session at this time.');
  return slots.map(s=>s.id===id?{...s,bookedBy:profile.id,player:profile.name}:s);
}
