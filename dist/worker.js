let python;
let initPromise;
let generation = 0;
async function boot() {
  if (python) return python;
  if (!initPromise) initPromise = (async () => {
    postMessage({type:'loading', message:'מכין את מנוע הסימולציה…'});
    importScripts('./runtime/pyodide.js');
    const runtime = await loadPyodide({indexURL:new URL('./runtime/', self.location.href).href});
    const response = await fetch('./engine.py');
    if (!response.ok) throw new Error('Engine source unavailable');
    await runtime.runPythonAsync(await response.text());
    python = runtime;
    postMessage({type:'ready'});
    return python;
  })();
  return initPromise;
}
self.onmessage = async ({data}) => {
  if (data.type === 'cancel') { generation++; return; }
  try {
    const py = await boot();
    if (data.type === 'init') return;
    if (data.type === 'simulate') {
      py.globals.set('ui_options_json', JSON.stringify(data.options));
      const result = JSON.parse(py.runPython('simulate_json(ui_options_json)'));
      postMessage({type:'trace', id:data.id, result});
    } else if (data.type === 'batch') {
      const token = ++generation;
      const count = Math.max(1, Math.min(500, Math.floor(Number(data.count)||1)));
      const results = [];
      for(let i=0;i<count;i++) {
        if (generation !== token) { postMessage({type:'batchCancelled', id:data.id}); return; }
        py.globals.set('ui_options_json', JSON.stringify(data.options));
        py.globals.set('ui_replication_index', i);
        results.push(JSON.parse(py.runPython('run_replication_json(ui_options_json, ui_replication_index)')));
        if ((i+1)%10===0 || i+1===count) {
          postMessage({type:'batchProgress', id:data.id, done:i+1, total:count});
          await new Promise(resolve=>setTimeout(resolve,0));
        }
      }
      postMessage({type:'batch', id:data.id, results, options:data.options});
    }
  } catch(error) {
    postMessage({type:'error', id:data.id, message:String(error.message||error)});
  }
};
boot().catch(error=>postMessage({type:'error',message:String(error.message||error)}));
