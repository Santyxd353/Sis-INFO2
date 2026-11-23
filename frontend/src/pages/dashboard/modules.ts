import type { LucideIcon } from 'lucide-react'
import {
  AlertTriangle, BookOpenCheck, Building2, CalendarRange, ClipboardCheck, CreditCard,
  GraduationCap, History, KeyRound, Scale, School, ShieldCheck, UserRoundCheck, Users,
} from 'lucide-react'

export interface ColumnaRecurso { clave: string; etiqueta: string }
export interface OpcionCampo { valor: string; etiqueta: string }

export interface CampoCrud {
  nombre: string
  etiqueta: string
  tipo?: 'text' | 'email' | 'password' | 'number' | 'date' | 'textarea' | 'select' | 'multiselect' | 'checkbox'
  requerido?: boolean
  soloCrear?: boolean
  valorRegistro?: string
  opciones?: OpcionCampo[]
  opcionesEndpoint?: string
  opcionValor?: string
  opcionEtiquetas?: string[]
  perfiles?: string[]
}

export interface ConfiguracionCrud {
  campos: CampoCrud[]
  idClave?: string
  crearEndpoint?: string
  editarEndpoint?: string
  eliminarEndpoint?: string
  metodoEditar?: 'patch' | 'put'
}

export interface RecursoModulo {
  titulo: string
  endpoint: string
  columnas: ColumnaRecurso[]
  crud?: ConfiguracionCrud
}

export interface ModuloPanel {
  titulo: string
  descripcion: string
  ruta: string
  icono: LucideIcon
  color: string
  recursos?: RecursoModulo[]
  directa?: boolean
}

export const modeloPermisoRecurso = (endpoint: string) => {
  const equivalencias: Array<[string, string]> = [
    ['/institucion/colegios/', 'colegio'],
    ['/institucion/unidades-educativas/', 'unidad-educativa'],
    ['/usuarios/usuarios/', 'usuario'],
    ['/usuarios/roles/', 'rol'],
    ['/calendario/calendarios/', 'calendario'],
    ['/calendario/periodos/', 'periodo'],
    ['/calendario/tipos-feriado/', 'tipo-feriado'],
    ['/calendario/feriados/', 'feriado'],
    ['/academico/grados/', 'grado'],
    ['/academico/paralelos/', 'paralelo'],
    ['/academico/cursos/', 'curso'],
    ['/personal/profesores/', 'profesor'],
    ['/estudiantes/estudiantes/', 'estudiante'],
    ['/estudiantes/tutores/', 'tutor'],
    ['/estudiantes/relaciones/', 'tutor-estudiante'],
    ['/suscripciones/planes/', 'plan'],
    ['/suscripciones/suscripciones/', 'suscripcion'],
    ['/suscripciones/pagos/', 'pago'],
  ]
  return equivalencias.find(([ruta]) => endpoint.startsWith(ruta))?.[1] ?? ''
}

export const rutaModuloEnPortal = (modulo: ModuloPanel, base: string) =>
  modulo.directa ? modulo.ruta : `${base}/${modulo.ruta.split('/').filter(Boolean).at(-1)}`

export const MODULO_AUDITORIA: ModuloPanel = {
  titulo: 'Seguridad y auditoría', descripcion: 'Consulta de eventos de seguridad.',
  ruta: '/dashboard/auditoria', icono: ShieldCheck, color: 'bg-red-50 text-red-700', directa: true,
}

export const MODULO_ASIGNACIONES: ModuloPanel = {
  titulo: 'Asignaciones docentes', descripcion: 'Carga académica de profesores.',
  ruta: '/dashboard/asignaciones-docentes', icono: BookOpenCheck, color: 'bg-brand-50 text-brand-700', directa: true,
}

export const MODULO_CONFIGURACION_EVALUACION: ModuloPanel = {
  titulo: 'Configuración de evaluación', descripcion: 'Dimensiones y ponderaciones por gestión académica.',
  ruta: '/dashboard/configuracion-evaluacion', icono: Scale, color: 'bg-teal-50 text-teal-700', directa: true,
}

export const MODULO_SUSCRIPCIONES: ModuloPanel = {
  titulo: 'Suscripciones SaaS', descripcion: 'Planes, contrataciones y pagos de la plataforma.',
  ruta: '/dashboard/suscripciones', icono: CreditCard, color: 'bg-brand-50 text-brand-700', directa: true,
}

export const MODULO_ROLES: ModuloPanel = {
  titulo: 'Usuarios, roles y privilegios', descripcion: 'Roles por colegio, permisos funcionales, componentes de interfaz y roles por usuario.',
  ruta: '/dashboard/roles', icono: KeyRound, color: 'bg-amber-50 text-amber-700', directa: true,
}

const opcionesEstado = [
  { valor: 'true', etiqueta: 'Activo' },
  { valor: 'false', etiqueta: 'Inactivo' },
]

const selectorUnidad: CampoCrud = {
  nombre: 'unidad_id', etiqueta: 'Unidad educativa', tipo: 'select',
  opcionesEndpoint: '/institucion/unidades-educativas/', opcionValor: 'id', opcionEtiquetas: ['nombre'],
}

export const MODULOS: ModuloPanel[] = [
  {
    titulo: 'Configuración institucional', descripcion: 'Datos del colegio y creación de unidades educativas o módulos administrativos.',
    ruta: '/dashboard/superadmin/institucion', icono: Building2, color: 'bg-sky-50 text-sky-700',
    recursos: [
      {
        titulo: 'Colegios', endpoint: '/institucion/colegios/',
        columnas: [
          { clave: 'nombre', etiqueta: 'Nombre' }, { clave: 'direccion', etiqueta: 'Dirección' },
          { clave: 'telefono', etiqueta: 'Teléfono' }, { clave: 'email', etiqueta: 'Correo' },
          { clave: 'sitio_web', etiqueta: 'Sitio web' },
        ],
        crud: { campos: [
          { nombre: 'nombre', etiqueta: 'Nombre', requerido: true },
          { nombre: 'direccion', etiqueta: 'Dirección', tipo: 'textarea', requerido: true },
          { nombre: 'telefono', etiqueta: 'Teléfono', requerido: true },
          { nombre: 'email', etiqueta: 'Correo', tipo: 'email' },
          { nombre: 'sitio_web', etiqueta: 'Sitio web' },
        ] },
      },
      {
        titulo: 'Unidades educativas o módulos administrativos', endpoint: '/institucion/unidades-educativas/',
        columnas: [
          { clave: 'nombre', etiqueta: 'Nombre' }, { clave: 'codigo_sie', etiqueta: 'Código SIE' },
          { clave: 'turno', etiqueta: 'Turno' }, { clave: 'nivel', etiqueta: 'Nivel' },
          { clave: 'colegio.nombre', etiqueta: 'Colegio' },
        ],
        crud: { campos: [
          { nombre: 'nombre', etiqueta: 'Nombre', requerido: true },
          { nombre: 'codigo_sie', etiqueta: 'Código SIE', requerido: true },
          { nombre: 'turno', etiqueta: 'Turno', tipo: 'select', requerido: true, opciones: [
            { valor: 'MAÑANA', etiqueta: 'Mañana' }, { valor: 'TARDE', etiqueta: 'Tarde' },
            { valor: 'NOCHE', etiqueta: 'Noche' }, { valor: 'COMPLETO', etiqueta: 'Jornada completa' },
          ] },
          { nombre: 'nivel', etiqueta: 'Nivel' },
          { nombre: 'direccion', etiqueta: 'Dirección', tipo: 'textarea' },
          { nombre: 'telefono', etiqueta: 'Teléfono' },
          {
            nombre: 'colegio_id', etiqueta: 'Colegio', tipo: 'select', valorRegistro: 'colegio.id',
            opcionesEndpoint: '/institucion/colegios/', opcionValor: 'id', opcionEtiquetas: ['nombre'],
          },
        ] },
      },
    ],
  },
  {
    titulo: 'Gestión de usuarios', descripcion: 'Registro y administración de usuarios.',
    ruta: '/dashboard/superadmin/usuarios', icono: Users, color: 'bg-violet-50 text-violet-700',
    recursos: [{
      titulo: 'Usuarios registrados', endpoint: '/usuarios/usuarios/',
      columnas: [
        { clave: 'nombre', etiqueta: 'Nombre' }, { clave: 'apellido', etiqueta: 'Apellido' },
        { clave: 'ci', etiqueta: 'CI' }, { clave: 'username', etiqueta: 'Usuario' },
        { clave: 'email', etiqueta: 'Correo' }, { clave: 'rol.nombre', etiqueta: 'Rol' },
        { clave: 'colegio.nombre', etiqueta: 'Colegio' },
        { clave: 'unidad.nombre', etiqueta: 'Unidad educativa' },
      ],
      crud: { campos: [
        { nombre: 'nombre', etiqueta: 'Nombre', requerido: true },
        { nombre: 'apellido', etiqueta: 'Apellido', requerido: true },
        { nombre: 'ci', etiqueta: 'CI', requerido: true },
        { nombre: 'username', etiqueta: 'Nombre de usuario', requerido: true },
        { nombre: 'email', etiqueta: 'Correo', tipo: 'email', requerido: true },
        { nombre: 'password', etiqueta: 'Contraseña', tipo: 'password', requerido: true, soloCrear: true },
        { nombre: 'sexo', etiqueta: 'Sexo', tipo: 'select', requerido: true, opciones: [
          { valor: 'M', etiqueta: 'Masculino' }, { valor: 'F', etiqueta: 'Femenino' },
        ] },
        { nombre: 'fecha_nacimiento', etiqueta: 'Fecha de nacimiento', tipo: 'date' },
        { nombre: 'telefono', etiqueta: 'Teléfono' },
        {
          nombre: 'rol_id', etiqueta: 'Rol', tipo: 'select', requerido: true, valorRegistro: 'rol.id', soloCrear: true,
          opcionesEndpoint: '/usuarios/roles/', opcionValor: 'id', opcionEtiquetas: ['nombre'],
        },
        {
          nombre: 'puesto_id', etiqueta: 'Puesto administrativo', tipo: 'select', requerido: true,
          valorRegistro: 'perfil.puesto.id', opcionesEndpoint: '/usuarios/puestos/',
          opcionValor: 'id', opcionEtiquetas: ['nombre'], perfiles: ['Admin'],
        },
        {
          nombre: 'colegio_id', etiqueta: 'Colegio', tipo: 'select', requerido: true,
          opcionesEndpoint: '/institucion/colegios/', opcionValor: 'id', opcionEtiquetas: ['nombre'],
          perfiles: ['Admin'],
        },
        {
          nombre: 'unidad_id', etiqueta: 'Unidad educativa o módulo', tipo: 'select', requerido: true,
          valorRegistro: 'unidad.id', opcionesEndpoint: '/institucion/unidades-educativas/',
          opcionValor: 'id', opcionEtiquetas: ['colegio.nombre', 'nombre'],
        },
        {
          nombre: 'curso_ids', etiqueta: 'Cursos asignados', tipo: 'multiselect',
          valorRegistro: 'perfil.cursos', opcionesEndpoint: '/academico/cursos/',
          opcionValor: 'id', opcionEtiquetas: ['nombre'], perfiles: ['Profesor'],
        },
        {
          nombre: 'curso_estudiante_id', etiqueta: 'Curso del estudiante', tipo: 'select', requerido: true,
          valorRegistro: 'perfil.curso.id', opcionesEndpoint: '/academico/cursos/',
          opcionValor: 'id', opcionEtiquetas: ['nombre'], perfiles: ['Estudiante'],
        },
        { nombre: 'rude', etiqueta: 'RUDE', requerido: true, valorRegistro: 'perfil.rude', perfiles: ['Estudiante'] },
        {
          nombre: 'parentesco', etiqueta: 'Parentesco', tipo: 'select', requerido: true,
          valorRegistro: 'perfil.parentesco', perfiles: ['Tutor'], opciones: [
            { valor: 'PAD', etiqueta: 'Padre' }, { valor: 'MAD', etiqueta: 'Madre' },
            { valor: 'TUT', etiqueta: 'Tutor legal' }, { valor: 'HER', etiqueta: 'Hermano/a' },
            { valor: 'OTR', etiqueta: 'Otro' },
          ],
        },
      ] },
    }],
  },
  {
    titulo: 'Gestión académica', descripcion: 'Calendario, periodos y feriados académicos.',
    ruta: '/dashboard/superadmin/gestion-academica', icono: CalendarRange, color: 'bg-emerald-50 text-emerald-700',
    recursos: [
      {
        titulo: 'Calendarios académicos', endpoint: '/calendario/calendarios/',
        columnas: [
          { clave: 'unidad_nombre', etiqueta: 'Unidad educativa' }, { clave: 'año', etiqueta: 'Año' },
          { clave: 'fecha_inicio', etiqueta: 'Inicio' }, { clave: 'fecha_fin', etiqueta: 'Fin' },
          { clave: 'activo', etiqueta: 'Estado' },
        ],
        crud: { campos: [
          {
            nombre: 'unidad_educativa', etiqueta: 'Unidad educativa', tipo: 'select', requerido: true,
            opcionesEndpoint: '/institucion/unidades-educativas/', opcionValor: 'id', opcionEtiquetas: ['nombre'],
          },
          { nombre: 'año', etiqueta: 'Año', tipo: 'number', requerido: true },
          { nombre: 'fecha_inicio', etiqueta: 'Fecha de inicio', tipo: 'date', requerido: true },
          { nombre: 'fecha_fin', etiqueta: 'Fecha de finalización', tipo: 'date', requerido: true },
          { nombre: 'activo', etiqueta: 'Calendario activo', tipo: 'checkbox' },
        ] },
      },
      {
        titulo: 'Periodos', endpoint: '/calendario/periodos/',
        columnas: [
          { clave: 'nombre', etiqueta: 'Nombre' }, { clave: 'calendario_nombre', etiqueta: 'Calendario' },
          { clave: 'tipo_division', etiqueta: 'División' }, { clave: 'fecha_inicio', etiqueta: 'Inicio' },
          { clave: 'fecha_fin', etiqueta: 'Fin' }, { clave: 'estado', etiqueta: 'Estado' },
        ],
        crud: { campos: [
          { nombre: 'nombre', etiqueta: 'Nombre', requerido: true },
          {
            nombre: 'calendario', etiqueta: 'Calendario', tipo: 'select', requerido: true,
            opcionesEndpoint: '/calendario/calendarios/', opcionValor: 'id', opcionEtiquetas: ['unidad_nombre', 'año'],
          },
          { nombre: 'tipo_division', etiqueta: 'Tipo de división', tipo: 'select', requerido: true, opciones: [
            { valor: 'SEM', etiqueta: 'Semestre' }, { valor: 'TRI', etiqueta: 'Trimestre' },
            { valor: 'BIM', etiqueta: 'Bimestre' }, { valor: 'CUA', etiqueta: 'Cuatrimestre' },
            { valor: 'OTR', etiqueta: 'Otro' },
          ] },
          { nombre: 'fecha_inicio', etiqueta: 'Fecha de inicio', tipo: 'date', requerido: true },
          { nombre: 'fecha_fin', etiqueta: 'Fecha de finalización', tipo: 'date', requerido: true },
          { nombre: 'estado', etiqueta: 'Estado', tipo: 'select', requerido: true, opciones: [
            { valor: 'PLA', etiqueta: 'Planificado' }, { valor: 'CUR', etiqueta: 'En curso' },
            { valor: 'FIN', etiqueta: 'Finalizado' }, { valor: 'CAN', etiqueta: 'Cancelado' },
          ] },
        ] },
      },
      {
        titulo: 'Tipos de feriado', endpoint: '/calendario/tipos-feriado/',
        columnas: [
          { clave: 'nombre', etiqueta: 'Nombre' }, { clave: 'descripcion', etiqueta: 'Descripción' },
          { clave: 'es_nacional', etiqueta: 'Nacional' },
        ],
        crud: { campos: [
          { nombre: 'nombre', etiqueta: 'Nombre', requerido: true },
          { nombre: 'descripcion', etiqueta: 'Descripción', tipo: 'textarea' },
          { nombre: 'es_nacional', etiqueta: 'Feriado nacional', tipo: 'checkbox' },
        ] },
      },
      {
        titulo: 'Feriados', endpoint: '/calendario/feriados/',
        columnas: [
          { clave: 'nombre', etiqueta: 'Nombre' }, { clave: 'fecha', etiqueta: 'Fecha' },
          { clave: 'tipo_nombre', etiqueta: 'Tipo' }, { clave: 'calendario_nombre', etiqueta: 'Calendario' },
        ],
        crud: { campos: [
          { nombre: 'nombre', etiqueta: 'Nombre', requerido: true },
          { nombre: 'descripcion', etiqueta: 'Descripción', tipo: 'textarea' },
          { nombre: 'fecha', etiqueta: 'Fecha', tipo: 'date', requerido: true },
          {
            nombre: 'calendario', etiqueta: 'Calendario', tipo: 'select', requerido: true,
            opcionesEndpoint: '/calendario/calendarios/', opcionValor: 'id', opcionEtiquetas: ['unidad_nombre', 'año'],
          },
          {
            nombre: 'tipo', etiqueta: 'Tipo de feriado', tipo: 'select', requerido: true,
            opcionesEndpoint: '/calendario/tipos-feriado/', opcionValor: 'id', opcionEtiquetas: ['nombre'],
          },
        ] },
      },
    ],
  },
  {
    titulo: 'Estructura académica', descripcion: 'Grados, paralelos y cursos.',
    ruta: '/dashboard/superadmin/estructura-academica', icono: BookOpenCheck, color: 'bg-brand-50 text-brand-700',
    recursos: [
      {
        titulo: 'Grados', endpoint: '/academico/grados/',
        columnas: [
          { clave: 'nombre', etiqueta: 'Grado' }, { clave: 'nivel_educativo_display', etiqueta: 'Nivel educativo' },
          { clave: 'unidad_nombre', etiqueta: 'Unidad educativa' },
        ],
        crud: { campos: [
          {
            nombre: 'unidad_educativa', etiqueta: 'Unidad educativa', tipo: 'select', requerido: true,
            opcionesEndpoint: '/institucion/unidades-educativas/', opcionValor: 'id', opcionEtiquetas: ['nombre'],
          },
          { nombre: 'nivel_educativo', etiqueta: 'Nivel educativo', tipo: 'select', requerido: true, opciones: [
            { valor: 'INI', etiqueta: 'Inicial' }, { valor: 'PRI', etiqueta: 'Primaria' },
            { valor: 'SEC', etiqueta: 'Secundaria' },
          ] },
          { nombre: 'numero', etiqueta: 'Número de grado', tipo: 'number', requerido: true },
        ] },
      },
      {
        titulo: 'Paralelos', endpoint: '/academico/paralelos/',
        columnas: [{ clave: 'grado.nombre', etiqueta: 'Grado' }, { clave: 'letra', etiqueta: 'Paralelo' }],
        crud: { campos: [
          {
            nombre: 'grado_id', etiqueta: 'Grado', tipo: 'select', requerido: true, valorRegistro: 'grado.id',
            opcionesEndpoint: '/academico/grados/', opcionValor: 'id', opcionEtiquetas: ['nombre', 'unidad_nombre'],
          },
          { nombre: 'letra', etiqueta: 'Letra', requerido: true },
        ] },
      },
      {
        titulo: 'Cursos', endpoint: '/academico/cursos/',
        columnas: [
          { clave: 'nombre', etiqueta: 'Curso' }, { clave: 'paralelo.grado.nombre', etiqueta: 'Grado' },
          { clave: 'paralelo.letra', etiqueta: 'Paralelo' }, { clave: 'tutor_nombre', etiqueta: 'Docente tutor' },
        ],
        crud: { campos: [
          { nombre: 'nombre', etiqueta: 'Nombre', requerido: true },
          {
            nombre: 'paralelo_id', etiqueta: 'Paralelo', tipo: 'select', requerido: true,
            valorRegistro: 'paralelo.id', opcionesEndpoint: '/academico/paralelos/', opcionValor: 'id',
            opcionEtiquetas: ['grado.nombre', 'letra'],
          },
          {
            nombre: 'tutor', etiqueta: 'Docente tutor', tipo: 'select',
            opcionesEndpoint: '/personal/profesores/', opcionValor: 'id', opcionEtiquetas: ['usuario.nombre', 'usuario.apellido'],
          },
        ] },
      },
    ],
  },
  {
    titulo: 'Registro de docentes', descripcion: 'Información y asignación de docentes.',
    ruta: '/dashboard/superadmin/docentes', icono: UserRoundCheck, color: 'bg-rose-50 text-rose-700',
    recursos: [{
      titulo: 'Docentes registrados', endpoint: '/personal/profesores/',
      columnas: [
        { clave: 'usuario.nombre', etiqueta: 'Nombre' }, { clave: 'usuario.apellido', etiqueta: 'Apellido' },
        { clave: 'usuario.ci', etiqueta: 'CI' }, { clave: 'usuario.username', etiqueta: 'Usuario' },
        { clave: 'usuario.email', etiqueta: 'Correo' },
        { clave: 'unidad_nombre', etiqueta: 'Unidad educativa' }, { clave: 'estado', etiqueta: 'Estado' },
      ],
      crud: {
        metodoEditar: 'patch',
        campos: [
          { nombre: 'nombre', etiqueta: 'Nombre', requerido: true, valorRegistro: 'usuario.nombre' },
          { nombre: 'apellido', etiqueta: 'Apellido', requerido: true, valorRegistro: 'usuario.apellido' },
          { nombre: 'ci', etiqueta: 'CI', requerido: true, valorRegistro: 'usuario.ci' },
          { nombre: 'username', etiqueta: 'Nombre de usuario', requerido: true, valorRegistro: 'usuario.username' },
          { nombre: 'email', etiqueta: 'Correo', tipo: 'email', requerido: true, valorRegistro: 'usuario.email' },
          { nombre: 'password', etiqueta: 'Contraseña temporal', tipo: 'password', requerido: true, soloCrear: true },
          { nombre: 'sexo', etiqueta: 'Sexo', tipo: 'select', requerido: true, valorRegistro: 'usuario.sexo', opciones: [
            { valor: 'M', etiqueta: 'Masculino' }, { valor: 'F', etiqueta: 'Femenino' },
          ] },
          { nombre: 'fecha_nacimiento', etiqueta: 'Fecha de nacimiento', tipo: 'date', valorRegistro: 'usuario.fecha_nacimiento' },
          { nombre: 'telefono', etiqueta: 'Teléfono', valorRegistro: 'usuario.telefono' },
          {
            nombre: 'unidad_id', etiqueta: 'Unidad educativa', tipo: 'select', requerido: true,
            valorRegistro: 'usuario.unidad.id', opcionesEndpoint: '/institucion/unidades-educativas/',
            opcionValor: 'id', opcionEtiquetas: ['colegio.nombre', 'nombre'],
          },
          {
            nombre: 'curso_ids', etiqueta: 'Cursos asignados', tipo: 'multiselect',
            valorRegistro: 'usuario.perfil.cursos', opcionesEndpoint: '/academico/cursos/',
            opcionValor: 'id', opcionEtiquetas: ['paralelo.grado.nombre', 'paralelo.letra', 'nombre'],
          },
          { nombre: 'estado', etiqueta: 'Estado', tipo: 'select', requerido: true, opciones: opcionesEstado },
        ],
      },
    }],
  },
  {
    titulo: 'Estudiantes y tutores', descripcion: 'Registro de estudiantes, tutores y relaciones.',
    ruta: '/dashboard/superadmin/estudiantes-tutores', icono: GraduationCap, color: 'bg-cyan-50 text-cyan-700',
    recursos: [
      {
        titulo: 'Estudiantes registrados', endpoint: '/estudiantes/estudiantes/',
        columnas: [
          { clave: 'usuario.nombre', etiqueta: 'Nombre' }, { clave: 'usuario.apellido', etiqueta: 'Apellido' },
          { clave: 'usuario.ci', etiqueta: 'CI' }, { clave: 'rude', etiqueta: 'RUDE' },
          { clave: 'curso.nombre', etiqueta: 'Curso' }, { clave: 'estado', etiqueta: 'Estado' },
        ],
        crud: {
          idClave: 'usuario.id', crearEndpoint: '/estudiantes/estudiantes/crear/',
          editarEndpoint: '/estudiantes/estudiantes/{id}/editar/',
          eliminarEndpoint: '/estudiantes/estudiantes/{id}/eliminar/', metodoEditar: 'patch',
          campos: [
            { nombre: 'nuevo_estudiante.nombre', etiqueta: 'Nombre', requerido: true, soloCrear: true },
            { nombre: 'nuevo_estudiante.apellido', etiqueta: 'Apellido', requerido: true, soloCrear: true },
            { nombre: 'nuevo_estudiante.ci', etiqueta: 'CI', requerido: true, soloCrear: true },
            { nombre: 'nuevo_estudiante.email', etiqueta: 'Correo', tipo: 'email', requerido: true, soloCrear: true },
            { nombre: 'nuevo_estudiante.username', etiqueta: 'Nombre de usuario', requerido: true, soloCrear: true },
            { nombre: 'nuevo_estudiante.password', etiqueta: 'Contraseña temporal', tipo: 'password', requerido: true, soloCrear: true },
            { nombre: 'nuevo_estudiante.sexo', etiqueta: 'Sexo', tipo: 'select', requerido: true, soloCrear: true, opciones: [
              { valor: 'M', etiqueta: 'Masculino' }, { valor: 'F', etiqueta: 'Femenino' },
            ] },
            { nombre: 'rude', etiqueta: 'RUDE', requerido: true },
            { nombre: 'estado', etiqueta: 'Estado', tipo: 'select', requerido: true, opciones: opcionesEstado },
            {
              nombre: 'curso_id', etiqueta: 'Curso', tipo: 'select', valorRegistro: 'curso.id',
              opcionesEndpoint: '/academico/cursos/', opcionValor: 'id', opcionEtiquetas: ['nombre'],
            },
            { ...selectorUnidad, valorRegistro: 'unidad.id' },
          ],
        },
      },
      {
        titulo: 'Tutores registrados', endpoint: '/estudiantes/tutores/',
        columnas: [
          { clave: 'usuario.nombre', etiqueta: 'Nombre' }, { clave: 'usuario.apellido', etiqueta: 'Apellido' },
          { clave: 'usuario.ci', etiqueta: 'CI' }, { clave: 'parentesco_display', etiqueta: 'Parentesco' },
        ],
      },
      {
        titulo: 'Relaciones entre tutores y estudiantes', endpoint: '/estudiantes/relaciones/',
        columnas: [
          { clave: 'tutor.usuario.nombre', etiqueta: 'Tutor' },
          { clave: 'estudiante.usuario.nombre', etiqueta: 'Estudiante' },
          { clave: 'es_principal', etiqueta: 'Tutor principal' },
        ],
        crud: {
          crearEndpoint: '/estudiantes/relaciones/crear/',
          editarEndpoint: '/estudiantes/relaciones/{id}/editar/',
          eliminarEndpoint: '/estudiantes/relaciones/{id}/eliminar/', metodoEditar: 'put',
          campos: [
            {
              nombre: 'tutor_id', etiqueta: 'Tutor', tipo: 'select', requerido: true,
              valorRegistro: 'tutor.usuario.id', opcionesEndpoint: '/estudiantes/tutores/',
              opcionValor: 'usuario.id', opcionEtiquetas: ['usuario.nombre', 'usuario.apellido'],
            },
            {
              nombre: 'estudiante_id', etiqueta: 'Estudiante', tipo: 'select', requerido: true,
              valorRegistro: 'estudiante.usuario.id', opcionesEndpoint: '/estudiantes/estudiantes/',
              opcionValor: 'usuario.id', opcionEtiquetas: ['usuario.nombre', 'usuario.apellido'],
            },
            { nombre: 'es_principal', etiqueta: 'Tutor principal', tipo: 'checkbox' },
          ],
        },
      },
    ],
  },
  {
    titulo: 'Inscribir estudiantes', descripcion: 'Proceso guiado de inscripción a cursos.',
    ruta: '/dashboard/superadmin/inscripcion', icono: School, color: 'bg-brand-50 text-brand-700',
  },
  {
    titulo: 'Asistencia', descripcion: 'Consulta de registros de asistencia.',
    ruta: '/dashboard/superadmin/asistencia', icono: ClipboardCheck, color: 'bg-emerald-50 text-emerald-700',
  },
  {
    titulo: 'Registrar asistencia', descripcion: 'Toma diaria de asistencia por curso.',
    ruta: '/dashboard/superadmin/asistencia-registro', icono: ClipboardCheck, color: 'bg-teal-50 text-teal-700',
  },
  {
    titulo: 'Historial académico', descripcion: 'Historial y notas por estudiante.',
    ruta: '/dashboard/superadmin/historial', icono: History, color: 'bg-brand-50 text-brand-700',
  },
  {
    titulo: 'Riesgo académico', descripcion: 'Alertas y seguimiento de riesgo académico.',
    ruta: '/dashboard/superadmin/riesgo', icono: AlertTriangle, color: 'bg-rose-50 text-rose-700',
  },
]

export const MODULOS_PROFESOR: ModuloPanel[] = [
  {
    titulo: 'Registrar asistencia', descripcion: 'Toma de asistencia por curso.',
    ruta: '/dashboard/profesor/asistencia', icono: ClipboardCheck, color: 'bg-emerald-50 text-emerald-700',
  },
  {
    titulo: 'Historial académico', descripcion: 'Consulta de historial y notas.',
    ruta: '/dashboard/profesor/historial', icono: History, color: 'bg-brand-50 text-brand-700',
  },
  {
    titulo: 'Riesgo académico', descripcion: 'Registro de estudiantes en riesgo.',
    ruta: '/dashboard/profesor/riesgo', icono: AlertTriangle, color: 'bg-rose-50 text-rose-700',
  },
]

export const MODULOS_TUTOR: ModuloPanel[] = [
  {
    titulo: 'Asistencia', descripcion: 'Asistencia de sus representados.',
    ruta: '/dashboard/tutor/asistencia', icono: ClipboardCheck, color: 'bg-emerald-50 text-emerald-700',
  },
  {
    titulo: 'Historial académico', descripcion: 'Historial y notas de sus representados.',
    ruta: '/dashboard/tutor/historial', icono: History, color: 'bg-brand-50 text-brand-700',
  },
  {
    titulo: 'Riesgo académico', descripcion: 'Alertas de riesgo académico.',
    ruta: '/dashboard/tutor/riesgo', icono: AlertTriangle, color: 'bg-rose-50 text-rose-700',
  },
]
