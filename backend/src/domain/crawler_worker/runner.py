import hashlib
import time
from opinion_core.schemas.records import PostRecord
from opinion_core.schemas.workflow import CrawlSpec
from opinion_core.schemas.event import EventSpec
from opinion_gateway.connectors import invoke_connector, WaitingForAuthentication, ConnectorUnavailable
from .x_api import fetch_page


def collect(event, spec, *, check_cancel=lambda:None, checkpoint=None, save_checkpoint=lambda state:None):
    event,spec = EventSpec.model_validate(event),CrawlSpec.model_validate(spec)
    if not event.requires_collection:
        raise ValueError('collection forbidden for uploaded/existing data')
    state=checkpoint or {}
    records=list(state.get('records',[]))
    seen={(p['platform'],p['kind'],p['raw_id']) for p in records}
    coverage=list(state.get('coverage',[]))
    requests=state.get('requests',0)
    totals={kind:sum(p['kind']==kind for p in records) for kind in ('post','comment')}
    progress=dict(state.get('progress',{}))
    def save():
        save_checkpoint({'records':records,'coverage':coverage,'requests':requests,'progress':progress})
    for platform in spec.platforms:
        previous=progress.get(platform,{})
        if previous.get('done'):
            continue
        cursor,cursors,status,pages=previous.get('cursor'),set(previous.get('cursors',[])),'completed',previous.get('pages',0)
        coverage=[entry for entry in coverage if entry['platform']!=platform]
        for page in range(pages,spec.max_pages):
            check_cancel()
            if totals['post'] >= spec.max_posts and totals['comment'] >= spec.max_comments:
                status='sample_limit'; break
            response = None
            for attempt in range(spec.max_retries+1):
                check_cancel()
                if requests>=spec.max_pages*len(spec.platforms)*(spec.max_retries+1):
                    status='partial'; break
                try:
                    requests += 1
                    save()
                    payload={'operation':'fetch_page',
                        'include_posts':spec.max_posts>0,'include_comments':spec.max_comments>0,
                        'event':event.model_dump(mode='json'),'cursor':cursor,'session_ref':spec.session_ref,
                        'remaining_posts':spec.max_posts-totals['post'],
                        'remaining_comments':spec.max_comments-totals['comment']}
                    response = fetch_page(payload) if platform=='x' else invoke_connector('crawl',platform,payload)
                    if response.get('partial'):
                        status='partial'
                    break
                except (WaitingForAuthentication,ConnectorUnavailable):
                    raise
                except Exception:
                    if attempt == spec.max_retries:
                        status='partial'
                    else:
                        time.sleep(spec.interval_seconds*(attempt+1))
            if response is None:
                break
            pages += 1
            for raw in response.get('records',[]):
                raw = dict(raw)
                raw.setdefault('platform',platform)
                raw.setdefault('post_id','p-'+hashlib.sha256(f"{platform}:{raw.get('kind','post')}:{raw.get('raw_id')}".encode()).hexdigest())
                post = PostRecord.model_validate(raw)
                if post.platform != platform:
                    raise ValueError('platform adapter returned records for another platform')
                key = (post.platform,post.kind,post.raw_id)
                if key in seen or totals[post.kind] >= (spec.max_posts if post.kind == 'post' else spec.max_comments):
                    continue
                seen.add(key)
                if event.start and post.published_at and not event.start <= post.published_at < event.end:
                    continue
                if post.published_at and post.published_at > event.as_of:
                    continue
                records.append(post.model_dump(mode='json')); totals[post.kind] += 1
            next_cursor = response.get('next_cursor')
            if next_cursor is None:
                progress[platform]={'done':True,'pages':pages}
                save()
                break
            if not isinstance(next_cursor,str) or next_cursor in cursors:
                status='partial'; break
            cursors.add(next_cursor); cursor=next_cursor
            progress[platform]={'cursor':cursor,'pages':pages,'cursors':list(cursors),'done':False}
            save()
            if page == spec.max_pages-1:
                status='page_limit'
            time.sleep(spec.interval_seconds)
        coverage.append({'platform':platform,'status':status,'pages':pages})
        save()
    return {'records':records,'coverage':coverage,'requests':requests,'counts':totals,
            'status':'completed' if records and all(c['status']=='completed' for c in coverage) else 'partial',
            'historical_completeness_verified':False}
