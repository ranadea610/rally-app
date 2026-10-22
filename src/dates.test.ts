import test from 'node:test';
import assert from 'node:assert/strict';
import {instant,parts,dayKey,dateOf,monday,addDays} from './dates.ts';
test('practice instants use the club timezone in winter and summer',()=>{
 assert.equal(instant('2030-01-07',1110,'America/Los_Angeles'),'2030-01-08T02:30:00.000Z');
 assert.equal(instant('2030-07-01',1110,'America/Los_Angeles'),'2030-07-02T01:30:00.000Z');
});
test('calendar groups slots by club-local date rather than UTC or browser timezone',()=>{
 assert.deepEqual(parts('2030-01-08T02:45:00Z','America/Los_Angeles'),{day:'2030-01-07',minutes:1125});
 assert.deepEqual(parts('2030-01-08T02:45:00Z','Asia/Tokyo'),{day:'2030-01-08',minutes:705});
});
test('week navigation handles month boundaries',()=>{
 assert.equal(dayKey(monday(dateOf('2026-11-01'))),'2026-10-26');
 assert.equal(dayKey(addDays(dateOf('2026-10-26'),7)),'2026-11-02');
});
