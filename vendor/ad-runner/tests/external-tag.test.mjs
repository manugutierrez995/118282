import test from 'node:test';
import assert from 'node:assert/strict';
import { externalTagAdapter, iframeDocument } from '../dist/packages/adapters/external-tag.js';
import { exoclickAdapter } from '../dist/packages/adapters/exoclick.js';

function installDom() {
  const windowListeners = new Map();
  class Iframe {
    constructor(){ this.attrs={}; this.style={}; this.listeners=new Map(); this.contentWindow={}; this.removed=false; }
    setAttribute(k,v){ this.attrs[k]=v; }
    addEventListener(k,fn){ this.listeners.set(k, fn); }
    removeEventListener(k){ this.listeners.delete(k); }
    remove(){ this.removed=true; }
    set srcdoc(v){ this._srcdoc=v; setTimeout(()=>this.listeners.get('load')?.({}),0); }
    get srcdoc(){ return this._srcdoc; }
  }
  class Container {
    constructor(){ this.children=[]; this.textContent=''; }
    appendChild(el){ this.children.push(el); }
    querySelectorAll(){ return this.children.filter(x => x instanceof Iframe); }
  }
  global.window = {
    setTimeout, clearTimeout,
    addEventListener(type, fn){ windowListeners.set(type, fn); },
    removeEventListener(type, fn){ if (windowListeners.get(type) === fn) windowListeners.delete(type); },
    __listeners: windowListeners
  };
  global.document = { createElement(name){ assert.equal(name, 'iframe'); return new Iframe(); } };
  global.DOMException = global.DOMException || class DOMException extends Error { constructor(message, name){ super(message); this.name = name; } };
  return { Container };
}

const ctx = { manifest: { networks: { exoclick: { adapter: 'exoclick', enabled: true }, ext: { adapter: 'external-tag', enabled: true } } }, site: 's', emit(){} };

test('partner head markup precedes untouched ad scripts in iframe document', () => {
  const head='<meta http-equiv="Delegate-CH" content="Sec-CH-UA https://s.pemsrv.com">';
  const ad='<script async src="https://a.pemsrv.com/ad-provider.js"></script>';
  const document=iframeDocument(ad,head);
  assert.ok(document.indexOf(head)<document.indexOf(ad));
  assert.equal(document.match(/ad-provider\.js/g)?.length,1);
});

test('external tag preserves scripts in sandboxed iframe srcdoc', async () => {
  const { Container } = installDom();
  const container = new Container();
  const result = await externalTagAdapter.mount({ network: 'ext', width: 300, height: 250, markup: '<script>window.x=1</script>', assume_filled_on_mount: true, mount_grace_ms: 1 }, container, ctx, new AbortController().signal);
  const iframe = container.children[0];
  assert.equal(result.outcome, 'filled');
  assert.equal(iframe.attrs.sandbox, 'allow-scripts allow-popups allow-popups-to-escape-sandbox');
  assert.match(iframe.srcdoc, /<script>window\.x=1<\/script>/);
});

test('exoclick assumes filled after iframe load grace period', async () => {
  const { Container } = installDom();
  const result = await exoclickAdapter.mount({ network: 'exoclick', markup: '<script>exo()</script>', mount_grace_ms: 1 }, new Container(), ctx, new AbortController().signal);
  assert.equal(result.outcome, 'filled');
});

test('external tag abort removes iframe and rejects', async () => {
  const { Container } = installDom();
  const container = new Container();
  const controller = new AbortController();
  const promise = externalTagAdapter.mount({ network: 'ext', markup: 'x', assume_filled_on_mount: true, mount_grace_ms: 50 }, container, ctx, controller.signal);
  controller.abort();
  await assert.rejects(promise, /aborted/);
  assert.equal(container.children[0].removed, true);
});
