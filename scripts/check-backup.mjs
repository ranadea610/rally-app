// Restore verification only: creates a NEW disposable database, never overwrites one.
import {execFileSync,spawn} from 'node:child_process';
import {createReadStream} from 'node:fs';
import {pipeline} from 'node:stream/promises';
import {randomUUID} from 'node:crypto';
if(process.env.RALLY_ALLOW_TEST_DATA!=='1'||!process.argv[2])throw new Error('Usage on a disposable CI stack: RALLY_ALLOW_TEST_DATA=1 node scripts/check-backup.mjs BACKUP.dump');
const database='rally_restore_'+randomUUID().slice(0,8)+'_test';
execFileSync('docker',['compose','exec','-T','db','createdb','-U','rally',database],{stdio:'inherit'});
const child=spawn('docker',['compose','exec','-T','db','pg_restore','--exit-on-error','-U','rally','-d',database],{stdio:['pipe','inherit','inherit'],windowsHide:true});
const completed=new Promise((resolve,reject)=>{child.on('error',reject);child.on('close',code=>code===0?resolve():reject(new Error('Backup restore failed.')));});
await Promise.all([pipeline(createReadStream(process.argv[2]),child.stdin),completed]);
const count=Number(execFileSync('docker',['compose','exec','-T','db','psql','-U','rally','-d',database,'-Atc','SELECT count(*) FROM users'],{encoding:'utf8'}).trim());
if(!(count>=1))throw new Error('Restored database is missing the smoke-test account.');
console.log('Backup restore verified in a fresh disposable database.');
