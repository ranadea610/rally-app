import test from 'node:test';
import assert from 'node:assert/strict';
import {validateDeployment} from './check-deploy.mjs';
const valid='DOMAIN=rally.university.edu\nACME_EMAIL=officer@university.edu\nPOSTGRES_PASSWORD='+('0123456789abcdef'.repeat(4))+'\nRELEASE_TAG='+('a'.repeat(40))+'\nCLUB_TIMEZONE=America/Los_Angeles';
test('production config accepts complete settings',()=>assert.equal(validateDeployment(valid).DOMAIN,'rally.university.edu'));
test('production config rejects placeholders and malformed settings',()=>{
 for(const [before,after] of [['rally.university.edu','https://rally.university.edu'],['rally.university.edu','club.example.edu'],['rally.university.edu','localhost'],['officer@university.edu',''],['0123456789abcdef'.repeat(4),'rally'],['a'.repeat(40),'latest'],['America/Los_Angeles','Mars/Olympus']])assert.throws(()=>validateDeployment(valid.replace(before,after)));
});
