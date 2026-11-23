import axios from 'axios'
import { Pencil, Plus, RefreshCw, ShieldCheck, Trash2, Users, X } from 'lucide-react'
import { Fragment, useCallback, useEffect, useState } from 'react'
import { useAuth } from '../../app/contexts/AuthContext'
import { MODULE_CATALOG } from '../../app/navigation/moduleCatalog'
import type { Usuario } from '../../app/modelos/Usuarios'
import { listarColegiosCatalogo, listarUsuariosCatalogo } from '../../api/catalogosInstitucionales'
import {
  asignarRolesUsuario, crearRol, editarRol, eliminarRol, guardarComponentesRol,
  guardarPermisosRol, listarAcciones, listarModelosPermitidos, listarRolesAsignables,
  listarRolesGestion, normalizarCatalogo, normalizarRoles, obtenerComponentesRol,
  obtenerPermisosRol, obtenerRolesUsuario, obtenerConfiguracionInstitucional,
  guardarConfiguracionInstitucional,
  type CatalogoItem, type ComponentePermiso, type PermisoPar, type Rol,
} from '../../api/roles'

type Pestana = 'roles' | 'permisos' | 'componentes' | 'usuarios'

const rolInicial = { nombre: '', descripcion: '', activo: 'true', alcance: 'COLEGIO', colegio: '', unidad: '', puesto: '' }

const alcanceEtiqueta = (alcance: Rol['alcance']) => ({
  SISTEMA: 'Sistema', COLEGIO: 'Colegio', UNIDAD: 'Unidad educativa',
}[alcance])

const moduloDeComponente = (componente: string) => MODULE_CATALOG.find((modulo) => componente === `modulo:${modulo.key}`)
const combinarComponentes = (componentes: ComponentePermiso[]) => {
  const guardados = new Map(componentes.map((item) => [item.componente, item]))
  const catalogo = MODULE_CATALOG.filter((modulo) => modulo.estadoFuncional === 'IMPLEMENTED')
    .map((modulo) => guardados.get(`modulo:${modulo.key}`) ?? { componente: `modulo:${modulo.key}`, visible: true, editable: false })
  return [...catalogo, ...componentes.filter((item) => !item.componente.startsWith('modulo:'))]
}

export default function RolesPage() {
  const { can, isSuperAdmin, user } = useAuth()
  const esPlataforma = isSuperAdmin()
  const puedeCrear = can('rol', 'crear')
  const puedeEditar = can('rol', 'editar')
  const puedeEliminar = can('rol', 'eliminar')
  const puedeAsignarUsuarios = can('usuario', 'editar')

  const [pestana, setPestana] = useState<Pestana>('roles')
  const [roles, setRoles] = useState<Rol[]>([])
  const [acciones, setAcciones] = useState<CatalogoItem[]>([])
  const [modelos, setModelos] = useState<CatalogoItem[]>([])
  const [colegios, setColegios] = useState<Array<{ id: number; nombre: string }>>([])
  const [unidades, setUnidades] = useState<Array<{ id: number; nombre: string; colegio_id?: number }>>([])
  const [puestos, setPuestos] = useState<Array<{ id: number; nombre: string }>>([])
  const [puestoInstitucional, setPuestoInstitucional] = useState('')
  const [alcanceInstitucional] = useState<'COLEGIO' | 'UNIDAD'>('COLEGIO')
  const [unidadInstitucional] = useState('')
  const [configInstitucional, setConfigInstitucional] = useState<Awaited<ReturnType<typeof obtenerConfiguracionInstitucional>>['data'] | null>(null)
  const [cargandoInstitucional, setCargandoInstitucional] = useState(false)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [exito, setExito] = useState('')
  const [enviando, setEnviando] = useState(false)

  const [modalRol, setModalRol] = useState(false)
  const [editando, setEditando] = useState<Rol | null>(null)
  const [formRol, setFormRol] = useState(rolInicial)
  const [errores, setErrores] = useState<Record<string, string>>({})

  const [rolSeleccionado, setRolSeleccionadoBase] = useState<Rol>(null as unknown as Rol)
  const setRolSeleccionado = (rol: Rol | null) => setRolSeleccionadoBase(rol as Rol)
  const [matriz, setMatriz] = useState<Set<string>>(new Set())
  const [metadatosPermisos, setMetadatosPermisos] = useState<NonNullable<Awaited<ReturnType<typeof obtenerPermisosRol>>['data']['metadatos']>>([])
  const [cargandoPermisos, setCargandoPermisos] = useState(false)
  const [componentes, setComponentes] = useState<ComponentePermiso[]>([])
  const [nuevoComponente, setNuevoComponente] = useState('')

  const [rolesAsignables, setRolesAsignables] = useState<Rol[]>([])
  const [usuarios, setUsuarios] = useState<Usuario[]>([])
  const [busqueda, setBusqueda] = useState('')
  const [usuarioSeleccionado, setUsuarioSeleccionado] = useState<Usuario | null>(null)
  const [rolesDelUsuario, setRolesDelUsuario] = useState<number[]>([])
  const [catalogosUsuariosCargados, setCatalogosUsuariosCargados] = useState(false)

  const mensajeError = (err: unknown, porDefecto: string) => {
    const respuesta = axios.isAxiosError(err) ? err.response : undefined
    if (respuesta?.status === 403) {
      const detalle = (respuesta.data as { detail?: string } | undefined)?.detail
      return detalle || 'No tiene permiso para realizar esta operación.'
    }
    if (respuesta?.status === 400) {
      const datos = respuesta.data
      if (datos && typeof datos === 'object') {
        return Object.entries(datos as Record<string, unknown>)
          .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(' ') : String(v)}`)
          .join(' ')
      }
    }
    return porDefecto
  }

  const esDirector = Boolean(user?.perfil?.puesto?.nombre
    && user.perfil.puesto.nombre.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase() === 'director')
  const esAdminBaseInstitucional = (rol: Rol | null | undefined) => Boolean(
    esDirector && rol?.categoria === 'BASE' && rol.nombre.trim().toLowerCase() === 'admin',
  )

  const cargar = useCallback(async () => {
    setCargando(true); setError('')
    try {
      const [respuestaRoles, respuestaAcciones, respuestaModelos] = await Promise.all([
        listarRolesGestion(), listarAcciones(), listarModelosPermitidos(),
      ])
      setRoles(normalizarRoles(respuestaRoles.data))
      setAcciones(normalizarCatalogo(respuestaAcciones.data))
      setModelos(normalizarCatalogo(respuestaModelos.data))
      if (esPlataforma) setColegios(await listarColegiosCatalogo())
    }
    catch (err) { setError(mensajeError(err, 'No fue posible cargar la gestión de roles.')) }
    finally { setCargando(false) }
  }, [esPlataforma])

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void cargar() }, [cargar])

  useEffect(() => {
    if (!modalRol || formRol.alcance !== 'UNIDAD') return
    const colegio = formRol.colegio || String(user?.alcance?.colegio_id ?? '')
    if (!colegio) return
    let activo = true
    void axios.get('/institucion/unidades-educativas/', { params: { colegio } })
      .then((respuesta) => {
        if (!activo) return
        const datos = Array.isArray(respuesta.data) ? respuesta.data : respuesta.data.results ?? []
        setUnidades(datos)
      })
      .catch(() => { if (activo) setError('No se pudieron cargar las unidades educativas.') })
    return () => { activo = false }
  }, [modalRol, formRol.alcance, formRol.colegio, user?.alcance?.colegio_id])

  useEffect(() => {
    if (!modalRol || puestos.length) return
    void axios.get('/usuarios/puestos/').then((respuesta) => {
      const datos = Array.isArray(respuesta.data) ? respuesta.data : respuesta.data.results ?? []
      setPuestos(datos)
    }).catch(() => setError('No se pudieron cargar los perfiles institucionales.'))
  }, [modalRol, puestos.length])

  useEffect(() => {
    if (!esDirector) return
    let activo = true
    void Promise.all([
      puestos.length ? Promise.resolve({ data: puestos }) : axios.get('/usuarios/puestos/').then((r) => ({ data: Array.isArray(r.data) ? r.data : r.data.results ?? [] })),
      axios.get('/institucion/unidades-educativas/', { params: { colegio: user?.alcance?.colegio_id } }),
    ]).then(([puestosRespuesta, unidadesRespuesta]) => {
      if (!activo) return
      setPuestos(puestosRespuesta.data)
      const normalizar = (valor: string) => valor.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
      const secretaria = puestosRespuesta.data.find((p: { id: number; nombre: string }) => normalizar(p.nombre) === 'secretaria')
      const subordinado = puestosRespuesta.data.find((p: { id: number; nombre: string }) => !['director', 'superadmin'].includes(normalizar(p.nombre)))
      setPuestoInstitucional((actual) => actual || String(secretaria?.id ?? subordinado?.id ?? ''))
      const datos = Array.isArray(unidadesRespuesta.data) ? unidadesRespuesta.data : unidadesRespuesta.data.results ?? []
      setUnidades(datos)
    }).catch(() => { if (activo) setError('No se pudo cargar la configuración institucional.') })
    return () => { activo = false }
  }, [esDirector, puestos, user?.alcance?.colegio_id])

  const cargarConfiguracionInstitucional = useCallback(async () => {
    if (!esDirector || !puestoInstitucional) return null
    setCargandoInstitucional(true); setError('')
    try {
      const respuesta = await obtenerConfiguracionInstitucional({
        puesto_id: Number(puestoInstitucional),
        unidad_id: alcanceInstitucional === 'UNIDAD' && unidadInstitucional ? Number(unidadInstitucional) : null,
      })
      setConfigInstitucional(respuesta.data)
      setMatriz(new Set(respuesta.data.permisos.map((p) => `${p.modelo}|${p.accion}`)))
      setMetadatosPermisos(respuesta.data.metadatos ?? [])
      setRolSeleccionado(respuesta.data.rol)
      return respuesta.data
    } catch (err) { setError(mensajeError(err, 'No fue posible cargar la configuración institucional.')) }
    finally { setCargandoInstitucional(false) }
  }, [alcanceInstitucional, esDirector, puestoInstitucional, unidadInstitucional])

  const cargarCatalogosUsuarios = useCallback(async () => {
    if (catalogosUsuariosCargados) return
    try {
      const [respuestaAsignables, listaUsuarios] = await Promise.all([
        listarRolesAsignables(), listarUsuariosCatalogo(),
      ])
      setRolesAsignables(normalizarRoles(respuestaAsignables.data))
      setUsuarios(listaUsuarios)
      setCatalogosUsuariosCargados(true)
    }
    catch (err) { setError(mensajeError(err, 'No fue posible cargar los catálogos de asignación.')) }
  }, [catalogosUsuariosCargados])

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { if (pestana === 'usuarios') void cargarCatalogosUsuarios() }, [pestana, cargarCatalogosUsuarios])

  const abrirModalRol = (rol?: Rol) => {
    setErrores({}); setError('')
    setEditando(rol ?? null)
    setFormRol(rol
      ? {
          nombre: rol.nombre, descripcion: rol.descripcion ?? '',
          activo: String(rol.activo), alcance: rol.alcance, colegio: String(rol.colegio_id ?? ''), unidad: String(rol.unidad_id ?? ''), puesto: String(rol.puesto_id ?? ''),
        }
      : rolInicial)
    setModalRol(true)
  }

  const guardarRol = async () => {
    if (enviando) return
    const e: Record<string, string> = {}
    if (!formRol.nombre.trim()) e.nombre = 'Indique el nombre del rol.'
    if (!editando && formRol.alcance !== 'SISTEMA' && !(formRol.colegio || user?.alcance?.colegio_id))
      e.colegio = 'Seleccione el colegio del rol o márcalo como rol de sistema.'
    if (!editando && formRol.alcance === 'UNIDAD' && !formRol.unidad) e.unidad = 'Seleccione la unidad educativa.'
    setErrores(e)
    if (Object.keys(e).length) return
    setEnviando(true); setError('')
    try {
      if (editando) {
        await editarRol(editando.id, {
          nombre: formRol.nombre.trim(),
          descripcion: formRol.descripcion.trim() || undefined,
          activo: formRol.activo === 'true',
        })
        setExito('Rol actualizado.')
      }
      else {
        const payload: { nombre: string; descripcion?: string; activo: boolean; colegio_id?: number | null; unidad_id?: number | null; puesto_id?: number | null } = {
          nombre: formRol.nombre.trim(),
          activo: formRol.activo === 'true',
        }
        if (formRol.descripcion.trim()) payload.descripcion = formRol.descripcion.trim()
        payload.colegio_id = formRol.alcance === 'SISTEMA'
          ? null
          : Number(formRol.colegio || user?.alcance?.colegio_id)
        payload.unidad_id = formRol.alcance === 'UNIDAD' ? Number(formRol.unidad) : null
        payload.puesto_id = formRol.puesto ? Number(formRol.puesto) : null
        const respuesta = await crearRol(payload)
        setExito('Rol creado. No concede permisos hasta que configure la matriz.')
        setModalRol(false)
        await cargar()
        setRolSeleccionado(respuesta.data)
        setPestana('permisos')
        return
      }
      setModalRol(false)
      await cargar()
    }
    catch (err) { setError(mensajeError(err, 'No fue posible guardar el rol.')) }
    finally { setEnviando(false) }
  }

  const borrarRol = async (rol: Rol) => {
    if (!window.confirm(`¿Eliminar el rol "${rol.nombre}"? Esta acción revoca sus permisos.`)) return
    setError('')
    try {
      await eliminarRol(rol.id)
      setExito('Rol eliminado.')
      if (rolSeleccionado?.id === rol.id) setRolSeleccionado(null)
      await cargar()
    }
    catch (err) { setError(mensajeError(err, 'No fue posible eliminar el rol.')) }
  }

  const abrirPermisos = async (rol: Rol) => {
    setError(''); setExito(''); setCargandoPermisos(true); setMatriz(new Set())
    if (!esAdminBaseInstitucional(rol)) { setRolSeleccionado(rol); setPestana('permisos') }
    try {
      const objetivo = esAdminBaseInstitucional(rol)
        ? (await cargarConfiguracionInstitucional())?.rol
        : rol
      if (!objetivo) {
        setError('No existe una configuración institucional para Secretaría.')
        return
      }
      setRolSeleccionado(objetivo)
      const respuesta = await obtenerPermisosRol(objetivo.id)
      setMatriz(new Set(respuesta.data.permisos.map((p) => `${p.modelo}|${p.accion}`)))
      setMetadatosPermisos(respuesta.data.metadatos ?? [])
      setPestana('permisos')
    }
    catch (err) { setError(mensajeError(err, 'No fue posible cargar los permisos del rol.')) }
    finally { setCargandoPermisos(false) }
  }

  const alternarPermiso = (modelo: string, accion: string) => {
    const clave = `${modelo}|${accion}`
    setMatriz((actual) => {
      const siguiente = new Set(actual)
      if (siguiente.has(clave)) siguiente.delete(clave)
      else siguiente.add(clave)
      return siguiente
    })
  }

  const accionDependiente = (accion: string) => ['crear', 'editar', 'desactivar', 'eliminar', 'descargar', 'generar', 'aprobar'].includes(accion)
  const permisoBaseActivo = (modelo: string) => matriz.has(`${modelo}|listar`) || matriz.has(`${modelo}|ver`)
  const permisoRolActivo = (modelo: string, accion: string) => Boolean(rolSeleccionado?.permisos.some((permiso) => permiso.modelo === modelo && permiso.accion === accion))

  const guardarMatriz = async () => {
    const adminInstitucional = esDirector && rolSeleccionado?.categoria === 'BASE' && rolSeleccionado.nombre.toLowerCase() === 'admin'
    if (!rolSeleccionado || (rolSeleccionado.categoria !== 'FUNCIONAL' && !adminInstitucional) || enviando) return
    setEnviando(true); setError(''); setExito('')
    try {
      const permisos: PermisoPar[] = [...matriz].map((clave) => {
        const [modelo, accion] = clave.split('|')
        return { modelo, accion }
      })
      if (esDirector && puestoInstitucional) {
        const respuesta = await guardarConfiguracionInstitucional({
          puesto_id: Number(puestoInstitucional),
          unidad_id: alcanceInstitucional === 'UNIDAD' && unidadInstitucional ? Number(unidadInstitucional) : null,
          permisos,
        })
        setConfigInstitucional(respuesta.data)
        setRolSeleccionado(respuesta.data.rol)
        setMetadatosPermisos(respuesta.data.metadatos ?? [])
        setExito(`Permisos de ${respuesta.data.perfil_objetivo.nombre} · Alcance ${respuesta.data.alcance.toLowerCase()} actualizados.`)
      } else if (rolSeleccionado) {
        await guardarPermisosRol(rolSeleccionado.id, permisos)
        setRolSeleccionado({ ...rolSeleccionado, permisos })
        setExito(`Permisos de "${rolSeleccionado.nombre}" actualizados (${permisos.length} concesiones).`)
      }
      await cargar()
    }
    catch (err) { setError(mensajeError(err, 'No fue posible guardar los permisos.')) }
    finally { setEnviando(false) }
  }

  const abrirComponentes = async (rol: Rol) => {
    setError(''); setExito('')
    try {
      const respuesta = await obtenerComponentesRol(rol.id)
      setRolSeleccionado(rol)
      setComponentes(combinarComponentes(respuesta.data.componentes))
      setNuevoComponente('')
      setPestana('componentes')
    }
    catch (err) { setError(mensajeError(err, 'No fue posible cargar los componentes del rol.')) }
  }

  const abrirComponentesInstitucionales = async () => {
    if (!esDirector || !puestoInstitucional) return
    setError(''); setCargandoInstitucional(true)
    try {
      const respuesta = await obtenerConfiguracionInstitucional({
        puesto_id: Number(puestoInstitucional),
        unidad_id: alcanceInstitucional === 'UNIDAD' && unidadInstitucional ? Number(unidadInstitucional) : null,
      })
      setConfigInstitucional(respuesta.data)
      setMatriz(new Set(respuesta.data.permisos.map((p) => `${p.modelo}|${p.accion}`)))
      setMetadatosPermisos(respuesta.data.metadatos ?? [])
      setRolSeleccionado(respuesta.data.rol)
      if (respuesta.data.rol) {
        const componentesRespuesta = await obtenerComponentesRol(respuesta.data.rol.id)
        setComponentes(combinarComponentes(componentesRespuesta.data.componentes))
      } else {
        setComponentes(MODULE_CATALOG.filter((modulo) => modulo.estadoFuncional === 'IMPLEMENTED').map((modulo) => ({ componente: `modulo:${modulo.key}`, visible: true, editable: false })))
      }
      setPestana('componentes')
    } catch (err) { setError(mensajeError(err, 'No fue posible cargar los componentes institucionales.')) }
    finally { setCargandoInstitucional(false) }
  }

  const actualizarComponente = (indice: number, cambios: Partial<ComponentePermiso>) => {
    setComponentes((actual) => actual.map((item, i) => (i === indice ? { ...item, ...cambios } : item)))
  }

  const agregarComponente = () => {
    const codigo = nuevoComponente.trim()
    if (!codigo) return
    if (componentes.some((item) => item.componente === codigo)) {
      setError(`El componente "${codigo}" ya está configurado en este rol.`)
      return
    }
    setComponentes((actual) => [...actual, { componente: codigo, visible: true, editable: false }])
    setNuevoComponente('')
  }

  const guardarComponentes = async () => {
    const adminInstitucional = esDirector && rolSeleccionado?.categoria === 'BASE' && rolSeleccionado.nombre.toLowerCase() === 'admin'
    if (!rolSeleccionado || (rolSeleccionado.categoria !== 'FUNCIONAL' && !adminInstitucional) || enviando) return
    setEnviando(true); setError(''); setExito('')
    try {
      let rol = rolSeleccionado
      if (esDirector && !rol && puestoInstitucional) {
        const guardado = await guardarConfiguracionInstitucional({
          puesto_id: Number(puestoInstitucional),
          unidad_id: alcanceInstitucional === 'UNIDAD' && unidadInstitucional ? Number(unidadInstitucional) : null,
          permisos: [...matriz].map((clave) => { const [modelo, accion] = clave.split('|'); return { modelo, accion } }),
        })
        const rolCreado = guardado.data.rol
        if (!rolCreado) throw new Error('No se pudo crear el rol institucional.')
        rol = rolCreado
        setConfigInstitucional(guardado.data)
        setRolSeleccionado(rol as Rol)
      }
      if (!rol) return
      await guardarComponentesRol(rol.id, componentes)
      const componentesActualizados = await obtenerComponentesRol(rol.id)
      setComponentes(combinarComponentes(componentesActualizados.data.componentes))
      setExito(`Componentes de interfaz de "${rol.nombre}" actualizados.`)
      await cargar()
    }
    catch (err) { setError(mensajeError(err, 'No fue posible guardar los componentes.')) }
    finally { setEnviando(false) }
  }

  const seleccionarUsuario = async (usuario: Usuario) => {
    setError(''); setExito('')
    try {
      const respuesta = await obtenerRolesUsuario(usuario.id)
      setUsuarioSeleccionado(usuario)
      setRolesDelUsuario(respuesta.data.roles.map((rol) => rol.id))
    }
    catch (err) { setError(mensajeError(err, 'No fue posible consultar los roles del usuario.')) }
  }

  const alternarRolUsuario = (rolId: number) => {
    setRolesDelUsuario((actual) => actual.includes(rolId)
      ? actual.filter((id) => id !== rolId)
      : [...actual, rolId])
  }

  const guardarRolesUsuario = async () => {
    if (!usuarioSeleccionado || enviando) return
    setEnviando(true); setError(''); setExito('')
    try {
      await asignarRolesUsuario(usuarioSeleccionado.id, rolesDelUsuario)
      setExito(`Roles adicionales de ${usuarioSeleccionado.nombre} ${usuarioSeleccionado.apellido} actualizados.`)
    }
    catch (err) { setError(mensajeError(err, 'No fue posible asignar los roles.')) }
    finally { setEnviando(false) }
  }

  const usuariosFiltrados = usuarios.filter((usuario) => {
    const texto = `${usuario.nombre} ${usuario.apellido} ${usuario.username}`.toLowerCase()
    return texto.includes(busqueda.trim().toLowerCase())
  })

  const gruposRoles: Array<[string, Rol[]]> = [
    ['Roles base del sistema', roles.filter((rol) => rol.categoria === 'BASE')],
    ['Plantillas funcionales del sistema', roles.filter((rol) => rol.categoria === 'FUNCIONAL' && rol.alcance === 'SISTEMA')],
    ['Roles de colegio', roles.filter((rol) => rol.categoria === 'FUNCIONAL' && rol.alcance === 'COLEGIO')],
    ['Roles de unidad educativa', roles.filter((rol) => rol.categoria === 'FUNCIONAL' && rol.alcance === 'UNIDAD')],
  ]

  const pestanas: Array<{ clave: Pestana; etiqueta: string; visible: boolean }> = [
    { clave: 'roles', etiqueta: 'Roles', visible: true },
    { clave: 'permisos', etiqueta: 'Permisos funcionales', visible: true },
    { clave: 'componentes', etiqueta: 'Componentes de interfaz', visible: true },
    { clave: 'usuarios', etiqueta: 'Roles por usuario', visible: puedeAsignarUsuarios },
  ]
  const puedeEditarSeleccionado = puedeEditar
    && (rolSeleccionado?.categoria === 'FUNCIONAL'
      && (esPlataforma || rolSeleccionado.colegio_id === user?.alcance?.colegio_id)
      || (esDirector && rolSeleccionado?.categoria === 'BASE' && rolSeleccionado.nombre.toLowerCase() === 'admin'))

  const abrirPermisosDesdeFila = (rol: Rol) => { void abrirPermisos(rol) }
  const abrirComponentesDesdeFila = (rol: Rol) => {
    if (esAdminBaseInstitucional(rol)) void abrirComponentesInstitucionales()
    else void abrirComponentes(rol)
  }

  return (
    <section className="p-4 sm:p-6 lg:p-8" aria-labelledby="roles-titulo">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <ShieldCheck className="text-amber-700" />
            <h1 id="roles-titulo" className="text-2xl font-bold">Usuarios, roles y privilegios</h1>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Roles por colegio, permisos funcionales por modelo y acción, componentes de interfaz y roles adicionales por usuario.
          </p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={() => void cargar()} aria-label="Actualizar roles">
            <RefreshCw size={17} />Actualizar
          </button>
          {puedeCrear && (
            <button className="btn-primary" onClick={() => abrirModalRol()}>
              <Plus size={18} />Nuevo rol
            </button>
          )}
        </div>
      </header>

      <nav className="mb-5 flex flex-wrap gap-2" aria-label="Secciones de gestión de roles">
        {pestanas.filter((p) => p.visible).map((p) => (
          <button
            key={p.clave}
            type="button"
            onClick={() => setPestana(p.clave)}
            aria-current={pestana === p.clave ? 'page' : undefined}
            className={pestana === p.clave ? 'btn-primary' : 'btn-secondary'}
          >
            {p.etiqueta}
          </button>
        ))}
      </nav>

      {exito && <p role="status" className="mb-4 rounded-xl bg-emerald-50 p-3 text-emerald-700">{exito}</p>}
      {error && <p role="alert" className="mb-4 rounded-xl bg-red-50 p-3 text-red-700">{error}</p>}

      {cargando && <p className="p-8 text-center text-slate-500">Cargando información...</p>}

      {!cargando && pestana === 'roles' && (
        <div className="overflow-x-auto rounded-2xl bg-white shadow-sm">
          {roles.length === 0
            ? <p className="p-8 text-center text-slate-500">No existen roles aplicables en este alcance.</p>
            : (
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    {['Rol', 'Descripción', 'Categoría', 'Estado', 'Permisos', 'Componentes', 'Acciones'].map((x) => (
                      <th key={x} className="px-4 py-3">{x}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {gruposRoles.filter(([, filas]) => filas.length > 0).map(([grupo, filas]) => (
                    <Fragment key={grupo}>
                    <tr className="bg-slate-50"><th colSpan={7} className="px-4 py-2 text-xs uppercase tracking-wide text-slate-500">{grupo}</th></tr>
                    {filas.map((rol) => {
                    const editable = puedeEditar && rol.categoria === 'FUNCIONAL' && (esPlataforma || rol.colegio_id === user?.alcance?.colegio_id)
                    return (
                    <tr key={rol.id} className="border-t border-slate-100">
                      <td className="px-4 py-3 font-medium">{rol.nombre}</td>
                      <td className="px-4 py-3 text-slate-500">{rol.descripcion || '—'}</td>
                      <td className="px-4 py-3">
                        <span className={`rounded-full px-2 py-1 text-xs font-medium ${
                          rol.categoria === 'BASE' ? 'bg-slate-100 text-slate-600' : 'bg-sky-50 text-sky-700'
                        }`}>
                          {rol.categoria === 'BASE' ? 'Rol base' : `Funcional · ${alcanceEtiqueta(rol.alcance)}`}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`rounded-full px-2 py-1 text-xs font-medium ${
                          rol.activo ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'
                        }`}>
                          {rol.activo ? 'Activo' : 'Inactivo'}
                        </span>
                      </td>
                      <td className="px-4 py-3">{rol.permisos.length}</td>
                      <td className="px-4 py-3">{rol.componentes.length}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          <button className="text-brand-700" onClick={() => abrirPermisosDesdeFila(rol)}>
                            Permisos
                          </button>
                          <button className="text-teal-700" onClick={() => abrirComponentesDesdeFila(rol)}>
                            Interfaz
                          </button>
                          {editable && (
                            <button className="text-amber-700" aria-label={`Editar rol ${rol.nombre}`}
                              onClick={() => abrirModalRol(rol)}>
                              <Pencil size={15} />
                            </button>
                          )}
                          {editable && puedeEliminar && (
                            <button className="text-red-600" aria-label={`Eliminar rol ${rol.nombre}`}
                              onClick={() => void borrarRol(rol)}>
                              <Trash2 size={15} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                    )
                    })}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            )}
        </div>
      )}

      {!cargando && pestana === 'permisos' && (
        <div>
          {!rolSeleccionado
            ? <p className="rounded-2xl bg-white p-8 text-center text-slate-500 shadow-sm">Seleccione "Permisos" en un rol de la lista.</p>
            : (
              <>
                {esDirector && configInstitucional && <p className="mb-4 text-sm text-slate-600">Perfil: <strong>{configInstitucional.perfil_objetivo.nombre}</strong> · Alcance: <strong>{configInstitucional.unidad?.nombre ?? 'Todo mi colegio'}</strong></p>}
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                  <p className="text-sm text-slate-600">
                    Rol: <strong>{rolSeleccionado.nombre}</strong> · Marque solo las acciones que el rol puede ejecutar.
                    Denegación por defecto: una celda sin marcar queda denegada.
                  </p>
                  {puedeEditarSeleccionado && (
                    <button className="btn-primary" disabled={enviando} onClick={() => void guardarMatriz()}>
                      {enviando ? 'Guardando...' : 'Guardar permisos'}
                    </button>
                  )}
                </div>
                <p className="mb-3 text-xs text-slate-500">Asignado · Heredado · Disponible · Bloqueado</p>
                {cargandoPermisos || cargandoInstitucional ? <div className="rounded-2xl bg-white p-8 text-center text-slate-500">Cargando permisos...</div> : <div className="overflow-x-auto rounded-2xl bg-white shadow-sm">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-50">
                      <tr>
                        <th className="px-4 py-3">Modelo</th>
                        {acciones.map((accion) => (
                          <th key={accion.id} className="px-3 py-3 text-center">{accion.nombre}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {modelos.map((modelo) => (
                        <tr key={modelo.id} className="border-t border-slate-100">
                          <td className="px-4 py-2 font-medium">{modelo.nombre}</td>
                          {acciones.map((accion) => {
                            const clave = `${modelo.nombre}|${accion.nombre}`
                            const metadata = metadatosPermisos.find((item) => item.modelo === modelo.nombre && item.accion === accion.nombre)
                            return (
                              <td key={accion.id} className="px-3 py-2 text-center">
                                <input
                                  type="checkbox"
                                  aria-label={`${modelo.nombre} ${accion.nombre}`}
                                  checked={matriz.has(clave)}
                                  disabled={!puedeEditarSeleccionado || (accionDependiente(accion.nombre) && !permisoBaseActivo(modelo.nombre))}
                                  onChange={() => alternarPermiso(modelo.nombre, accion.nombre)}
                                  title={metadata?.motivo_bloqueo ?? undefined}
                                  className="size-4 accent-brand-600"
                                />
                              </td>
                            )
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>}
              </>
            )}
        </div>
      )}

      {!cargando && pestana === 'componentes' && (
        <div>
          {!rolSeleccionado
            ? <p className="rounded-2xl bg-white p-8 text-center text-slate-500 shadow-sm">Seleccione "Interfaz" en un rol de la lista.</p>
            : (
              <>
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                  <p className="text-sm text-slate-600">
                    Rol: <strong>{rolSeleccionado.nombre}</strong> · Oculto si algún rol lo deshabilita; editable solo si algún rol lo habilita.
                  </p>
                  {puedeEditarSeleccionado && (
                    <button className="btn-primary" disabled={enviando} onClick={() => void guardarComponentes()}>
                      {enviando ? 'Guardando...' : 'Guardar componentes'}
                    </button>
                  )}
                </div>
                <div className="rounded-2xl bg-white p-5 shadow-sm">
                  {puedeEditarSeleccionado && (
                    <div className="mb-4 flex flex-wrap gap-2">
                      <input
                        aria-label="Nuevo componente"
                        list="componentes-modulo"
                        value={nuevoComponente}
                        onChange={(e) => setNuevoComponente(e.target.value)}
                        placeholder="codigo-del-componente"
                        className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                      />
                      <datalist id="componentes-modulo">{MODULE_CATALOG.filter((modulo) => modulo.estadoFuncional === 'IMPLEMENTED').map((modulo) => <option key={modulo.key} value={`modulo:${modulo.key}`}>{modulo.titulo}</option>)}</datalist>
                      <button className="btn-secondary" onClick={agregarComponente}>
                        <Plus size={17} />Agregar componente
                      </button>
                    </div>
                  )}
                  <p className="mb-3 text-xs text-slate-500">Use modulo:nombre para ocultar una sección del menú. La visibilidad de interfaz no reemplaza los permisos funcionales.</p>
                  {componentes.length === 0
                    ? <p className="text-sm text-slate-500">Sin componentes configurados: todos son visibles y no editables.</p>
                    : (
                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                          <thead className="bg-slate-50">
                            <tr>
                              {['Componente', 'Visible', 'Editable', ''].map((x) => <th key={x} className="px-4 py-3">{x}</th>)}
                            </tr>
                          </thead>
                          <tbody>
                            {componentes.map((item, indice) => (
                              <tr key={item.componente} className="border-t border-slate-100">
                                <td className="px-4 py-3 font-medium">{moduloDeComponente(item.componente)?.titulo ?? item.componente}</td>
                                <td className="px-4 py-3">
                                  <input
                                    type="checkbox"
                                    aria-label={`Visible ${item.componente}`}
                                    checked={item.visible}
                                    disabled={!puedeEditarSeleccionado || Boolean(moduloDeComponente(item.componente)?.permiso && !permisoRolActivo(moduloDeComponente(item.componente)?.permiso?.modelo ?? '', moduloDeComponente(item.componente)?.permiso?.accion ?? ''))}
                                    onChange={(e) => actualizarComponente(indice, { visible: e.target.checked })}
                                    className="size-4 accent-brand-600"
                                  />
                                </td>
                                <td className="px-4 py-3">
                                  <input
                                    type="checkbox"
                                    aria-label={`Editable ${item.componente}`}
                                    checked={item.editable}
                                    disabled={!puedeEditarSeleccionado || Boolean(moduloDeComponente(item.componente)?.permiso && !permisoRolActivo(moduloDeComponente(item.componente)?.permiso?.modelo ?? '', 'editar'))}
                                    onChange={(e) => actualizarComponente(indice, { editable: e.target.checked })}
                                    className="size-4 accent-brand-600"
                                  />
                                </td>
                                <td className="px-4 py-3">
                                  {puedeEditarSeleccionado && (
                                    <button
                                      className="text-red-600"
                                      aria-label={`Quitar componente ${item.componente}`}
                                      onClick={() => setComponentes((actual) => actual.filter((_, i) => i !== indice))}
                                    >
                                      <Trash2 size={15} />
                                    </button>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                </div>
              </>
            )}
        </div>
      )}

      {!cargando && pestana === 'usuarios' && (
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center gap-2">
              <Users size={18} className="text-brand-700" />
              <h2 className="font-semibold">Usuarios</h2>
            </div>
            <input
              aria-label="Buscar usuario"
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
              placeholder="Buscar por nombre o usuario..."
              className="mb-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
            <ul className="max-h-96 space-y-1 overflow-y-auto">
              {usuariosFiltrados.length === 0
                ? <li className="p-3 text-sm text-slate-500">Sin usuarios.</li>
                : usuariosFiltrados.map((usuario) => (
                  <li key={usuario.id}>
                    <button
                      type="button"
                      onClick={() => void seleccionarUsuario(usuario)}
                      className={`w-full rounded-lg px-3 py-2 text-left text-sm ${
                        usuarioSeleccionado?.id === usuario.id
                          ? 'bg-brand-50 font-medium text-brand-700'
                          : 'hover:bg-slate-50'
                      }`}
                    >
                      {usuario.nombre} {usuario.apellido}
                      <span className="block text-xs text-slate-500">Rol base: {usuario.rol?.nombre}</span>
                    </button>
                  </li>
                ))}
            </ul>
          </div>

          <div className="rounded-2xl bg-white p-5 shadow-sm">
            <h2 className="mb-3 font-semibold">Roles adicionales</h2>
            {!usuarioSeleccionado
              ? <p className="text-sm text-slate-500">Seleccione un usuario para asignarle roles personalizados.</p>
              : (
                <>
                  <p className="mb-3 text-sm text-slate-600">
                    {usuarioSeleccionado.nombre} {usuarioSeleccionado.apellido} puede recibir varios roles activos de este colegio.
                  </p>
                  <ul className="mb-4 space-y-2">
                    {rolesAsignables.length === 0
                      ? <li className="text-sm text-slate-500">No hay roles personalizados activos en su colegio.</li>
                      : rolesAsignables.map((rol) => (
                        <li key={rol.id} className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            aria-label={`Rol ${rol.nombre}`}
                            checked={rolesDelUsuario.includes(rol.id)}
                            disabled={!puedeAsignarUsuarios || enviando || rol.asignable === false || !rol.activo || rol.permisos.length === 0}
                            onChange={() => alternarRolUsuario(rol.id)}
                            className="size-4 accent-brand-600"
                          />
                          {rol.nombre} <span className="text-xs text-slate-500">({alcanceEtiqueta(rol.alcance)})</span>
                        </li>
                      ))}
                  </ul>
                  {puedeAsignarUsuarios && (
                    <button className="btn-primary" disabled={enviando} onClick={() => void guardarRolesUsuario()}>
                      {enviando ? 'Guardando...' : 'Guardar roles del usuario'}
                    </button>
                  )}
                </>
              )}
          </div>
        </div>
      )}

      {modalRol && (
        <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-slate-950/50 p-4">
          <div className="w-full max-w-xl rounded-2xl bg-white p-6">
            <button aria-label="Cerrar formulario" className="float-right" onClick={() => setModalRol(false)}><X /></button>
            <h2 className="text-xl font-bold">{editando ? 'Editar' : 'Nuevo'} rol</h2>
            <div className="mt-5 grid gap-4">
              <Campo label="Nombre" value={formRol.nombre} error={errores.nombre}
                onChange={(v) => setFormRol({ ...formRol, nombre: v })} />
              <label className="text-sm font-medium">Descripción
                <textarea
                  aria-label="Descripción"
                  value={formRol.descripcion}
                  onChange={(e) => setFormRol({ ...formRol, descripcion: e.target.value })}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
                  rows={2}
                />
              </label>
              <Select label="Estado" value={formRol.activo}
                onChange={(v) => setFormRol({ ...formRol, activo: v })}
                opciones={[['true', 'Activo'], ['false', 'Inactivo (no concede permisos)']]} />
              {!editando && (
                <>
                  <Select
                    label="Alcance"
                    value={formRol.alcance === 'SISTEMA' ? 'true' : formRol.alcance === 'COLEGIO' ? 'false' : formRol.alcance}
                    onChange={(v) => setFormRol({ ...formRol, alcance: v === 'true' ? 'SISTEMA' : v === 'false' ? 'COLEGIO' : v, unidad: v === 'UNIDAD' ? formRol.unidad : '' })}
                    ocultarValores={esPlataforma ? [] : ['true']}
                    opciones={[
                      ['UNIDAD', 'Rol funcional de unidad educativa'],
                      ['false', 'Rol de un colegio específico'],
                      ['true', 'Rol de sistema (todos los colegios)'],
                    ]}
                  />
                  {formRol.alcance !== 'SISTEMA' && esPlataforma && (
                    <Select
                      label="Colegio"
                      value={formRol.colegio}
                      onChange={(v) => setFormRol({ ...formRol, colegio: v })}
                      error={errores.colegio}
                      opciones={[['', 'Seleccione...'], ...colegios.map((c) => [String(c.id), c.nombre])]}
                    />
                  )}
                  {formRol.alcance !== 'SISTEMA' && !esPlataforma && (
                    <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">Colegio autorizado: {user?.alcance?.colegio_nombre ?? 'Colegio actual'}</p>
                  )}
                  <Select
                    label="Perfil institucional (opcional)"
                    value={formRol.puesto}
                    onChange={(v) => setFormRol({ ...formRol, puesto: v })}
                    opciones={[['', 'Configuración general'], ...puestos.map((puesto) => [String(puesto.id), puesto.nombre])]}
                  />
                  {formRol.alcance === 'UNIDAD' && (
                    <Select label="Unidad educativa" value={formRol.unidad} onChange={(v) => setFormRol({ ...formRol, unidad: v })} error={errores.unidad}
                      opciones={[['', 'Seleccione...'], ...unidades.map((u) => [String(u.id), u.nombre])]}/>
                  )}
                </>
              )}
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button className="btn-secondary" onClick={() => setModalRol(false)}>Cancelar</button>
              <button className="btn-primary" disabled={enviando} onClick={() => void guardarRol()}>
                {enviando ? 'Guardando...' : 'Guardar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}

function Campo({ label, value, onChange, type = 'text', error }: {
  label: string; value: string; onChange: (v: string) => void; type?: string; error?: string
}) {
  return (
    <label className="text-sm font-medium">
      {label}
      <input
        aria-label={label}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
      />
      {error && <span className="block text-xs text-red-600">{error}</span>}
    </label>
  )
}

function Select({ label, value, onChange, opciones, error, ocultarValores = [] }: {
  label: string; value: string; onChange: (v: string) => void; opciones: string[][]; error?: string; ocultarValores?: string[]
}) {
  return (
    <label className="text-sm font-medium">
      {label}
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2"
      >
        {opciones.filter(([v]) => !ocultarValores.includes(v)).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
      </select>
      {error && <span className="block text-xs text-red-600">{error}</span>}
    </label>
  )
}
