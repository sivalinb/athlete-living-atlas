"""Loopback-only static app with an optional private SQLite snapshot and agent API."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit
from .export import ROOT, snapshot
from observatory.investigator.agent import Investigator


class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,db=None,**kwargs):
        self.db=db
        super().__init__(*args,**kwargs)

    def allowed(self):
        host=self.headers.get('Host','')
        permitted={'127.0.0.1:'+str(self.server.server_port),'localhost:'+str(self.server.server_port)}
        origin=self.headers.get('Origin')
        return host in permitted and (not origin or urlsplit(origin).netloc in permitted)

    def json_response(self,value,status=200):
        payload=json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if not self.allowed():
            return self.json_response({'error':'Local origin required'},403)
        if self.path=='/api/snapshot':
            if not self.db:
                return self.json_response({'error':'No local snapshot configured'},404)
            return self.json_response(snapshot(self.db))
        return super().do_GET()

    def do_POST(self):
        if not self.allowed():
            return self.json_response({'error':'Local origin required'},403)
        if self.path!='/api/investigate' or not self.db:
            return self.json_response({'error':'Unavailable'},404)
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=4096:
                raise ValueError('Invalid request size')
            body=json.loads(self.rfile.read(size))
            if not isinstance(body.get('question'),str):
                raise ValueError('Question required')
            agent=Investigator(self.db,':memory:')
            try:
                result=agent.ask(body['question'])
            finally:
                agent.close()
            self.json_response(result)
        except (ValueError,TypeError,json.JSONDecodeError):
            self.json_response({'error':'Use a question of up to 2,000 characters'},400)

    def log_message(self,*args):
        pass


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--db',help='Optional private or fictional SQLite snapshot; read-only')
    p.add_argument('--port',type=int,default=8787)
    a=p.parse_args()
    if a.db and not Path(a.db).is_file():
        p.error('Database does not exist')
    server=ThreadingHTTPServer(('127.0.0.1',a.port),partial(Handler,directory=str(ROOT/'dist'),db=a.db))
    print(f'Living Atlas: http://127.0.0.1:{a.port}',flush=True)
    server.serve_forever()
