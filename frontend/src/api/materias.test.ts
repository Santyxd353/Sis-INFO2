import MockAdapter from 'axios-mock-adapter'
import { afterEach, describe, expect, it } from 'vitest'
import axiosInstance from './axiosInstance'
import { listarMaterias, listarMateriasCurso, normalizarColeccion } from './materias'

describe('cliente de materias', () => {
  const mock = new MockAdapter(axiosInstance)
  afterEach(() => mock.reset())

  it('envía filtros paginados de materias al backend sin page_size masivo', async () => {
    mock.onGet('/academico/materias/').reply(config => [200, { count: 0, next: null, previous: null, results: [], parametros: config.params }])
    const response = await listarMaterias({ unidad_educativa: 2, nombre: 'mate', estado: 'ACTIVO', page: 2, page_size: 20 })
    expect(response.config.params).toEqual({ unidad_educativa: 2, nombre: 'mate', estado: 'ACTIVO', page: 2, page_size: 20 })
    expect(response.config.params.page_size).not.toBe(100)
  })

  it('conserva MateriaCurso.id y filtra la relación en el servidor', async () => {
    mock.onGet('/academico/materias-curso/').reply(200, { count: 1, next: null, previous: null, results: [{ id: 44, curso: 2, curso_nombre: 'Primero A', materia: 7, materia_nombre: 'Matemática' }] })
    const response = await listarMateriasCurso({ unidad_educativa: 1, curso: 2, materia: 7, estado: 'ACTIVO', page: 1, page_size: 20 })
    expect(normalizarColeccion(response.data).results[0].id).toBe(44)
  })

  it('normaliza respuestas heredadas en arreglo para que la vista nunca reciba results indefinido', () => {
    expect(normalizarColeccion([{ id: 1, nombre: 'Matemática' }]).results).toEqual([{ id: 1, nombre: 'Matemática' }])
    expect(normalizarColeccion([{ id: 1 }]).count).toBe(1)
  })
})
