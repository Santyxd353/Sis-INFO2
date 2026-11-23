export type ErrorReporte = { ruta: Array<string | number>; mensaje: string }

// Mantiene la ruta de cada error DRF; nunca representa objetos ni HTML.
export function normalizarErrores(data: unknown): ErrorReporte[] {
  const errores: ErrorReporte[] = []
  const visitar = (valor: unknown, ruta: Array<string | number>) => {
    if (typeof valor === 'string') {
      const mensaje = valor.trim()
      if (mensaje && mensaje.length <= 300 && !/[<>]/.test(mensaje) && !/traceback|\bsql\b|queryset|(?:[a-z]:\\|\/[^\s]+\/)/i.test(mensaje)) errores.push({ ruta, mensaje })
    } else if (Array.isArray(valor)) {
      valor.forEach((elemento, indice) => visitar(elemento, typeof elemento === 'string' ? ruta : [...ruta, indice]))
    } else if (valor && typeof valor === 'object') {
      Object.entries(valor).forEach(([clave, elemento]) => visitar(elemento, [...ruta, /^\d+$/.test(clave) ? Number(clave) : clave]))
    }
  }
  visitar(data, [])
  return errores
}
