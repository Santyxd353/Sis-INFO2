import { render,screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Users } from 'lucide-react'
import { describe,expect,it } from 'vitest'
import { DashboardEmptyState,DashboardErrorState,DashboardMetricCard,DashboardQuickAction,DashboardSection,InstitutionalIdentity } from './DashboardComponents'

describe('componentes compartidos de dashboard',()=>{
 it('muestra un valor real',()=>{render(<DashboardMetricCard title="Usuarios" value={8} description="Total" icon={Users} loading={false}/>);expect(screen.getByText('8')).toBeInTheDocument()})
 it('muestra skeleton durante carga',()=>{render(<DashboardMetricCard title="Usuarios" description="Total" icon={Users} loading/>);expect(screen.getByLabelText('Cargando Usuarios')).toBeInTheDocument()})
 it('muestra error no bloqueante',()=>{render(<DashboardMetricCard title="Usuarios" description="Total" icon={Users} loading={false} error/>);expect(screen.getByText('No se pudo cargar este indicador')).toBeInTheDocument()})
 it('no inventa cero sin valor',()=>{render(<DashboardMetricCard title="Usuarios" description="Total" icon={Users} loading={false}/>);expect(screen.queryByText('0')).not.toBeInTheDocument()})
 it('la métrica tiene nombre accesible',()=>{render(<DashboardMetricCard title="Usuarios" value={1} description="Total" icon={Users} loading={false}/>);expect(screen.getByLabelText('Usuarios')).toBeInTheDocument()})
 it('renderiza una acción funcional',()=>{render(<MemoryRouter><DashboardQuickAction title="Usuarios" description="Gestionar" to="/usuarios" icon={Users}/></MemoryRouter>);expect(screen.getByRole('link')).toHaveAttribute('href','/usuarios')})
 it('renderiza sección reutilizable',()=>{render(<DashboardSection title="Resumen"><span>Contenido</span></DashboardSection>);expect(screen.getByText('Contenido')).toBeInTheDocument()})
 it('renderiza estado vacío',()=>{render(<DashboardEmptyState/>);expect(screen.getByText('Todavía no existen registros para mostrar')).toBeInTheDocument()})
 it('renderiza error de permiso',()=>{render(<DashboardErrorState restricted/>);expect(screen.getByText('No tiene permisos para acceder a esta funcionalidad')).toBeInTheDocument()})
 it('muestra identidad institucional real',()=>{render(<InstitutionalIdentity title="Secretaría académica" description="Resumen" college="Colegio" unit="Primaria" role="Secretaría"/>);expect(screen.getByText('Colegio')).toBeInTheDocument();expect(screen.getByText('Primaria')).toBeInTheDocument()})
 it('distingue el alcance global',()=>{render(<InstitutionalIdentity title="Plataforma" description="Resumen" global/>);expect(screen.getByText('Alcance global')).toBeInTheDocument()})
 it('informa datos institucionales incompletos sin inventar una unidad',()=>{render(<InstitutionalIdentity title="Panel" description="Resumen"/>);expect(screen.getByText('Institución sin completar')).toBeInTheDocument();expect(screen.queryByText('Unidad sin asignar')).not.toBeInTheDocument()})
})
