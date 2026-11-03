import hashlib
import re
from datetime import datetime, timezone
from opinion_core.schemas.artifacts import EvidenceCard


def web_cards(response, as_of):
    cards, seen = [],set()
    for source in response.get('results',[]):
        text = str(source.get('snippet') or source.get('content') or '')
        fingerprint = hashlib.sha256(re.sub(r'\s+','',text).casefold().encode()).hexdigest()
        if not text or fingerprint in seen:
            continue
        seen.add(fingerprint)
        date = source.get('date')
        try:
            date = datetime.fromisoformat(date.replace('Z','+00:00')) if date else None
            if date and not date.tzinfo:
                date=None
        except (ValueError,TypeError):
            date=None
        if date and date > as_of:
            continue
        cards.append(EvidenceCard(evidence_id='e-'+fingerprint,kind='web',title=str(source.get('title','')),
                     excerpt=text,source_url=source.get('url'),provider=response.get('provider'),
                     published_at=date,retrieved_at=datetime.now(timezone.utc),content_sha256=fingerprint).model_dump(mode='json'))
    return cards


def post_cards(posts, limit=20):
    return [EvidenceCard(evidence_id='p-'+hashlib.sha256(p['post_id'].encode()).hexdigest(),kind='post',
             title=p['post_id'],excerpt=p['content'][:1000],source_url=p.get('source_url'),source_ref=p['post_id'],
             published_at=p.get('published_at'),retrieved_at=datetime.now(timezone.utc),
             content_sha256=hashlib.sha256(p['content'].encode()).hexdigest()).model_dump(mode='json') for p in posts[:limit]]
