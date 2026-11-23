import MockAdapter from 'axios-mock-adapter'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import axiosInstance from './axiosInstance'
import {
  asignarRolesUsuario, crearRol, editarRol, eliminarRol, guardarComponentesRol,
  guardarPermisosRol, listarAcciones, listarModelosPermitidos, listarRolesAsignables,
  listarRolesGestion, normalizarRoles, obtenerComponentesRol, obtenerPermisosRol,
  obtenerRolesUsuario,
} from './roles'

describe('servicios de gestión de roles (HU-SE02)', () => {
  let mock: MockAdapter
  beforeEach(() => { mock = new MockAdapter(axiosInstance) })
  afterEach(() => mock.restore())

  it('lista los roles en modo gestión', async () => {
    mock.onGet('/usuarios/roles/').reply(200, [{ id: 1, nombre: 'Coordinador', activo: true }])
    const { data } = await listarRolesGestion()
    expect(mock.history.get[0].params).toEqual({ gestion: '1' })
    expect(data).toHaveLength(1)
  })

  it('lista solo los roles personalizados asignables', async () => {
    mock.onGet('/usuarios/roles/').reply(200, [])
    await listarRolesAsignables()
    expect(mock.history.get[0].params).toEqual({ asignables: '1' })
  })

  it('crea un rol de sistema enviando colegio_id nulo solo cuando se elige sistema', async () => {
    mock.onPost('/usuarios/roles/').reply(201, { id: 9, categoria: 'SISTEMA' })
    await crearRol({ nombre: 'Jefe de unidad', colegio_id: null })
    const payload = JSON.parse(mock.history.post[0].data)
    expect(payload.colegio_id).toBeNull()
    expect(payload.nombre).toBe('Jefe de unidad')
  })

  it('edita un rol mediante PATCH', async () => {
    mock.onPatch('/usuarios/roles/3/').reply(200, { id: 3, activo: false })
    await editarRol(3, { activo: false })
    expect(mock.history.patch).toHaveLength(1)
    expect(JSON.parse(mock.history.patch[0].data).activo).toBe(false)
  })

  it('elimina un rol personalizado mediante DELETE', async () => {
    mock.onDelete('/usuarios/roles/3/').reply(204)
    await eliminarRol(3)
    expect(mock.history.delete).toHaveLength(1)
  })

  it('consulta los permisos funcionales vigentes de un rol', async () => {
    mock.onGet('/usuarios/roles/7/permisos/').reply(200, {
      rol_id: 7, permisos: [{ modelo: 'curso', accion: 'listar' }],
    })
    const { data } = await obtenerPermisosRol(7)
    expect(data.permisos[0]).toMatchObject({ modelo: 'curso', accion: 'listar' })
  })

  it('reemplaza la matriz completa de permisos funcionales', async () => {
    mock.onPut('/usuarios/roles/7/permisos/').reply(200, { rol_id: 7, permisos: [] })
    await guardarPermisosRol(7, [{ modelo: 'horario', accion: 'editar' }])
    const payload = JSON.parse(mock.history.put[0].data)
    expect(payload.permisos).toEqual([{ modelo: 'horario', accion: 'editar' }])
    expect(mock.history.put[0].url).toBe('/usuarios/roles/7/permisos/')
  })

  it('permite vaciar la matriz (denegación por defecto)', async () => {
    mock.onPut('/usuarios/roles/7/permisos/').reply(200, { rol_id: 7, permisos: [] })
    await guardarPermisosRol(7, [])
    expect(JSON.parse(mock.history.put[0].data).permisos).toEqual([])
  })

  it('consulta y guarda los componentes de interfaz de un rol', async () => {
    mock.onGet('/usuarios/roles/7/componentes/').reply(200, {
      rol_id: 7, componentes: [{ id: 1, componente: 'boton-matricular', visible: true, editable: false }],
    })
    const { data } = await obtenerComponentesRol(7)
    expect(data.componentes[0].componente).toBe('boton-matricular')

    mock.onPut('/usuarios/roles/7/componentes/').reply(200, { rol_id: 7, componentes: [] })
    await guardarComponentesRol(7, [
      { id: 1, componente: 'boton-matricular', visible: false, editable: true },
    ])
    const payload = JSON.parse(mock.history.put[0].data)
    // El id es interno de la fila; el payload solo lleva los campos de la regla.
    expect(payload.componentes).toEqual([
      { componente: 'boton-matricular', visible: false, editable: true },
    ])
  })

  it('consulta los roles adicionales de un usuario', async () => {
    mock.onGet('/usuarios/usuarios/12/roles/').reply(200, {
      usuario_id: 12, roles: [{ id: 4, nombre: 'Invitado' }],
    })
    const { data } = await obtenerRolesUsuario(12)
    expect(data.roles[0].nombre).toBe('Invitado')
  })

  it('reasigna la lista completa de roles adicionales', async () => {
    mock.onPut('/usuarios/usuarios/12/roles/').reply(200, { usuario_id: 12, roles: [] })
    await asignarRolesUsuario(12, [4, 5])
    const payload = JSON.parse(mock.history.put[0].data)
    expect(payload.rol_ids).toEqual([4, 5])
    expect(mock.history.put[0].url).toBe('/usuarios/usuarios/12/roles/')
  })

  it('carga los catálogos de acciones y modelos de la matriz', async () => {
    mock.onGet('/usuarios/acciones/').reply(200, [{ id: 1, nombre: 'listar' }])
    mock.onGet('/usuarios/modelos-permitidos/').reply(200, [{ id: 1, nombre: 'curso' }])
    const acciones = await listarAcciones()
    const modelos = await listarModelosPermitidos()
    expect(acciones.data[0].nombre).toBe('listar')
    expect(modelos.data[0].nombre).toBe('curso')
  })

  it('normaliza respuestas paginadas de roles', () => {
    expect(normalizarRoles({ count: 1, results: [{ id: 1, nombre: 'X' } as never] }))
      .toHaveLength(1)
    expect(normalizarRoles([{ id: 2, nombre: 'Y' } as never])).toHaveLength(1)
  })

  it('propaga 403 sin limpiar sesión (prevención de escalación)', async () => {
    sessionStorage.setItem('auth_access_token', 'vigente')
    mock.onPut('/usuarios/roles/7/permisos/').reply(403, {
      detail: 'No puede conceder permisos que usted no posee: curso.eliminar.',
    })
    await expect(
      guardarPermisosRol(7, [{ modelo: 'curso', accion: 'eliminar' }]),
    ).rejects.toMatchObject({ response: { status: 403 } })
    expect(sessionStorage.getItem('auth_access_token')).toBe('vigente')
  })
})
