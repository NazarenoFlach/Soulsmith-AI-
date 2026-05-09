from html import escape

from app.models.build import Item


class ImageService:
    def fallback_svg(self, item: Item) -> str:
        label = escape(item.name)
        category = escape(item.category.title())
        accent = self._accent_for_category(item.category)
        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="360" height="360" viewBox="0 0 360 360" role="img" aria-label="{label}">
  <defs>
    <radialGradient id="glow" cx="50%" cy="38%" r="62%">
      <stop offset="0%" stop-color="{accent}" stop-opacity=".34"/>
      <stop offset="55%" stop-color="#18130d" stop-opacity=".78"/>
      <stop offset="100%" stop-color="#070605"/>
    </radialGradient>
  </defs>
  <rect width="360" height="360" fill="url(#glow)"/>
  <rect x="32" y="32" width="296" height="296" rx="18" fill="none" stroke="#8f7241" stroke-opacity=".55"/>
  <path d="M180 78l34 73 78 12-56 55 13 77-69-36-69 36 13-77-56-55 78-12z" fill="{accent}" fill-opacity=".18" stroke="{accent}" stroke-opacity=".55" stroke-width="4"/>
  <text x="180" y="250" text-anchor="middle" fill="#efe2c0" font-size="26" font-family="Georgia, serif">{label}</text>
  <text x="180" y="282" text-anchor="middle" fill="#b9a06d" font-size="16" font-family="Arial, sans-serif" letter-spacing="2">{category}</text>
</svg>"""

    def _accent_for_category(self, category: str) -> str:
        return {
            "weapon": "#d2a84c",
            "shield": "#9ca3af",
            "armor": "#b45309",
            "ring": "#f7c948",
            "spell": "#60a5fa",
            "tool": "#a78bfa",
        }.get(category, "#d2a84c")
