"""Domain-specific bounded BFS over authored grid moves, using existing Move.

Not a replacement world-model/MPC planner and not learned skill discovery.
"""
from collections import deque
from .core import Move, MOVES


def movement_reward(before,after,done,information=0.):
    """Existing authored-world reward, shared by the interactive lab adapter."""
    return (before-after)*.2-.02+(1. if done else 0.)+information


def to_cell(obj, x, y, check, max_expansions=128):
    if any(type(v) is not int or not 0<=v<6 for v in (x,y)):
        raise ValueError('goal_grid_bounds')
    if type(max_expansions) is not int or not 1<=max_expansions<=128:
        raise ValueError('symbolic_search_cap')
    start=(obj['x'],obj['y']);queue=deque([(start,())]);seen={start}
    expanded=0;edges=0
    while queue:
        check()
        position,path=queue.popleft()
        if position==(x,y):
            return path,dict(expanded=expanded,edges=edges,kind='authored_symbolic_search_not_neural_imagination')
        if expanded>=max_expansions:
            raise TimeoutError('symbolic_search_expansion_cap')
        expanded+=1
        for direction,(dx,dy) in MOVES.items():
            edges+=1;destination=(position[0]+dx,position[1]+dy)
            if all(0<=v<6 for v in destination) and destination not in seen:
                seen.add(destination);queue.append((destination,path+(Move(obj['id'],direction),)))
    raise ValueError('unreachable_authored_goal')


def compact(program):
    # Existing executor allows8clauses; combine adjacent identical moves.
    result=[]
    for m in program:
        if result and result[-1].reference==m.reference and result[-1].direction==m.direction:
            previous=result.pop();result.append(Move(m.reference,m.direction,previous.steps+1))
        else:
            result.append(m)
    return tuple(result)
