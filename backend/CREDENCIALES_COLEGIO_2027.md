# Credenciales del colegio demo 2027

Estas credenciales corresponden al seeder explícito. Los nombres son datos
ficticios realistas para demostración y no representan personas reales:

```powershell
cd backend
.\env\Scripts\python.exe manage.py seed_colegio_2027
```

El comando es idempotente y no se ejecuta automáticamente con `migrate`.

## Colegio

- Colegio: `Colegio Demo Gestión 2027`
- Código tenant: `DEMO-2027`
- Plan: el primer plan activo existente; si no existe, crea `Plan Demo Académico 2027` gratuito.
- Gestión: `2027`
- Unidades: `DEMO-2027-PRI` y `DEMO-2027-SEC`

## Usuarios institucionales

| Rol | Usuario | Correo | Contraseña | Alcance |
|---|---|---|---|---|
| Carlos Mamani Quispe (Director) | `dir2027` | `director2027@demo2027.edu.bo` | `Demo2027-Director!` | Colegio completo |
| María Fernanda Condori Flores (Secretaría) | `sec2027pri` | `secretaria.primaria2027@demo2027.edu.bo` | `Demo2027-Secretaria!` | Unidad Primaria |
| Roxana Apaza Choque (Secretaría) | `sec2027sec` | `secretaria.secundaria2027@demo2027.edu.bo` | `Demo2027-Secretaria!` | Unidad Secundaria |

## Profesores

Hay seis profesores ficticios por unidad educativa, uno por cada materia. El patrón es:

- Usuario Primaria: `profpri2027{1..6}`
- Usuario Secundaria: `profsec2027{1..6}`
- Correo: `profesor.pri{n}.2027@demo2027.edu.bo` o `profesor.sec{n}.2027@demo2027.edu.bo`
- Contraseña de todos: `Demo2027-Profesor!`

## Estudiantes

Hay 10 estudiantes ficticios por curso, mezclando nombres generados por el seeder. El
patrón de usuario es `estpri2027{paralelo}{grado}{01..10}` para Primaria y
`estsec2027{paralelo}{grado}{01..10}` para Secundaria.

- Correo: `<usuario>@demo2027.edu.bo`
- Contraseña de todos: `Demo2027-Estudiante!`

No reutilizar estas credenciales fuera de desarrollo o demostraciones locales.
