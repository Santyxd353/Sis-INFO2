import MockAdapter from 'axios-mock-adapter'
import { afterEach,beforeEach,describe,expect,it } from 'vitest'
import axiosInstance from './axiosInstance'
import { loadDashboardMetrics,loadRecentAudit } from './dashboard'

describe('datos reales de dashboards',()=>{
 let mock:MockAdapter
 beforeEach(()=>{mock=new MockAdapter(axiosInstance)})
 afterEach(()=>mock.restore())
 it('usa count paginado para colegios',async()=>{mock.onGet('/institucion/colegios/').reply(200,{count:7,results:[]});expect((await loadDashboardMetrics(['colegios']))[0].value).toBe(7)})
 it('usa count paginado para usuarios',async()=>{mock.onGet('/usuarios/usuarios/').reply(200,{count:11,results:[]});expect((await loadDashboardMetrics(['usuarios']))[0].value).toBe(11)})
 it('cuenta una respuesta real no paginada',async()=>{mock.onGet('/personal/profesores/').reply(200,[{id:1},{id:2}]);expect((await loadDashboardMetrics(['docentes']))[0].value).toBe(2)})
 it('consulta solamente una página para el conteo',async()=>{mock.onGet('/academico/asignaciones-docentes/').reply(200,{count:5,results:[]});await loadDashboardMetrics(['asignaciones']);expect(mock.history.get[0].params).toEqual({page:1,page_size:1})})
 it('tolera fallo parcial',async()=>{mock.onGet('/academico/cursos/').reply(500);mock.onGet('/personal/profesores/').reply(200,{count:2,results:[]});const r=await loadDashboardMetrics(['cursos','docentes']);expect(r[0].error).toBe(true);expect(r[1].value).toBe(2)})
 it('marca un 403 como restringido',async()=>{mock.onGet('/estudiantes/estudiantes/').reply(403);expect((await loadDashboardMetrics(['estudiantes']))[0].restricted).toBe(true)})
 it('un 403 no elimina la sesión',async()=>{sessionStorage.setItem('auth_access_token','token');mock.onGet('/estudiantes/estudiantes/').reply(403);await loadDashboardMetrics(['estudiantes']);expect(sessionStorage.getItem('auth_access_token')).toBe('token')})
 it('consulta auditoría limitada a cinco eventos',async()=>{mock.onGet('/usuarios/auditoria/').reply(200,{results:[]});await loadRecentAudit();expect(mock.history.get[0].params).toEqual({page:1,page_size:5})})
 it('devuelve actividad de auditoría sanitizada por contrato',async()=>{mock.onGet('/usuarios/auditoria/').reply(200,{results:[{id:1,accion:'CREAR',entidad:'CURSO',ambito:'UNIDAD',created_at:'2026-01-01'}]});expect((await loadRecentAudit())[0].entidad).toBe('CURSO')})
 it('tolera una respuesta institucional no paginada de auditoría',async()=>{mock.onGet('/usuarios/auditoria/').reply(200,[{id:1,accion:'CREAR',entidad:'CURSO',ambito:'UNIDAD',created_at:'2026-01-01'}]);expect((await loadRecentAudit())).toHaveLength(1)})
 it('no consulta endpoints de Sprint 3',async()=>{mock.onGet().reply(200,{count:0,results:[]});await loadDashboardMetrics(['colegios','usuarios']);expect(mock.history.get.every(r=>!r.url?.includes('finanzas'))).toBe(true)})
 it('preserva el orden solicitado',async()=>{mock.onGet().reply(200,{count:1,results:[]});expect((await loadDashboardMetrics(['cursos','usuarios'])).map(r=>r.key)).toEqual(['cursos','usuarios'])})
 it('no inventa valor cuando la respuesta carece de count',async()=>{mock.onGet('/academico/cursos/').reply(200,{});expect((await loadDashboardMetrics(['cursos']))[0].value).toBeUndefined()})
})

