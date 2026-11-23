import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import AppearanceSettings from './AppearanceSettings'
import { DEFAULT_APPEARANCE, normalizeAppearance, STORAGE_KEY } from './appearance'

describe('Personalización de apariencia', () => {
  beforeEach(() => { localStorage.clear(); document.documentElement.removeAttribute('style') })
  afterEach(() => { localStorage.clear(); document.documentElement.removeAttribute('style') })

  it('aplica y guarda las preferencias y permite restaurarlas', async () => {
    render(<AppearanceSettings />)
    fireEvent.click(screen.getByRole('button', { name: 'Personalizar' }))
    fireEvent.click(screen.getByRole('button', { name: 'Verde' }))
    fireEvent.change(screen.getByLabelText('Tipo de letra'), { target: { value: 'serif' } })
    fireEvent.change(screen.getByRole('slider', { name: /Tamaño de letra/ }), { target: { value: '115' } })
    await waitFor(() => expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!)).toMatchObject({ color: '#047857', font: 'serif', size: 115 }))
    expect(document.documentElement.style.fontSize).toBe('115%')
    expect(document.documentElement.style.getPropertyValue('--color-brand-700')).not.toBe('')
    fireEvent.click(screen.getByRole('button', { name: /Restaurar valores originales/ }))
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY)!)).toEqual(DEFAULT_APPEARANCE)
    expect(document.documentElement.style.getPropertyValue('--color-brand-700')).toBe('')
  })

  it('recupera preferencias y cierra con Escape', () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ color: '#6d28d9', font: 'humanist', size: 110, corners: 'soft' }))
    render(<AppearanceSettings />)
    fireEvent.click(screen.getByRole('button', { name: 'Personalizar' }))
    expect(screen.getByRole('button', { name: 'Violeta' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByLabelText('Tipo de letra')).toHaveValue('humanist')
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByLabelText('Personalizar apariencia')).not.toBeInTheDocument()
  })

  it('valida los datos guardados antes de aplicarlos', () => {
    expect(normalizeAppearance({ color: 'red', size: 999, font: 'invalida', corners: 'invalido' })).toEqual({ ...DEFAULT_APPEARANCE, size: 120 })
  })

  it('ubica la personalización en la cabecera cuando está disponible', async () => {
    const slot = document.createElement('div')
    slot.id = 'appearance-slot'
    document.body.appendChild(slot)
    const vista = render(<AppearanceSettings />)
    await waitFor(() => expect(slot.querySelector('.appearance-toggle')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Personalizar' }))
    expect(screen.getByLabelText('Personalizar apariencia')).toBeInTheDocument()
    vista.unmount()
    slot.remove()
  })
})
