import MockAdapter from 'axios-mock-adapter'
import { afterEach, describe, expect, it } from 'vitest'
import api from './axiosInstance'
import { actualizarComunicado, archivarComunicado, confirmarLectura, crearComunicado, emitirAlerta, guardarPreferencias, leerNotificacion, publicarComunicado } from './comunicacion'

describe('contrato HU27 y HU28', () => {
  const mock = new MockAdapter(api)
  afterEach(() => mock.reset())
  it('crea y edita únicamente el borrador con la audiencia y prioridad explícitas', async () => {
    mock.onPost('/comunicacion/comunicados/').reply(201, { id: 4 })
    mock.onPatch('/comunicacion/comunicados/4/').reply(200, { id: 4 })
    const payload = { titulo: 'Reunión', cuerpo: 'Mañana', unidad_educativa: 2, curso: null, prioridad: 'NORMAL' as const, requiere_confirmacion: true }
    await crearComunicado(payload)
    await actualizarComunicado(4, { titulo: 'Reunión de familias' })
    expect(JSON.parse(mock.history.post[0].data)).toEqual(payload)
    expect(JSON.parse(mock.history.patch[0].data)).toEqual({ titulo: 'Reunión de familias' })
  })
  it('usa acciones idempotentes del servidor sin enviar contadores ni fechas del cliente', async () => {
    mock.onPost().reply(200, {})
    await publicarComunicado(4)
    await archivarComunicado(4)
    await confirmarLectura(4)
    await leerNotificacion(8)
    expect(mock.history.post.map(r => r.url)).toEqual(['/comunicacion/comunicados/4/publicar/', '/comunicacion/comunicados/4/archivar/', '/comunicacion/comunicados/4/leer/', '/comunicacion/notificaciones/8/leer/'])
    expect(mock.history.post.every(r => r.data === undefined)).toBe(true)
  })
  it('guarda preferencias de push y emite alertas administrativas con clave estable', async () => {
    mock.onPatch('/comunicacion/preferencias/').reply(200, { PAGO: false })
    mock.onPost('/comunicacion/alertas/').reply(201, { creadas: 2 })
    await guardarPreferencias({ PAGO: false })
    const payload = { estudiante: 3, tipo: 'PAGO' as const, titulo: 'Aviso', cuerpo: 'Consulte administración', clave_evento: 'pago-2026-11-3' }
    await emitirAlerta(payload)
    expect(JSON.parse(mock.history.patch[0].data)).toEqual({ PAGO: false })
    expect(JSON.parse(mock.history.post[0].data)).toEqual(payload)
  })
})
