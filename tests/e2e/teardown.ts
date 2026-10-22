import {execFileSync} from 'node:child_process';
export default function teardown(){execFileSync(process.platform==='win32'?'backend/.venv/Scripts/python.exe':'backend/.venv/bin/python',['backend/tests/seed_browser.py','cleanup'],{stdio:'inherit',env:process.env});}
