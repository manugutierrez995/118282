"""Shared canonical placement vocabulary for Ad Runner import surfaces."""
CANONICAL_PLACEMENTS = {
    "Top Banner": ("top-banner", "728x90", "display", "all"),
    "Leaderboard": ("leaderboard", "970x90", "display", "all"),
    "Banner": ("banner", "728x90", "display", "all"),
    "Left Skyscraper": ("left-rail", "160x600", "display", "desktop"),
    "Right Skyscraper": ("right-rail", "160x600", "display", "desktop"),
    "Between Content": ("between-content", "728x90", "display", "all"),
    "Between-Pages Banner": ("between-content", "728x90", "display", "all"),
    "Chapter End": ("chapter-end", "728x90", "display", "all"),
    "Rectangle": ("in-content", "300x250", "display", "all"),
    "Mobile Intermission": ("mobile-intermission", "300x250", "display", "mobile"),
    "Mobile Sticky": ("mobile-sticky", "320x50", "sticky", "mobile"),
    "Mobile Interstitial": ("mobile-interstitial", "N/A", "interstitial", "mobile"),
    "Desktop Interstitial": ("desktop-interstitial", "N/A", "interstitial", "desktop"),
    "Desktop Video Slider": ("desktop-video-slider", "N/A", "video-slider", "desktop"),
    "Popunder": ("popunder", "1x1", "popunder", "all"),
    "Custom": ("custom", "300x250", "custom", "all"),
}

# Runtime/manifests keep accepting these IDs. Importers never destructively rewrite
# rows that already contain one of them.
LEGACY_ALIASES = {
    "top": "top-banner",
    "between-pages-banner": "between-content",
    "left-skyscraper": "left-rail",
    "right-skyscraper": "right-rail",
    "mobile-bottom": "mobile-sticky",
    "interstitial": "mobile-interstitial",
}

def placement_for(name: str):
    return CANONICAL_PLACEMENTS.get(name.strip().title())
