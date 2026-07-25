import type { AdNetworkAdapter } from "./registry.js";
import { externalTagAdapter } from "./external-tag.js";
const loaded = new Set<string>();

export const exoclickAdapter: AdNetworkAdapter = {
  id: "exoclick",
  async load(network, context) {
    const src = network.loader?.src;
    if (src && !loaded.has(src)) {
      loaded.add(src);
      context.emit("network-loaded", { network: "exoclick", loader: src });
    }
  },
  mount(unit, container, context, signal) {
    return externalTagAdapter.mount({ assume_filled_on_mount: true, mount_grace_ms: 750, ...unit }, container, context, signal);
  },
  destroy: externalTagAdapter.destroy
};
