import asyncio
import tempfile
import unittest
from datetime import date
from pathlib import Path
import httpx
import council as c


def model(name='alpha/model:free', **prices):
    return {'id':name,'pricing':{'prompt':'0','completion':'0','request':'0', **prices},
            'architecture':{'input_modalities':['text'],'output_modalities':['text']}, 'supported_parameters':['max_tokens']}


class CouncilTests(unittest.TestCase):
    def test_gate(self):
        self.assertTrue(c.free_model(model()))
        for m in [model('alpha/paid'), model(completion='0.001'), model(request='1'), model(prompt=None), model(prompt='NaN'), model(prompt=True)]:
            self.assertFalse(c.free_model(m))
        m=model(); del m['pricing']['completion']; self.assertFalse(c.free_model(m))

    def test_account(self):
        cfg={'providers':{'openrouter':{'confirmed_unbilled_free_account':True,'checked_on':date.today().isoformat(),'daily_cap':40}}}
        self.assertTrue(c.account_ok(cfg,'openrouter'))
        cfg['providers']['openrouter']['checked_on']='2000-01-01'
        self.assertFalse(c.account_ok(cfg,'openrouter'))

    def test_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'usage.sqlite3'
            self.assertTrue(c.reserve(db,'openrouter',2,100000))
            self.assertTrue(c.reserve(db,'openrouter',2,100001))
            self.assertFalse(c.reserve(db,'openrouter',2,100002))
            self.assertTrue(c.reserve(db,'openrouter',2,200000))

    def test_diversity(self):
        ms=[{'provider':'openrouter','model':m,'family':m.split('/')[0]} for m in ['a/x:free','a/y:free','b/x:free']]
        self.assertEqual([m['model'] for m in c.select(ms,2)],['a/x:free','b/x:free'])

    def test_scrub(self):
        self.assertEqual(c.scrub({'text':'key123'}, {'p':'key123'})['text'],'[REDACTED API KEY]')

    def test_mock_discovery_and_calls(self):
        async def work(d):
            seen=[]
            def handler(request):
                if request.method=='GET':
                    return httpx.Response(200,json={'data':[model(),model('beta/model:free'),model('alpha/paid'),model('gamma/model:free',prompt='1')]})
                import json
                body=json.loads(request.content); seen.append(body)
                if body['model'].startswith('beta/'):
                    return httpx.Response(429,json={'error':'limited'})
                return httpx.Response(200,json={'model':body['model'],'choices':[{'message':{'content':'नमस्ते'},'finish_reason':'length'}]})
            cfg={'providers':{'openrouter':{'confirmed_unbilled_free_account':True,'checked_on':date.today().isoformat(),'daily_cap':40}}}
            keys={'openrouter':'test-secret'}
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as cli:
                ms,_=await c.discover(cli,cfg,keys)
                self.assertEqual(len(ms),2)
                sem={'openrouter':asyncio.Semaphore(2)}
                a,b=await asyncio.gather(*(c.ask(cli,sem,m,'मूल prompt',keys,Path(d)/'usage.db',4096) for m in ms))
                self.assertEqual(a['status'],'partial'); self.assertEqual(a['text'],'नमस्ते')
                self.assertEqual(b['status'],'error'); self.assertEqual(b['text'],'')
                self.assertEqual(len(seen),2)
                self.assertEqual(seen[0]['provider']['max_price']['completion'],0)
                c.report(Path(d),'मूल prompt',{1:a,2:b},[])
                text=(Path(d)/'master_report.md').read_text(encoding='utf-8')
                self.assertIn('नमस्ते',text); self.assertIn('HTTP 429',text)
        with tempfile.TemporaryDirectory() as d: asyncio.run(work(d))

    def test_catalog_failure(self):
        async def work():
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(503))) as cli:
                cfg={'providers':{'openrouter':{'confirmed_unbilled_free_account':True,'checked_on':date.today().isoformat(),'daily_cap':40}}}
                ms,notes=await c.discover(cli,cfg,{'openrouter':'test'})
                self.assertFalse(ms); self.assertTrue(notes)
        asyncio.run(work())


    def test_budget_and_compact(self):
        m={'context_length':10000,'max_output_tokens':1024}
        self.assertEqual(c.budget(m,'hello',8192),1024)
        self.assertEqual(c.budget(m,'x'*10000,8192),0)
        self.assertEqual(c.budget({},'hello',8192),4096)
        self.assertIn('मूल prompt',c.compact('मूल prompt',250))
        self.assertIn('250 words',c.compact('मूल prompt',250))

    def test_health_and_selection(self):
        a={'provider':'openrouter','model':'a/x:free','family':'a'}
        b={'provider':'openrouter','model':'b/x:free','family':'b'}
        history={}
        c.update_health(history,{**a,'status':'error'})
        self.assertEqual(c.health_order([a,b],history),[b,a])
        c.update_health(history,{**a,'status':'ok'})
        self.assertEqual(c.health_order([a,b],history),[a,b])
        self.assertEqual(c.select([a,b],0),[])

if __name__=='__main__': unittest.main()
