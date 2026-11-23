import type { Usuario } from '../app/modelos/Usuarios'

export const testUser: Usuario = {
  id: 1,
  ci: '123',
  nombre: 'Ana',
  apellido: 'Pérez',
  sexo: 'F',
  email: 'ana@colegio.test',
  username: 'ana',
  estado: true,
  rol: { id: 1, nombre: 'superadmin' },
  is_staff: true,
  is_active: true,
  date_joined: '2026-01-01T00:00:00Z',
  debe_cambiar_password: false,
  alcance: { tipo: 'GLOBAL', colegio_id: null, colegio_nombre: null, unidad_id: null, unidad_nombre: null },
  permisos_efectivos: [],
  permisos_ui: [],
}
