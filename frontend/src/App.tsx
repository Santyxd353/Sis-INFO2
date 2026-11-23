import { Navigate, Route, Routes } from 'react-router-dom'
import './App.css'
import RequireAuth from './app/routes/RequireAuth'
import Login from './pages/Login'
import Inscripcion from './pages/Inscripcion'
import Dashboard from './pages/Dashboard'
import { RegistroInstitucional, VerificarCorreo } from './pages/RegistroInstitucional'
import ModuloGestion from './pages/dashboard/ModuloGestion'
import SuperAdminInicio from './pages/dashboard/SuperAdminInicio'
import SuperAdminLayout from './pages/dashboard/SuperAdminLayout'
import { MODULOS } from './pages/dashboard/modules'
import { modeloPermisoRecurso } from './pages/dashboard/modules'
import AdminLayout from './pages/dashboard/AdminLayout'
import AdminInicio from './pages/dashboard/AdminInicio'
import PortalRolLayout from './pages/dashboard/PortalRolLayout'
import PortalRolInicio from './pages/dashboard/PortalRolInicio'
import InstitutionalRoleLayout from './pages/dashboard/InstitutionalRoleLayout'
import RoleDashboardHome from './pages/dashboard/RoleDashboardHome'
import RequirePermission from './app/routes/RequirePermission'
import RequireProfile from './app/routes/RequireProfile'
import NoPermission from './pages/NoPermission'
import RegistrarAsistencia from './pages/asistencia/RegistrarAsistencia'
import VerAsistencia from './pages/asistencia/VerAsistencia'
import HistorialAcademico from './pages/seguimiento/HistorialAcademico'
import RiesgoAcademico from './pages/seguimiento/RiesgoAcademico'
import AuditoriaPage from './pages/auditoria/AuditoriaPage'
import AsignacionesDocentesPage from './pages/asignaciones/AsignacionesDocentesPage'
import ConfiguracionEvaluacionPage from './pages/evaluacion/ConfiguracionEvaluacionPage'
import EvaluacionPage from './pages/evaluacion/EvaluacionPage'
import RequireReportes from './app/routes/RequireReportes'
import SuscripcionesPage from './pages/suscripciones/SuscripcionesPage'
import RolesPage from './pages/roles/RolesPage'
import DisciplinaPage from './pages/disciplina/DisciplinaPage'
import CorreccionesNotasPage from './pages/correcciones/CorreccionesNotasPage'
import HorariosPage from './pages/horarios/HorariosPage'
import MateriasPlanEstudioPage from './pages/materias/MateriasPlanEstudioPage'
import FinanzasPage from './pages/finanzas/FinanzasPage'
import InfraestructuraFisicaPage from './pages/infraestructura/InfraestructuraFisicaPage'
import FunctionalDashboardLayout from './pages/dashboard/FunctionalDashboardLayout'
import DashboardRedirect from './app/routes/DashboardRedirect'
import { MODULE_CATALOG } from './app/navigation/moduleCatalog'
import type { VisualProfile } from './app/navigation/types'
import RespaldosPage from './pages/respaldos/RespaldosPage'
import ComunicadosPage from './pages/comunicacion/ComunicadosPage'
import NotificacionesPage from './pages/comunicacion/NotificacionesPage'
import PortalFamiliar from './pages/portal/PortalFamiliar'
import PanelInstitucional from './pages/portal/PanelInstitucional'

const modulosGestion = MODULOS.filter((modulo) => modulo.recursos)
const perfilesComunicacion: VisualProfile[] = ['SUPERADMIN', 'ADMINISTRADOR_INSTITUCIONAL', 'DIRECTOR', 'SECRETARIA', 'PROFESOR', 'REGENTE', 'TUTOR', 'ESTUDIANTE']
const modulosDePerfil = (profile: VisualProfile) => MODULE_CATALOG
  .filter((modulo) => modulo.estadoFuncional === 'IMPLEMENTED' && modulo.perfiles.includes(profile) && modulo.recursos)

function App() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/login" element={<Login />} />
      <Route path="/registro-institucional" element={<RegistroInstitucional />} />
      <Route path="/verificar-correo" element={<VerificarCorreo />} />
      <Route
        path="/dashboard/superadmin"
        element={
          <RequireAuth allowedRoles={['superadmin']}>
            <SuperAdminLayout />
          </RequireAuth>
        }
      >
        <Route index element={<SuperAdminInicio />} />
        <Route path="respaldos" element={<RespaldosPage />} />
        {modulosDePerfil('SUPERADMIN').map((modulo) => (
          <Route
            key={modulo.ruta}
            path={modulo.ruta.replace('/dashboard/superadmin/', '')}
            element={<ModuloGestion modulo={modulo} />}
          />
        ))}
        <Route path="inscripcion" element={<Inscripcion />} />
        <Route path="asistencia" element={<VerAsistencia />} />
        <Route path="asistencia-registro" element={<RegistrarAsistencia />} />
        <Route path="historial" element={<HistorialAcademico />} />
        <Route path="riesgo" element={<RiesgoAcademico />} />
      </Route>
      <Route
        path="/dashboard/admin"
        element={<RequireAuth allowedRoles={['admin']}><AdminLayout /></RequireAuth>}
      >
        <Route index element={<AdminInicio />} />
        {modulosGestion.map((modulo) => (
          <Route
            key={modulo.ruta}
            path={modulo.ruta.replace('/dashboard/superadmin/', '')}
            element={
              <RequirePermission modelos={(modulo.recursos ?? []).map((recurso) => modeloPermisoRecurso(recurso.endpoint))}>
                <ModuloGestion modulo={modulo} />
              </RequirePermission>
            }
          />
        ))}
        <Route
          path="inscripcion"
          element={
            <RequirePermission modelos={['estudiante']} accion="crear">
              <Inscripcion />
            </RequirePermission>
          }
        />
        <Route path="asistencia" element={<VerAsistencia />} />
        <Route path="asistencia-registro" element={<RegistrarAsistencia />} />
        <Route path="historial" element={<HistorialAcademico />} />
        <Route path="riesgo" element={<RiesgoAcademico />} />
      </Route>
      <Route path="/dashboard/profesor" element={<RequireAuth allowedRoles={['profesor']}><PortalRolLayout basePath="/dashboard/profesor" titulo="Panel Docente" /></RequireAuth>}>
        <Route index element={<PortalRolInicio />} />
      </Route>
      <Route path="/dashboard/tutor" element={<RequireAuth allowedRoles={['tutor']}><PortalRolLayout basePath="/dashboard/tutor" titulo="Portal de Tutor" /></RequireAuth>}>
        <Route index element={<PortalRolInicio />} />
      </Route>
      <Route path="/dashboard/director" element={<RequireAuth><RequireProfile profiles={['DIRECTOR']}><InstitutionalRoleLayout basePath="/dashboard/director" title="Dirección académica" /></RequireProfile></RequireAuth>}>
        <Route index element={<RoleDashboardHome profile="DIRECTOR" basePath="/dashboard/director" />} />
        {modulosDePerfil('DIRECTOR').map((modulo) => (
          <Route
            key={modulo.ruta}
            path={modulo.ruta.replace('/dashboard/superadmin/', '')}
            element={<RequirePermission modelos={(modulo.recursos ?? []).map((recurso) => modeloPermisoRecurso(recurso.endpoint))}><ModuloGestion modulo={modulo} /></RequirePermission>}
          />
        ))}
        <Route path="inscripcion" element={<RequirePermission modelos={['estudiante']} accion="crear"><Inscripcion /></RequirePermission>} />
      </Route>
      <Route path="/dashboard/secretaria" element={<RequireAuth><RequireProfile profiles={['SECRETARIA']}><InstitutionalRoleLayout basePath="/dashboard/secretaria" title="Secretaría académica" /></RequireProfile></RequireAuth>}>
        <Route index element={<RoleDashboardHome profile="SECRETARIA" basePath="/dashboard/secretaria" />} />
        {modulosDePerfil('SECRETARIA').map((modulo) => (
          <Route
            key={modulo.ruta}
            path={modulo.ruta.replace('/dashboard/superadmin/', '')}
            element={<RequirePermission modelos={(modulo.recursos ?? []).map((recurso) => modeloPermisoRecurso(recurso.endpoint))}><ModuloGestion modulo={modulo} /></RequirePermission>}
          />
        ))}
        <Route path="inscripcion" element={<RequirePermission modelos={['estudiante']} accion="crear"><Inscripcion /></RequirePermission>} />
      </Route>
      <Route path="/dashboard/tesoreria" element={<RequireAuth><RequireProfile profiles={['TESORERIA']}><InstitutionalRoleLayout basePath="/dashboard/tesoreria" title="Tesorería" /></RequireProfile></RequireAuth>}>
        <Route index element={<RoleDashboardHome profile="TESORERIA" basePath="/dashboard/tesoreria" />} />
        {modulosDePerfil('TESORERIA').map((modulo) => (
          <Route key={modulo.ruta} path={modulo.ruta.replace('/dashboard/superadmin/', '')} element={<RequirePermission modelos={(modulo.recursos ?? []).map((recurso) => modeloPermisoRecurso(recurso.endpoint))}><ModuloGestion modulo={modulo} /></RequirePermission>} />
        ))}
      </Route>
      <Route path="/dashboard/regente" element={<RequireAuth><RequireProfile profiles={['REGENTE']}><PortalRolLayout basePath="/dashboard/regente" titulo="Panel de Regencia" /></RequireProfile></RequireAuth>}>
        <Route index element={<PortalRolInicio profile="REGENTE" />} />
      </Route>
      <Route path="/dashboard/estudiante" element={<RequireAuth><RequireProfile profiles={['ESTUDIANTE']}><PortalRolLayout basePath="/dashboard/estudiante" titulo="Portal del Estudiante" /></RequireProfile></RequireAuth>}>
        <Route index element={<PortalRolInicio profile="ESTUDIANTE" />} />
      </Route>
      <Route path="/dashboard" element={<RequireAuth><FunctionalDashboardLayout /></RequireAuth>}>
        <Route index element={<DashboardRedirect />} />
        <Route path="portal-familiar" element={<RequireProfile profiles={['TUTOR', 'ESTUDIANTE']}><PortalFamiliar /></RequireProfile>} />
        <Route path="panel-institucional" element={<RequirePermission modelos={['portal-panel']} profiles={['DIRECTOR']} scopes={['COLEGIO', 'UNIDAD']}><PanelInstitucional /></RequirePermission>} />
        <Route path="comunicaciones" element={<RequireProfile profiles={perfilesComunicacion}><ComunicadosPage /></RequireProfile>} />
        <Route path="notificaciones" element={<RequireProfile profiles={perfilesComunicacion}><NotificacionesPage /></RequireProfile>} />
        <Route path="respaldos" element={<RequireProfile profiles={['SUPERADMIN', 'DIRECTOR']}><RespaldosPage /></RequireProfile>} />
        <Route path="horarios" element={<RequirePermission modelos={['horario']} profiles={['ADMINISTRADOR_INSTITUCIONAL','DIRECTOR','SECRETARIA','PROFESOR']} scopes={['COLEGIO','UNIDAD','PERSONAL']}><HorariosPage /></RequirePermission>} />
        <Route path="infraestructura" element={<RequirePermission modelos={['modulo','aula']} profiles={['SUPERADMIN','DIRECTOR','SECRETARIA']} scopes={['GLOBAL','COLEGIO','UNIDAD']}><InfraestructuraFisicaPage /></RequirePermission>} />
        <Route path="disciplina" element={<RequirePermission modelos={['disciplina']} profiles={['ADMINISTRADOR_INSTITUCIONAL','DIRECTOR','REGENTE']} scopes={['COLEGIO','UNIDAD']}><DisciplinaPage /></RequirePermission>} />
        <Route path="correcciones-notas" element={<RequirePermission modelos={['correccion-nota']} profiles={['ADMINISTRADOR_INSTITUCIONAL','DIRECTOR','PROFESOR']} scopes={['COLEGIO','UNIDAD','PERSONAL']}><CorreccionesNotasPage /></RequirePermission>} />
        <Route path="auditoria" element={<RequirePermission modelos={['auditoria']} profiles={['SUPERADMIN','ADMINISTRADOR_INSTITUCIONAL','DIRECTOR']} scopes={['GLOBAL','COLEGIO']}><AuditoriaPage /></RequirePermission>} />
        <Route path="asignaciones-docentes" element={<RequirePermission modelos={['asignacion-docente']} allowPersonalProfessor profiles={['ADMINISTRADOR_INSTITUCIONAL','DIRECTOR','SECRETARIA','PROFESOR']} scopes={['COLEGIO','UNIDAD','PERSONAL']}><AsignacionesDocentesPage /></RequirePermission>} />
        <Route path="materias-plan-estudio" element={<RequirePermission modelos={['materia']} profiles={['DIRECTOR','SECRETARIA']} scopes={['COLEGIO','UNIDAD']}><MateriasPlanEstudioPage /></RequirePermission>} />
        <Route path="configuracion-evaluacion" element={<RequirePermission modelos={['configuracion-evaluacion']} profiles={['SUPERADMIN','ADMINISTRADOR_INSTITUCIONAL','DIRECTOR','SECRETARIA']} scopes={['GLOBAL','COLEGIO','UNIDAD']}><ConfiguracionEvaluacionPage /></RequirePermission>} />
        <Route path="evaluacion" element={<RequirePermission modelos={['actividad-evaluacion']} allowPersonalProfessor profiles={['ADMINISTRADOR_INSTITUCIONAL','DIRECTOR','SECRETARIA','PROFESOR']} scopes={['COLEGIO','UNIDAD','PERSONAL']}><EvaluacionPage /></RequirePermission>} />
        <Route path="reportes" element={<RequireReportes />} />
        <Route path="suscripciones" element={<RequirePermission modelos={['suscripcion']} profiles={['SUPERADMIN','ADMINISTRADOR_INSTITUCIONAL','DIRECTOR','SECRETARIA']} scopes={['GLOBAL','COLEGIO','UNIDAD']}><SuscripcionesPage /></RequirePermission>} />
        <Route path="finanzas" element={<RequirePermission modelos={['plan-pago', 'beca', 'obligacion-pago', 'pago', 'pago-qr', 'estado-cuenta', 'morosidad', 'simulacion-tributaria', 'alerta-pago']} profiles={['ADMINISTRADOR_INSTITUCIONAL','DIRECTOR','SECRETARIA','TESORERIA']} scopes={['COLEGIO','UNIDAD']}><FinanzasPage /></RequirePermission>} />
        <Route path="roles" element={<RequirePermission modelos={['rol']} profiles={['SUPERADMIN','DIRECTOR','SECRETARIA']} scopes={['GLOBAL','COLEGIO']}><RolesPage /></RequirePermission>} />
      </Route>
      <Route path="/inscripcion" element={<Navigate to="/dashboard/superadmin/inscripcion" replace />} />
      <Route path="/dashboard/no-permission" element={<NoPermission />} />
      <Route path="/no-permission" element={<NoPermission />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
