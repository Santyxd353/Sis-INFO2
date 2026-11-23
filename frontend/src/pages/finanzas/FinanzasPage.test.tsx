import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import FinanzasPage from './FinanzasPage'
import * as api from '../../api/finanzas'
import { cargarCatalogoPaginado } from '../../api/catalogosPaginados'

let permissions = new Set<string>()
vi.mock('../../app/contexts/AuthContext', () => ({ useAuth: () => ({ user: { alcance: { tipo: 'UNIDAD', colegio_id: 1, unidad_id: 2, unidad_nombre: 'Primaria' } }, can: (modelo: string, accion: string) => permissions.has(`${modelo}:${accion}`) }) }))
vi.mock('../../api/catalogosInstitucionales', () => ({ listarUnidadesCatalogo: vi.fn() }))
vi.mock('../../api/catalogosPaginados', () => ({ cargarCatalogoPaginado: vi.fn() }))
vi.mock('../../api/finanzas', async (original) => ({
  ...(await original<typeof import('../../api/finanzas')>()),
  listarPlanes: vi.fn(), crearPlan: vi.fn(), listarBecas: vi.fn(), listarAsignacionesBeca: vi.fn(), listarObligaciones: vi.fn(),
  listarPagos: vi.fn(), registrarPago: vi.fn(), buscarEstudiantes: vi.fn(), obtenerMorosidad: vi.fn(), simularTributos: vi.fn(),
  listarSolicitudesQR: vi.fn(), obtenerConciliacionQR: vi.fn(), resolverSolicitudQR: vi.fn(), simularCobroQR: vi.fn(),
  listarRecordatoriosPago: vi.fn(), enviarRecordatoriosPago: vi.fn(),
}))

const pagina = <T,>(results: T[]) => ({ data: { count: results.length, next: null, previous: null, results }, status: 200, statusText: 'OK', headers: {}, config: {} as never })
const plan = {
  id: 7, unidad_educativa: 2, unidad_nombre: 'Primaria', calendario_academico: 11, gestion: 2026, nombre: 'Pensión 2026',
  descripcion: '', nivel_educativo: null, nivel_display: null, monto_total: '3000.00', numero_cuotas: 10, moneda: 'BOB',
  estado: 'BORRADOR' as const, cuotas: [], estudiantes_asignados: 0,
}

describe('Pensiones y pagos', () => {
  beforeEach(() => {
    permissions = new Set(['plan-pago:listar', 'plan-pago:crear', 'plan-pago:editar', 'beca:listar', 'obligacion-pago:listar'])
    vi.mocked(cargarCatalogoPaginado).mockImplementation(async (endpoint: string) => (
      endpoint.includes('calendarios') ? [{ id: 10, año: 2025, activo: false }, { id: 11, año: 2026, activo: true }] : [{ id: 3, nombre: 'Tercero A' }]
    ) as never)
    vi.mocked(api.listarPlanes).mockResolvedValue(pagina([plan]))
    vi.mocked(api.listarBecas).mockResolvedValue(pagina([]))
    vi.mocked(api.listarAsignacionesBeca).mockResolvedValue(pagina([]))
    vi.mocked(api.listarObligaciones).mockResolvedValue(pagina([]))
  })

  it('consulta los planes de la gestión activa de la unidad fija', async () => {
    render(<FinanzasPage />)
    expect(await screen.findByText('Pensión 2026')).toBeInTheDocument()
    expect(api.listarPlanes).toHaveBeenCalledWith(expect.objectContaining({ unidad_educativa: 2, calendario_academico: 11 }), expect.anything())
    expect(screen.getByText('Bs 3.000,00')).toBeInTheDocument()
  })

  it('crea un plan con el nombre normalizado y la gestión seleccionada', async () => {
    vi.mocked(api.crearPlan).mockResolvedValue({ data: plan } as never)
    render(<FinanzasPage />); await screen.findByText('Pensión 2026')
    fireEvent.click(screen.getByText('Nuevo plan'))
    fireEvent.change(screen.getByLabelText('Nombre del plan'), { target: { value: '  Pensión   secundaria ' } })
    fireEvent.change(screen.getByLabelText('Monto total'), { target: { value: '4500' } })
    fireEvent.change(screen.getByLabelText('Nivel del plan'), { target: { value: 'SEC' } })
    fireEvent.click(screen.getByText('Guardar'))
    await waitFor(() => expect(api.crearPlan).toHaveBeenCalledWith(expect.objectContaining({
      unidad_educativa: 2, calendario_academico: 11, nombre: 'Pensión secundaria', monto_total: '4500', numero_cuotas: 10, nivel_educativo: 'SEC',
    })))
  })

  it('oculta acciones sin permiso y muestra solo pestañas autorizadas', async () => {
    permissions = new Set(['plan-pago:listar'])
    render(<FinanzasPage />); await screen.findByText('Pensión 2026')
    expect(screen.queryByText('Nuevo plan')).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Becas' })).not.toBeInTheDocument()
  })

  it('sin permisos de finanzas no consulta nada', () => {
    permissions = new Set()
    render(<FinanzasPage />)
    expect(screen.getByText('No tiene permisos para realizar esta acción.')).toBeInTheDocument()
    expect(api.listarPlanes).not.toHaveBeenCalled()
  })

  it('registra un pago sobre las cuotas seleccionadas', async () => {
    permissions = new Set(['pago:listar', 'pago:crear'])
    vi.mocked(api.listarPagos).mockResolvedValue(pagina([]))
    vi.mocked(api.buscarEstudiantes).mockResolvedValue({ data: [{ id: 9, nombre: 'Ana Rojas', rude: 'R-1', curso: 3, curso_nombre: 'Tercero A' }] } as never)
    vi.mocked(api.listarObligaciones).mockResolvedValue(pagina([
      { id: 21, concepto: 'Cuota 1 - Febrero', saldo: '300.00', fecha_vencimiento: '2026-02-10', vencida: true },
      { id: 22, concepto: 'Cuota 2 - Marzo', saldo: '300.00', fecha_vencimiento: '2026-03-10', vencida: false },
    ] as never))
    vi.mocked(api.registrarPago).mockResolvedValue({ data: { id: 1, numero_recibo: 15, monto: '300.00', estudiante_nombre: 'Ana Rojas', detalles: [] } } as never)
    render(<FinanzasPage />)
    fireEvent.click(await screen.findByText('Registrar pago'))
    fireEvent.change(screen.getByLabelText('Buscar estudiante'), { target: { value: 'Ana' } })
    fireEvent.click(screen.getByLabelText('Buscar'))
    fireEvent.click(await screen.findByText('Ana Rojas'))
    fireEvent.click(await screen.findByLabelText('Seleccionar Cuota 2 - Marzo'))
    expect(screen.getByLabelText('Monto del pago')).toHaveValue(300)
    fireEvent.click(screen.getAllByText('Registrar pago').at(-1)!)
    await waitFor(() => expect(api.registrarPago).toHaveBeenCalledWith(expect.objectContaining({ estudiante: 9, monto: '300.00', metodo: 'EFECTIVO', obligaciones: [22] })))
    expect(await screen.findByText(/Recibo N.º 000015/)).toBeInTheDocument()
  })

  it('muestra el resumen de morosidad', async () => {
    permissions = new Set(['morosidad:listar'])
    vi.mocked(api.obtenerMorosidad).mockResolvedValue({ data: {
      fecha_corte: '2026-11-16',
      resumen: { estudiantes_morosos: 1, estudiantes_con_cuotas: 4, monto_vencido: 600, monto_exigible: 2400, indice_morosidad: 25, por_tramo: [{ tramo: '31-60', estudiantes: 1, monto: 600 }] },
      estudiantes: [{ estudiante: 9, estudiante_nombre: 'Ana Rojas', curso_nombre: 'Tercero A', cuotas_vencidas: 2, monto_vencido: 600, vencimiento_mas_antiguo: '2026-10-01', dias_mora: 46, tramo: '31-60' }],
    } } as never)
    render(<FinanzasPage />)
    expect(await screen.findByText('Ana Rojas')).toBeInTheDocument()
    expect(screen.getByText('25.00%')).toBeInTheDocument()
    expect(screen.getByText('1 / 4')).toBeInTheDocument()
  })

  it('la conciliación QR permite aplicar cobros observados y simular solo solicitudes de prueba', async () => {
    permissions = new Set(['pago-qr:listar', 'pago-qr:crear', 'pago-qr:conciliar'])
    const observada = { id: 4, estudiante: 9, estudiante_nombre: 'Ana Rojas', curso_nombre: 'Tercero A', conceptos: ['Cuota 1 - Febrero'], monto: '333.33', qr_id: 'q', qr_url: 'https://x/qr.png', expira_at: '2026-11-16T20:00:00Z', estado: 'OBSERVADA', conciliacion: 'OBSERVADA', pago: null, numero_recibo: null, monto_reportado: '300.00', observacion: 'El monto no coincide.', solicitado_por_nombre: 'Tutor', created_at: '2026-11-16T19:00:00Z', simulado: false }
    const pendiente = { ...observada, id: 5, estado: 'PENDIENTE', conciliacion: 'PENDIENTE', monto_reportado: null, observacion: '', simulado: true }
    const real = { ...pendiente, id: 6, estudiante: 10, estudiante_nombre: 'Pedro Rojas', simulado: false }
    vi.mocked(api.listarSolicitudesQR).mockResolvedValue(pagina([pendiente, real] as never))
    vi.mocked(api.obtenerConciliacionQR).mockResolvedValue({ data: { modo_simulado: true, resumen: { cobrado_pasarela: 300, registrado_sistema: 0, diferencia: 300, conciliadas: 0, descuadres: 0, observadas: 1, pendientes: 1, expiradas: 0, pagos_qr_sin_respaldo: 0, monto_qr_sin_respaldo: 0 }, por_resolver: [observada] } } as never)
    vi.mocked(api.resolverSolicitudQR).mockResolvedValue({ data: observada } as never)
    vi.mocked(api.simularCobroQR).mockResolvedValue({ data: { ...pendiente, estado: 'PAGADA', conciliacion: 'CONCILIADA', numero_recibo: 8 } } as never)
    vi.spyOn(window, 'prompt').mockReturnValue('Verificado en extracto')
    render(<FinanzasPage />)
    fireEvent.click(await screen.findByText('Aplicar cobro'))
    await waitFor(() => expect(api.resolverSolicitudQR).toHaveBeenCalledWith(4, 'aplicar', 'Verificado en extracto'))
    expect(screen.getByText(/modo simulado/)).toBeInTheDocument()

    fireEvent.click(await screen.findByLabelText('Ver QR de Pedro Rojas'))
    const dialogoReal = within(screen.getByRole('dialog', { name: 'Pago QR · Pedro Rojas' }))
    expect(dialogoReal.queryByRole('button', { name: 'Simular cobro' })).not.toBeInTheDocument()
    expect(dialogoReal.getByRole('button', { name: 'Verificar pago' })).toBeInTheDocument()
    fireEvent.click(dialogoReal.getByRole('button', { name: 'Cerrar' }))

    const filaDemo = await screen.findByRole('row', { name: /Ana Rojas.*QR simulado/ })
    fireEvent.click(within(filaDemo).getByLabelText('Ver QR de Ana Rojas'))
    fireEvent.click(screen.getByText('Simular cobro'))
    expect(await screen.findByText(/Recibo N.º 000008/)).toBeInTheDocument()
  })

  it('la pestaña de obligaciones filtra pendientes por defecto', async () => {
    render(<FinanzasPage />); await screen.findByText('Pensión 2026')
    fireEvent.click(screen.getByRole('tab', { name: 'Obligaciones' }))
    await waitFor(() => expect(api.listarObligaciones).toHaveBeenCalledWith(expect.objectContaining({ estado: 'PENDIENTE', calendario_academico: 11 }), expect.anything()))
  })
  it('envía recordatorios de cuotas por vencer y muestra el historial', async () => {
    permissions = new Set(['alerta-pago:listar', 'alerta-pago:crear'])
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.mocked(api.listarRecordatoriosPago).mockResolvedValue({ data: [
      { id: 1, estudiante: 9, estudiante_nombre: 'Ana Rojas', tipo: 'VENCIDAS', tipo_display: 'Cuotas vencidas', fecha: '2026-11-18', monto: '300.00', created_at: '' },
    ] } as never)
    vi.mocked(api.enviarRecordatoriosPago).mockResolvedValue({ data: { estudiantes_avisados: 3, ya_avisados_hoy: 1 } } as never)
    render(<FinanzasPage />)
    expect(await screen.findByText('Ana Rojas')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Tipo de recordatorio'), { target: { value: 'POR_VENCER' } })
    fireEvent.change(screen.getByLabelText('Días de anticipación'), { target: { value: '10' } })
    fireEvent.click(screen.getByText('Enviar recordatorios'))
    expect(await screen.findByText('3 familia(s) avisadas. 1 ya habían sido avisadas hoy.')).toBeInTheDocument()
    expect(api.enviarRecordatoriosPago).toHaveBeenCalledWith({ tipo: 'POR_VENCER', dias: 10, unidad_educativa: 2 })
  })

  it('con solo permiso de consulta no ofrece enviar recordatorios', async () => {
    permissions = new Set(['alerta-pago:listar'])
    vi.mocked(api.listarRecordatoriosPago).mockResolvedValue({ data: [] } as never)
    render(<FinanzasPage />)
    await waitFor(() => expect(api.listarRecordatoriosPago).toHaveBeenCalled())
    expect(screen.queryByText('Enviar recordatorios')).not.toBeInTheDocument()
  })
})
