"""Durable reservations shared by every paid stage of a run."""
import json
import math
import os
import sqlite3
import uuid
from pathlib import Path


class BudgetExceeded(RuntimeError):
    pass


class CallLedger:
    def __init__(self, root, scope, max_calls, max_cost=None):
        self.path = Path(root) / 'call-ledger.sqlite'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.scope, self.max_calls, self.max_cost = scope, max_calls, max_cost
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS limits (scope TEXT PRIMARY KEY, calls INTEGER, cost REAL)')
            db.execute('CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, scope TEXT, stage TEXT, provider TEXT, reserved REAL, actual REAL, status TEXT, usage TEXT)')
            db.execute('INSERT OR IGNORE INTO limits VALUES (?,?,?)', (scope,max_calls,max_cost))
            if db.execute('SELECT calls,cost FROM limits WHERE scope=?',(scope,)).fetchone() != (max_calls,max_cost):
                raise ValueError('run budget is immutable')

    def reserve(self, stage, provider, upper_cost=None):
        if upper_cost is None and os.environ.get('T2I_PRICING_FILE'):
            prices=json.loads(Path(os.environ['T2I_PRICING_FILE']).read_text(encoding='utf-8'))
            upper_cost=prices.get(provider)
        if upper_cost is not None and (type(upper_cost) not in (int,float) or not math.isfinite(upper_cost) or upper_cost<0):
            raise ValueError('invalid operator-supplied upper cost')
        with sqlite3.connect(self.path, timeout=30) as db:
            db.execute('BEGIN IMMEDIATE')
            count, cost = db.execute('SELECT COUNT(*),COALESCE(SUM(COALESCE(actual,reserved)),0) FROM calls WHERE scope=?',(self.scope,)).fetchone()
            if count >= self.max_calls:
                raise BudgetExceeded('total call limit reached')
            if self.max_cost is not None and (upper_cost is None or cost+upper_cost > self.max_cost):
                raise BudgetExceeded('priced upper bound required within remaining money budget')
            call_id = uuid.uuid4().hex
            db.execute('INSERT INTO calls VALUES (?,?,?,?,?,?,?,?)',
                       (call_id,self.scope,stage,provider,upper_cost,None,'in_flight','{}'))
            return call_id

    def settle(self, call_id, usage=None, actual=None, status='returned'):
        if actual is not None and (type(actual) not in (int,float) or not math.isfinite(actual) or actual<0):
            raise ValueError('invalid actual provider cost')
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE calls SET usage=?,actual=?,status=? WHERE id=? AND scope=?',
                       (json.dumps(usage or {}),actual,status,call_id,self.scope))

    def summary(self):
        with sqlite3.connect(self.path) as db:
            rows = db.execute('SELECT stage,provider,reserved,actual,status,usage FROM calls WHERE scope=?',(self.scope,)).fetchall()
        return {'calls':len(rows), 'known_cost':sum(row[3] or 0 for row in rows),
                'cost_complete':all(row[3] is not None for row in rows),
                'records':[{'stage':r[0],'provider':r[1],'reserved_cost':r[2],'actual_cost':r[3],
                            'status':r[4],'usage':json.loads(r[5])} for r in rows]}
