import {execFileSync} from 'node:child_process';
export default function setup(){
 const python=process.platform==='win32'?'backend/.venv/Scripts/python.exe':'backend/.venv/bin/python';
 execFileSync(python,['backend/tests/seed_browser.py','setup'],{stdio:'inherit',env:process.env});
}
