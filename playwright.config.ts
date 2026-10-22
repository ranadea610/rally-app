import {defineConfig} from '@playwright/test';
import {randomUUID} from 'node:crypto';
process.env.RALLY_E2E_RUN_ID ||= randomUUID();
process.env.RALLY_E2E_DATABASE_URL ||= 'postgresql+psycopg://rally:rally@127.0.0.1:5432/rally_test';
const python=process.platform==='win32'?'backend/.venv/Scripts/python.exe':'backend/.venv/bin/python';
if(!new URL(process.env.RALLY_E2E_DATABASE_URL).pathname.endsWith('_test'))throw new Error('E2E requires a dedicated database ending in _test.');
const localPython=process.platform==='win32'?'".venv\\Scripts\\python.exe"':'.venv/bin/python';
export default defineConfig({testDir:'./tests/e2e',workers:1,fullyParallel:false,timeout:45000,expect:{timeout:10000},globalSetup:'./tests/e2e/setup.ts',globalTeardown:'./tests/e2e/teardown.ts',use:{baseURL:'http://127.0.0.1:5175',browserName:'chromium',timezoneId:'Asia/Tokyo',trace:'retain-on-failure'},webServer:[
 {command:`cd backend && ${localPython} -m alembic upgrade head && ${localPython} -m uvicorn app.main:app --host 127.0.0.1 --port 8001`,url:'http://127.0.0.1:8001/health/ready',reuseExistingServer:false,env:{DATABASE_URL:process.env.RALLY_E2E_DATABASE_URL,ALLOWED_ORIGINS:'["http://127.0.0.1:5175"]',COOKIE_SECURE:'false'}},
 {command:'npm run dev -- --port 5175 --strictPort',url:'http://127.0.0.1:5175',reuseExistingServer:false,env:{RALLY_API_TARGET:'http://127.0.0.1:8001'}},
]});
