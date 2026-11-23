import { useEffect, useRef, useState } from 'react'
import axios from 'axios'
import { Mic, Square } from 'lucide-react'
import { ejecutarVoz, interpretarVoz, type FiltrosAnalitica, type InterpretacionVoz, type ResultadoVoz } from '../../api/reportes'

type Recognition = { lang: string; continuous: boolean; interimResults: boolean; processLocally: boolean; onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null; onerror: ((event: { error: string }) => void) | null; onend: (() => void) | null; start: () => void; stop: () => void }
type RecognitionConstructor = { new(): Recognition; available?: (options: { langs: string[]; processLocally: boolean }) => Promise<string> }

export default function VozPanel({ contexto, onExportado }: { contexto: Partial<FiltrosAnalitica>; onExportado: () => void }) {
  const [texto, setTexto] = useState('')
  const [interpretacion, setInterpretacion] = useState<InterpretacionVoz | null>(null)
  const [contextoInterpretado, setContextoInterpretado] = useState('')
  const [resultado, setResultado] = useState<ResultadoVoz | null>(null)
  const [error, setError] = useState('')
  const [escuchando, setEscuchando] = useState(false)
  const [ocupado, setOcupado] = useState(false)
  const [modoVoz, setModoVoz] = useState<'verificando' | 'local' | 'navegador' | 'incompatible'>('verificando')
  const [idioma, setIdioma] = useState('es-BO')
  const [consentimiento, setConsentimiento] = useState(false)
  const reconocimiento = useRef<Recognition | null>(null)
  const transcripcionVoz = useRef('')
  const interpretarAlFinalizar = useRef(false)
  const ejecutando = useRef(false)
  const version = useRef(0)
  const actual = JSON.stringify(contexto)
  useEffect(() => { version.current++ }, [actual])
  useEffect(() => () => { version.current++; reconocimiento.current?.stop() }, [])
  useEffect(() => {
    let activo = true
    const ventana = window as unknown as { SpeechRecognition?: RecognitionConstructor; webkitSpeechRecognition?: RecognitionConstructor }
    const Constructor = ventana.SpeechRecognition ?? ventana.webkitSpeechRecognition
    void (async () => {
      await Promise.resolve()
      if (!activo) return
      if (!Constructor) { setModoVoz('incompatible'); return }
      if (!Constructor.available) { setModoVoz('navegador'); return }
      try {
        const bolivia = await Constructor.available!({ langs: ['es-BO'], processLocally: true })
        if (!activo) return
        if (bolivia === 'available') { setModoVoz('local'); return }
        const espana = await Constructor.available!({ langs: ['es-ES'], processLocally: true })
        if (activo) { if (espana === 'available') { setIdioma('es-ES'); setModoVoz('local') } else setModoVoz('navegador') }
      } catch { if (activo) setModoVoz('navegador') }
    })()
    return () => { activo = false }
  }, [])
  const interpretar = async (solicitud = texto) => {
    if (!solicitud.trim()) return
    const v = version.current; setOcupado(true); setError(''); setInterpretacion(null); setResultado(null)
    try { const response = await interpretarVoz(solicitud, contexto); if (v === version.current) { setInterpretacion(response.data); setContextoInterpretado(actual) } }
    catch (e) { if (v === version.current) setError(axios.isAxiosError(e) && e.response?.status === 403 ? 'No tiene permiso para consultar este reporte.' : 'No fue posible interpretar la solicitud.') }
    finally { setOcupado(false) }
  }
  const iniciar = async () => {
    const ventana = window as unknown as { SpeechRecognition?: RecognitionConstructor; webkitSpeechRecognition?: RecognitionConstructor }
    const Constructor = ventana.SpeechRecognition ?? ventana.webkitSpeechRecognition
    if (!Constructor || modoVoz === 'incompatible' || modoVoz === 'verificando' || (modoVoz === 'navegador' && !consentimiento)) return
    try {
      const r = new Constructor(); reconocimiento.current = r; r.lang = idioma; r.processLocally = modoVoz === 'local'; r.continuous = true; r.interimResults = true
      transcripcionVoz.current = ''; interpretarAlFinalizar.current = true
      setTexto(''); setInterpretacion(null); setResultado(null)
      r.onresult = event => {
        const transcripcion = Array.from(event.results, resultado => resultado[0]?.transcript ?? '').join(' ').trim()
        transcripcionVoz.current = transcripcion
        setTexto(transcripcion)
      }
      r.onerror = event => {
        interpretarAlFinalizar.current = false
        if (event.error === 'language-not-supported' && r.lang === 'es-BO') { r.lang = 'es-ES'; setIdioma('es-ES'); try { interpretarAlFinalizar.current = true; r.start(); return } catch { /* El navegador no permite reiniciar la sesión. */ } }
        const errores: Record<string, string> = { 'not-allowed': 'Permiso de micrófono denegado. En Edge, abre los permisos del sitio desde el icono junto a la dirección y cambia Micrófono a Permitir. Si continúa, habilítalo en Configuración de Windows > Privacidad y seguridad > Micrófono. También puedes escribir la solicitud manualmente.', 'service-not-allowed': 'Servicio de voz no disponible.', 'no-speech': 'No se detectó voz.', 'language-not-supported': 'Idioma no soportado.', 'network': 'Servicio de voz no disponible.', 'audio-capture': 'Micrófono no disponible o ocupado.' }
        setError(errores[event.error] ?? 'Error desconocido de reconocimiento de voz.'); setEscuchando(false)
      }
      r.onend = () => {
        setEscuchando(false)
        if (interpretarAlFinalizar.current) {
          interpretarAlFinalizar.current = false
          void interpretar(transcripcionVoz.current)
        }
      }
      setError(''); r.start(); setEscuchando(true)
    } catch { interpretarAlFinalizar.current = false; setEscuchando(false); setError('No fue posible iniciar el reconocimiento local. Use la entrada manual.') }
  }
  const ejecutar = async () => {
    if (!interpretacion?.token_interpretacion || !interpretacion.formato || ocupado || ejecutando.current) return
    ejecutando.current = true
    const v = version.current; setOcupado(true); setError('')
    try {
      const response = await ejecutarVoz(interpretacion.token_interpretacion, interpretacion.formato)
      if (v !== version.current) return
      if (interpretacion.formato === 'VISTA') {
        if (response.data instanceof Blob) throw new Error('La respuesta del reporte no tiene el formato esperado.')
        setResultado(response.data)
      }
      else { const url = URL.createObjectURL(response.data as Blob); const a = document.createElement('a'); a.href = url; a.download = `analitica.${interpretacion.formato.toLowerCase()}`; a.click(); URL.revokeObjectURL(url); onExportado() }
      setInterpretacion(null)
    } catch (e) { if (v === version.current) setError(axios.isAxiosError(e) && e.response?.status === 403 ? 'No tiene permiso para ejecutar el reporte.' : 'No fue posible ejecutar la solicitud.') }
    finally { ejecutando.current = false; setOcupado(false) }
  }
  const vigente = contextoInterpretado === actual && interpretacion
  return <section className="mt-5 rounded border p-4" aria-labelledby="voz-titulo">
    <h3 id="voz-titulo" className="font-semibold">Por voz</h3>
    <p className="text-sm">Puede solicitar estudiantes inscritos, matrícula actual, rendimiento, asistencia o incidentes. La solicitud se interpretará y deberá confirmarla antes de ejecutarla. Utilice los selectores para indicar unidad, gestión y curso.</p>
    <p className="text-sm">Al interpretar, el texto de la consulta puede enviarse a Google Gemini según la configuración del servidor; el audio no se envía al backend.</p>
    <div className="my-2 flex flex-wrap gap-2">{['Lista los estudiantes inscritos en el curso', 'Muéstrame la matrícula actual', 'Genera un PDF del promedio por materia', 'Exporta la asistencia en CSV'].map(ejemplo => <button type="button" key={ejemplo} className="rounded border px-2 py-1 text-sm" onClick={() => { setTexto(ejemplo); setInterpretacion(null) }}>{ejemplo}</button>)}</div>
    {modoVoz === 'incompatible' && <p>Su navegador no admite reconocimiento de voz. Puede escribir la solicitud manualmente.</p>}
    {modoVoz === 'navegador' && <div><p>El reconocimiento local no está disponible. Puede usar el servicio de reconocimiento del navegador. El sistema no almacena el audio ni lo envía a nuestro backend, pero el proveedor del navegador podría procesarlo.</p><label><input type="checkbox" checked={consentimiento} onChange={e => setConsentimiento(e.target.checked)} /> Autorizo utilizar el reconocimiento de voz del navegador.</label></div>}
    <div className="my-2 flex items-center gap-2">
      {!escuchando
        ? <button type="button" className="inline-flex items-center gap-2 rounded border px-3 py-2" disabled={ocupado || modoVoz === 'incompatible' || modoVoz === 'verificando' || (modoVoz === 'navegador' && !consentimiento)} onClick={() => void iniciar()}><Mic size={18} aria-hidden="true" /> Iniciar escucha</button>
        : <button type="button" className="inline-flex items-center gap-2 rounded border px-3 py-2" onClick={() => reconocimiento.current?.stop()}><Square size={16} aria-hidden="true" /> Detener y enviar consulta</button>}
      {escuchando && <span role="status" aria-live="polite" className="inline-flex items-center gap-2 text-red-700"><Mic size={18} aria-hidden="true" className="animate-pulse" /> Escuchando ahora; hable para dictar.</span>}
    </div>
    <label className="block">Solicitud<textarea className="mt-1 block w-full rounded border p-2" maxLength={500} value={texto} onChange={e => { setTexto(e.target.value); transcripcionVoz.current = e.target.value; setInterpretacion(null) }} /></label>
    <div className="my-2 flex gap-2"><button type="button" className="btn-primary" disabled={ocupado || escuchando || !texto.trim()} onClick={() => void interpretar()}>Interpretar</button><button type="button" className="rounded border px-3 py-2" disabled={ocupado || escuchando} onClick={() => { setTexto(''); setInterpretacion(null); setResultado(null); setError('') }}>Limpiar</button></div>
    {error && <p role="alert" className="text-red-700">{error}</p>}
    {interpretacion && interpretacion.estado !== 'LISTO' && <p role="status">{interpretacion.estado === 'NO_SOPORTADO' ? 'No entendí esa consulta. Prueba con estudiantes inscritos, matrícula actual, rendimiento/promedio, asistencia o incidentes. Si Gemini no está configurado o no responde, el intérprete local reconoce menos frases.' : `Complete los selectores: ${(interpretacion.faltantes ?? []).join(', ')}. Vuelva a interpretar.`}{interpretacion.opciones?.map(o => ` ${o.nombre} (${o.id})`)}</p>}
    {vigente && interpretacion.estado === 'LISTO' && <div className="rounded bg-slate-50 p-3"><p>Interpretación: {interpretacion.intencion} — {interpretacion.formato}</p><p>{interpretacion.intencion === 'ESTUDIANTES_INSCRITOS' ? 'Se mostrará una lista limitada de estudiantes activos en el curso seleccionado.' : 'El resultado incluye el resumen analítico completo, con matrícula, rendimiento, asistencia e incidentes.'}</p><p>Colegio: {interpretacion.colegio}; unidad: {interpretacion.filtros?.unidad_educativa}; gestión: {interpretacion.filtros?.calendario_academico}; periodo: {interpretacion.filtros?.periodo ?? 'todos'}; curso: {interpretacion.filtros?.curso ?? 'todos'}; materia: {interpretacion.filtros?.materia ?? 'todas'}</p>{interpretacion.advertencias?.map(a => <p key={a}>{a}</p>)}<button type="button" className="btn-primary" disabled={ocupado} onClick={() => void ejecutar()}>Confirmar y ejecutar</button><button type="button" className="ml-2 rounded border px-3 py-2" onClick={() => setInterpretacion(null)}>Cancelar / editar</button></div>}
    {resultado && <div className="mt-3"><h4 className="font-semibold">{'tipo' in resultado ? 'Estudiantes inscritos' : 'Vista previa analítica'}</h4>{'tipo' in resultado ? <><table><thead><tr>{resultado.columnas.map(columna => <th key={columna} className="px-3 text-left">{columna}</th>)}</tr></thead><tbody>{resultado.filas.map((fila, indice) => <tr key={`${fila[0]}-${indice}`}>{fila.map((valor, celda) => <td key={`${celda}-${valor}`} className="px-3">{valor}</td>)}</tr>)}</tbody></table>{resultado.hay_mas && <p role="status">Se muestran los primeros {resultado.limite} estudiantes; refine la consulta por curso para ver menos resultados.</p>}</> : <><table><tbody>{Object.entries(resultado.indicadores).map(([k, v]) => <tr key={k}><th className="pr-4 text-left">{k.replaceAll('_', ' ')}</th><td>{v ?? 'Sin datos'}</td></tr>)}</tbody></table><p>{resultado.metadatos.matricula_actual.advertencia}</p></>}</div>}
  </section>
}
