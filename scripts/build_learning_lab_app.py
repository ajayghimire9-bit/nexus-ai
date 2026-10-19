"""Create a separate offline interactive replay; no server or live experiments."""
import json
from pathlib import Path
from nexus.evolution2.learning_lab import load_control_replay,load_operator_replay,load_training_audit,load_preparation

ROOT=Path(__file__).resolve().parents[1]


def build(root=ROOT):
    html=(root/'web/learning-lab/index.html').read_text()
    data={'/api/replay?study='+study:load_control_replay(root,study) for study in ('forecast16','horizon64')}
    data['/api/status']=dict(fixtures_enabled=False,requests_remaining=0,live_environment=False)
    data['/api/operators']=load_operator_replay(root)
    data['/api/training-audit']=load_training_audit(root)
    data['/api/parent-retention']=load_operator_replay(root,parent_retention=True)
    data['/api/preparation']=load_preparation(root)
    payload=json.dumps(data,allow_nan=False).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e')
    shim='<script>const offlineData='+payload+''';window.fetch=async function(url,options){const known=Object.prototype.hasOwnProperty.call(offlineData,url)&&(!options||!options.method||options.method==='GET');return {ok:known,json:async()=>known?offlineData[url]:{error:'Offline replay only; use the bounded local server for authored fixtures.'}};};</script>'''
    return html.replace('<script>',shim+'<script>',1)


if __name__=='__main__':
    target=ROOT/'artifacts/nexus_learning_lab_sessions.html'
    with target.open('x') as out:out.write(build())
    print(target)
