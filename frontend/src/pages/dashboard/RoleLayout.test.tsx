import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { Building2, Users } from 'lucide-react'
import { describe, expect, it, vi } from 'vitest'
import RoleLayout from './RoleLayout'
import type { NavigationModule } from '../../app/navigation/types'

const logout = vi.fn().mockResolvedValue(undefined)
vi.mock('../../app/contexts/AuthContext',()=>({useAuth:()=>({user:{nombre:'Luno',apellido:'Pérez',rol:{nombre:'Admin'},unidad:{nombre:'Primaria',colegio:{nombre:'Colegio Central'}}},logout,isSuperAdmin:()=>false})}))
const modulos: NavigationModule[] = [
  {key:'inst',titulo:'Datos institucionales',descripcion:'',ruta:'/dashboard/admin/institucion',icono:Building2,color:'',grupo:'institucion',perfiles:['ADMINISTRADOR_INSTITUCIONAL'],alcance:'COLEGIO',estadoFuncional:'IMPLEMENTED',sprint:1,orden:1},
  {key:'users',titulo:'Usuarios',descripcion:'',ruta:'/dashboard/admin/usuarios',icono:Users,color:'',grupo:'personas',perfiles:['ADMINISTRADOR_INSTITUCIONAL'],alcance:'COLEGIO',estadoFuncional:'IMPLEMENTED',sprint:1,orden:2},
]
const montar=(ruta='/dashboard/admin/institucion')=>render(<MemoryRouter initialEntries={[ruta]}><Routes><Route path="/dashboard/admin" element={<RoleLayout basePath="/dashboard/admin" titulo="Panel" subtitulo="Gestión" modulos={modulos}/>}><Route path="institucion" element={<p>Contenido</p>}/></Route></Routes></MemoryRouter>)

describe('RoleLayout compartido',()=>{
  it('muestra grupos no vacíos',()=>{montar();expect(screen.getByText('Institución')).toBeInTheDocument();expect(screen.getByText('Personas y matrícula')).toBeInTheDocument();expect(screen.queryByText('Evaluación')).not.toBeInTheDocument()})
  it('resalta la ruta activa',()=>{montar();expect(screen.getAllByText('Datos institucionales')[0].closest('a')).toHaveClass('bg-brand-700')})
  it('mantiene expandido el grupo activo',()=>{montar();expect(screen.getByText('Institución').closest('button')).toHaveAttribute('aria-expanded','true')})
  it('permite colapsar un grupo inactivo',()=>{montar();const boton=screen.getByText('Personas y matrícula').closest('button')!;fireEvent.click(boton);expect(boton).toHaveAttribute('aria-expanded','false');expect(screen.queryByText('Usuarios')).not.toBeInTheDocument()})
  it('permite contraer el menú lateral',()=>{montar();fireEvent.click(screen.getByLabelText('Contraer menú'));expect(screen.getByLabelText('Expandir menú')).toBeInTheDocument()})
  it('incluye control accesible para menú móvil',()=>{montar();expect(screen.getByLabelText('Abrir menú')).toBeInTheDocument()})
  it('muestra breadcrumb e institución reales',()=>{montar();expect(screen.getAllByText('Datos institucionales').find((n)=>n.getAttribute('aria-current')==='page')).toBeTruthy();expect(screen.getByText('Colegio Central — Primaria')).toBeInTheDocument()})
  it('mantiene visible el cierre de sesión',()=>{montar();expect(screen.getByText('Cerrar sesión')).toBeInTheDocument()})
  it('usa la identidad visual sin cortar el nombre',()=>{montar();expect(screen.getByText('EduGestión Cloud')).toBeInTheDocument();expect(screen.getByText('Gestión escolar SaaS')).toBeInTheDocument()})
})

