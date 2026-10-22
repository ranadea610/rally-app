import assert from 'node:assert/strict';
const base=process.env.RALLY_RATE_LIMIT_URL || 'http://127.0.0.1:8082';
if(process.env.RALLY_ALLOW_TEST_DATA!=='1'||!['127.0.0.1','localhost'].includes(new URL(base).hostname))throw new Error('Use RALLY_ALLOW_TEST_DATA=1 with a disposable local proxy.');
let ready=false;
for(let i=0;i<10;i++){try{ready=(await fetch(base,{signal:AbortSignal.timeout(2000)})).ok;if(ready)break;}catch{}await new Promise(resolve=>setTimeout(resolve,500));}
assert.ok(ready,'Production nginx proxy did not become ready.');
const statuses=[];
for(let i=0;i<15;i++)statuses.push((await fetch(base+'/api/auth/login',{method:'POST',signal:AbortSignal.timeout(10000),headers:{'Content-Type':'application/json','X-Forwarded-For':'198.51.100.8'},body:JSON.stringify({contact_method:'instagram',contact:'invalid_proxy_test',password:'invalid-password-test'})})).status);
assert.ok(statuses.includes(401),'Authentication requests did not reach the API.');
assert.ok(statuses.includes(429),'Repeated sign-in attempts were not rate limited.');
assert.ok(statuses.every(status=>[401,429].includes(status)));
console.log('Production nginx login proxy and rate limiting verified.');
