import campaigns from "../../data/monetization/house-campaigns.json" with { type: "json" };

export const houseProvider = {
    id: "house",
    async initialize() {},
    supports({ placement, format }) { return campaigns.campaigns.some(item => item.enabled && item.placements.includes(placement) && item.formats.includes(format)); },
    async request({ placement, format, now = new Date() }) {
        const eligible = campaigns.campaigns.filter(item => item.enabled && item.placements.includes(placement) && item.formats.includes(format) && (!item.start || new Date(item.start) <= now) && (!item.end || new Date(item.end) >= now));
        eligible.sort((a, b) => b.priority - a.priority || a.id.localeCompare(b.id));
        return eligible[0] ? { state: "filled", creative: eligible[0] } : { state: "no-fill" };
    },
    render() {}, destroy() {}
};
