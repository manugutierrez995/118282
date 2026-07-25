import json, tempfile, unittest
from pathlib import Path
from simple_partner_csv import parse_simple_csv, import_into_workbook
from ad_runner_gui import save_workbook

HEAD='<meta http-equiv="Delegate-CH" content="Sec-CH-UA https://s.pemsrv.com">\n<meta name="x" content="y">'
MOBILE='<script async src="https://a.pemsrv.com/ad-provider.js"></script>\n<ins class="one"></ins>\n<script>(AdProvider=window.AdProvider||[]).push({"serve":{}});</script>'
BANNER='<script async src="https://a.magsrv.com/ad-provider.js"></script>\n<ins class="two"></ins>'
def block(n,site,owner,code=MOBILE,enabled='true',share='50%',ad='Mobile Interstitial',dims='N/A',head=HEAD):
 code=code.replace(chr(34),chr(34)*2); head=head.replace(chr(34),chr(34)*2)
 return f'''OWNER BLOCK {n},VALUE,WHAT TO ENTER\nWebsite / Domain,{site},x\nOwner Name,{owner},x\nEnabled,{enabled},x\nTraffic Share,{share},x\nAd Traffic Name,{owner} Ads,x\nClient Hints Meta Tag(s),"{head}",x\n,,\nAD NAME,DIMENSIONS,COMPLETE AD CODE\n{ad},{dims},"{code}"\nUnused,N/A,NONE\n'''
class ImportTest(unittest.TestCase):
 def parse(self,text):
  td=tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup); p=Path(td.name)/'x.csv'; p.write_text(text); return parse_simple_csv(p)
 def test_multiline_exact_and_none(self):
  bs=self.parse(block(1,'same.test','Alice')+block(2,'same.test','Bob',BANNER,ad='Banner',dims='900x250'))
  self.assertFalse([e for b in bs for e in b.errors]); self.assertEqual(bs[0].head_markup,HEAD); self.assertEqual(bs[0].ads[0].code,MOBILE); self.assertTrue(bs[0].ads[1].skipped)
  wb={'SheetNames':[],'Sheets':{}}; s=import_into_workbook(wb,bs); self.assertEqual(s['ads'],2)
  rows=wb['Sheets']['same.test']['rows']; self.assertEqual(len(rows),2); self.assertNotEqual(rows[0]['unit_id'],rows[1]['unit_id']); self.assertEqual(rows[0]['ad_code'],MOBILE)
 def test_reimport_and_manual_preservation(self):
  bs=self.parse(block(1,'same.test','Alice',share='100%')); manual={'site_id':'same.test','notes':'manual'}; wb={'SheetNames':['same.test'],'Sheets':{'same.test':{'rows':[manual]}}}
  import_into_workbook(wb,bs); import_into_workbook(wb,bs); self.assertEqual(len(wb['Sheets']['same.test']['rows']),2); self.assertIn(manual,wb['Sheets']['same.test']['rows'])
 def test_disabled_excluded_and_different_sites(self):
  bs=self.parse(block(1,'a.test','Alice',share='100%')+block(2,'b.test','Bob',enabled='false',share='50%'))
  self.assertFalse([e for b in bs for e in b.errors]); wb={'SheetNames':[],'Sheets':{}}; import_into_workbook(wb,bs); self.assertEqual(set(wb['SheetNames']),{'a.test','b.test'})
 def test_share_and_placeholder_rejected(self):
  bs=self.parse(block(1,'same.test','Alice',share='40%')+block(2,'same.test','Bob',share='50%',code='PASTE_CODE_OR_NONE'))
  errors='\n'.join(e for b in bs for e in b.errors); self.assertIn('not exactly 100%',errors); self.assertIn('CSV row',errors); self.assertIn('unresolved template',errors)
 def test_backup_atomic_save(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'w.xlsx'; save_workbook(p,{'SheetNames':[],'Sheets':{}}); backup=save_workbook(p,{'SheetNames':['x'],'Sheets':{'x':{'rows':[]}}}); self.assertTrue(backup.exists()); self.assertEqual(json.loads(p.read_text())['SheetNames'],['x'])
if __name__=='__main__': unittest.main()
