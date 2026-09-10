"""Run the Python production simulation and its browser interface locally."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import traceback
import uuid
import webbrowser
from factory.data import Calibration
from factory.engine import Config, Simulation
from factory.experiments import ExperimentRunner, atomic_json

ROOT = Path(__file__).resolve().parent


class Service:
    def __init__(self, data):
        self.data = data
        self.operating_point = None
        point_path = ROOT/'results/load-calibration/operating_point.json'
        if point_path.exists():
            point = json.loads(point_path.read_text())
            from factory.engine import ENGINE_SOURCE_SHA256
            if point.get('status')=='CALIBRATED' and point.get('dataset_sha256')==data.digest and point.get('engine_source_sha256')==ENGINE_SOURCE_SHA256:
                self.operating_point = point
        self.tasks = {}
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.lock = threading.Lock()

    def submit(self, request):
        mode = request.get('mode', 'run')
        if mode not in ('run', 'scenario', 'grid'):
            raise ValueError('Unknown run mode')
        options = request.get('config', {})
        allowed = {'algorithm','arrival_load','batch_size','horizon_days','warmup_days','seed','trace_days','replication'}
        if set(options)-allowed:
            raise ValueError('Unknown configuration fields')
        config = Config(**options)
        if self.operating_point:
            config.baseline_calibration_multiplier = self.operating_point['baseline_calibration_multiplier']
        config.validate()
        if config.horizon_days > 365 or config.trace_days > 28:
            raise ValueError('UI limit: 365 measurement days and 28 replay days; use CLI for larger studies')
        with self.lock:
            if any(t['status']=='RUNNING' for t in self.tasks.values()):
                raise ValueError('A run is already in progress; cancel or wait for completion')
            tid = uuid.uuid4().hex
            task = {'id':tid,'status':'RUNNING','message':'Preparing Python simulation','cancel':False}
            self.tasks[tid] = task
        self.executor.submit(self.execute, tid, mode, config, request.get('manual_jobs'))
        return {'id': tid}

    def execute(self, tid, mode, config, manual):
        task = self.tasks[tid]
        try:
            if mode == 'run':
                result = Simulation(self.data, config, manual, cancel=lambda: task['cancel']).run()
            else:
                runner = ExperimentRunner(self.data, ROOT/'results'/'experiments',
                    progress=lambda message: task.update(message=message), cancel=lambda: task['cancel'])
                result = runner.scenario(config) if mode == 'scenario' else runner.grid(config)
            atomic_json(ROOT/'results'/(tid+'.json'), result)
            task.update(status='CANCELLED' if result.get('status')=='CANCELLED' else 'COMPLETE',result=result,
                        message='Cancelled; partial diagnostic saved' if result.get('status')=='CANCELLED' else 'Completed and saved')
        except InterruptedError as exc:
            task.update(status='CANCELLED',message=str(exc))
        except Exception as exc:
            task.update(status='ERROR',message=str(exc))
            traceback.print_exc()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,service=None,**kwargs):
        self.service = service
        super().__init__(*args,directory=str(ROOT/'dist'),**kwargs)

    def reply(self, value, code=200):
        content = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(content)))
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if self.path == '/api/config':
            data = self.service.data
            self.reply({'machines':list(data.machines.values()),'dataset_sha256':data.digest,
                        'world_version':'v0.3','templates':len(data.templates),'items':len({j['item'] for j in data.templates}),
                        'operating_point':{k:v for k,v in (self.service.operating_point or {'status':'NOT_CALIBRATED'}).items() if k!='results'},'mode':'production world','profiles':len(data.profiles)})
        elif self.path.startswith('/api/tasks/'):
            task = self.service.tasks.get(self.path.split('/')[-1])
            self.reply(task or {'message':'Unknown task'},200 if task else 404)
        elif self.path == '/':
            self.send_response(302)
            self.send_header('Location','/production/')
            self.end_headers()
        else:
            super().do_GET()

    def do_POST(self):
        # This local application accepts same-origin browser requests only.
        origin = self.headers.get('Origin')
        if origin and origin.split('://')[-1] != self.headers.get('Host'):
            self.reply({'message':'Origin denied'},403)
            return
        try:
            size = int(self.headers.get('Content-Length',0))
            if size > 2_000_000:
                raise ValueError('Request too large')
            payload = json.loads(self.rfile.read(size))
            if self.path == '/api/run':
                self.reply(self.service.submit(payload),202)
            elif self.path.startswith('/api/cancel/'):
                tid = self.path.split('/')[-1]
                self.service.tasks[tid]['cancel'] = True
                self.reply({'message':'Cancellation requested; current replication is retained'})
            else:
                self.reply({'message':'Unknown endpoint'},404)
        except (ValueError,TypeError,KeyError) as exc:
            self.reply({'message':str(exc)},400)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--calibration',default=str(ROOT/'data/calibration/Final_Baseline_Calibration.json'))
    parser.add_argument('--no-browser',action='store_true')
    args = parser.parse_args()
    data = Calibration.load(args.calibration)
    handler = partial(Handler,service=Service(data))
    server = ThreadingHTTPServer((args.host,args.port),handler)
    url = f'http://127.0.0.1:{args.port}/production/'
    print(f'Production simulation: {url}',flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
