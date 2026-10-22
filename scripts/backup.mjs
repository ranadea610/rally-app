import {spawn} from 'node:child_process';
import {createWriteStream,mkdirSync,renameSync} from 'node:fs';
import {pipeline} from 'node:stream/promises';
import {resolve} from 'node:path';
import {randomUUID} from 'node:crypto';
const development=process.argv.includes('--development');
if(process.argv.slice(2).some(arg=>arg!=='--development'))throw new Error('Usage: node scripts/backup.mjs [--development]');
const root=resolve('backups');mkdirSync(root,{recursive:true,mode:0o700});
const name=`rally-${new Date().toISOString().replaceAll(':','-')}-${randomUUID().slice(0,8)}.dump`;
const destination=resolve(root,name),partial=destination+'.partial';
const args=development?['compose']:['compose','--project-name','rally-production','--env-file','deploy/.env.production','-f','compose.production.yaml'];
args.push('exec','-T','db','pg_dump','-U','rally','-d','rally','--format=custom');
const child=spawn('docker',args,{stdio:['ignore','pipe','inherit'],windowsHide:true});
const completed=new Promise((resolve,reject)=>{child.on('error',reject);child.on('close',code=>code===0?resolve():reject(new Error(`pg_dump failed (${code}). Incomplete backup retained at ${partial}`)));});
try{await Promise.all([pipeline(child.stdout,createWriteStream(partial,{flags:'wx',mode:0o600})),completed]);renameSync(partial,destination);console.log(destination);}catch(e){console.error(e.message);process.exitCode=1;}
