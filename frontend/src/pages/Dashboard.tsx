import { ArrowDown, ArrowRight, BookOpen, Building2, Check, GraduationCap, Layers3, School, ShieldCheck, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { authAxios } from '../api/axiosInstance'
import { normalizarPlanes, type Plan } from '../api/suscripciones'
import { DESCRIPCION_SISTEMA, NOMBRE_SISTEMA } from '../app/config/branding'
import './landing.css'

const areas = [
  { number: '01', title: 'Tu institución, organizada', body: 'Configura tu colegio, sus unidades educativas y la estructura que acompaña cada gestión.', icon: Building2 },
  { number: '02', title: 'Personas en el centro', body: 'Administra usuarios, docentes, estudiantes y sus inscripciones desde un mismo espacio.', icon: Users },
  { number: '03', title: 'El día a día académico', body: 'Organiza materias, asignaciones y horarios para acompañar el trabajo de tu comunidad.', icon: BookOpen },
  { number: '04', title: 'Seguimiento con contexto', body: 'Consulta asistencia, evaluación y reportes de acuerdo con los permisos de cada perfil.', icon: Layers3 },
]

const nombresModulos: Record<string, string> = {
  colegio: 'Institución', 'unidad-educativa': 'Unidades educativas', usuario: 'Usuarios', estudiante: 'Estudiantes',
  profesor: 'Docentes', curso: 'Cursos', calendario: 'Calendario académico', horario: 'Horarios',
  'asignacion-docente': 'Asignaciones docentes', materia: 'Materias', asistencia: 'Asistencia',
  disciplina: 'Disciplina', 'actividad-evaluacion': 'Evaluación', reporte: 'Reportes',
}

function precioPlan(plan: Plan) {
  const value = Number(plan.precio)
  if (!Number.isFinite(value)) return `${plan.moneda} ${plan.precio}`
  try { return new Intl.NumberFormat('es-BO', { style: 'currency', currency: plan.moneda }).format(value) }
  catch { return `${plan.moneda} ${plan.precio}` }
}

export default function Dashboard() {
  const [planes, setPlanes] = useState<Plan[]>([])
  const [planesError, setPlanesError] = useState(false)
  const [cargandoPlanes, setCargandoPlanes] = useState(true)
  const [revision, setRevision] = useState(0)

  useEffect(() => {
    let activo = true
    authAxios.get<Plan[] | { count: number; results: Plan[] }>('/suscripciones/planes-publicos/')
      .then(({ data }) => { if (activo) { setPlanes(normalizarPlanes(data)); setPlanesError(false) } })
      .catch(() => { if (activo) setPlanesError(true) })
      .finally(() => { if (activo) setCargandoPlanes(false) })
    return () => { activo = false }
  }, [revision])

  const reintentar = () => { setCargandoPlanes(true); setPlanesError(false); setRevision(value => value + 1) }

  return <div className="landing">
    <a href="#contenido" className="landing-skip">Ir al contenido principal</a>
    <header className="landing-header">
      <nav className="landing-nav" aria-label="Navegación principal">
        <Link to="/" className="landing-logo"><span className="landing-logo-mark"><School size={22}/></span><span><strong>{NOMBRE_SISTEMA}</strong><small>GESTIÓN EDUCATIVA</small></span></Link>
        <div className="landing-nav-links"><a href="#funcionalidades">La plataforma</a><a href="#comunidad">Para tu equipo</a><a href="#planes">Planes</a></div>
        <div className="landing-nav-actions"><Link to="/login" className="landing-login">Iniciar sesión</Link><Link to="/registro-institucional" className="landing-header-cta">Registrar colegio <ArrowRight size={16}/></Link><details className="landing-mobile-menu"><summary aria-label="Abrir menú">☰</summary><div><a href="#funcionalidades">La plataforma</a><a href="#comunidad">Para tu equipo</a><a href="#planes">Planes</a><Link to="/registro-institucional">Registrar colegio</Link></div></details></div>
      </nav>
    </header>
    <main id="contenido">
      <section className="landing-hero"><div className="landing-hero-inner">
        <div className="landing-hero-copy"><p className="landing-eyebrow"><span/> GESTIÓN EDUCATIVA, EN COMUNIDAD</p>
          <h1>Más tiempo para <em>educar.</em><br/>Más espacio para crecer.</h1>
          <p className="landing-lead">Un espacio para organizar tu institución y acompañar a las personas que hacen posible cada día de clases.</p>
          <div className="landing-hero-actions"><Link to="/registro-institucional" className="landing-button landing-button-primary">Registrar mi colegio <ArrowRight size={18}/></Link><a href="#planes" className="landing-button landing-button-quiet">Explorar planes <ArrowDown size={17}/></a></div>
          <div className="landing-hero-note"><span className="landing-note-icon"><ShieldCheck size={18}/></span><span>Organización, gestión académica y seguimiento<br/><strong>en un mismo lugar.</strong></span></div>
        </div>
        <div className="landing-visual"><div className="landing-visual-top"><span>UN ESPACIO PARA APRENDER</span><span>01 / COMUNIDAD</span></div><CampusIllustration/><div className="landing-visual-caption"><span>EDUCACIÓN · ORGANIZACIÓN · COMUNIDAD</span><p>El trabajo de todos,<br/><em>mejor conectado.</em></p></div></div>
      </div></section>
      <section className="landing-intro" id="funcionalidades"><div className="landing-section-wrap"><div className="landing-section-heading"><div><p className="landing-eyebrow"><span/> UNA PLATAFORMA, MUCHAS TAREAS</p><h2>La gestión escolar<br/><em>toma forma.</em></h2></div><p>Desde la organización de tu colegio hasta el seguimiento académico, encuentra lo que necesitas para trabajar con claridad.</p></div><div className="landing-areas">{areas.map(({ number, title, body, icon: Icon }) => <article className="landing-area" key={number}><div className="landing-area-top"><span>{number}</span><Icon size={23} strokeWidth={1.5}/></div><h3>{title}</h3><p>{body}</p></article>)}</div></div></section>
      <section className="landing-community" id="comunidad"><div className="landing-section-wrap landing-community-grid"><div className="landing-community-art"><div className="landing-community-label"><span>TRABAJO EN EQUIPO</span><GraduationCap size={23}/></div><div className="landing-community-circle"><School size={62} strokeWidth={1.1}/></div><p>La educación<br/><em>se construye juntos.</em></p><div className="landing-community-footer"><span>PERSONAS</span><span>·</span><span>APRENDIZAJE</span><span>·</span><span>COMUNIDAD</span></div></div><div className="landing-community-copy"><p className="landing-eyebrow"><span/> CADA PERSONA IMPORTA</p><h2>Un lugar para<br/><em>cada perspectiva.</em></h2><p>Dirección, secretaría y docentes tienen responsabilidades distintas. Cada persona accede a las herramientas que corresponden a su cuenta.</p><ul><li><Check size={16}/> Organización institucional para dirección</li><li><Check size={16}/> Inscripciones y gestión para secretaría</li><li><Check size={16}/> Asignaciones y trabajo académico para docentes</li></ul><Link to="/login" className="landing-link">Ingresar a mi cuenta <ArrowRight size={17}/></Link></div></div></section>
      <section className="landing-steps"><div className="landing-section-wrap"><div className="landing-section-heading"><div><p className="landing-eyebrow"><span/> CÓMO COMENZAR</p><h2>Tu institución,<br/><em>paso a paso.</em></h2></div><p>Comienza con los datos de tu colegio y elige la opción que se adapte a tu institución.</p></div><div className="landing-step-grid"><article><span>01</span><h3>Registra tu colegio</h3><p>Completa los datos de la institución y de su responsable.</p></article><article><span>02</span><h3>Confirma tu correo</h3><p>Verifica tu dirección para acceder a tu cuenta.</p></article><article><span>03</span><h3>Contrata un plan</h3><p>Confirma el plan y registra el pago para su validación.</p></article></div></div></section>
      <section className="landing-pricing" id="planes"><div className="landing-section-wrap"><div className="landing-section-heading"><div><p className="landing-eyebrow"><span/> PLANES PARA TU INSTITUCIÓN</p><h2>Elige cómo<br/><em>quieres empezar.</em></h2></div><p>Consulta las opciones disponibles y sus límites antes de registrar tu colegio.</p></div>
        {cargandoPlanes && <p role="status" className="landing-plan-message">Cargando planes disponibles...</p>}
        {planesError && <div role="alert" className="landing-plan-message">No se pudieron cargar los planes. <button type="button" onClick={reintentar}>Reintentar</button></div>}
        {!cargandoPlanes && !planesError && planes.length === 0 && <p className="landing-plan-message">No hay planes disponibles en este momento.</p>}
        {!cargandoPlanes && !planesError && <div className="landing-plan-grid">{planes.map((plan) => <article className="landing-plan" key={plan.id}><div className="landing-plan-header"><span>PLAN INSTITUCIONAL</span><School size={21}/></div><h3>{plan.nombre}</h3><p className="landing-plan-description">{plan.descripcion || 'Una opción para la gestión de tu institución.'}</p><p className="landing-price">{precioPlan(plan)} <small>/ {plan.periodicidad_display.toLowerCase()}</small></p><div className="landing-plan-features"><p><Check size={16}/> {plan.limite_usuarios ? `Hasta ${plan.limite_usuarios} usuarios` : 'Usuarios sin límite'}</p><p><Check size={16}/> {plan.limite_unidades ? `Hasta ${plan.limite_unidades} unidades educativas` : 'Unidades educativas sin límite'}</p><p><Check size={16}/> {plan.modulos_habilitados.length ? plan.modulos_habilitados.map(m => nombresModulos[m] || m.replace(/[-_]/g, ' ')).join(', ') : 'Todos los módulos'}</p></div><Link to={`/registro-institucional?plan=${plan.id}`} className="landing-plan-cta">Elegir este plan <ArrowRight size={17}/></Link></article>)}</div>}
        <p className="landing-pricing-note">El pago con QR está disponible para planes en bolivianos. Para otras monedas, coordina el pago con la plataforma.</p>
      </div></section>
      <section className="landing-faq"><div className="landing-section-wrap landing-faq-grid"><div><p className="landing-eyebrow"><span/> PREGUNTAS FRECUENTES</p><h2>Lo esencial,<br/><em>más claro.</em></h2></div><div className="landing-faq-items"><details><summary>¿Cómo registro mi institución?</summary><p>Completa los datos del responsable y del colegio, confirma el correo y continúa con la contratación de un plan.</p></details><details><summary>¿El precio y los límites son iguales para todos los planes?</summary><p>Cada plan publicado indica su precio, periodo, moneda y límites. Consulta las opciones disponibles en la sección de planes.</p></details><details><summary>¿Cómo se confirma un pago?</summary><p>La suscripción se activa cuando se valida el pago. El QR está disponible para planes en bolivianos; para otras monedas se debe coordinar con la plataforma.</p></details></div></div></section>
      <section className="landing-closing"><div className="landing-section-wrap landing-closing-inner"><div><p className="landing-eyebrow"><span/> EMPECEMOS</p><h2>Una comunidad educativa.<br/><em>Un espacio para avanzar.</em></h2></div><Link to="/registro-institucional" className="landing-button landing-button-light">Registrar mi colegio <ArrowRight size={18}/></Link></div></section>
    </main>
    <footer className="landing-footer"><div className="landing-section-wrap landing-footer-inner"><Link to="/" className="landing-logo landing-footer-logo"><span className="landing-logo-mark"><School size={21}/></span><span><strong>{NOMBRE_SISTEMA}</strong><small>{DESCRIPCION_SISTEMA}</small></span></Link><div><a href="#funcionalidades">Plataforma</a><a href="#planes">Planes</a><Link to="/login">Iniciar sesión</Link></div><p>Hecho para acompañar la gestión educativa.</p></div></footer>
  </div>
}

function CampusIllustration() {
  return <svg className="landing-campus" viewBox="0 0 560 420" role="img" aria-label="Ilustración de una escuela rodeada de árboles">
    <rect x="23" y="34" width="514" height="349" rx="190" fill="#d7d9bf"/><circle cx="405" cy="113" r="41" fill="#eabf77"/><path d="M45 284C108 249 167 263 211 277c62 20 115-19 164-16 54 3 94 18 136 3v86H45z" fill="#a9c1a6"/>
    <path d="M96 291V179l164-78 164 78v112z" fill="#f7f3e9"/><path d="M77 185l183-91 183 91-9 18-174-82-174 82z" fill="#234f42"/><path d="M124 291v-92l136-64 136 64v92" fill="#e6c99b"/><path d="M157 291v-87h206v87" fill="#f8f3e8"/><path d="M243 291v-71h34v71" fill="#285447"/><path d="M249 225h22v66h-22z" fill="#d4ab6f"/><path d="M177 216h35v34h-35zm131 0h35v34h-35z" fill="#aec7bb"/><path d="M194 216v34m-17-17h35m113-17v34m-17-17h35" stroke="#f8f3e8" strokeWidth="4"/>
    <circle cx="260" cy="176" r="15" fill="#e2e9d8"/><path d="M260 165v12l8 5" fill="none" stroke="#285447" strokeWidth="3" strokeLinecap="round"/><path d="M78 320h365M119 301h282" stroke="#557766" strokeWidth="3" strokeLinecap="round"/>
    <path d="M73 313v-74m0 15-19-18m19 9 18-19M462 312v-79m0 18-19-20m19 11 17-19" fill="none" stroke="#355f4c" strokeWidth="6" strokeLinecap="round"/><circle cx="72" cy="218" r="35" fill="#6b9879"/><circle cx="47" cy="235" r="21" fill="#7eaa87"/><circle cx="93" cy="237" r="23" fill="#88b18e"/><circle cx="460" cy="210" r="39" fill="#5f8d70"/><circle cx="435" cy="232" r="22" fill="#80a98a"/><circle cx="486" cy="229" r="23" fill="#87af8f"/><path d="M36 350c74-21 149-12 225-12 80 0 156-9 235 12" fill="none" stroke="#f7f3e9" strokeWidth="2" strokeDasharray="5 8"/>
  </svg>
}
