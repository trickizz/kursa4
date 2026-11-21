# Генерирует badges/coverage.svg из coverage.json (для CI).
import json
import os

with open('coverage.json', encoding='utf-8') as fh:
    pct = round(json.load(fh)['totals']['percent_covered'])
color = '#4c1' if pct >= 90 else ('#a3c51c' if pct >= 75 else ('#dfb317' if pct >= 60 else '#e05d44'))
label, value, lw, vw = 'coverage', str(pct) + '%', 60, 48
svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{lw + vw}" height="20" role="img" aria-label="{label}: {value}"><linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient><clipPath id="r"><rect width="{lw + vw}" height="20" rx="3" fill="#fff"/></clipPath><g clip-path="url(#r)"><rect width="{lw}" height="20" fill="#555"/><rect x="{lw}" width="{vw}" height="20" fill="{color}"/><rect width="{lw + vw}" height="20" fill="url(#s)"/></g><g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11"><text x="{lw / 2}" y="15" fill="#010101" fill-opacity=".3">{label}</text><text x="{lw / 2}" y="14">{label}</text><text x="{lw + vw / 2}" y="15" fill="#010101" fill-opacity=".3">{value}</text><text x="{lw + vw / 2}" y="14">{value}</text></g></svg>'
os.makedirs('badges', exist_ok=True)
with open('badges/coverage.svg', 'w', encoding='utf-8') as fh:
    fh.write(svg)
print('coverage badge:', value)
