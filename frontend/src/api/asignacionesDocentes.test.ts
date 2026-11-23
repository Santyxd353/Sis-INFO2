import MockAdapter from 'axios-mock-adapter'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import axiosInstance from './axiosInstance'
import { crearAsignacion, desactivarAsignacion, editarAsignacion, listarAsignaciones, listarCalendarios, listarCursos, listarMateriasCurso, listarProfesores, type AsignacionPayload } from './asignacionesDocentes'

const payload: AsignacionPayload = { calendario_academico: 1, tipo: 'MATERIA', curso: 2, profesor: 3, materia_curso: 44, fecha_inicio: '2026-02-01', fecha_fin: null, horas_semanales: 4 }

describe('servicios de asignaciones HU-11', () => {
  let mock: MockAdapter
  beforeEach(() => { mock = new MockAdapter(axiosInstance) })
  afterEach(() => mock.restore())

  it('consulta el listado paginado', async () => { mock.onGet('/academico/asignaciones-docentes/').reply(200,{count:2,results:[]}); expect((await listarAsignaciones({page:1})).data.count).toBe(2) })
  it('consulta por profesor', async () => { mock.onGet('/academico/asignaciones-docentes/').reply(200,{count:0,results:[]}); await listarAsignaciones({profesor:'3'}); expect(mock.history.get[0].params.profesor).toBe('3') })
  it('consulta por curso', async () => { mock.onGet('/academico/asignaciones-docentes/').reply(200,{count:0,results:[]}); await listarAsignaciones({curso:'2'}); expect(mock.history.get[0].params.curso).toBe('2') })
  it('carga calendarios como lista', async () => { mock.onGet('/calendario/calendarios/').reply(200,[{id:1}]); expect(await listarCalendarios()).toHaveLength(1) })
  it('carga calendarios paginados', async () => { mock.onGet('/calendario/calendarios/').reply(200,{count:1,results:[{id:1}]}); expect(await listarCalendarios()).toHaveLength(1) })
  it('carga cursos reales', async () => { mock.onGet('/academico/cursos/').reply(200,[{id:2,nombre:'1 A'}]); expect((await listarCursos())[0].id).toBe(2) })
  it('carga profesores reales', async () => { mock.onGet('/personal/profesores/').reply(200,[{id:3,estado:true}]); expect((await listarProfesores())[0].id).toBe(3) })
  it('consulta materias filtradas por curso', async () => { mock.onGet('/academico/materias-curso/').reply(200,{count:1,results:[{id:44,materia:8}]}); expect((await listarMateriasCurso(2))[0].id).toBe(44); expect(mock.history.get[0].params.curso).toBe(2) })
  it('usa MateriaCurso.id en la creación', async () => { mock.onPost('/academico/asignaciones-docentes/').reply(201,{id:1}); await crearAsignacion(payload); expect(JSON.parse(mock.history.post[0].data).materia_curso).toBe(44) })
  it('crea una asignación mediante POST', async () => { mock.onPost('/academico/asignaciones-docentes/').reply(201,{id:7}); expect((await crearAsignacion(payload)).data.id).toBe(7) })
  it('edita una asignación mediante PATCH', async () => { mock.onPatch('/academico/asignaciones-docentes/7/').reply(200,{id:7}); await editarAsignacion(7,{horas_semanales:5}); expect(mock.history.patch).toHaveLength(1) })
  it('desactiva mediante POST', async () => { mock.onPost('/academico/asignaciones-docentes/7/desactivar/').reply(200,{id:7,estado:'INACTIVO'}); await desactivarAsignacion(7); expect(mock.history.post[0].url).toContain('/desactivar/') })
  it('nunca utiliza DELETE', async () => { mock.onPost('/academico/asignaciones-docentes/7/desactivar/').reply(200,{}); await desactivarAsignacion(7); expect(mock.history.delete).toHaveLength(0) })
  it('envía materia null para tutor de curso', async () => { mock.onPost('/academico/asignaciones-docentes/').reply(201,{}); await crearAsignacion({...payload,tipo:'TUTOR_CURSO',materia_curso:null}); expect(JSON.parse(mock.history.post[0].data).materia_curso).toBeNull() })
  it('no envía campos derivados', async () => { mock.onPost('/academico/asignaciones-docentes/').reply(201,{}); await crearAsignacion(payload); const data=JSON.parse(mock.history.post[0].data); expect(data).not.toHaveProperty('colegio'); expect(data).not.toHaveProperty('unidad') })
  it('propaga errores de dominio 400', async () => { mock.onPost('/academico/asignaciones-docentes/').reply(400,{curso:['Inválido']}); await expect(crearAsignacion(payload)).rejects.toMatchObject({response:{status:400}}) })
  it('propaga 403 sin limpiar sesión', async () => { sessionStorage.setItem('auth_access_token','vigente'); mock.onGet('/academico/asignaciones-docentes/').reply(403); await expect(listarAsignaciones({})).rejects.toMatchObject({response:{status:403}}); expect(sessionStorage.getItem('auth_access_token')).toBe('vigente') })
  it('conserva un calendario histórico nulo', async () => { mock.onGet('/academico/asignaciones-docentes/').reply(200,{count:1,results:[{id:1,calendario_academico:null,gestion_anio:null}]}); const item=(await listarAsignaciones({})).data.results[0]; expect(item.calendario_academico).toBeNull() })
  it('envía fechas y horas tipadas', async () => { mock.onPost('/academico/asignaciones-docentes/').reply(201,{}); await crearAsignacion(payload); expect(JSON.parse(mock.history.post[0].data)).toMatchObject({fecha_inicio:'2026-02-01',horas_semanales:4}) })
  it('normaliza cursos paginados', async () => { mock.onGet('/academico/cursos/').reply(200,{count:1,results:[{id:9,nombre:'2 B'}]}); expect((await listarCursos())[0].nombre).toBe('2 B') })
})

