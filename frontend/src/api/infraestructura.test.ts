import MockAdapter from 'axios-mock-adapter'
import { afterEach, describe, expect, it } from 'vitest'
import api from './axiosInstance'
import {
  actualizarAula,
  actualizarModulo,
  crearAula,
  crearModulo,
  desactivarAula,
  desactivarModulo,
  listarAulas,
  listarModulos,
} from './infraestructura'

describe('cliente de infraestructura física', () => {
  const mock = new MockAdapter(api)
  afterEach(() => mock.reset())

  it('consulta módulos y aulas con filtros institucionales sin parámetros vacíos', async () => {
    mock.onGet('/institucion/modulos/').reply(200, { count: 0, results: [] })
    mock.onGet('/institucion/aulas/').reply(200, { count: 0, results: [] })

    await listarModulos({ unidad_educativa: 2, nombre: 'Central', estado: 'ACTIVO', page: 1, page_size: 20, colegio: undefined })
    await listarAulas({ unidad_educativa: 2, modulo: 4, tipo: 'LAB', nombre: '', page: 2, page_size: 20 })

    expect(mock.history.get[0].params).toEqual({ unidad_educativa: 2, nombre: 'Central', estado: 'ACTIVO', page: 1, page_size: 20 })
    expect(mock.history.get[1].params).toEqual({ unidad_educativa: 2, modulo: 4, tipo: 'LAB', page: 2, page_size: 20 })
  })

  it('usa POST, PATCH y la acción de desactivación; nunca DELETE', async () => {
    mock.onPost('/institucion/modulos/').reply(201, { id: 1 })
    mock.onPatch('/institucion/modulos/1/').reply(200, { id: 1 })
    mock.onPost('/institucion/modulos/1/desactivar/').reply(200, { id: 1 })
    mock.onPost('/institucion/aulas/').reply(201, { id: 2 })
    mock.onPatch('/institucion/aulas/2/').reply(200, { id: 2 })
    mock.onPost('/institucion/aulas/2/desactivar/').reply(200, { id: 2 })

    await crearModulo({ unidad_educativa: 2, nombre: 'Bloque A', cantidad_aulas: 4, pisos: 2 })
    await actualizarModulo(1, { descripcion: 'Actualizado' })
    await desactivarModulo(1)
    await crearAula({ modulo: 1, nombre: 'Aula 1', capacidad: 30, tipo: 'AUL', piso: 1 })
    await actualizarAula(2, { capacidad: 32 })
    await desactivarAula(2)

    expect(JSON.parse(mock.history.post[0].data)).toMatchObject({ unidad_educativa: 2, nombre: 'Bloque A' })
    expect(JSON.parse(mock.history.patch[0].data)).toEqual({ descripcion: 'Actualizado' })
    expect(mock.history.post.map((request) => request.url)).toEqual([
      '/institucion/modulos/',
      '/institucion/modulos/1/desactivar/',
      '/institucion/aulas/',
      '/institucion/aulas/2/desactivar/',
    ])
    expect(mock.history.delete).toHaveLength(0)
  })
})
