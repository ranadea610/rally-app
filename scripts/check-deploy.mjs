import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
export function validateDeployment(content){
 const values=Object.fromEntries(content.split(/\r?\n/).filter(line=>line.trim()&&!line.trim().startsWith('#')).map(line=>{const index=line.indexOf('=');if(index<1)throw new Error('Expected KEY=value configuration.');const key=line.slice(0,index).trim();let value=line.slice(index+1).trim();if((value.startsWith('"')&&value.endsWith('"'))||(value.startsWith("'")&&value.endsWith("'")))value=value.slice(1,-1);return [key,value];}));
 if(!/^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/i.test(values.DOMAIN||'')||/(?:^|\.)(example|invalid|test|localhost)$/.test(values.DOMAIN)||values.DOMAIN?.includes('example.'))throw new Error('DOMAIN must be your real public hostname, without scheme, port, or path.');
 if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.ACME_EMAIL||''))throw new Error('Set a valid ACME_EMAIL for certificate registration.');
 if(!/^[a-f0-9]{64,}$/i.test(values.POSTGRES_PASSWORD||'')||new Set(values.POSTGRES_PASSWORD).size<8)throw new Error('POSTGRES_PASSWORD must be a freshly generated random hex secret of at least 64 characters.');
 if(!/^[a-f0-9]{40}$/i.test(values.RELEASE_TAG||''))throw new Error('RELEASE_TAG must be the full tested Git commit SHA.');
 try{new Intl.DateTimeFormat('en-US',{timeZone:values.CLUB_TIMEZONE||'America/Los_Angeles'});}catch{throw new Error('CLUB_TIMEZONE must be a valid IANA timezone.');}
 return values;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){try{validateDeployment(readFileSync(process.argv[2]||'deploy/.env.production','utf8'));console.log('Deployment settings validated. No secret values were printed.');}catch(e){console.error(e.message);process.exitCode=1;}}
