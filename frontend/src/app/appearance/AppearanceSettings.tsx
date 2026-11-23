import { Palette, RotateCcw, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { applyAppearance, DEFAULT_APPEARANCE, loadAppearance, STORAGE_KEY } from './appearance'
import type { Appearance } from './appearance'
import './appearance.css'

const colors = [ ['Institucional', '#185648'], ['Azul', '#1d4ed8'], ['Verde', '#047857'], ['Violeta', '#6d28d9'], ['Turquesa', '#0e7490'], ['Coral', '#b93832'] ] as const

export default function AppearanceSettings() {
  const [open, setOpen] = useState(false)
  const [slot, setSlot] = useState<HTMLElement | null>(null)
  const [appearance, setAppearance] = useState<Appearance>(loadAppearance)
  useEffect(() => {
    const updateSlot = () => setSlot(document.getElementById('appearance-slot'))
    const observer = new MutationObserver(updateSlot)
    observer.observe(document.body, { childList: true, subtree: true })
    const timer = window.setTimeout(updateSlot, 0)
    return () => { observer.disconnect(); window.clearTimeout(timer) }
  }, [])
  useEffect(() => {
    applyAppearance(appearance)
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(appearance)) } catch { /* La vista sigue funcionando sin almacenamiento. */ }
  }, [appearance])
  useEffect(() => {
    if (!open) return
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [open])
  const change = <K extends keyof Appearance>(key: K, value: Appearance[K]) => setAppearance((current) => ({ ...current, [key]: value }))
  const widget = <div className={`appearance-widget ${slot ? 'appearance-widget--inline' : ''}`}>
    {open && <section className="appearance-panel" aria-label="Personalizar apariencia" id="appearance-panel">
      <div className="appearance-heading"><div><span className="appearance-eyebrow">A TU MANERA</span><h2>Personaliza tu vista</h2><p>Elige cómo quieres ver la plataforma.</p></div><button type="button" className="appearance-close" aria-label="Cerrar personalización" onClick={() => setOpen(false)}><X size={20} /></button></div>
      <div className="appearance-preview"><span>Vista previa</span><strong>Tu espacio de trabajo</strong><p>Una experiencia más cómoda para ti.</p><span className="appearance-preview-button">Botón de ejemplo</span></div>
      <fieldset><legend>Color principal</legend><p className="appearance-hint">Se aplica a los elementos principales de la interfaz.</p><div className="appearance-colors">{colors.map(([name, color]) => <button key={color} type="button" aria-label={name} aria-pressed={appearance.color === color} title={name} className="appearance-swatch" style={{ backgroundColor: color }} onClick={() => change('color', color)}>{appearance.color === color && '✓'}</button>)}<label className="appearance-custom" title="Elegir otro color"><span>Otro</span><input type="color" aria-label="Elegir color personalizado" value={appearance.color} onChange={(event) => change('color', event.target.value)} /></label></div><p className="appearance-hint">Los tonos se ajustan para facilitar la lectura.</p></fieldset>
      <label className="appearance-field" htmlFor="appearance-font"><span>Tipo de letra</span><select id="appearance-font" value={appearance.font} onChange={(event) => change('font', event.target.value as Appearance['font'])}><option value="system">Moderna (predeterminada)</option><option value="humanist">Verdana</option><option value="serif">Clásica (Georgia)</option></select></label>
      <label className="appearance-field" htmlFor="appearance-size"><span>Tamaño de letra <output>{appearance.size}%</output></span><input id="appearance-size" type="range" min="90" max="120" step="5" value={appearance.size} onChange={(event) => change('size', Number(event.target.value))} /><span className="appearance-range-labels"><span>Más pequeña</span><span>Más grande</span></span></label>
      <label className="appearance-field" htmlFor="appearance-corners"><span>Estilo de bordes</span><select id="appearance-corners" value={appearance.corners} onChange={(event) => change('corners', event.target.value as Appearance['corners'])}><option value="normal">Equilibrado</option><option value="soft">Redondeado</option><option value="square">Recto</option></select></label>
      <button type="button" className="appearance-reset" onClick={() => setAppearance({ ...DEFAULT_APPEARANCE })}><RotateCcw size={16} /> Restaurar valores originales</button><p className="appearance-note">Se guarda solo en este navegador y no cambia la vista de otros usuarios.</p>
    </section>}
    <button type="button" className="appearance-toggle" aria-label="Personalizar" aria-expanded={open} aria-controls="appearance-panel" onClick={() => setOpen((current) => !current)}><Palette size={19} /><span>Personalizar</span></button>
  </div>
  return slot ? createPortal(widget, slot) : widget
}
