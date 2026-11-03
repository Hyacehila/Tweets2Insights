"""Explicit media connector boundary; no fabricated OCR or visual interpretation."""
import hashlib
from datetime import datetime, timezone
from opinion_core.schemas.artifacts import EvidenceCard


def analyze_media(posts, invoke, limit=20):
    sources = [{'post_id':p['post_id'],'media_ref':ref} for p in posts for ref in p.get('media_refs',[])][:limit]
    if not sources:
        return {'status':'skipped_no_media','evidence':[]}
    response = invoke({'operation':'analyze_media','items':sources})
    allowed = {(s['post_id'],s['media_ref']) for s in sources}
    cards = []
    for item in response.get('items',[]):
        if (item['post_id'],item['media_ref']) not in allowed:
            raise ValueError('media adapter returned an unrequested source')
        text = str(item.get('ocr',''))+'\n'+str(item.get('interpretation',''))
        digest = hashlib.sha256((item['media_ref']+text).encode()).hexdigest()
        cards.append(EvidenceCard(evidence_id='m-'+digest,kind='media',title=item['post_id'],excerpt=text,
                     source_ref=item['media_ref'],retrieved_at=datetime.now(timezone.utc),content_sha256=digest).model_dump(mode='json'))
    return {'status':'completed','evidence':cards,'selected_n':len(sources),
            'scope':'connector-supplied OCR/interpretation; image contribution requires separate ablation'}
