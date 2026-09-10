import json
import threading
import time
import unittest
from functools import partial
from http.server import ThreadingHTTPServer
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from test_factory import fixture, manual
from run_factory import Handler, Service

class ServiceTests(unittest.TestCase):
    def test_python_http_run_returns_real_engine_result(self):
        service=Service(fixture())
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,service=service))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            with urlopen(base+'/api/config') as response:
                config=json.load(response)
            self.assertEqual(len(config['machines']),3)
            req=Request(base+'/api/run',data=json.dumps({'config':{'horizon_days':1},'manual_jobs':[manual(quantity=10)]}).encode(),headers={'Content-Type':'application/json'})
            with urlopen(req) as response:tid=json.load(response)['id']
            for _ in range(100):
                with urlopen(base+'/api/tasks/'+tid) as response:task=json.load(response)
                if task['status']!='RUNNING':break
                time.sleep(.01)
            self.assertEqual(task['result']['status'],'COMPLETE')
            self.assertEqual(task['result']['jobs'][0]['completed'],10)
            self.assertEqual(task['result']['demand_provenance']['mode'],'manual')
            denied=Request(base+'/api/run',data=b'{}',headers={'Origin':'http://unrelated.example'})
            with self.assertRaises(HTTPError) as e:urlopen(denied)
            self.assertEqual(e.exception.code,403)
        finally:
            server.shutdown();server.server_close();service.executor.shutdown()
