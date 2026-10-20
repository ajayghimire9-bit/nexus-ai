"""Narrow text ingestion and evidence projection; text is never an instruction.

Only explicit `subject relation object` sentences are extracted. Unsupported
prose remains retrievable verbatim. Conflicts are retained, never majority-voted
into truth. Supplied assertions are not independent observed facts.
"""
import re
from collections import defaultdict
from nexus.evolution1.catalogue import digest

IDENT=r'[a-z][a-z0-9_-]{0,23}'
RELATIONS=('is','inside','requires','matches','before','after','holds')


def ingest(source, text):
    if type(source) is not str or not 1<=len(source)<=160 or type(text) is not str or not 1<=len(text)<=8000: raise ValueError('bounded_source_document')
    parts=[p.strip() for p in re.split(r'[.\n]+',text) if p.strip()]
    if len(parts)>64: raise ValueError('document_unit_cap')
    units=[]
    pattern=rf'({IDENT}) (not )?({"|".join(RELATIONS)}) ({IDENT})'
    for index,part in enumerate(parts):
        m=re.fullmatch(pattern,part.lower())
        claim=None if m is None else dict(subject=m[1],relation=m[3],object=m[4],positive=m[2] is None)
        units.append(dict(id=digest([source,index,part]),source=source,index=index,text=part,
                          claim=claim,status='source_assertion' if claim else 'retrieval_only',confidence=None))
    return dict(source=source,text=text,sha256=digest(text),units=units)


def consolidate(documents):
    groups=defaultdict(list)
    for d in documents:
        for unit in d['units']:
            c=unit['claim']
            if c: groups[(c['subject'],c['relation'],c['object'])].append(unit)
    rules=[]
    for key,units in sorted(groups.items()):
        signs={u['claim']['positive'] for u in units}
        rules.append(dict(subject=key[0],relation=key[1],object=key[2],
            status='contradicted' if len(signs)>1 else 'source_assertion',
            positive=None if len(signs)>1 else next(iter(signs)),
            evidence=[u['id'] for u in units],sources=sorted({u['source'] for u in units}),
            rehearsal=[next(u['id'] for u in units if u['claim']['positive']==sign) for sign in sorted(signs)],
            check=f'Does {key[0]} {key[1]} {key[2]}?'))
    return rules


def retrieve(documents, query, limit=5):
    if type(query) is not str or len(query)>256 or type(limit) is not int or not 1<=limit<=8: raise ValueError('retrieval_query_cap')
    words=set(re.findall(IDENT,query.lower()));ranked=[]
    for d in documents:
        for u in d['units']:
            score=len(words & set(re.findall(IDENT,u['text'].lower())))
            if score: ranked.append((score,u['id'],u))
    return [u for _,_,u in sorted(ranked,key=lambda x:(-x[0],x[1]))[:limit]]
