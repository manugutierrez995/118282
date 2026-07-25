import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

test('index and reveal startup shells remain byte-for-byte identical', async () => {
  const [index, reveal] = await Promise.all([readFile('index.html', 'utf8'), readFile('reveal.html', 'utf8')]);
  assert.equal(index, reveal);
});
