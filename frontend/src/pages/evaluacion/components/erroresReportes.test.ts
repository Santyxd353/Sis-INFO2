import { describe, expect, it } from 'vitest'
import { normalizarErrores } from './erroresReportes'

describe('errores de reportes', () => {
  it('conserva las rutas e índices de validación', () => {
    expect(normalizarErrores({ especificacion: { condiciones: { condiciones: [{}, { valor: ['Valor inválido'] }] }, columnas: ['Seleccione columnas'] } })).toEqual([
      { ruta: ['especificacion', 'condiciones', 'condiciones', 1, 'valor'], mensaje: 'Valor inválido' },
      { ruta: ['especificacion', 'columnas'], mensaje: 'Seleccione columnas' },
    ])
  })
  it('ignora contenido técnico y no serializa objetos', () => {
    expect(normalizarErrores({ detail: '<html>error</html>', debug: 'Traceback: SQL', valor: ['Dato incorrecto'] })).toEqual([{ ruta: ['valor'], mensaje: 'Dato incorrecto' }])
  })
})
