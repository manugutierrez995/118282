export const emptyProvider = { id: "empty", async initialize() {}, supports: () => true, async request() { return { state: "no-fill" }; }, render() {}, destroy() {} };
