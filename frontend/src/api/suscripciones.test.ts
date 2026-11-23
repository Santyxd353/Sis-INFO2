import MockAdapter from 'axios-mock-adapter'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import axiosInstance from './axiosInstance'
import {
  cancelarSuscripcion, contratarPlan, crearPlan, editarPlan, eliminarPlan,
  listarPagos, listarPlanes, listarSuscripciones, obtenerEstadoSuscripcion,
  rechazarPago, reactivarSuscripcion, registrarPago, suspenderSuscripcion,
  validarPago,
} from './suscripciones'

describe('servicios de suscripciones SaaS (HU-SE01)', () => {
  let mock: MockAdapter
  beforeEach(() => { mock = new MockAdapter(axiosInstance) })
  afterEach(() => mock.restore())

  it('lista los planes del catálogo', async () => {
    mock.onGet('/suscripciones/planes/').reply(200, [{ id: 1, nombre: 'Básico' }])
    const { data } = await listarPlanes()
    expect(data).toHaveLength(1)
    expect(mock.history.get[0].url).toBe('/suscripciones/planes/')
  })

  it('crea un plan mediante POST solo con datos de catálogo', async () => {
    mock.onPost('/suscripciones/planes/').reply(201, { id: 9 })
    await crearPlan({ nombre: 'Premium', precio: '200.00', periodicidad: 'TRIMESTRAL' })
    const payload = JSON.parse(mock.history.post[0].data)
    expect(payload).not.toHaveProperty('estado_efectivo')
    expect(payload.nombre).toBe('Premium')
  })

  it('edita un plan mediante PATCH', async () => {
    mock.onPatch('/suscripciones/planes/3/').reply(200, { id: 3 })
    await editarPlan(3, { precio: '250.00' })
    expect(mock.history.patch).toHaveLength(1)
  })

  it('elimina un plan mediante DELETE (baja lógica del backend)', async () => {
    mock.onDelete('/suscripciones/planes/3/').reply(204)
    await eliminarPlan(3)
    expect(mock.history.delete).toHaveLength(1)
  })

  it('contrata un plan enviando colegio y plan', async () => {
    mock.onPost('/suscripciones/suscripciones/').reply(201, { id: 5, estado: 'PENDIENTE' })
    const { data } = await contratarPlan({ plan: 2, colegio: 7 })
    expect(data.estado).toBe('PENDIENTE')
    const payload = JSON.parse(mock.history.post[0].data)
    expect(payload).toMatchObject({ plan: 2, colegio: 7 })
  })

  it('consulta el estado de la suscripción del colegio', async () => {
    mock.onGet('/suscripciones/suscripciones/mi-estado/').reply(200, {
      tiene_suscripcion: true, suscripcion_activa: false, restriccion: 'Pendiente de pago',
    })
    const { data } = await obtenerEstadoSuscripcion()
    expect(data.suscripcion_activa).toBe(false)
    expect(data.restriccion).toContain('Pendiente')
  })

  it('transiciones de estado mediante acciones del backend', async () => {
    mock.onPost('/suscripciones/suscripciones/1/suspender/').reply(200, { estado: 'SUSPENDIDA' })
    mock.onPost('/suscripciones/suscripciones/1/cancelar/').reply(200, { estado: 'CANCELADA' })
    mock.onPost('/suscripciones/suscripciones/2/reactivar/').reply(200, { estado: 'ACTIVA' })
    await suspenderSuscripcion(1)
    await cancelarSuscripcion(1)
    await reactivarSuscripcion(2)
    expect(mock.history.post.map((p) => p.url)).toEqual([
      '/suscripciones/suscripciones/1/suspender/',
      '/suscripciones/suscripciones/1/cancelar/',
      '/suscripciones/suscripciones/2/reactivar/',
    ])
  })

  it('registra un pago de renovación', async () => {
    mock.onPost('/suscripciones/pagos/').reply(201, { id: 4, resultado: 'PENDIENTE' })
    const { data } = await registrarPago({
      suscripcion: 5, metodo: 'TRANSFERENCIA', referencia: 'TRX-1', monto: '100.00',
    })
    expect(data.resultado).toBe('PENDIENTE')
  })

  it('valida y rechaza pagos mediante acciones del backend', async () => {
    mock.onPost('/suscripciones/pagos/4/validar/').reply(200, { resultado: 'VALIDADO' })
    mock.onPost('/suscripciones/pagos/5/rechazar/').reply(200, { resultado: 'RECHAZADO' })
    await validarPago(4)
    await rechazarPago(5, 'Comprobante ilegible')
    expect(JSON.parse(mock.history.post[1].data).motivo).toBe('Comprobante ilegible')
  })

  it('lista pagos aceptando filtro por resultado', async () => {
    mock.onGet('/suscripciones/pagos/').reply(200, [])
    await listarPagos({ resultado: 'PENDIENTE' })
    expect(mock.history.get[0].params.resultado).toBe('PENDIENTE')
  })

  it('lista suscripciones aceptando filtro por colegio', async () => {
    mock.onGet('/suscripciones/suscripciones/').reply(200, [])
    await listarSuscripciones({ colegio: '12' })
    expect(mock.history.get[0].params.colegio).toBe('12')
  })

  it('propaga 403 sin limpiar sesión', async () => {
    sessionStorage.setItem('auth_access_token', 'vigente')
    mock.onGet('/suscripciones/planes/').reply(403)
    await expect(listarPlanes()).rejects.toMatchObject({ response: { status: 403 } })
    expect(sessionStorage.getItem('auth_access_token')).toBe('vigente')
  })
})
