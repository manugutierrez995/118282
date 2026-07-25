import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { eligibleGroup } from '../src/components/landing_ads.js';

test('landing ad device groups do not reinterpret intrusive formats', () => {
  assert.equal(eligibleGroup(1920), 'wide');
  assert.equal(eligibleGroup(1499), 'middle');
  assert.equal(eligibleGroup(768), 'middle');
  assert.equal(eligibleGroup(767), 'mobile');
  assert.equal(eligibleGroup(320), 'mobile');
});

test('landing uses one native runtime contract with cleanup and failure isolation', async () => {
  const source = await readFile(new URL('../src/components/landing_ads.js', import.meta.url), 'utf8');
  assert.match(source, /dataset\.adRunnerSlot = slot/);
  assert.match(source, /dataset\.adRunnerSite = config\.siteId/);
  assert.match(source, /dataset\.adRunnerBase = config\.baseUrl/);
  assert.match(source, /window\.AdRunner\?\.stop/);
  assert.match(source, /if \(session\?\.root === root\)/);
  assert.match(source, /catch \{\s*cleanup\(\)/);
  assert.doesNotMatch(source, /popunder|mobile-sticky|interstitial/);
});

test('production configuration is disabled safely until an explicit origin is supplied', async () => {
  const config = JSON.parse(await readFile(new URL('../public/ad-runner.json', import.meta.url), 'utf8'));
  assert.deepEqual(config, { enabled: false, siteId: '564578634.xyz', baseUrl: '' });
});
