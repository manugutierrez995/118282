const externalScripts = new Map();

export function copyScript(source) {
  const script = document.createElement("script");
  for (const attribute of source.attributes) script.setAttribute(attribute.name, attribute.value);
  script.textContent = source.textContent;
  return script;
}

function loadedPromise(script) {
  if (script.dataset.dokuLoaderReady === "true" || script.readyState === "complete") return Promise.resolve();
  return new Promise((resolve, reject) => {
    script.addEventListener("load", () => { script.dataset.dokuLoaderReady = "true"; resolve(); }, { once: true });
    script.addEventListener("error", reject, { once: true });
  });
}

/** Deduplicate only the network loader. Placement DOM and serve calls stay private. */
export function appendExternalScript(source, parent) {
  const url = source.src;
  if (!url) { const script = copyScript(source); parent.appendChild(script); return { node: script, promise: Promise.resolve() }; }
  if (externalScripts.has(url)) return { node: null, promise: externalScripts.get(url) };
  const existing = [...document.scripts].find(script => script.src === url);
  const script = existing || copyScript(source);
  const promise = loadedPromise(script);
  externalScripts.set(url, promise);
  if (!existing) (document.head || parent).appendChild(script);
  return { node: existing ? null : script, promise };
}

export function clearScriptRegistryForTests() { externalScripts.clear(); }
