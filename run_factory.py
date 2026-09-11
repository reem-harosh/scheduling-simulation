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
import hashlib
import os
from factory.data import Calibration
from factory.world import World
from factory.world_engine import WorldConfig, WorldSimulation
from factory.world_experiments import WorldExperimentRunner
from factory.engine import Config, Simulation
from factory.experiments import ExperimentRunner, atomic_json

ROOT = Path(__file__).resolve().parent
APP_VERSION = '0.5.3'


class Service:
    def __init__(self, data):
        self.instance_id=uuid.uuid4().hex[:8]
        self.data = data
        self.is_world = isinstance(data, World)
        self.operating_point = None
        point_path = ROOT/'results/load-calibration/operating_point.json'
        if point_path.exists() and not self.is_world:
            point = json.loads(point_path.read_text())
            from factory.engine import ENGINE_SOURCE_SHA256
            if point.get('status')=='CALIBRATED' and point.get('dataset_sha256')==data.digest and point.get('engine_source_sha256')==ENGINE_SOURCE_SHA256:
                self.operating_point = point
        self.tasks = {}
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.lock = threading.Lock()

    def submit(self, request):
        if not isinstance(request,dict):raise ValueError('Request must be a JSON object')
        mode = request.get('mode', 'run')
        if mode not in ('run', 'scenario', 'grid'):
            raise ValueError('Unknown run mode')
        options = request.get('config', {})
        if not isinstance(options,dict):raise ValueError('Config must be a JSON object')
        allowed = {'algorithm','arrival_load','batch_size','horizon_days','warmup_days','seed','trace_days','replication'}
        if set(options)-allowed:
            raise ValueError('Unknown configuration fields')
        config = (WorldConfig if self.is_world else Config)(**options)
        if self.operating_point:
            config.baseline_calibration_multiplier = self.operating_point['baseline_calibration_multiplier']
            if 'warmup_days' not in options:config.warmup_days=self.operating_point['warmup_days']
        config.validate()
        if config.horizon_days > 365 or config.trace_days > 28 or config.warmup_days > 730 or config.arrival_load > 10 or config.batch_size > 10:
            raise ValueError('UI limits: 365 measurement days, 730 warmup days, 28 replay days, scales at most 10; use CLI for larger studies')
        with self.lock:
            if any(t['status']=='RUNNING' for t in self.tasks.values()):
                raise ValueError('A run is already in progress; cancel or wait for completion')
            tid = uuid.uuid4().hex
            task = {'id':tid,'status':'RUNNING','message':'Preparing Python simulation','cancel':False}
            self.tasks[tid] = task
        replications = request.get('replications', 3)
        grid = request.get('grid', [.5,.75,1.,1.25,1.5])
        if type(replications) is not int or not 1 <= replications <= 100:
            task.update(status='ERROR');raise ValueError('Replication count must be 1–100')
        if not isinstance(grid,list) or not grid or len(grid)>10 or any(type(x) not in (int,float) or not 0 < x <= 10 for x in grid):
            task.update(status='ERROR');raise ValueError('Grid requires 1–10 positive scales, at most 10')
        self.executor.submit(self.execute, tid, mode, config, request.get('manual_jobs'),replications,grid)
        return {'id': tid}

    def execute(self, tid, mode, config, manual, replications=3, grid=None):
        task = self.tasks[tid]
        try:
            if mode == 'run':
                result = (WorldSimulation if self.is_world else Simulation)(self.data, config, manual, cancel=lambda: task['cancel'], **({'observer':lambda live: task.update(live=live)} if self.is_world else {})).run()
            else:
                runner = (WorldExperimentRunner if self.is_world else ExperimentRunner)(self.data, ROOT/'results'/('world-experiments' if self.is_world else 'experiments'),
                    progress=lambda message: task.update(message=message), cancel=lambda: task['cancel'], **({'observer':lambda live: task.update(live=live), 'surface_observer':lambda surface: task.update(surface=surface)} if self.is_world else {}))
                if self.is_world:
                    result = runner.scenario(config,replications=replications) if mode=='scenario' else runner.grid(config,grid=grid,replications=replications)
                else:
                    result = runner.scenario(config) if mode == 'scenario' else runner.grid(config)
            result['operating_point']={k:v for k,v in (self.operating_point or {'status':'NOT_CALIBRATED'}).items() if k!='results'}
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

    def end_headers(self):
        self.send_header('Cache-Control','no-store, max-age=0')
        super().end_headers()

    def send_head(self):
        # Do not reuse old assets through an If-Modified-Since 304 response.
        if 'If-Modified-Since' in self.headers:del self.headers['If-Modified-Since']
        return super().send_head()

    def reply(self, value, code=200):
        content = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if self.path == '/api/config':
            data = self.service.data
            self.reply({'machines':list(data.machines.values()),'dataset_sha256':data.digest,
                        'app_version':APP_VERSION,'server_instance':self.service.instance_id,'ui_sha256':hashlib.sha256((ROOT/'dist/production/production.js').read_bytes()).hexdigest()[:12],
                        'world_version':data.raw['version'] if self.service.is_world else 'v0.3','templates':len(data.templates),'items':len({j['item'] for j in data.templates}),
                        'operating_point':{k:v for k,v in (self.service.operating_point or {'status':'NOT_CALIBRATED'}).items() if k!='results'},'mode':'calibrated world' if self.service.is_world else 'historical world','profiles':len(data.profiles),'model_provenance':data.raw.get('provenance',{}),'part_families':data.raw.get('part_families',[]),'demand':data.raw.get('demand',{})})
        elif self.path == '/api/surface':
            path=ROOT/'results'/'world-experiments'/'surface.json'
            if not path.exists():path=ROOT/'research'/'world_v05'/'response_surface.json'
            if path.exists():
                surface=json.loads(path.read_text())
                code=hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT/'factory').glob('*.py')))).hexdigest()
                surface['source_compatibility']={'matches_current_code':surface.get('code_sha256')==code,
                    'matches_current_world':surface.get('dataset_sha256')==self.service.data.digest,
                    'archival_reference':path.parent.name=='world_v05','current_code_sha256':code}
                self.reply(surface)
            else:self.reply({'message':'No saved grid yet; run a grid experiment or load a saved surface JSON'},404)
        elif self.path == '/api/world' and self.service.is_world:
            self.reply(self.service.data.raw)
        elif self.path.startswith('/api/tasks/'):
            task = self.service.tasks.get(self.path.split('/')[-1])
            self.reply(dict(task) if task else {'message':'Unknown task'},200 if task else 404)
        elif self.path == '/':
            self.send_response(302)
            self.send_header('Location','/production/')
            self.end_headers()
        else:
            super().do_GET()

    def do_POST(self):
        # This local application accepts same-origin browser requests only.
        origin = self.headers.get('Origin')
        allowed_hosts={self.headers.get('Host')}
        if os.environ.get('CODESPACE_NAME'):
            domain=os.environ.get('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN','app.github.dev')
            allowed_hosts.add(f"{os.environ['CODESPACE_NAME']}-{self.server.server_port}.{domain}")
        if origin and origin.split('://')[-1] not in allowed_hosts:
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
    parser.add_argument('--calibration',default=str(ROOT/'research/world_v05/world.json'))
    parser.add_argument('--no-browser',action='store_true')
    args = parser.parse_args()
    raw = json.loads(Path(args.calibration).read_text())
    data = World(raw) if 'part_families' in raw else Calibration.load(args.calibration)
    handler = partial(Handler,service=Service(data))
    try:
        server = ThreadingHTTPServer((args.host,args.port),handler)
    except OSError as exc:
        raise SystemExit(f'Cannot start version {APP_VERSION} on port {args.port}: another server may still be running. Stop the old server or choose --port 8001. Details: {exc}')
    url = f'http://127.0.0.1:{args.port}/production/'
    print(f'Production simulation v{APP_VERSION}: {url}',flush=True)
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
