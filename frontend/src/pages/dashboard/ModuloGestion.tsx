import { AlertCircle, Pencil, Plus, RefreshCw, Trash2, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import axios from '../../api/axiosInstance'
import { useAuth } from '../../app/contexts/AuthContext'
import { modeloPermisoRecurso } from './modules'
import type { CampoCrud, ConfiguracionCrud, ModuloPanel, RecursoModulo } from './modules'

type Registro = Record<string, unknown>
type ValoresFormulario = Record<string, string | boolean | string[]>

interface EstadoRecurso {
  datos: Registro[]
  cargando: boolean
  error: string | null
}

interface ModalCrud {
  recurso: RecursoModulo
  registro: Registro | null
}

const listaDesdeRespuesta = (data: unknown): Registro[] => {
  if (Array.isArray(data)) return data as Registro[]
  if (data && typeof data === 'object' && 'results' in data) {
    const results = (data as { results?: unknown }).results
    return Array.isArray(results) ? (results as Registro[]) : []
  }
  return []
}

const valorPorRuta = (registro: Registro, ruta: string): unknown =>
  ruta.split('.').reduce<unknown>((valor, clave) => {
    if (valor && typeof valor === 'object') return (valor as Registro)[clave]
    return undefined
  }, registro)

const mostrarValor = (valor: unknown): string => {
  if (typeof valor === 'boolean') return valor ? 'Sí' : 'No'
  if (valor === null || valor === undefined || valor === '') return '—'
  if (typeof valor === 'object') return '—'
  return String(valor)
}

const normalizarNombre = (valor: unknown) => String(valor ?? '')
  .trim()
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .toLowerCase()

const esRecursoUsuarios = (recurso: RecursoModulo) => recurso.endpoint === '/usuarios/usuarios/'

const listaMensajes = (valor: unknown) => {
  if (Array.isArray(valor)) return valor.map(String).join(', ')
  return String(valor)
}

const erroresPorCampo = (error: unknown): Record<string, string> => {
  if (typeof error !== 'object' || error === null || !('response' in error)) return {}
  const data = (error as { response?: { data?: unknown } }).response?.data
  if (!data || typeof data !== 'object' || Array.isArray(data)) return {}
  const respuesta = data as Registro
  const errores: Record<string, string> = {}
  const alias: Record<string, string> = {
    colegio: 'colegio_id',
    unidad: 'unidad_id',
    puesto: 'puesto_id',
    rol: 'rol_id',
  }
  Object.entries(respuesta).forEach(([campo, valor]) => {
    const campoFormulario = alias[campo] ?? campo
    if (typeof valor === 'string' || Array.isArray(valor)) {
      errores[campoFormulario] = listaMensajes(valor)
    }
  })
  return errores
}

const mensajeError = (error: unknown) => {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = (error as { response?: { status?: number; data?: unknown } }).response
    const data = response?.data
    if (typeof data === 'string') return data
    if (data && typeof data === 'object') {
      if ('detail' in data) return String((data as { detail: unknown }).detail)
      return Object.entries(data as Registro)
        .map(([campo, valor]) => `${campo}: ${listaMensajes(valor)}`)
        .join(' · ')
    }
    if (response?.status === 403) return 'No tiene permisos para realizar esta acción.'
  }
  return 'No se pudo completar la operación.'
}

const colegioDeUsuario = (registro: Registro | null) => {
  if (!registro) return ''
  const colegioId = valorPorRuta(registro, 'colegio.id')
    ?? valorPorRuta(registro, 'colegio_id')
    ?? valorPorRuta(registro, 'alcance.colegio_id')
    ?? valorPorRuta(registro, 'unidad.colegio.id')
  return colegioId === null || colegioId === undefined ? '' : String(colegioId)
}

const puestoDeUsuario = (registro: Registro | null) =>
  valorPorRuta(registro ?? {}, 'puesto.nombre')
  ?? valorPorRuta(registro ?? {}, 'perfil.puesto.nombre')
  ?? ''

const rolVisibleDeUsuario = (registro: Registro) => {
  const rol = String(valorPorRuta(registro, 'rol.nombre') ?? '')
  if (normalizarNombre(rol) !== 'admin') return rol
  const puesto = String(puestoDeUsuario(registro) || '').trim()
  return puesto || rol
}

const esDirector = (registro: Registro) =>
  normalizarNombre(valorPorRuta(registro, 'rol.nombre')) === 'admin'
  && normalizarNombre(puestoDeUsuario(registro)) === 'director'

const esTesoreria = (registro: Registro) =>
  normalizarNombre(valorPorRuta(registro, 'rol.nombre')) === 'admin'
  && normalizarNombre(puestoDeUsuario(registro)) === 'tesoreria'

const valorColumna = (recurso: RecursoModulo, registro: Registro, clave: string) => {
  if (!esRecursoUsuarios(recurso)) return mostrarValor(valorPorRuta(registro, clave))
  if (clave === 'colegio.nombre') {
    return mostrarValor(
      valorPorRuta(registro, 'colegio.nombre')
      ?? valorPorRuta(registro, 'alcance.colegio_nombre')
      ?? valorPorRuta(registro, 'unidad.colegio.nombre'),
    )
  }
  if (clave === 'unidad.nombre' && esDirector(registro)) {
    return colegioDeUsuario(registro) ? 'Todas las unidades' : '—'
  }
  if (clave === 'unidad.nombre' && esTesoreria(registro)
    && valorPorRuta(registro, 'alcance.tipo') === 'COLEGIO') return 'Todas las unidades'
  if (clave === 'rol.nombre') return rolVisibleDeUsuario(registro)
  return mostrarValor(valorPorRuta(registro, clave))
}

const consultarRecursos = async (recursos: RecursoModulo[]) => {
  const resultados = await Promise.all(recursos.map(async (recurso) => {
    try {
      const response = await axios.get(recurso.endpoint)
      return [recurso.endpoint, {
        datos: listaDesdeRespuesta(response.data), cargando: false, error: null,
      }] as const
    } catch {
      return [recurso.endpoint, {
        datos: [], cargando: false,
        error: 'No se pudieron cargar los datos. Verifique que el backend esté ejecutándose.',
      }] as const
    }
  }))
  return Object.fromEntries(resultados) as Record<string, EstadoRecurso>
}

const resolverEndpoint = (plantilla: string, id: unknown) => plantilla.replace('{id}', String(id))

const asignarPorRuta = (destino: Registro, ruta: string, valor: unknown) => {
  const partes = ruta.split('.')
  let actual = destino
  partes.slice(0, -1).forEach((parte) => {
    if (!actual[parte] || typeof actual[parte] !== 'object') actual[parte] = {}
    actual = actual[parte] as Registro
  })
  actual[partes.at(-1)!] = valor
}

export default function ModuloGestion({ modulo }: { modulo: ModuloPanel }) {
  const { can, isSuperAdmin } = useAuth()
  const recursos = useMemo(
    () => (modulo.recursos ?? []).filter(
      (recurso) => isSuperAdmin() || can(modeloPermisoRecurso(recurso.endpoint), 'listar'),
    ),
    [modulo.recursos, isSuperAdmin, can],
  )
  const estadoCargando = () => Object.fromEntries(recursos.map((recurso) => [recurso.endpoint, {
    datos: [], cargando: true, error: null,
  }]))
  const [estados, setEstados] = useState<Record<string, EstadoRecurso>>(estadoCargando)
  const [modal, setModal] = useState<ModalCrud | null>(null)
  const [errorAccion, setErrorAccion] = useState<string | null>(null)

  useEffect(() => {
    let activo = true
    void consultarRecursos(recursos).then((resultado) => {
      if (activo) setEstados(resultado)
    })
    return () => { activo = false }
  }, [recursos])

  const cargar = async () => {
    setEstados(estadoCargando())
    setEstados(await consultarRecursos(recursos))
  }

  const eliminar = async (recurso: RecursoModulo, registro: Registro) => {
    if (!recurso.crud || !window.confirm('¿Confirma que desea eliminar este registro?')) return
    const id = valorPorRuta(registro, recurso.crud.idClave ?? 'id')
    const endpoint = resolverEndpoint(
      recurso.crud.eliminarEndpoint ?? `${recurso.endpoint}{id}/`, id,
    )
    setErrorAccion(null)
    try {
      await axios.delete(endpoint)
      await cargar()
    } catch (error) {
      setErrorAccion(mensajeError(error))
    }
  }

  const Icono = modulo.icono

  return (
    <div className="px-4 py-8 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-4 rounded-xl border border-brand-100 bg-white p-6 shadow-sm sm:flex-row sm:items-center">
        <span className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-xl ${modulo.color}`}>
          <Icono size={29} />
        </span>
        <div>
          <h1 className="font-serif text-3xl font-bold text-brand-950">{modulo.titulo}</h1>
          <p className="mt-1 text-slate-600">{modulo.descripcion}</p>
        </div>
        <button
          type="button" onClick={() => void cargar()}
          className="ml-auto flex items-center justify-center gap-2 rounded-xl border border-brand-200 px-4 py-2 font-semibold text-brand-700 hover:bg-brand-50"
        >
          <RefreshCw size={18} /> Actualizar
        </button>
      </header>

      {errorAccion && (
        <div className="mt-5 flex gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">
          <AlertCircle className="shrink-0" size={20} /> {errorAccion}
        </div>
      )}

      <div className="mt-6 space-y-6">
        {recursos.map((recurso) => (
          <TablaRecurso
            key={recurso.endpoint}
            recurso={recurso}
            estado={estados[recurso.endpoint]}
            onCrear={() => setModal({ recurso, registro: null })}
            onEditar={(registro) => setModal({ recurso, registro })}
            onEliminar={(registro) => void eliminar(recurso, registro)}
            puedeCrear={can(modeloPermisoRecurso(recurso.endpoint), 'crear')}
            puedeEditar={can(modeloPermisoRecurso(recurso.endpoint), 'editar')}
            puedeEliminar={can(modeloPermisoRecurso(recurso.endpoint), 'eliminar')}
          />
        ))}
      </div>

      {modal && modal.recurso.crud && (
        <FormularioCrud
          key={`${modal.recurso.endpoint}-${String(modal.registro ? valorPorRuta(modal.registro, modal.recurso.crud.idClave ?? 'id') : 'nuevo')}`}
          recurso={modal.recurso}
          registro={modal.registro}
          onCerrar={() => setModal(null)}
          onGuardado={async () => {
            setModal(null)
            await cargar()
          }}
        />
      )}
    </div>
  )
}

function TablaRecurso({ recurso, estado, onCrear, onEditar, onEliminar, puedeCrear, puedeEditar, puedeEliminar }: {
  recurso: RecursoModulo
  estado?: EstadoRecurso
  onCrear: () => void
  onEditar: (registro: Registro) => void
  onEliminar: (registro: Registro) => void
  puedeCrear: boolean
  puedeEditar: boolean
  puedeEliminar: boolean
}) {
  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-4 border-b border-slate-200 px-6 py-4">
        <h2 className="text-lg font-bold text-slate-900">{recurso.titulo}</h2>
        {recurso.crud && puedeCrear && (
          <button type="button" onClick={onCrear} className="flex items-center gap-2 rounded-lg bg-brand-700 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-800">
            <Plus size={17} /> Nuevo
          </button>
        )}
      </div>
      {!estado || estado.cargando ? (
        <p className="p-8 text-center text-slate-500">Cargando información...</p>
      ) : estado.error ? (
        <div className="m-6 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">
          <AlertCircle className="mt-0.5 shrink-0" size={20} /><p>{estado.error}</p>
        </div>
      ) : estado.datos.length === 0 ? (
        <p className="p-8 text-center text-slate-500">
          {puedeCrear ? 'Todavía no hay registros. Use “Nuevo” para crear el primero.' : 'Todavía no hay registros.'}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50"><tr>
              {recurso.columnas.map((columna) => (
                <th key={columna.clave} className="px-6 py-3 text-left font-semibold text-slate-600">{columna.etiqueta}</th>
              ))}
              {recurso.crud && (puedeEditar || puedeEliminar) && <th className="px-6 py-3 text-right font-semibold text-slate-600">Acciones</th>}
            </tr></thead>
            <tbody className="divide-y divide-slate-100">
              {estado.datos.map((registro, indice) => (
                <tr key={String(valorPorRuta(registro, recurso.crud?.idClave ?? 'id') ?? indice)} className="hover:bg-slate-50">
                  {recurso.columnas.map((columna) => (
                    <td key={columna.clave} className="whitespace-nowrap px-6 py-4 text-slate-700">
                      {valorColumna(recurso, registro, columna.clave)}
                    </td>
                  ))}
                  {recurso.crud && (puedeEditar || puedeEliminar) && (
                    <td className="whitespace-nowrap px-6 py-3 text-right">
                      {puedeEditar && <button type="button" onClick={() => onEditar(registro)} title="Editar" className="rounded-lg p-2 text-brand-700 hover:bg-brand-50"><Pencil size={18} /></button>}
                      {puedeEliminar && <button type="button" onClick={() => onEliminar(registro)} title="Eliminar" className="ml-1 rounded-lg p-2 text-red-600 hover:bg-red-50"><Trash2 size={18} /></button>}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function FormularioCrud({ recurso, registro, onCerrar, onGuardado }: {
  recurso: RecursoModulo
  registro: Registro | null
  onCerrar: () => void
  onGuardado: () => Promise<void>
}) {
  const crud = recurso.crud as ConfiguracionCrud
  const gestionUsuarios = esRecursoUsuarios(recurso)
  const campos = useMemo(
    () => crud.campos.filter((campo) => !(registro && campo.soloCrear)),
    [crud.campos, registro],
  )
  const valoresIniciales = Object.fromEntries(campos.map((campo) => {
    let valor = registro ? valorPorRuta(registro, campo.valorRegistro ?? campo.nombre) : undefined
    if (gestionUsuarios && campo.nombre === 'colegio_id') {
      valor = colegioDeUsuario(registro) || undefined
    }
    if (gestionUsuarios && campo.nombre === 'puesto_id') {
      valor = valorPorRuta(registro ?? {}, 'puesto.id')
        ?? valorPorRuta(registro ?? {}, 'perfil.puesto.id')
        ?? valor
    }
    if (gestionUsuarios && campo.nombre === 'unidad_id' && esDirector(registro ?? {})) {
      valor = undefined
    }
    if (campo.tipo === 'checkbox') return [campo.nombre, Boolean(valor)]
    if (campo.tipo === 'multiselect') {
      const seleccionados = Array.isArray(valor)
        ? valor.map((item) => String(typeof item === 'object' && item !== null ? (item as Registro).id : item))
        : []
      return [campo.nombre, seleccionados]
    }
    return [campo.nombre, mostrarValorFormulario(valor)]
  }))
  const [valores, setValores] = useState<ValoresFormulario>(valoresIniciales)
  const [opcionesRemotas, setOpcionesRemotas] = useState<Record<string, Registro[]>>({})
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [erroresCampo, setErroresCampo] = useState<Record<string, string>>({})
  const [unidadesCargadas, setUnidadesCargadas] = useState<Record<string, boolean>>({})
  const [erroresUnidades, setErroresUnidades] = useState<Record<string, string>>({})

  const rolSeleccionado = useMemo(() => {
    const rolId = String(valores.rol_id ?? '')
    const rol = (opcionesRemotas['/usuarios/roles/'] ?? []).find(
      (item) => String(item.id) === rolId,
    )
    const rolRegistro = registro ? valorPorRuta(registro, 'rol.nombre') : ''
    return String(rol?.nombre ?? rolRegistro ?? '')
  }, [opcionesRemotas, registro, valores.rol_id])

  const puestoSeleccionado = useMemo(() => {
    const puestoId = String(valores.puesto_id ?? '')
    const puesto = (opcionesRemotas['/usuarios/puestos/'] ?? []).find(
      (item) => String(item.id) === puestoId,
    )
    return String(puesto?.nombre ?? puestoDeUsuario(registro))
  }, [opcionesRemotas, registro, valores.puesto_id])

  const esAdmin = gestionUsuarios && normalizarNombre(rolSeleccionado) === 'admin'
  const esDirectorAdmin = esAdmin && normalizarNombre(puestoSeleccionado) === 'director'
  const esSecretariaAdmin = esAdmin && normalizarNombre(puestoSeleccionado) === 'secretaria'
  const esTesoreriaAdmin = esAdmin && normalizarNombre(puestoSeleccionado) === 'tesoreria'
  const esPerfilColegioUnidad = esDirectorAdmin || esSecretariaAdmin || esTesoreriaAdmin
  const colegioSeleccionado = String(valores.colegio_id ?? '')
  const unidadesCargando = (esSecretariaAdmin || esTesoreriaAdmin)
    && Boolean(colegioSeleccionado)
    && !unidadesCargadas[colegioSeleccionado]
  const errorUnidades = colegioSeleccionado ? erroresUnidades[colegioSeleccionado] ?? null : null

  const camposVisibles = useMemo(
    () => campos.filter((campo) => {
      if (campo.perfiles && !campo.perfiles.some(
        (perfil) => normalizarNombre(perfil) === normalizarNombre(rolSeleccionado),
      )) return false
      if (gestionUsuarios && campo.nombre === 'colegio_id') {
        return esPerfilColegioUnidad
      }
      if (gestionUsuarios && campo.nombre === 'unidad_id') return !esDirectorAdmin
      return true
    }),
    [campos, esDirectorAdmin, esPerfilColegioUnidad, gestionUsuarios, rolSeleccionado],
  )

  useEffect(() => {
    const endpoints = [...new Set(campos
      .filter((campo) => !(gestionUsuarios && campo.nombre === 'unidad_id'))
      .map((campo) => campo.opcionesEndpoint)
      .filter(Boolean))] as string[]
    let activo = true
    void Promise.all(endpoints.map(async (endpoint) => {
      const response = await axios.get(endpoint)
      return [endpoint, listaDesdeRespuesta(response.data)] as const
    })).then((resultados) => {
      if (activo) {
        setOpcionesRemotas((actuales) => ({ ...actuales, ...Object.fromEntries(resultados) }))
      }
    }).catch(() => {
      if (activo) setError('No se pudieron cargar las opciones del formulario.')
    })
    return () => { activo = false }
  }, [campos, gestionUsuarios])

  useEffect(() => {
    if (!gestionUsuarios) return
    const endpoint = '/institucion/unidades-educativas/'
    if (esDirectorAdmin || ((esSecretariaAdmin || esTesoreriaAdmin) && !colegioSeleccionado)) {
      return
    }

    const controlador = new AbortController()
    let activo = true
    void axios.get(endpoint, {
      ...((esSecretariaAdmin || esTesoreriaAdmin) ? { params: { colegio: colegioSeleccionado } } : {}),
      signal: controlador.signal,
    }).then((response) => {
      if (!activo) return
      const unidades = listaDesdeRespuesta(response.data)
      setOpcionesRemotas((actuales) => ({ ...actuales, [endpoint]: unidades }))
      if (esSecretariaAdmin || esTesoreriaAdmin) {
        setUnidadesCargadas((actuales) => ({ ...actuales, [colegioSeleccionado]: true }))
        setErroresUnidades((actuales) => {
          const siguientes = { ...actuales }
          delete siguientes[colegioSeleccionado]
          return siguientes
        })
        setValores((actuales) => (
          actuales.unidad_id && !unidades.some((unidad) => String(unidad.id) === actuales.unidad_id)
            ? { ...actuales, unidad_id: '' }
            : actuales
        ))
      }
    }).catch(() => {
      if (!activo) return
      if (esSecretariaAdmin || esTesoreriaAdmin) {
        setUnidadesCargadas((actuales) => ({ ...actuales, [colegioSeleccionado]: true }))
        setErroresUnidades((actuales) => ({
          ...actuales,
          [colegioSeleccionado]: 'No se pudieron cargar las unidades educativas.',
        }))
      } else {
        setError('No se pudieron cargar las opciones del formulario.')
      }
    })
    return () => {
      activo = false
      controlador.abort()
    }
  }, [colegioSeleccionado, esDirectorAdmin, esSecretariaAdmin, esTesoreriaAdmin, gestionUsuarios, rolSeleccionado])

  const cambiarCampo = (nombre: string, valor: string | boolean | string[]) => {
    setError(null)
    setErroresCampo((actuales) => {
      const siguientes = { ...actuales }
      delete siguientes[nombre]
      if (nombre === 'rol_id') {
        delete siguientes.puesto_id
        delete siguientes.colegio_id
        delete siguientes.unidad_id
      }
      if (nombre === 'puesto_id') {
        delete siguientes.colegio_id
        delete siguientes.unidad_id
      }
      if (nombre === 'colegio_id') delete siguientes.unidad_id
      return siguientes
    })

    if (recurso.endpoint === '/academico/grados/' && nombre === 'nivel_educativo') {
      setValores((actuales) => ({ ...actuales, nivel_educativo: valor, numero: '' }))
      return
    }
    if (recurso.endpoint === '/academico/cursos/' && nombre === 'paralelo_id') {
      setValores((actuales) => ({ ...actuales, paralelo_id: valor, tutor: '' }))
      return
    }
    if (gestionUsuarios && nombre === 'rol_id') {
      const nuevoRol = (opcionesRemotas['/usuarios/roles/'] ?? [])
        .find((rol) => String(rol.id) === String(valor))?.nombre ?? ''
      if (normalizarNombre(nuevoRol) !== normalizarNombre(rolSeleccionado)) {
        setValores((actuales) => ({
          ...actuales,
          rol_id: valor,
          puesto_id: '',
          colegio_id: '',
          unidad_id: '',
        }))
        setOpcionesRemotas((actuales) => ({
          ...actuales,
          '/institucion/unidades-educativas/': [],
        }))
        setUnidadesCargadas({})
        setErroresUnidades({})
        return
      }
    }

    if (gestionUsuarios && nombre === 'puesto_id') {
      const anterior = normalizarNombre(puestoSeleccionado)
      const siguiente = normalizarNombre((opcionesRemotas['/usuarios/puestos/'] ?? [])
        .find((puesto) => String(puesto.id) === String(valor))?.nombre)
      if (anterior === siguiente) {
        setValores((actuales) => ({ ...actuales, puesto_id: valor }))
        return
      }
      const anteriorInstitucional = ['director', 'secretaria', 'tesoreria'].includes(anterior)
      const puestoInstitucional = ['director', 'secretaria', 'tesoreria'].includes(siguiente)
      setValores((actuales) => ({
        ...actuales,
        puesto_id: valor,
        unidad_id: '',
        ...(!puestoInstitucional && anteriorInstitucional ? { colegio_id: '' } : {}),
      }))
      if (anterior !== siguiente || !puestoInstitucional) {
        setOpcionesRemotas((actuales) => ({
          ...actuales,
          '/institucion/unidades-educativas/': [],
        }))
        setUnidadesCargadas({})
        setErroresUnidades({})
      }
      return
    }

    if (gestionUsuarios && nombre === 'colegio_id') {
      if (String(valor) === colegioSeleccionado) {
        setValores((actuales) => ({ ...actuales, colegio_id: valor }))
        return
      }
      setValores((actuales) => ({ ...actuales, colegio_id: valor, unidad_id: '' }))
      setOpcionesRemotas((actuales) => ({
        ...actuales,
        '/institucion/unidades-educativas/': [],
      }))
      setUnidadesCargadas({})
      setErroresUnidades({})
      return
    }
    setValores((actuales) => ({ ...actuales, [nombre]: valor }))
  }

  const guardar = async (event: React.FormEvent) => {
    event.preventDefault()
    setError(null)
    setErroresCampo({})
    if (gestionUsuarios && esAdmin) {
      const faltantes: Record<string, string> = {}
      if (!String(valores.rol_id ?? '') && !registro) faltantes.rol_id = 'Seleccione un rol.'
      if (!String(valores.puesto_id ?? '')) faltantes.puesto_id = 'Seleccione un puesto administrativo.'
      if (esPerfilColegioUnidad) {
        if (!colegioSeleccionado) faltantes.colegio_id = 'Seleccione un colegio.'
        if (esSecretariaAdmin && !String(valores.unidad_id ?? '')) {
          faltantes.unidad_id = 'Seleccione una unidad educativa o módulo.'
        }
      }
      if (Object.keys(faltantes).length > 0) {
        setErroresCampo(faltantes)
        return
      }
    }
    setGuardando(true)
    const payload: Registro = {}
    camposVisibles.forEach((campo) => {
      const valor = valores[campo.nombre]
      let convertido: unknown = valor
      if (campo.tipo === 'checkbox') convertido = Boolean(valor)
      else if (campo.tipo === 'number') convertido = valor === '' ? null : Number(valor)
      else if (campo.tipo === 'date') convertido = valor === '' ? null : valor
      else if (campo.tipo === 'multiselect') convertido = (valor as string[]).map(Number)
      if (campo.tipo === 'select' && (valor === 'true' || valor === 'false')) {
        convertido = valor === 'true'
      } else if (campo.tipo === 'select' && campo.opcionesEndpoint) {
        convertido = valor === '' ? null : Number(valor)
      }
      asignarPorRuta(payload, campo.nombre, convertido)
    })
    if (gestionUsuarios && esDirectorAdmin) {
      payload.colegio_id = Number(colegioSeleccionado)
      payload.unidad_id = null
    }
    if (gestionUsuarios && esTesoreriaAdmin) {
      payload.colegio_id = Number(colegioSeleccionado)
      payload.unidad_id = valores.unidad_id ? Number(valores.unidad_id) : null
    }

    try {
      if (registro) {
        const id = valorPorRuta(registro, crud.idClave ?? 'id')
        const endpoint = resolverEndpoint(crud.editarEndpoint ?? `${recurso.endpoint}{id}/`, id)
        if ((crud.metodoEditar ?? 'patch') === 'put') await axios.put(endpoint, payload)
        else await axios.patch(endpoint, payload)
      } else {
        await axios.post(crud.crearEndpoint ?? recurso.endpoint, payload)
      }
      await onGuardado()
    } catch (err) {
      setErroresCampo(erroresPorCampo(err))
      setError(mensajeError(err))
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/55 p-4" role="dialog" aria-modal="true" aria-labelledby="crud-dialog-title">
      <div className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
        <div className="sticky top-0 flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4">
          <div><h2 id="crud-dialog-title" className="font-serif text-xl font-bold text-brand-950">{registro ? 'Editar' : 'Nuevo'} · {recurso.titulo}</h2></div>
          <button type="button" aria-label="Cerrar formulario" onClick={onCerrar} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X size={21} /></button>
        </div>
        <form onSubmit={guardar} className="p-6">
          {error && <div className="mb-5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}
          <div className="grid gap-4 sm:grid-cols-2">
            {camposVisibles.map((campoOriginal) => {
              const campo: CampoCrud = gestionUsuarios && esTesoreriaAdmin && campoOriginal.nombre === 'unidad_id'
                ? { ...campoOriginal, requerido: false }
                : recurso.endpoint === '/academico/grados/' && campoOriginal.nombre === 'numero' && valores.nivel_educativo === 'INI'
                ? { ...campoOriginal, etiqueta: 'Etapa de inicial', tipo: 'select', opciones: [
                  { valor: '1', etiqueta: 'Prekínder' }, { valor: '2', etiqueta: 'Kínder' },
                  ...(['3', '4', '5', '6'].includes(String(valores.numero)) ? [{ valor: String(valores.numero), etiqueta: `Registro existente (${valores.numero})` }] : []),
                ] }
                : campoOriginal
              const paralelo = (opcionesRemotas['/academico/paralelos/'] ?? []).find((item) => String(item.id) === String(valores.paralelo_id))
              const unidadCurso = valorPorRuta(paralelo ?? {}, 'grado.unidad_educativa')
              const opcionesCampo = recurso.endpoint === '/academico/cursos/' && campo.nombre === 'tutor'
                ? { ...opcionesRemotas, '/personal/profesores/': (opcionesRemotas['/personal/profesores/'] ?? []).filter((item) => unidadCurso != null && String(item.unidad_id ?? item.unidad) === String(unidadCurso)) }
                : opcionesRemotas
              return (
              <CampoFormulario
                key={campo.nombre} campo={campo} valor={valores[campo.nombre]}
                opcionesRemotas={opcionesCampo}
                errorText={erroresCampo[campo.nombre]}
                helpText={
                  campo.nombre === 'colegio_id' && esDirectorAdmin
                    ? 'El Director tendrá acceso a todas las unidades educativas del colegio.'
                    : campo.nombre === 'colegio_id' && esSecretariaAdmin
                      ? 'La Secretaría administrará solamente la unidad educativa seleccionada.'
                      : campo.nombre === 'colegio_id' && esTesoreriaAdmin
                        ? 'El alcance dependerá de la unidad: seleccione una unidad o Todas las unidades para todo el colegio.'
                      : undefined
                }
                busy={campo.nombre === 'unidad_id' && unidadesCargando}
                disabled={campo.nombre === 'unidad_id' && (esSecretariaAdmin || esTesoreriaAdmin)
                  ? !colegioSeleccionado || unidadesCargando
                  : false}
                emptyText={campo.nombre === 'unidad_id' && esTesoreriaAdmin
                  ? 'Todas las unidades (alcance colegio)'
                  : campo.nombre === 'unidad_id' && esSecretariaAdmin
                    && !unidadesCargando && !errorUnidades
                    && opcionesRemotas['/institucion/unidades-educativas/']?.length === 0
                    ? 'El colegio seleccionado no tiene unidades educativas registradas'
                    : undefined}
                loadError={campo.nombre === 'unidad_id' ? errorUnidades : null}
                onChange={(valor) => cambiarCampo(campo.nombre, valor)}
              />
              )
            })}
          </div>
          <div className="mt-7 flex justify-end gap-3">
            <button type="button" onClick={onCerrar} className="rounded-xl border border-slate-300 px-5 py-2.5 font-semibold text-slate-700 hover:bg-slate-50">Cancelar</button>
            <button type="submit" disabled={guardando} className="rounded-xl bg-brand-700 px-5 py-2.5 font-semibold text-white hover:bg-brand-800 disabled:opacity-60">
              {guardando ? 'Guardando...' : 'Guardar'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function CampoFormulario({ campo, valor, opcionesRemotas, onChange, errorText, helpText, busy, disabled, emptyText, loadError }: {
  campo: CampoCrud
  valor: string | boolean | string[]
  opcionesRemotas: Record<string, Registro[]>
  onChange: (valor: string | boolean | string[]) => void
  errorText?: string
  helpText?: string
  busy?: boolean
  disabled?: boolean
  emptyText?: string
  loadError?: string | null
}) {
  const clase = 'mt-2 w-full rounded-lg border border-slate-300 px-3 py-2.5 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100'
  const descripcionId = `${campo.nombre}-description`
  const errorId = `${campo.nombre}-error`
  const describedBy = [
    helpText || emptyText || loadError ? descripcionId : '',
    errorText ? errorId : '',
  ].filter(Boolean).join(' ') || undefined
  if (campo.tipo === 'checkbox') {
    return <div className="self-end">
      <label htmlFor={campo.nombre} className="flex items-center gap-3 rounded-lg border border-slate-200 px-4 py-3 text-sm font-medium text-slate-700">
        <input id={campo.nombre} type="checkbox" checked={Boolean(valor)} onChange={(event) => onChange(event.target.checked)} /> {campo.etiqueta}
      </label>
      {errorText && <p id={errorId} role="alert" className="mt-1 text-sm text-red-700">{errorText}</p>}
    </div>
  }

  const opciones = campo.opcionesEndpoint
    ? (opcionesRemotas[campo.opcionesEndpoint] ?? []).map((item) => ({
        valor: String(valorPorRuta(item, campo.opcionValor ?? 'id') ?? ''),
        etiqueta: (campo.opcionEtiquetas ?? ['nombre'])
          .map((ruta) => mostrarValor(valorPorRuta(item, ruta))).filter((texto) => texto !== '—').join(' · '),
      }))
    : campo.opciones

  return <div className={`text-sm font-medium text-slate-700 ${campo.tipo === 'textarea' ? 'sm:col-span-2' : ''}`}>
    <label htmlFor={campo.nombre}>
      {campo.etiqueta}{campo.requerido ? ' *' : ''}
    </label>
    {campo.tipo === 'select' ? (
      <select
        id={campo.nombre}
        value={String(valor ?? '')}
        required={campo.requerido}
        disabled={disabled}
        aria-busy={busy}
        aria-invalid={Boolean(errorText)}
        aria-describedby={describedBy}
        onChange={(event) => onChange(event.target.value)}
        className={clase}
      >
        <option value="">
          {busy ? 'Cargando unidades educativas...' : emptyText ?? 'Seleccione una opción'}
        </option>
        {opciones?.map((opcion) => <option key={opcion.valor} value={opcion.valor}>{opcion.etiqueta}</option>)}
      </select>
    ) : campo.tipo === 'multiselect' ? (
      <select
        id={campo.nombre}
        multiple
        value={Array.isArray(valor) ? valor : []}
        required={campo.requerido}
        aria-invalid={Boolean(errorText)}
        aria-describedby={describedBy}
        onChange={(event) => onChange(Array.from(event.target.selectedOptions, (option) => option.value))}
        className={`${clase} min-h-32`}
      >
        {opciones?.map((opcion) => <option key={opcion.valor} value={opcion.valor}>{opcion.etiqueta}</option>)}
      </select>
    ) : campo.tipo === 'textarea' ? (
      <textarea id={campo.nombre} value={String(valor ?? '')} required={campo.requerido} aria-invalid={Boolean(errorText)} aria-describedby={describedBy} onChange={(event) => onChange(event.target.value)} rows={3} className={clase} />
    ) : (
      <input id={campo.nombre} type={campo.tipo ?? 'text'} value={String(valor ?? '')} required={campo.requerido} aria-invalid={Boolean(errorText)} aria-describedby={describedBy} onChange={(event) => onChange(event.target.value)} className={clase} />
    )}
    {(helpText || emptyText || loadError) && (
      <p id={descripcionId} className={`mt-1 text-sm ${loadError ? 'text-red-700' : 'text-slate-600'}`}>
        {loadError ?? emptyText ?? helpText}
      </p>
    )}
    {errorText && <p id={errorId} role="alert" className="mt-1 text-sm text-red-700">{errorText}</p>}
  </div>
}

function mostrarValorFormulario(valor: unknown): string {
  if (valor === null || valor === undefined) return ''
  return String(valor)
}
