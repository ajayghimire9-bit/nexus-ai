"""Post-run descriptive audit from saved trials; no model or new data calls.

Two reset repetitions give an additional timing-sensitivity interval. This was
NOT the registered primary endpoint and cannot upgrade the failed screen.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics


def analyze(records):
    trials=[r for r in records if r['kind']=='trial']
    methods=sorted({r['method'] for r in trials})
    result={'label':'posthoc saved-data sensitivity audit, not a new experiment',
            'methods':{},'timing_reset_replication_sensitivity':{},'incorrect_cases':{}}
    for method in methods:
        rows=[r for r in trials if r['method']==method]
        uncached=[r['result']['telemetry']['request_wall_s'] for r in rows
                  if r['result']['telemetry']['inference_ran'] is True and r['index']!=0]
        stages=sorted({k for r in rows for k in r['result']['stages']})
        result['methods'][method]=dict(
            warm_uncached_model_requests=len(uncached),
            warm_uncached_model_mean_s=statistics.mean(uncached),
            median_workflow_s=statistics.median(r['result']['workflow_s'] for r in rows),
            stage_total_s={k:sum(r['result']['stages'].get(k,0) for r in rows) for k in stages},
            ordinary_program_cache_hits=sum(r['result']['counters']['program_cache_hit'] for r in rows),
            max_serialized_program_cache_bytes=max(r['result']['program_cache_bytes'] for r in rows),
            max_serialized_capsules_bytes=max(r['result']['library_bytes'] for r in rows))
    for baseline in ('tools_retrieval','ordinary_cache'):
        differences=[]
        for rep in (0,1):
            def mean(method):
                return statistics.mean(r['result']['workflow_s']+r['amortized_startup_s'] for r in trials
                                       if r['repeat']==rep and r['method']==method)
            differences.append(mean(baseline)-mean('nexus_capsules'))
        mean=statistics.mean(differences)
        half=12.706204736*statistics.stdev(differences)/math.sqrt(2)
        result['timing_reset_replication_sensitivity'][baseline]=dict(
            differences_s=differences,mean_s=mean,t95_s=[mean-half,mean+half],
            reset_repetitions=2,degrees_of_freedom=1,
            scope='posthoc n=2 reset-pair interval; not independent pretrained models')
    for r in trials:
        if not r['correct']:
            case=result['incorrect_cases'].setdefault(r['task_id'],dict(occurrences=0,intents=[],methods=[]))
            case['occurrences']+=1
            if r['result']['intent'] not in case['intents']:case['intents'].append(r['result']['intent'])
            if r['method'] not in case['methods']:case['methods'].append(r['method'])
    integrations=[r for r in records if r['kind']=='live_integration']
    telemetry=[r['result']['telemetry'] for r in trials]
    for r in integrations:telemetry.extend((r['first']['telemetry'],r['second']['telemetry']))
    result['all_requests_including_integration']=dict(
        client_requests=len(telemetry),confirmed_model_calls=sum(t['inference_ran'] is True for t in telemetry),
        response_cache_hits=sum(t['application_cache_hit'] for t in telemetry),
        actual_input_tokens=sum(t['input_tokens'] for t in telemetry if t['input_tokens'] is not None),
        actual_generated_tokens=sum(t['generated_tokens'] for t in telemetry if t['generated_tokens'] is not None),
        unknown_token_requests=sum(t['input_tokens'] is None or t['generated_tokens'] is None for t in telemetry))
    return result


def ledger_export(directory):
    """Export the contiguous new E1 host events, anchored to preceding history."""
    events=[json.loads(p.read_text()) for p in sorted(Path(directory).glob('*.json'))]
    start=next(i for i,e in enumerate(events) if json.loads(e['payload_json']).get('id')=='assistant-v2-carry-reconciliation')
    end=next(i for i,e in enumerate(events) if e['kind']=='settled' and
             json.loads(e['payload_json']).get('run_id')=='seed-assistant-benchmark-v2p1-1')
    selected=events[start:end+1]
    out=dict(schema='assistant_v2_e1_ledger_export_v1',events=selected,
             prior_sequence=start-1,previous_anchor=selected[0]['previous'],
             head=selected[-1]['fingerprint'],count=len(selected),
             accounted_balance_before_reconciliation_s=2005.6321034559958,
             session_limit_s=3600)
    out['reconstructed_used_s']=verify_ledger(out)
    out['remaining_s']=3600-out['reconstructed_used_s']
    return out


def verify_ledger(value):
    previous=value['previous_anchor'];balance=value['accounted_balance_before_reconciliation_s']
    reserved={};settled=set()
    if len(value['events'])!=value['count']:raise ValueError('ledger count mismatch')
    for i,e in enumerate(value['events'],start=value['prior_sequence']+1):
        payload=json.loads(e['payload_json'])
        raw=json.dumps(dict(mode='synthetic_fixture',sequence=i,kind=e['kind'],payload=payload,
                            previous=previous),sort_keys=True,separators=(',',':'),allow_nan=False)
        fingerprint=hashlib.sha256(raw.encode()).hexdigest()
        if e['sequence']!=i or e['previous']!=previous or fingerprint!=e['fingerprint']:
            raise ValueError('ledger event mismatch')
        previous=fingerprint
        if e['kind']=='session_debit':balance+=payload['seconds']
        elif e['kind']=='reserved':reserved[payload['run_id']]=payload['wall_cap_s']
        elif e['kind']=='settled':
            if payload['run_id'] in settled or payload['run_id'] not in reserved:raise ValueError('invalid settlement')
            settled.add(payload['run_id']);balance+=payload['charged_wall_s']
    for run_id,cap in reserved.items():
        if run_id not in settled:balance+=cap
    if previous!=value['head']:raise ValueError('ledger head mismatch')
    return balance


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('raw',type=Path)
    p.add_argument('--output',type=Path);p.add_argument('--verify',type=Path)
    p.add_argument('--verify-ledger',type=Path);a=p.parse_args()
    if a.verify_ledger:
        ledger=json.loads(a.verify_ledger.read_text());balance=verify_ledger(ledger)
        if abs(balance-ledger['reconstructed_used_s'])>1e-8:raise ValueError('ledger balance mismatch')
        print('E1 ledger event hashes, reservation settlements and balance verified: '+str(balance))
        return
    result=analyze([json.loads(x) for x in a.raw.read_text().splitlines()])
    if a.verify:
        if json.loads(a.verify.read_text())!=result:raise ValueError('saved analysis mismatch')
        print('Saved analysis exactly reconstructs from raw records')
    elif a.output:
        with a.output.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    else:print(json.dumps(result,indent=2))


if __name__=='__main__':main()
