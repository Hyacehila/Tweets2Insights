from collections import Counter
from datetime import timedelta
import numpy as np
from opinion_core.schemas.records import PostRecord, AnnotationRecord
from opinion_core.schemas.event import EventSchema
from opinion_core.schemas.workflow import ObservationSpec

FIELDS = ('topic','publisher','emotion','sentiment','stance')
STANCE = {'oppose':-1., 'neutral':0., 'support':1.}


def distribution(values, edges):
    if not values:
        return {'n':0,'mass':None,'mean':None,'variance':None,'quantiles':None}
    x = np.asarray(values, dtype=float)
    counts, _ = np.histogram(x, bins=edges)
    return {'n':len(values),'mass':(counts/len(values)).tolist(),'mean':float(x.mean()),
            'variance':float(x.var()),'quantiles':np.quantile(x,[.1,.25,.5,.75,.9]).tolist()}


def build_observations(posts, annotations, schema, spec, check_cancel=lambda:None):
    schema, spec = EventSchema.model_validate(schema), ObservationSpec.model_validate(spec)
    posts = [PostRecord.model_validate(p) for p in posts]
    parsed = [AnnotationRecord.model_validate(a) for a in annotations]
    ann = {a.post_id:a for a in parsed}
    if len(ann) != len(parsed) or len({p.post_id for p in posts}) != len(posts):
        raise ValueError('duplicate records in observation input')
    if not set(ann) <= {p.post_id for p in posts}:
        raise ValueError('annotation references another dataset')
    if any(a.schema_version != schema.schema_version for a in parsed):
        raise ValueError('mixed annotation schemas')
    topic_ids, emotion_ids = [t.id for t in schema.topics], [e.id for e in schema.emotions]
    target = schema.targets[0].id
    edges = np.linspace(-1,1,spec.bins+1).tolist()
    windows, selected = [], []
    for post in posts:
        if post.kind not in spec.kinds or spec.platforms and post.platform not in spec.platforms:
            continue
        a = ann.get(post.post_id)
        if spec.topic_ids and (a is None or a.topic.status != 'accepted' or a.topic.value not in spec.topic_ids):
            continue
        selected.append(post)
    cursor = spec.start
    while cursor < spec.end:
        check_cancel()
        end = min(cursor+timedelta(seconds=spec.window_seconds), spec.end)
        rows = [p for p in selected if p.published_at is not None and cursor <= p.published_at < end]
        accepted = {field:[] for field in FIELDS}
        counts = {field:Counter() for field in FIELDS}
        vectors, joint_ids, by_topic = [], [], {}
        for post in rows:
            a = ann.get(post.post_id)
            for field in FIELDS:
                f = getattr(a,field) if a else None
                state = f.status if f else 'missing'
                if field == 'stance' and state == 'accepted' and a.target_id != target:
                    raise ValueError('mixed stance targets')
                counts[field][state] += 1
                if state == 'accepted':
                    accepted[field].append(f.value)
            if a and a.topic.status == 'accepted' and a.sentiment.status == 'accepted':
                by_topic.setdefault(a.topic.value,[]).append(a.sentiment.value)
            if a and all(getattr(a,k).status == 'accepted' for k in ('topic','emotion','stance','sentiment')):
                if a.topic.value not in topic_ids or a.emotion.value not in emotion_ids:
                    raise ValueError('labels outside frozen vocabulary')
                vectors.append([float(t == a.topic.value) for t in topic_ids]+
                               [float(e == a.emotion.value) for e in emotion_ids]+
                               [STANCE[a.stance.value], a.sentiment.value])
                joint_ids.append(post.post_id)
        fields = {}
        for field in FIELDS:
            values = accepted[field]
            detail = distribution([STANCE[v] for v in values] if field == 'stance' else values,edges) if field in ('stance','sentiment') else {'counts':dict(Counter(values))}
            fields[field] = {**detail,'valid_n':len(values),'coverage':len(values)/len(rows) if rows else None,
                             'statuses':{s:counts[field][s] for s in ('accepted','abstained','failed','missing')}}
        moments, variance = None, None
        if vectors:
            x = np.asarray(vectors)
            transformed = np.concatenate([x,x*x],axis=1)
            moments = transformed.mean(axis=0).tolist()
            variance = (transformed.var(axis=0)/len(vectors)).tolist()
        windows.append({'start':cursor.isoformat(),'end':end.isoformat(),'raw_n':len(rows), 'joint_n':len(vectors),
                        'fields':fields,'joint_vectors':vectors,'joint_post_ids':joint_ids,
                        'summary':moments,'summary_sampling_variance':variance,
                        'topic_sentiment':{t:distribution(v,edges) for t,v in by_topic.items()},
                        'unique_authors':len({p.author_ref for p in rows if p.author_ref})})
        cursor=end
    return {'representation_version':'joint-categorical-moments-v1','kind':'observed',
            'schema_version':schema.schema_version,'target_id':target,'bins':edges,
            'features':[f'topic:{t}' for t in topic_ids]+[f'emotion:{e}' for e in emotion_ids]+['stance','sentiment'],
            'simplex_blocks':[[0,len(topic_ids)],[len(topic_ids),len(topic_ids)+len(emotion_ids)]],
            'spec':spec.model_dump(mode='json'),'input_n':len(posts),'filtered_n':len(selected),
            'missing_time_n':sum(p.published_at is None for p in selected),
            'historical_availability_verified':False,'windows':windows}


def summarize(observations):
    return {k:v for k,v in observations.items() if k != 'windows'} | {
        'windows':[{k:v for k,v in w.items() if k not in {'joint_vectors','joint_post_ids'}} for w in observations['windows']]}
