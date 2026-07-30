const externalScripts = new Map();
export function copyScript(source) {
  const script = document.createElement("script");
  for (const attribute of source.attributes) script.setAttribute(attribute.name, attribute.value);
  script.textContent = source.textContent;
  return script;
}
export function appendExternalScript(source, parent) {
  const url = source.src;
  if (!url || !externalScripts.has(url)) {
    const script = copyScript(source);
    parent.appendChild(script);
    if (url) externalScripts.set(url, new Promise((resolve, reject) => { script.addEventListener("load", resolve, { once: true }); script.addEventListener("error", reject, { once: true }); }));
    return { node: script, promise: url ? externalScripts.get(url) : Promise.resolve() };
  }
  return { node: null, promise: externalScripts.get(url) };
}
export function clearScriptRegistryForTests() { externalScripts.clear(); }
