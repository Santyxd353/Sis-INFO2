import axios from 'axios'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { Building2, DoorOpen, Pencil, Plus, Power, RefreshCw } from 'lucide-react'
import { useAuth } from '../../app/contexts/AuthContext'
import { cargarCatalogoPaginado } from '../../api/catalogosPaginados'
import {
  actualizarAula, actualizarModulo, crearAula, crearModulo, desactivarAula, desactivarModulo,
  listarAulas, listarModulos, type AulaFisica, type AulaPayload, type FiltrosInfraestructura,
  type ModuloFisico, type ModuloPayload, type TipoAula,
} from '../../api/infraestructura'
import { resolveVisualProfile } from '../../app/navigation/navigationConfig'
import type { UnidadEducativa } from '../../app/modelos/Institucion'
import { errorFields, useOperation } from '../workflows/useWorkflow'
import { Errors, Field, Pages, Status } from '../workflows/WorkflowUI'
import '../workflows/workflows.css'

const tipos: Array<{ value: TipoAula; label: string }> = [
  { value: 'AUL', label: 'Aula regular' }, { value: 'LAB', label: 'Laboratorio' },
  { value: 'TAL', label: 'Taller' }, { value: 'AUD', label: 'Auditorio' },
  { value: 'COM', label: 'Sala de computación' }, { value: 'GIM', label: 'Gimnasio' }, { value: 'BIB', label: 'Biblioteca' },
]
const tipoLabel = (value: string) => tipos.find((tipo) => tipo.value === value)?.label ?? value

function useInfraPage<T>(loader: (filters: FiltrosInfraestructura, signal?: AbortSignal) => Promise<{ data: { results: T[]; count: number } }>, filters: FiltrosInfraestructura, revision: number) {
  const key = JSON.stringify(filters)
  const [state, setState] = useState<{ key: string; items: T[]; count: number; error: string; loading: boolean }>({ key: '', items: [], count: 0, error: '', loading: true })
  useEffect(() => {
    const controller = new AbortController()
    void loader(JSON.parse(key) as FiltrosInfraestructura, controller.signal)
      .then(({ data }) => { if (!controller.signal.aborted) setState({ key, items: data.results, count: data.count, error: '', loading: false }) })
      .catch((error: unknown) => {
        if (!controller.signal.aborted && !axios.isCancel(error)) setState({ key, items: [], count: 0, error: Object.values(errorFields(error)).join(' '), loading: false })
      })
    return () => controller.abort()
  }, [key, loader, revision])
  return state.key === key ? state : { items: [], count: 0, error: '', loading: true }
}

export default function InfraestructuraFisicaPage() {
  const { user, can } = useAuth()
  const profile = resolveVisualProfile(user)
  const isSupport = profile === 'SUPERADMIN'
  const canListModule = can('modulo', 'listar')
  const canListRoom = can('aula', 'listar')
  const canCreateModule = !isSupport && can('modulo', 'crear')
  const canEditModule = !isSupport && can('modulo', 'editar')
  const canDeactivateModule = !isSupport && can('modulo', 'desactivar')
  const canCreateRoom = !isSupport && can('aula', 'crear')
  const canEditRoom = !isSupport && can('aula', 'editar')
  const canDeactivateRoom = !isSupport && can('aula', 'desactivar')
  const fixedUnit = profile === 'SECRETARIA' ? user?.alcance?.unidad_id ?? user?.unidad?.id ?? null : null
  const [units, setUnits] = useState<UnidadEducativa[]>([])
  const [unitsError, setUnitsError] = useState('')
  const [unit, setUnit] = useState<number | null>(fixedUnit)
  const [moduleName, setModuleName] = useState(''), [moduleState, setModuleState] = useState('ACTIVO'), [modulePage, setModulePage] = useState(1)
  const [roomName, setRoomName] = useState(''), [roomState, setRoomState] = useState('ACTIVO'), [roomType, setRoomType] = useState(''), [roomModule, setRoomModule] = useState<number | null>(null), [roomPage, setRoomPage] = useState(1)
  const [revision, setRevision] = useState(0)
  const [moduleForm, setModuleForm] = useState<ModuloFisico | true | null>(null)
  const [roomForm, setRoomForm] = useState<AulaFisica | true | null>(null)
  const [confirm, setConfirm] = useState<{ kind: 'module' | 'room'; row: ModuloFisico | AulaFisica } | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    void cargarCatalogoPaginado<UnidadEducativa>('/institucion/unidades-educativas/', {}, controller.signal)
      .then((rows) => { setUnits(rows); if (!fixedUnit && rows.length === 1) setUnit(rows[0].id) })
      .catch((error: unknown) => { if (!controller.signal.aborted) setUnitsError(Object.values(errorFields(error)).join(' ')) })
    return () => controller.abort()
  }, [fixedUnit])

  const changeUnit = (nextUnit: number | null) => {
    setUnit(nextUnit)
    setRoomModule(null)
    setModulePage(1)
    setRoomPage(1)
  }

  const moduleFilters = useMemo<FiltrosInfraestructura>(() => ({ unidad_educativa: unit ?? undefined, nombre: moduleName.trim() || undefined, estado: moduleState as FiltrosInfraestructura['estado'] || undefined, page: modulePage, page_size: 20 }), [unit, moduleName, moduleState, modulePage])
  const roomFilters = useMemo<FiltrosInfraestructura>(() => ({ unidad_educativa: unit ?? undefined, modulo: roomModule ?? undefined, nombre: roomName.trim() || undefined, estado: roomState as FiltrosInfraestructura['estado'] || undefined, tipo: roomType as TipoAula || undefined, page: roomPage, page_size: 20 }), [unit, roomModule, roomName, roomState, roomType, roomPage])
  const modules = useInfraPage(listarModulos, moduleFilters, revision)
  const rooms = useInfraPage(listarAulas, roomFilters, revision)
  const activeModules = useMemo(() => modules.items.filter((row) => row.estado === 'ACTIVO'), [modules.items])
  const selectedUnitName = units.find((row) => row.id === unit)?.nombre ?? 'Unidad educativa'
  const retry = () => setRevision((value) => value + 1)

  if (!canListModule && !canListRoom) return <main className="wf-page"><section className="wf-card"><h1>Infraestructura física</h1><p className="mt-3">No tiene permisos para realizar esta acción.</p></section></main>

  return <main className="wf-page space-y-7">
    <header className="flex flex-wrap items-start justify-between gap-4"><div><h1>Infraestructura física</h1><p className="mt-2 text-slate-600">Gestione bloques físicos, edificios, sectores y aulas por unidad educativa.</p></div>{isSupport && <p className="wf-warning">Consulta global de soporte. No tiene edición implícita.</p>}</header>
    {unitsError && <div role="alert" className="wf-error">No fue posible cargar las unidades educativas. {unitsError} <button className="wf-secondary ml-2" onClick={() => window.location.reload()}>Reintentar</button></div>}
    <section className="wf-card space-y-4" aria-label="Contexto institucional"><Field label="Unidad educativa"><select className="wf-input max-w-xl" value={unit ?? ''} disabled={Boolean(fixedUnit)} onChange={(event) => changeUnit(event.target.value ? Number(event.target.value) : null)}><option value="">Seleccione una unidad</option>{units.map((row) => <option key={row.id} value={row.id}>{row.nombre}</option>)}</select></Field>{fixedUnit && <p className="text-sm text-slate-600">Unidad asignada: {selectedUnitName}</p>}</section>
    <InfraSection title="Módulos o bloques físicos" icon={<Building2 size={22} />} canCreate={canCreateModule} createLabel="Nuevo módulo físico" onCreate={() => setModuleForm(true)}>
      <div className="grid gap-3 md:grid-cols-3"><FilterInput label="Buscar por nombre" value={moduleName} onChange={(value) => { setModuleName(value); setModulePage(1) }} /><Field label="Estado"><select className="wf-input" value={moduleState} onChange={(event) => { setModuleState(event.target.value); setModulePage(1) }}><option value="">Todos</option><option value="ACTIVO">Activo</option><option value="INACTIVO">Inactivo</option></select></Field></div>
      <Status loading={modules.loading} error={modules.error} empty={!modules.items.length} />
      {modules.error && <button className="wf-secondary" onClick={retry}><RefreshCw size={16} />Reintentar</button>}
      {!modules.loading && !modules.error && modules.items.length > 0 && <div className="overflow-x-auto"><table className="wf-table" aria-label="Bloques físicos">
        <thead><tr><th>Unidad</th><th>Bloque</th><th>Estado</th><th>Creado</th><th>Acciones</th></tr></thead>
        <tbody>{modules.items.map((row) => <tr key={row.id}>
          <td>{units.find((item) => item.id === row.unidad_educativa)?.nombre ?? selectedUnitName}</td><td>{row.nombre}</td><td>{row.estado === 'ACTIVO' ? 'Activo' : 'Inactivo'}</td><td className="whitespace-nowrap">{formatDate(row.created_at)}</td>
          <td><div className="flex flex-wrap gap-2">
            {canEditModule && <button className="wf-secondary" onClick={() => setModuleForm(row)}><Pencil size={15} />Editar</button>}
            {canDeactivateModule && row.estado === 'ACTIVO' && <button className="wf-secondary text-red-800" onClick={() => setConfirm({ kind: 'module', row })}><Power size={15} />Desactivar</button>}
          </div></td>
        </tr>)}</tbody>
      </table></div>}
      <Pages page={modulePage} count={modules.count} onChange={setModulePage} />
    </InfraSection>
    <InfraSection title="Aulas" icon={<DoorOpen size={22} />} canCreate={canCreateRoom} createLabel="Nueva aula" onCreate={() => setRoomForm(true)}>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4"><FilterInput label="Buscar por nombre" value={roomName} onChange={(value) => { setRoomName(value); setRoomPage(1) }} /><Field label="Módulo físico"><select className="wf-input" value={roomModule ?? ''} onChange={(event) => { setRoomModule(event.target.value ? Number(event.target.value) : null); setRoomPage(1) }}><option value="">Todos</option>{activeModules.map((row) => <option key={row.id} value={row.id}>{row.nombre}</option>)}</select></Field><Field label="Tipo"><select className="wf-input" value={roomType} onChange={(event) => { setRoomType(event.target.value); setRoomPage(1) }}><option value="">Todos</option>{tipos.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}</select></Field><Field label="Estado"><select className="wf-input" value={roomState} onChange={(event) => { setRoomState(event.target.value); setRoomPage(1) }}><option value="">Todos</option><option value="ACTIVO">Activo</option><option value="INACTIVO">Inactivo</option></select></Field></div>
      <Status loading={rooms.loading} error={rooms.error} empty={!rooms.items.length} />
      {rooms.error && <button className="wf-secondary" onClick={retry}><RefreshCw size={16} />Reintentar</button>}
      {!rooms.loading && !rooms.error && rooms.items.length > 0 && <div className="overflow-x-auto"><table className="wf-table" aria-label="Aulas">
        <thead><tr><th>Aula</th><th>Tipo</th><th>Capacidad</th><th>Piso</th><th>Estado</th><th>Acciones</th></tr></thead>
        <tbody>{rooms.items.map((row) => <tr key={row.id}>
          <td>{row.nombre}</td><td>{tipoLabel(row.tipo)}</td><td>{row.capacidad}</td><td>{row.piso}</td><td>{row.estado ? 'Activo' : 'Inactivo'}</td>
          <td><div className="flex flex-wrap gap-2">
            {canEditRoom && <button className="wf-secondary" onClick={() => setRoomForm(row)}><Pencil size={15} />Editar</button>}
            {canDeactivateRoom && row.estado && <button className="wf-secondary text-red-800" onClick={() => setConfirm({ kind: 'room', row })}><Power size={15} />Desactivar</button>}
          </div></td>
        </tr>)}</tbody>
      </table></div>}
      <Pages page={roomPage} count={rooms.count} onChange={setRoomPage} />
    </InfraSection>
    {moduleForm && <ModuloDialog initial={moduleForm === true ? undefined : moduleForm} unit={unit} onDone={() => { setModuleForm(null); retry() }} onCancel={() => setModuleForm(null)} />}
    {roomForm && <AulaDialog initial={roomForm === true ? undefined : roomForm} unit={unit} modules={activeModules} onDone={() => { setRoomForm(null); retry() }} onCancel={() => setRoomForm(null)} />}
    {confirm && <DeactivateDialog kind={confirm.kind} row={confirm.row} onCancel={() => setConfirm(null)} onDone={() => { setConfirm(null); retry() }} />}
  </main>
}

function InfraSection({ title, icon, canCreate, createLabel, onCreate, children }: { title: string; icon: ReactNode; canCreate: boolean; createLabel: string; onCreate: () => void; children: ReactNode }) { return <section className="wf-card space-y-5"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="flex items-center gap-2">{icon}{title}</h2>{canCreate && <button className="wf-primary" onClick={onCreate}><Plus size={17} />{createLabel}</button>}</div>{children}</section> }
function FilterInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) { return <Field label={label}><input className="wf-input" value={value} onChange={(event) => onChange(event.target.value)} /></Field> }
function formatDate(value: string | null) { return value ? new Date(value).toLocaleDateString() : '—' }

function ModuloDialog({ initial, unit, onDone, onCancel }: { initial?: ModuloFisico; unit: number | null; onDone: () => void; onCancel: () => void }) {
  const [name, setName] = useState(initial?.nombre ?? ''), [rooms, setRooms] = useState(String(initial?.cantidad_aulas ?? 1)), [floors, setFloors] = useState(String(initial?.pisos ?? 1)), [description, setDescription] = useState(initial?.descripcion ?? ''), [local, setLocal] = useState<Record<string, string>>({})
  const op = useOperation()
  const save = () => { const normalized = name.trim(); const count = Number(rooms); const floorsCount = Number(floors); const errors: Record<string, string> = {}; if (!unit) errors.unidad_educativa = 'Seleccione una unidad educativa.'; if (!normalized) errors.nombre = 'El nombre es obligatorio.'; if (!Number.isInteger(count) || count < 1) errors.cantidad_aulas = 'Ingrese una cantidad válida.'; if (!Number.isInteger(floorsCount) || floorsCount < 1) errors.pisos = 'Ingrese un piso válido.'; setLocal(errors); if (Object.keys(errors).length || !unit) return; const payload: ModuloPayload = { unidad_educativa: unit, nombre: normalized, cantidad_aulas: count, pisos: floorsCount, descripcion: description.trim() || undefined }; void op.run(() => initial ? actualizarModulo(initial.id, payload) : crearModulo(payload), onDone) }
  return <Dialog title={initial ? 'Editar módulo físico' : 'Nuevo módulo físico'}><Errors errors={{ ...op.errors, ...local }} /><Field label="Nombre *" error={local.nombre}><input className="wf-input" value={name} onChange={(event) => setName(event.target.value)} /></Field><div className="grid gap-4 md:grid-cols-2"><Field label="Cantidad de aulas *" error={local.cantidad_aulas}><input className="wf-input" min="1" type="number" value={rooms} onChange={(event) => setRooms(event.target.value)} /></Field><Field label="Pisos *" error={local.pisos}><input className="wf-input" min="1" type="number" value={floors} onChange={(event) => setFloors(event.target.value)} /></Field></div><Field label="Descripción"><textarea className="wf-input" value={description} onChange={(event) => setDescription(event.target.value)} /></Field><DialogActions busy={op.busy} onCancel={onCancel} onSave={save} /></Dialog>
}

function AulaDialog({ initial, unit, modules, onDone, onCancel }: { initial?: AulaFisica; unit: number | null; modules: ModuloFisico[]; onDone: () => void; onCancel: () => void }) {
  const [module, setModule] = useState<number | null>(initial?.modulo ?? null), [name, setName] = useState(initial?.nombre ?? ''), [capacity, setCapacity] = useState(String(initial?.capacidad ?? '')), [type, setType] = useState<TipoAula>(initial?.tipo ?? 'AUL'), [floor, setFloor] = useState(String(initial?.piso ?? 1)), [equipment, setEquipment] = useState(initial?.equipamiento ?? ''), [local, setLocal] = useState<Record<string, string>>({})
  const op = useOperation()
  const save = () => { const normalized = name.trim(); const value = Number(capacity); const floorValue = Number(floor); const errors: Record<string, string> = {}; if (!unit) errors.unidad_educativa_id = 'Seleccione una unidad educativa.'; if (!module) errors.modulo = 'Seleccione un módulo físico activo.'; if (!normalized) errors.nombre = 'El nombre es obligatorio.'; if (!Number.isInteger(value) || value < 1) errors.capacidad = 'La capacidad debe ser un entero positivo.'; if (!Number.isInteger(floorValue) || floorValue < 1) errors.piso = 'El piso debe ser válido.'; setLocal(errors); if (Object.keys(errors).length || !module) return; const payload: AulaPayload = { modulo: module, nombre: normalized, capacidad: value, tipo: type, piso: floorValue, equipamiento: equipment.trim() || undefined }; void op.run(() => initial ? actualizarAula(initial.id, payload) : crearAula(payload), onDone) }
  return <Dialog title={initial ? 'Editar aula' : 'Nueva aula'}><Errors errors={{ ...op.errors, ...local }} /><Field label="Módulo físico *" error={local.modulo}><select className="wf-input" value={module ?? ''} onChange={(event) => setModule(event.target.value ? Number(event.target.value) : null)}><option value="">Seleccione un módulo</option>{modules.map((row) => <option key={row.id} value={row.id}>{row.nombre}</option>)}</select></Field><Field label="Nombre *" error={local.nombre}><input className="wf-input" value={name} onChange={(event) => setName(event.target.value)} /></Field><div className="grid gap-4 md:grid-cols-3"><Field label="Capacidad *" error={local.capacidad}><input className="wf-input" min="1" type="number" value={capacity} onChange={(event) => setCapacity(event.target.value)} /></Field><Field label="Tipo"><select className="wf-input" value={type} onChange={(event) => setType(event.target.value as TipoAula)}>{tipos.map((row) => <option key={row.value} value={row.value}>{row.label}</option>)}</select></Field><Field label="Piso *" error={local.piso}><input className="wf-input" min="1" type="number" value={floor} onChange={(event) => setFloor(event.target.value)} /></Field></div><Field label="Equipamiento"><textarea className="wf-input" value={equipment} onChange={(event) => setEquipment(event.target.value)} /></Field><DialogActions busy={op.busy} onCancel={onCancel} onSave={save} /></Dialog>
}

function DeactivateDialog({ kind, row, onCancel, onDone }: { kind: 'module' | 'room'; row: ModuloFisico | AulaFisica; onCancel: () => void; onDone: () => void }) { const op = useOperation(); return <Dialog title={`Desactivar ${kind === 'module' ? 'módulo físico' : 'aula'}`}><p>¿Confirma la desactivación de <strong>{row.nombre}</strong>? El registro no será eliminado.</p><Errors errors={op.errors} /><DialogActions busy={op.busy} onCancel={onCancel} onSave={() => void op.run(() => kind === 'module' ? desactivarModulo(row.id) : desactivarAula(row.id), onDone)} saveLabel="Confirmar desactivación" /></Dialog> }
function Dialog({ title, children }: { title: string; children: ReactNode }) { return <div className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-slate-950/50 p-4"><section role="dialog" aria-modal="true" aria-label={title} className="wf-card w-full max-w-xl space-y-4"><h2>{title}</h2>{children}</section></div> }
function DialogActions({ busy, onCancel, onSave, saveLabel = 'Guardar' }: { busy: boolean; onCancel: () => void; onSave: () => void; saveLabel?: string }) { return <div className="flex flex-wrap gap-3"><button className="wf-primary" disabled={busy} onClick={onSave}>{busy ? 'Guardando...' : saveLabel}</button><button className="wf-secondary" disabled={busy} onClick={onCancel}>Cancelar</button></div> }
