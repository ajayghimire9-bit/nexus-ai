"""Source-only comparison of short-horizon ranking vs episode-level control.

Does not collect environment steps, train, or authorize the locked
decision-aware diagnostic. Confirmation physics are not reopened.
"""
from __future__ import annotations
import json
import math
import statistics
from pathlib import Path
import numpy as np
from nexus.world.long_continuation import paired_interval
from nexus.world.planning_value import sha
from nexus.world.terminal_value_execution import save
from nexus.world import decision_aware_world_model as dawm

ASSESSMENT=Path('docs/NEXUS_NEXT_DIRECTION_ASSESSMENT.md')
OUTPUT=Path('artifacts/next_direction_assessment.json')
RETURN_PHASE=Path('artifacts/return_phase_decomposition.json')
WINDOWS=(('early_0_15',0,16),('mid_16_63',16,64),('late_64_127',64,128),('tail_128_199',128,200),('late_16_199',16,200))
DECISION_AWARE_PROTOCOL_SHA='c66a2960af8243c2a2ea22233081681b75549df1705e9fbebd6b881afd049f39'
DECISION_AWARE_CONFIG_SHA='0fe69d772b524d7d16d58f8ed81e4f2fdf7402b5f38d792e6b99c733b59c7611'
RETURN_PHASE_SHA='aaa8fc037f8bc481799d65b08308e7e7bdf0f2a8cf27686c5803db22da2e2cc8'


def assert_decision_aware_frozen():
    record=dawm.load_allocation()
    if sha(dawm.PROTOCOL)!=DECISION_AWARE_PROTOCOL_SHA or sha(dawm.CONFIG)!=DECISION_AWARE_CONFIG_SHA:
        raise ValueError('locked decision-aware protocol or config changed')
    if record.get('authorized') is not False or int(record.get('runs',0))!=0:
        raise ValueError('decision-aware collection must remain unauthorized')
    if dawm.OUTPUT.exists():raise ValueError('decision-aware collection artifact must not exist')
    dawm.load_config()


def _decoder_means(rows,key,tasks=None):
    values=[]
    for d in range(10):
        xs=[r[key] for r in rows if r['decoder']==d and (tasks is None or r['task'] in tasks)]
        if not xs:raise ValueError('missing decoder window')
        values.append(statistics.mean(xs))
    return values


def return_phase_windows():
    payload=json.loads(RETURN_PHASE.read_text())
    if sha(RETURN_PHASE)!=RETURN_PHASE_SHA:raise ValueError('closed return-phase artifact changed')
    if payload.get('primary_label')!='primarily_late':raise ValueError('closed return-phase label changed')
    rows=[]
    for episode in payload['paired_episodes']:
        student=np.mean(np.asarray(episode['student_rewards'],dtype=np.float64),axis=0)
        zero=np.asarray(episode['zero_rewards'],dtype=np.float64)
        if student.shape!=(200,) or zero.shape!=(200,):raise ValueError('episode length drifted')
        delta=student-zero
        if not math.isclose(float(delta[:16].sum()+delta[16:].sum()),float(delta.sum()),abs_tol=1e-10):
            raise ValueError('window identity failed')
        row=dict(decoder=episode['decoder'],task=episode['task'])
        for name,start,stop in WINDOWS:
            row[name]=float(delta[start:stop].sum())
        rows.append(row)
    if len(rows)!=160:raise ValueError('return-phase episode grid incomplete')
    summary={'n_episodes':160,'historical':True,'exploratory':True,'retuned':False,
             'closed_primary_label':'primarily_late','confirmation_reopened':False}
    for name,_,_ in WINDOWS:
        values=_decoder_means(rows,name)
        summary[name]=dict(per_decoder=values,interval=paired_interval(values))
    rp2=_decoder_means(rows,'late_16_199',{'pendulum_ctrl_rp2'})
    summary['rp2_late_16_199']=dict(per_decoder=rp2,interval=paired_interval(rp2))
    early=summary['early_0_15']['interval'];mid=summary['mid_16_63']['interval']
    w64=summary['late_64_127']['interval'];tail=summary['tail_128_199']['interval']
    if not (early['lo']<0<early['hi'] and mid['lo']<0<mid['hi']):raise ValueError('early/mid identity drifted')
    if not (w64['hi']<0 and tail['hi']<0):raise ValueError('post-64 windows no longer exclude 0')
    return summary


def recommend():
    assert_decision_aware_frozen()
    windows=return_phase_windows()
    return dict(
        complete=True,new_environment_steps=0,new_imagined_transitions=0,training=0,
        authorized=False,decision_aware_collection_authorized=False,
        decision_aware_protocol_sha256=DECISION_AWARE_PROTOCOL_SHA,
        return_phase_sha256=RETURN_PHASE_SHA,windows=windows,
        recommendation='B',
        reason=('Short-horizon ranking is already strong, source H1 is not established, '
                'and the recorded 200-step loss sits after step 64, not in the H=16 window.'),
        direction_a=dict(question='Does development physics show concentrated near-best H=16 score error?',
                         archive_sufficient=False,locked_protocol='docs/NEXUS_DECISION_AWARE_WORLD_MODEL_PROTOCOL.md',
                         cost=dict(time_cap_s=90,env=19680,imagined=3164160),authorized=False,
                         information_gain='low'),
        direction_b=dict(question='Where does receding H=16 control lose 200-step return after ranking looks adequate?',
                         archive_sufficient_for_timing=True,confirmation_reopened=False,
                         next_simulation='none in this assessment',authorized=False,
                         information_gain='high'),
        confirmation_physics_used_for_new_collection=False,
        score_correction_closed=True)


def run():
    report=recommend();save(OUTPUT,report);return report
