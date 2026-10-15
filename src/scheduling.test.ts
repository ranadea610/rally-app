import test from 'node:test';
import assert from 'node:assert/strict';
import {seedSlots,reserve,weekStart,dateKey,type Profile} from './scheduling.ts';
const profile: Profile={id:'alex',name:'Alex',method:'Discord',contact:'alex',role:'both'};
test('sample availability is on practice days and consists of 15-minute slots',()=>{const slots=seedSlots(new Date(2026,9,15));assert.ok(slots.length>0);for(const s of slots){assert.ok([1,2,4].includes(new Date(s.date+'T12:00:00').getDay()));assert.equal(s.start%15,0);assert.ok(s.start>=1110&&s.start<1260);}assert.equal(new Set(slots.map(s=>s.id)).size,slots.length);});
test('booking reserves exactly one slot and rejects a second booking',()=>{const slots=seedSlots(new Date(2026,9,15));const free=slots.find(s=>!s.bookedBy)!;const booked=reserve(slots,free.id,profile);assert.equal(booked.find(s=>s.id===free.id)?.bookedBy,'alex');assert.equal(slots.find(s=>s.id===free.id)?.bookedBy,undefined);assert.throws(()=>reserve(booked,free.id,profile));});
test('a player cannot book two coaches at the same time',()=>{const slots=seedSlots(new Date(2026,9,15));const first=slots.find(s=>s.start===1140&&s.coachId==='john')!;const second=slots.find(s=>s.start===1140&&s.date===first.date&&s.coachId==='joe')!;assert.throws(()=>reserve(reserve(slots,first.id,profile),second.id,profile));});
test('weeks begin on Monday including a Sunday selection',()=>{assert.equal(dateKey(weekStart(new Date(2026,9,18))),'2026-10-12');});
