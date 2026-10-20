"""Existing authored relation primitives, accessible without neural imports."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Relation:
    name:str

    def matches(self,pair):
        a,b=pair
        return {'left_of':a['x']<b['x'],'right_of':a['x']>b['x'],
                'above':a['y']<b['y'],'below':a['y']>b['y'],
                'same_color':a['color']==b['color'],'same_shape':a['shape']==b['shape']}[self.name]

RELATIONS=tuple(Relation(n) for n in ('left_of','right_of','above','below','same_color','same_shape'))
