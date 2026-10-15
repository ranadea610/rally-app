export type Role = 'player' | 'coach' | 'both';
export interface Profile { id: string; name: string; method: string; contact: string; role: Role }
export const TRAINING_TYPES = [
  { id: 'rally', label: 'Rally (recommended for beginners)', equipment: false },
  { id: 'multi-ball', label: 'Multi-ball', equipment: true },
  { id: 'serve-practice', label: 'Serve practice', equipment: true },
  { id: 'receive-practice', label: 'Receive practice', equipment: true },
  { id: 'serve-receive', label: 'Serve/receive', equipment: true },
  { id: 'short-game', label: 'Short game (pushes)', equipment: false },
] as const;
export type TrainingType = typeof TRAINING_TYPES[number]['id'];
export interface Slot { id: string; date: string; coachId: string; coach: string; start: number; bookedBy?: string; player?: string; trainingType?: TrainingType }
export const trainingLabel = (type?: TrainingType) => TRAINING_TYPES.find(t=>t.id===type)?.label;
export function equipmentAvailable(slots: Slot[], target: Slot): boolean {
  // The club has one shared set: training balls and a ball catcher.
  return !slots.some(s=>s.id!==target.id && s.bookedBy && TRAINING_TYPES.some(t=>t.id===s.trainingType && t.equipment)
    && s.date===target.date && s.start<target.start+15 && target.start<s.start+15);
}
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
export function reserve(slots: Slot[], id: string, profile: Profile, trainingType: TrainingType): Slot[] {
  const training=TRAINING_TYPES.find(t=>t.id===trainingType);
  if(!training) throw new Error('Choose a training type to book your session.');
  const target=slots.find(s=>s.id===id);
  if(!target || target.bookedBy) throw new Error('This slot is no longer available.');
  if(slots.some(s=>s.date===target.date && s.start===target.start && s.bookedBy===profile.id)) throw new Error('You already have a session at this time.');
  if(training.equipment && !equipmentAvailable(slots,target)) throw new Error('The training balls and ball catcher are already reserved at this time. Choose rally, short game, or a different time.');
  return slots.map(s=>s.id===id?{...s,bookedBy:profile.id,player:profile.name,trainingType}:s);
}
export function cancelReservation(slots: Slot[], id: string, playerId: string): Slot[] {
  return slots.map(s=>{if(s.id!==id||s.bookedBy!==playerId)return s;const {bookedBy,player,trainingType,...available}=s;return available;});
}
