import type { Colegio, UnidadEducativa } from '../app/modelos/Institucion'
import type { Usuario } from '../app/modelos/Usuarios'
import { cargarCatalogoPaginado } from './catalogosPaginados'

export const listarColegiosCatalogo = (signal?: AbortSignal) =>
  cargarCatalogoPaginado<Colegio>('/institucion/colegios/', undefined, signal)

export const listarUnidadesCatalogo = (colegio?: number, signal?: AbortSignal) =>
  cargarCatalogoPaginado<UnidadEducativa>('/institucion/unidades-educativas/', { colegio }, signal)

export const listarUsuariosCatalogo = (signal?: AbortSignal) =>
  cargarCatalogoPaginado<Usuario>('/usuarios/usuarios/', undefined, signal)
