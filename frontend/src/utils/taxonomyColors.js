/**
 * Taxonomy-based color assignment for ecosystem network nodes.
 * JS mirror of backend/app/services/taxonomy_colors.py
 */

export const PHYLUM_PRIORITY_COLORS = {
  Bacillota: '#08519c',
  Bacillota_A: '#2171b5',
  Bacillota_B: '#4292c6',
  Bacillota_C: '#6baed6',
  Bacillota_I: '#9ecae1',
  Bacteroidota: '#d73027',
  Pseudomonadota: '#1a9850',
  Actinomycetota: '#ae017e',
  Heterokonta: '#756bb1',
  Firmicutes: '#4292c6',
  Bacteroidetes: '#d73027',
  Proteobacteria: '#1a9850',
  Actinobacteria: '#ae017e',
  Fusobacteria: '#e6ab02',
  Verrucomicrobia: '#66c2a5',
  Euryarchaeota: '#a6761d',
  Tenericutes: '#e78ac3',
  Spirochaetes: '#fc8d62',
}

export const MODULE_COLORS = [
  '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
  '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
  '#aec7e8', '#ffbb78',
]

function hexToRgb(hex) {
  const h = hex.replace('#', '')
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}

function rgbToHex(r, g, b) {
  return '#' + [r, g, b].map(c => Math.max(0, Math.min(255, Math.round(c))).toString(16).padStart(2, '0')).join('')
}

export function lightenColor(hex, amount = 0.35) {
  const [r, g, b] = hexToRgb(hex)
  return rgbToHex(r + (255 - r) * amount, g + (255 - g) * amount, b + (255 - b) * amount)
}

export function darkenColor(hex, amount = 0.35) {
  const [r, g, b] = hexToRgb(hex)
  return rgbToHex(r * (1 - amount), g * (1 - amount), b * (1 - amount))
}
