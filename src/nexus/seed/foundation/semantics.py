"""Executable supplied container semantics with observable preconditions.

Predictions are pure copies, never simulator actions or evidence that a physical
law was learned. Unknown attributes prevent execution. Observed outcomes must
be supplied through the ordinary observation interface.
"""
import copy
from .programs import bounded


def container(graph,item,target,action):
    bounded(graph)
    if type(graph) is not dict or set(graph)!={'objects','inside'} or type(graph['objects']) is not dict or type(graph['inside']) is not dict: raise ValueError('container_graph')
    objects=graph['objects'];inside=graph['inside']
    for child,parent in inside.items():
        if child not in objects or parent not in objects or child==parent: raise ValueError('known_container_edges')
        seen={child};cursor=parent
        while cursor in inside:
            if cursor in seen: raise ValueError('containment_cycle')
            seen.add(cursor);cursor=inside[cursor]
    if action not in ('recognize','insert','remove'): raise ValueError('container_action')
    if target not in objects or type(objects[target]) is not dict: raise ValueError('known_container')
    obj=objects[target];capacity=obj.get('capacity');opened=obj.get('open')
    if capacity is not None and (type(capacity) is not int or not 0<=capacity<=32): raise ValueError('container_capacity')
    if opened is not None and type(opened) is not bool: raise ValueError('container_open')
    if action=='recognize': return dict(value=None if capacity is None else capacity>0,origin='supplied_operator')
    if item not in objects or item==target: raise ValueError('distinct_known_item')
    if capacity is None or opened is None: return dict(status='unknown_precondition',graph=copy.deepcopy(graph))
    if not opened or capacity==0: return dict(status='failed_precondition',graph=copy.deepcopy(graph))
    if action=='insert':
        cursor=target
        while cursor in inside:
            if cursor==item: raise ValueError('containment_cycle')
            cursor=inside[cursor]
        if cursor==item: raise ValueError('containment_cycle')
        if item in inside or sum(p==target for p in inside.values())>=capacity: return dict(status='failed_precondition',graph=copy.deepcopy(graph))
    elif inside.get(item)!=target: return dict(status='failed_precondition',graph=copy.deepcopy(graph))
    out=copy.deepcopy(graph)
    if action=='insert': out['inside'][item]=target
    else: del out['inside'][item]
    return dict(status='predicted',graph=out,hypothetical=True,origin='supplied_operator',instructions=1)
