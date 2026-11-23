import { describe, expect, it } from 'vitest'
import type { Usuario } from '../modelos/Usuarios'
import { dashboardPath } from './dashboardPath'

const u=(rol:string,puesto?:string)=>({rol:{nombre:rol},perfil:puesto?{puesto:{nombre:puesto}}:null} as Usuario)
describe('redirección compatible de dashboard',()=>{
  it('redirige cada rol técnico a su portal',()=>{expect(dashboardPath(u('SuperAdmin'))).toBe('/dashboard/superadmin');expect(dashboardPath(u('Profesor'))).toBe('/dashboard/profesor');expect(dashboardPath(u('Tutor'))).toBe('/dashboard/tutor');expect(dashboardPath(u('Estudiante'))).toBe('/dashboard/estudiante')})
  it('envía puestos institucionales a su portal propio',()=>{expect(dashboardPath(u('Admin','Director'))).toBe('/dashboard/director');expect(dashboardPath(u('Admin','Secretaría'))).toBe('/dashboard/secretaria')})
  it('envía Tesorería al dashboard institucional protegido',()=>{expect(dashboardPath(u('Admin','Tesorería'))).toBe('/dashboard/tesoreria')})
  it('redirige Regente por rol o puesto al portal de regencia',()=>{expect(dashboardPath(u('Regente'))).toBe('/dashboard/regente');expect(dashboardPath(u('Admin','Regente'))).toBe('/dashboard/regente')})
})
