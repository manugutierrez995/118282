import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';

test('GUI and simple CSV share canonical placements and preserve documented aliases', () => {
  const code = `import json, ad_runner_gui as gui, simple_partner_csv as csv\nfrom placement_vocabulary import LEGACY_ALIASES\nprint(json.dumps({'gui':gui.MAPPINGS,'csv':csv.PLACEMENTS,'aliases':LEGACY_ALIASES}))`;
  const data = JSON.parse(execFileSync('python3', ['-c', code], { encoding: 'utf8' }));
  assert.equal(data.gui['Top Banner'][0], 'top-banner');
  assert.equal(data.csv['top banner'][0], 'top-banner');
  assert.equal(data.gui['Left Skyscraper'][0], 'left-rail');
  assert.equal(data.csv['mobile intermission'][0], 'mobile-intermission');
  assert.equal(data.gui['Mobile Sticky'][0], 'mobile-sticky');
  assert.equal(data.aliases.top, 'top-banner');
  assert.equal(data.aliases['mobile-bottom'], 'mobile-sticky');
});
