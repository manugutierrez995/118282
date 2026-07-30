export function sizeLabel(size = {}) { return size.width ? `${size.width}×${size.height}` : size.mode || "provider-defined"; }
export function createFallback(ad, reader = false) {
  const node = document.createElement("div");
  node.className = `doku-ad-fallback${ad.size?.width ? ` doku-ad-fallback--${ad.size.width}x${ad.size.height}` : ""}`;
  if (ad.size?.width) { node.style.setProperty("--ad-width", `${ad.size.width}px`); node.style.setProperty("--ad-ratio", `${ad.size.width}/${ad.size.height}`); }
  const copy = document.createElement("span");
  const title = document.createElement("strong"); title.className = "doku-ad-fallback-title"; title.textContent = "Doku-Doujins";
  const subtitle = document.createElement("small"); subtitle.className = "doku-ad-fallback-subtitle"; subtitle.textContent = reader ? "The next page awaits." : "Independent works. Endless pages.";
  copy.append(title, subtitle); node.append(copy); return node;
}
