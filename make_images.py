"""Generates the bundled illustrated food images (SVG) into frontend/assets/images.
Run once:  python tools/make_images.py   (output is already included in the project)"""
import os

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "assets", "images")
EMOJI_FONT = "'Segoe UI Emoji','Apple Color Emoji','Noto Color Emoji',sans-serif"

# file, emoji, gradient start, gradient end
ITEMS = [
    ("masala-dosa", "🥞", "#FFE0B2", "#FFB74D"), ("idli-sambar", "🍚", "#FFF3E0", "#FFCC80"),
    ("poha", "🥣", "#FFF9C4", "#FFD54F"), ("aloo-paratha", "🥙", "#FFE7C2", "#F4A261"),
    ("veg-thali", "🍱", "#FFD9C2", "#FF8A5B"), ("chicken-biryani", "🍛", "#FFE0B2", "#FF9A3C"),
    ("paneer-butter-masala", "🧀", "#FFE1D0", "#FF8F6B"), ("egg-curry-rice", "🥚", "#FFF0D6", "#FFB35C"),
    ("rajma-chawal", "🍲", "#FFD7D0", "#E86A4B"), ("samosa", "🥟", "#FFE9C7", "#F6B352"),
    ("vada-pav", "🥯", "#FFE3C4", "#F28C4B"), ("pav-bhaji", "🍲", "#FFD0C0", "#F4623A"),
    ("veg-sandwich", "🥪", "#E8F5D9", "#9CCC65"), ("veg-burger", "🍔", "#FFE2BC", "#FF9F45"),
    ("chicken-burger", "🍔", "#FFD8C4", "#F4793E"), ("french-fries", "🍟", "#FFF1B8", "#FFC93C"),
    ("hakka-noodles", "🍜", "#FFE6C9", "#FF9E5E"), ("chicken-roll", "🌯", "#FFE0C2", "#F59D52"),
    ("masala-chai", "☕", "#F3E0CF", "#C98B5E"), ("filter-coffee", "☕", "#EAD9C9", "#A9714B"),
    ("cold-coffee", "🥤", "#EFE0D4", "#B98560"), ("lime-soda", "🍋", "#F4FBD0", "#C6E04B"),
    ("mango-lassi", "🥭", "#FFF0B3", "#FFC107"), ("gulab-jamun", "🍮", "#FFD9CC", "#E57A5A"),
    ("ice-cream", "🍨", "#FFE0EC", "#F48FB1"), ("brownie", "🍫", "#EBD5C9", "#9C6B55"),
]


def card(emoji, c1, c2):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 400" width="600" height="400">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient></defs>
<rect width="600" height="400" fill="url(#g)"/>
<circle cx="70" cy="60" r="90" fill="#fff" opacity=".18"/><circle cx="560" cy="360" r="120" fill="#fff" opacity=".16"/>
<circle cx="300" cy="205" r="140" fill="#fff" opacity=".55"/><circle cx="300" cy="205" r="112" fill="#fff" opacity=".6"/>
<ellipse cx="300" cy="352" rx="120" ry="12" fill="#000" opacity=".08"/>
<text x="300" y="250" font-size="140" text-anchor="middle" font-family="{EMOJI_FONT}">{emoji}</text>
</svg>"""


os.makedirs(OUT, exist_ok=True)
for name, emoji, c1, c2 in ITEMS:
    with open(os.path.join(OUT, name + ".svg"), "w", encoding="utf-8") as f:
        f.write(card(emoji, c1, c2))

with open(os.path.join(OUT, "placeholder.svg"), "w", encoding="utf-8") as f:
    f.write(card("🍽️", "#FFF1E8", "#FFD2BC"))

with open(os.path.join(OUT, "hero.svg"), "w", encoding="utf-8") as f:
    f.write(f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 560 460" width="560" height="460">
<defs><linearGradient id="h" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFE3D3"/><stop offset="1" stop-color="#FFB894"/></linearGradient></defs>
<rect width="560" height="460" rx="40" fill="url(#h)"/>
<circle cx="280" cy="230" r="170" fill="#fff" opacity=".6"/><circle cx="280" cy="230" r="135" fill="#fff" opacity=".7"/>
<text x="280" y="290" font-size="190" text-anchor="middle" font-family="{EMOJI_FONT}">🍛</text>
<text x="95" y="110" font-size="64" text-anchor="middle" font-family="{EMOJI_FONT}">🥞</text>
<text x="470" y="120" font-size="64" text-anchor="middle" font-family="{EMOJI_FONT}">🍔</text>
<text x="80" y="390" font-size="60" text-anchor="middle" font-family="{EMOJI_FONT}">☕</text>
<text x="480" y="390" font-size="60" text-anchor="middle" font-family="{EMOJI_FONT}">🥟</text>
</svg>""")

logo = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
<defs><linearGradient id="l" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FF7A45"/><stop offset="1" stop-color="#FF6533"/></linearGradient></defs>
<rect width="64" height="64" rx="16" fill="url(#l)"/>
<path d="M20 14v14a4 4 0 0 0 4 4v18M16 14v12M24 14v12M28 14v12" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M42 50V14c-5 3-8 9-8 16 0 4 3 6 8 6" stroke="#fff" stroke-width="3" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""
for fn in ("logo.svg", "favicon.svg"):
    with open(os.path.join(OUT, fn), "w", encoding="utf-8") as f:
        f.write(logo)
print("generated", len(os.listdir(OUT)), "files")
