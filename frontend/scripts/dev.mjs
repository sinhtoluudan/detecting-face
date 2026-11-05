// Supports normal npm run dev and the managed preview's host/port arguments.
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const args = process.argv.slice(2);
function value(flag, fallback) { const i=args.indexOf(flag); return i>=0 ? args[i+1] : fallback; }
const child = spawn(process.execPath, [require.resolve('next/dist/bin/next'), 'dev', '--webpack',
  '--hostname', value('--host', '0.0.0.0'), '--port', value('--port', process.env.PORT || '3000')], { stdio:'inherit' });
for (const signal of ['SIGINT','SIGTERM']) process.on(signal,()=>child.kill(signal));
child.on('exit',code=>process.exit(code || 0));
