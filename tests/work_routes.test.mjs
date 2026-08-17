import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolveRoute, workUrl } from '../src/router/router.js';

test('/work/foo parses as a work route with exact slug', () => {
  assert.deepEqual(resolveRoute({ pathname: '/work/foo', search: '' }), { kind: 'work', work: 'foo', chapter: null, pathname: '/work/foo' });
});

test('encoded work slugs decode safely and URLs encode from stored slugs', () => {
  assert.equal(resolveRoute({ pathname: '/work/Foo%20Bar%2FBaz', search: '?chapter=chapter_2' }).work, 'Foo Bar/Baz');
  assert.equal(resolveRoute({ pathname: '/work/Foo%20Bar%2FBaz', search: '?chapter=chapter_2' }).chapter, 'chapter_2');
  assert.equal(workUrl('Foo Bar/Baz', 'chapter_2'), '/work/Foo%20Bar%2FBaz?chapter=chapter_2');
});

test('malformed work slug encoding fails safely to not-found', () => {
  assert.equal(resolveRoute({ pathname: '/work/%E0%A4%A', search: '' }).kind, 'not-found');
});

test('/ remains home and account routes remain unchanged', () => {
  assert.equal(resolveRoute({ pathname: '/', search: '' }).kind, 'home');
  assert.equal(resolveRoute({ pathname: '/profiles', search: '' }).kind, 'profiles');
  assert.equal(resolveRoute({ pathname: '/profiles/new', search: '' }).kind, 'profiles-new');
  assert.equal(resolveRoute({ pathname: '/account/profile', search: '' }).kind, 'account-profile');
  assert.equal(resolveRoute({ pathname: '/account/bookmarks', search: '' }).kind, 'account-bookmarks');
  assert.equal(resolveRoute({ pathname: '/account/settings', search: '' }).kind, 'account-settings');
});

test('legacy query-style reader URLs still resolve as legacy reader routes', () => {
  assert.deepEqual(resolveRoute({ pathname: '/', search: '?source=e&work=foo&chapter=chapter_1' }), { kind: 'legacy-reader', work: 'foo', chapter: 'chapter_1', pathname: '/' });
  assert.equal(resolveRoute({ pathname: '/reader', search: '?source=e&work=foo&chapter=chapter_1' }).kind, 'legacy-reader');
});

test('work route renderer loads existing catalog work, validates chapters, and shows not-found for missing work', async () => {
  const page = await readFile(new URL('../src/page/page.js', import.meta.url), 'utf8');
  assert.match(page, /const work=await loadWork\(route\.work\)/);
  assert.match(page, /if\(!work\) return showNotFound\(\)/);
  assert.match(page, /if\(!chapters\.length\) return showNotFound\(\)/);
  assert.match(page, /route\.chapter&&chapters\.includes\(route\.chapter\)\?route\.chapter:chapters\[0\]/);
  assert.match(page, /Reader\.start\(work\.slug,chapter,\{source:workSource\(work\)\}\)/);
});

test('work clicks navigate through canonical router and reader events canonicalize', async () => {
  const [search, rotunda, reader] = await Promise.all([
    readFile(new URL('../src/components/search.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/components/rotunda.js', import.meta.url), 'utf8'),
    readFile(new URL('../src/page/reader.js', import.meta.url), 'utf8'),
  ]);
  assert.match(search, /navigate\(workUrl\(slug\)\)/);
  assert.match(rotunda, /navigate\(workUrl\(card\.slug\)\)/);
  assert.match(reader, /navigate\(workUrl\(work, chapter\)\)/);
});

