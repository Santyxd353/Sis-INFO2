import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import type { FiltroReporteOperativo } from '../../../api/reportes'
import FilterValueInput, { convertirValor } from './FilterValueInput'

vi.mock('../../../app/contexts/AuthContext', () => ({ useAuth: () => ({ user: null }) }))

const filtro = (tipo: string) => ({ campo: 'valor', tipo, operadores: ['eq', 'in'] }) as FiltroReporteOperativo

describe('conversión de filtros de reportes', () => {
  it('conserva texto y convierte enteros y decimales', () => {
    expect(convertirValor(filtro('texto'), 'eq', ' 012 ')).toBe('012')
    expect(convertirValor(filtro('entero'), 'eq', '12')).toBe(12)
    expect(convertirValor(filtro('decimal'), 'eq', '1.5')).toBe(1.5)
  })
  it('rechaza números inválidos sin producir NaN ni null', () => {
    expect(() => convertirValor(filtro('entero'), 'eq', '1.5')).toThrow()
    expect(() => convertirValor(filtro('decimal'), 'eq', 'abc')).toThrow()
    expect(() => convertirValor(filtro('entero'), 'eq', '')).toThrow()
  })
  it('convierte booleanos explícitos y rechaza otros valores', () => {
    expect(convertirValor(filtro('booleano'), 'eq', 'true')).toBe(true)
    expect(convertirValor(filtro('booleano'), 'eq', 'false')).toBe(false)
    expect(() => convertirValor(filtro('booleano'), 'eq', 'otro')).toThrow()
  })
  it('convierte listas y exige al menos un valor', () => {
    expect(convertirValor(filtro('entero'), 'in', '1, 2, , 3')).toEqual([1, 2, 3])
    expect(() => convertirValor(filtro('entero'), 'in', ', ,')).toThrow()
  })
  it('valida el formato de fecha', () => {
    expect(convertirValor(filtro('fecha'), 'eq', '2026-10-21')).toBe('2026-10-21')
    expect(() => convertirValor(filtro('fecha'), 'eq', '21/10/2026')).toThrow()
  })
})

describe('control de valor', () => {
  it('deshabilita el valor sin filtro', () => {
    render(<FilterValueInput operador="eq" valor="" onChange={() => {}} />)
    expect(screen.getByLabelText('Valor')).toBeDisabled()
  })
  it('permite escribir texto y seleccionar booleanos', () => {
    const cambio = vi.fn()
    const { rerender } = render(<FilterValueInput filtro={filtro('texto')} operador="eq" valor="" onChange={cambio} />)
    fireEvent.change(screen.getByLabelText('Valor'), { target: { value: 'Ana' } })
    expect(cambio).toHaveBeenCalledWith('Ana')
    rerender(<FilterValueInput filtro={filtro('booleano')} operador="eq" valor="" onChange={cambio} />)
    fireEvent.change(screen.getByLabelText('Valor'), { target: { value: 'false' } })
    expect(cambio).toHaveBeenCalledWith('false')
  })
})
