export const STORAGE_KEY = 'unidad.apariencia.v1'

export type Appearance = {
  color: string
  font: 'system' | 'humanist' | 'serif'
  size: number
  corners: 'normal' | 'soft' | 'square'
}

export const DEFAULT_APPEARANCE: Appearance = { color: '#185648', font: 'system', size: 100, corners: 'normal' }

const fonts: Record<Appearance['font'], string> = {
  system: '"Source Sans 3", "Segoe UI", ui-sans-serif, system-ui, sans-serif',
  humanist: 'Verdana, Geneva, sans-serif',
  serif: 'Georgia, "Times New Roman", serif',
}

export function normalizeAppearance(value: unknown): Appearance {
  const data = value && typeof value === 'object' ? value as Record<string, unknown> : {}
  return {
    color: typeof data.color === 'string' && /^#[0-9a-f]{6}$/i.test(data.color) ? data.color.toLowerCase() : DEFAULT_APPEARANCE.color,
    font: data.font === 'humanist' || data.font === 'serif' ? data.font : 'system',
    size: typeof data.size === 'number' && Number.isFinite(data.size) ? Math.max(90, Math.min(120, Math.round(data.size / 5) * 5)) : 100,
    corners: data.corners === 'soft' || data.corners === 'square' ? data.corners : 'normal',
  }
}

export function loadAppearance(): Appearance {
  try { return normalizeAppearance(JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')) }
  catch { return { ...DEFAULT_APPEARANCE } }
}

function blend(hex: string, target: string, amount: number): string {
  const rgb = (color: string) => [1, 3, 5].map((i) => parseInt(color.slice(i, i + 2), 16))
  const source = rgb(hex), dest = rgb(target)
  return '#' + source.map((n, i) => Math.round(n * (1 - amount) + dest[i] * amount).toString(16).padStart(2, '0')).join('')
}

function contrastWithWhite(hex: string): number {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
  return 1.05 / (0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2] + 0.05)
}

export function applyAppearance(appearance: Appearance): void {
  const root = document.documentElement
  root.style.fontSize = `${appearance.size}%`
  root.style.setProperty('--font-sans', fonts[appearance.font])
  root.style.fontFamily = fonts[appearance.font]
  const radii = appearance.corners === 'square' ? ['0.125rem', '0.25rem', '0.375rem'] : appearance.corners === 'soft' ? ['0.75rem', '1rem', '1.25rem'] : ['0.375rem', '0.5rem', '0.75rem']
  ;['--radius-md', '--radius-lg', '--radius-xl'].forEach((name, index) => root.style.setProperty(name, radii[index]))
  if (appearance.color === DEFAULT_APPEARANCE.color) {
    for (const shade of [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]) root.style.removeProperty(`--color-brand-${shade}`)
    return
  }
  // El tono principal se oscurece si hace falta para mantener contraste con blanco.
  let primary = appearance.color
  while (contrastWithWhite(primary) < 4.5) primary = blend(primary, '#000000', 0.08)
  const colors: Record<number, string> = { 50: blend(primary, '#ffffff', .95), 100: blend(primary, '#ffffff', .90), 200: blend(primary, '#ffffff', .77), 300: blend(primary, '#ffffff', .60), 400: blend(primary, '#ffffff', .35), 500: blend(primary, '#ffffff', .12), 600: primary, 700: primary, 800: blend(primary, '#000000', .18), 900: blend(primary, '#000000', .32), 950: blend(primary, '#000000', .48) }
  Object.entries(colors).forEach(([shade, color]) => root.style.setProperty(`--color-brand-${shade}`, color))
}
