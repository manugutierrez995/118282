import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import os from 'node:os';
import { compileWorkbook } from '../dist/packages/compiler/compiler.js';
import { ShareLedger, normalizePartners, selectPartner } from '../dist/server/share-ledger.js';

const workbook='examples/ad-runner-template.xlsx';

test('groups repeated websites, slots, partners, networks and sheets into v2 manifests', async()=>{
  const result=await compileWorkbook(workbook);
  assert.equal(result.valid,true, result.sites.flatMap(s=>s.errors).join('\n'));
  const anime=result.sites.find(s=>s.site==='animeplex.lol').manifest;
  assert.equal(anime.spec,'ad-runner/2');
  const right=anime.placements.find(p=>p.id==='right_rail');
  assert.equal(right.partners.length,2);
  assert.deepEqual(right.partners.map(p=>p.partner_id).sort(),['alejandro','partner_b']);
  assert.ok(Object.keys(anime.accounts).includes('exo_account_a'));
  assert.ok(Object.keys(anime.accounts).includes('exo_account_b'));
  const solo=result.sites.find(s=>s.site==='solo.example').manifest;
  assert.equal(solo.placements[0].partners[0].lane.length,3);
});

test('confirmed-fills prioritizes partner behind target and normalizes shares', ()=>{
  const partners=normalizePartners([{partner_id:'a',partner_name:'A',share_target:70,lane:[]},{partner_id:'b',partner_name:'B',share_target:30,lane:[]}]);
  const selected=selectPartner(partners,[{site_id:'s',slot_id:'x',partner_id:'a',opportunities_assigned:1,confirmed_fills:9,no_fills:0,failures:0},{site_id:'s',slot_id:'x',partner_id:'b',opportunities_assigned:1,confirmed_fills:1,no_fills:0,failures:0}], 'confirmed-fills');
  assert.equal(selected.partner.partner_id,'b');
  assert.equal(partners[0].normalized_share,0.7);
});

test('zero total shares are rejected', ()=>{
  assert.throws(()=>normalizePartners([{partner_id:'a',partner_name:'A',share_target:0,lane:[]}]),/every Share Target/);
});

test('ledger is persistent and duplicate outcome reports are idempotent', async()=>{
  const dir=await mkdtemp(os.tmpdir()+'/adrunner-');
  try{
    const ledger=new ShareLedger(dir);
    const placement={id:'slot',anchor:'slot',devices:['all'],priority:0,enabled:true,candidates:[],share_basis:'confirmed-fills',share_policy:'open-yield',partners:[{partner_id:'a',partner_name:'A',share_target:50,lane:[{unit:'u',priority:1,timeout_ms:100}]},{partner_id:'b',partner_name:'B',share_target:50,lane:[{unit:'v',priority:1,timeout_ms:100}]}]};
    const sel=ledger.select('site.test', placement, true);
    assert.ok(sel.cycle_id);
    ledger.outcome('site.test','slot',{cycle_id:sel.cycle_id,final_partner:sel.partner,unit:'u',outcome:'filled'});
    ledger.outcome('site.test','slot',{cycle_id:sel.cycle_id,final_partner:sel.partner,unit:'u',outcome:'filled'});
    const reopened=new ShareLedger(dir);
    const row=reopened.rows('site.test','slot').find(r=>r.partner_id===sel.partner);
    assert.equal(row.confirmed_fills,1);
  } finally { await rm(dir,{recursive:true,force:true}); }
});

