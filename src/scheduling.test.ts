import test from 'node:test';
import assert from 'node:assert/strict';
import {seedSlots,reserve,weekStart,dateKey,type Profile, type Slot, type TrainingType, TRAINING_TYPES, equipmentAvailable, cancelReservation} from './scheduling.ts';
const profile: Profile={id:'alex',name:'Alex',method:'Discord',contact:'alex',role:'both'};
test('sample availability is on practice days and consists of 15-minute slots',()=>{const slots=seedSlots(new Date(2026,9,15));assert.ok(slots.length>0);for(const s of slots){assert.ok([1,2,4].includes(new Date(s.date+'T12:00:00').getDay()));assert.equal(s.start%15,0);assert.ok(s.start>=1110&&s.start<1260);}assert.equal(new Set(slots.map(s=>s.id)).size,slots.length);});
test('booking reserves exactly one slot and rejects a second booking',()=>{const slots=seedSlots(new Date(2026,9,15));const free=slots.find(s=>!s.bookedBy)!;const booked=reserve(slots,free.id,profile,'rally');assert.equal(booked.find(s=>s.id===free.id)?.bookedBy,'alex');assert.equal(slots.find(s=>s.id===free.id)?.bookedBy,undefined);assert.throws(()=>reserve(booked,free.id,profile,'rally'));});
test('a player cannot book two coaches at the same time',()=>{const slots=seedSlots(new Date(2026,9,15));const first=slots.find(s=>s.start===1140&&s.coachId==='john')!;const second=slots.find(s=>s.start===1140&&s.date===first.date&&s.coachId==='joe')!;assert.throws(()=>reserve(reserve(slots,first.id,profile,'rally'),second.id,profile,'rally'));});
test('weeks begin on Monday including a Sunday selection',()=>{assert.equal(dateKey(weekStart(new Date(2026,9,18))),'2026-10-12');});

const equipmentSlots: Slot[]=[
 {id:'john-slot',date:'2026-10-19',coachId:'john',coach:'John',start:1140},
 {id:'joe-slot',date:'2026-10-19',coachId:'joe',coach:'Joe',start:1140},
 {id:'later-slot',date:'2026-10-19',coachId:'joe',coach:'Joe',start:1155},
];
const other: Profile={...profile,id:'other',name:'Other Player'};
test('each equipment training type blocks all equipment types across coaches',()=>{
 const types=TRAINING_TYPES.filter(t=>t.equipment);
 for(const first of types)for(const second of types){
  const booked=reserve(equipmentSlots,'john-slot',profile,first.id);
  assert.equal(booked[0].trainingType,first.id);
  assert.equal(equipmentAvailable(booked,equipmentSlots[1]),false);
  assert.throws(()=>reserve(booked,'joe-slot',other,second.id),/already reserved/);
 }
});
test('rally and short game can be booked while shared equipment is occupied',()=>{
 for(const type of ['rally','short-game'] as const){const booked=reserve(equipmentSlots,'john-slot',profile,'multi-ball');assert.equal(reserve(booked,'joe-slot',other,type)[1].trainingType,type);}
 for(const type of ['rally','short-game'] as const){const booked=reserve(equipmentSlots,'john-slot',profile,type);assert.doesNotThrow(()=>reserve(booked,'joe-slot',other,'multi-ball'));}
});
test('adjacent sessions and different dates do not conflict for equipment',()=>{
 const booked=reserve(equipmentSlots,'john-slot',profile,'serve-practice');
 assert.doesNotThrow(()=>reserve(booked,'later-slot',other,'receive-practice'));
 const nextDay={...equipmentSlots[1],id:'next-day',date:'2026-10-20'};
 assert.doesNotThrow(()=>reserve([...booked,nextDay],nextDay.id,other,'serve-receive'));
});
test('canceling releases equipment and clears training without affecting other bookings',()=>{
 const booked=reserve(equipmentSlots,'john-slot',profile,'multi-ball');
 const canceled=cancelReservation(booked,'john-slot',profile.id);
 assert.equal(canceled[0].trainingType,undefined);assert.equal(canceled[0].bookedBy,undefined);
 assert.equal(equipmentAvailable(canceled,equipmentSlots[1]),true);
 assert.doesNotThrow(()=>reserve(canceled,'joe-slot',other,'serve-practice'));
 assert.deepEqual(cancelReservation(booked,'john-slot',other.id),booked);
});
test('invalid training types cannot be booked and legacy bookings still load',()=>{
 assert.throws(()=>reserve(equipmentSlots,'john-slot',profile,'invalid' as TrainingType),/Choose a training/);
 const legacy=[{...equipmentSlots[0],bookedBy:'legacy'},equipmentSlots[1]];
 assert.doesNotThrow(()=>reserve(legacy,'joe-slot',other,'multi-ball'));
});
