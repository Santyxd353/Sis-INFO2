import api from '../../api/axiosInstance'

export const getProfesores = () => api.get('/profesores/')
export const getDimensiones = () => api.get('/dimensiones/')
export const getEstudiantes = () => api.get('/estudiantes/estudiantes/listar/')
