"""Carga un colegio demo completo para la gestión académica 2027.

Uso explícito:
    python manage.py seed_colegio_2027

El comando es idempotente y no se ejecuta durante ``migrate``.  Todos los
objetos se identifican por códigos/nombres propios del demo para no tocar los
datos de otros colegios.
"""

from datetime import date, time

from django.core.management.base import BaseCommand
from django.db import transaction

from aplicaciones.academico.models import (
    AsignacionDocente,
    BloqueHorario,
    Curso,
    Grado,
    Materia,
    MateriaCurso,
    Paralelo,
    HorarioClase,
)
from aplicaciones.calendario.models import CalendarioAcademico, Periodo
from aplicaciones.estudiantes.models import Estudiante, HistorialInscripcion
from aplicaciones.institucion.models import Aula, Colegio, Modulo, UnidadEducativa
from aplicaciones.personal.models import Profesor
from aplicaciones.suscripciones.models import Plan, Suscripcion
from aplicaciones.usuarios.models import Admin, Puesto, RegistroInstitucional, Rol, Usuario


PASSWORDS = {
    'director': 'Demo2027-Director!',
    'secretaria': 'Demo2027-Secretaria!',
    'profesor': 'Demo2027-Profesor!',
    'estudiante': 'Demo2027-Estudiante!',
}
COLEGIO_NOMBRE = 'Colegio Demo Gestión 2027'
FECHA_INICIO = date(2027, 2, 1)
FECHA_FIN = date(2027, 12, 15)
MATERIAS = ('Matemática', 'Lenguaje', 'Ciencias Naturales', 'Ciencias Sociales', 'Inglés', 'Educación Física')
DIRECTOR_NOMBRE = ('Carlos', 'Mamani Quispe')
SECRETARIAS = {
    'PRI': ('María Fernanda', 'Condori Flores'),
    'SEC': ('Roxana', 'Apaza Choque'),
}
PROFESORES = {
    'PRI': (
        ('Patricia', 'Mendoza Vargas'), ('Jorge', 'Quispe Nina'),
        ('Verónica', 'Calle Mamani'), ('Luis', 'Huanca Rojas'),
        ('Gabriela', 'Paredes Choque'), ('Diego', 'Ticona Flores'),
    ),
    'SEC': (
        ('Ana María', 'Soto Limachi'), ('Marco Antonio', 'Vega Condori'),
        ('Silvia', 'Mamani Ríos'), ('Edgar', 'Choque Apaza'),
        ('Natalia', 'Flores Quisbert'), ('Óscar', 'Cruz Nina'),
    ),
}
ESTUDIANTES = (
    ('Valentina', 'Mamani'), ('Mateo', 'Quispe'), ('Camila', 'Condori'),
    ('Santiago', 'Flores'), ('Luciana', 'Apaza'), ('Diego', 'Choque'),
    ('Sofía', 'Huanca'), ('Nicolás', 'Vargas'), ('Daniela', 'Ticona'),
    ('Alejandro', 'Limachi'),
)


class Command(BaseCommand):
    help = 'Carga un colegio demo con estructura, usuarios y horarios para la gestión 2027.'

    @transaction.atomic
    def handle(self, *args, **options):
        admin_role, _ = Rol.objects.get_or_create(nombre='Admin', colegio=None, defaults={'categoria': Rol.Categoria.BASE})
        profesor_role, _ = Rol.objects.get_or_create(nombre='Profesor', colegio=None, defaults={'categoria': Rol.Categoria.BASE})
        estudiante_role, _ = Rol.objects.get_or_create(nombre='Estudiante', colegio=None, defaults={'categoria': Rol.Categoria.BASE})

        colegio, _ = Colegio.objects.get_or_create(
            nombre=COLEGIO_NOMBRE,
            defaults={
                'codigo_tenant': 'DEMO-2027',
                'tipo_subsistema': Colegio.TipoSubsistema.PRIVADO,
                'direccion': 'Av. Demo 2027',
                'telefono': '+59170002027',
                'email': 'contacto@demo2027.edu.bo',
                'pais': 'BO', 'region': 'LP', 'ciudad': 'La Paz',
            },
        )
        if not colegio.codigo_tenant:
            colegio.codigo_tenant = 'DEMO-2027'
            colegio.save(update_fields=['codigo_tenant'])

        plan = Plan.objects.filter(
            estado=Plan.Estado.ACTIVO,
            eliminado_at__isnull=True,
            limite_unidades__gte=2,
            limite_usuarios__gte=61,
        ).order_by('id').first()
        if plan is None:
            plan = Plan.objects.create(
                nombre='Plan Demo Académico 2027', descripcion='Plan demo para pruebas académicas.',
                precio=0, moneda='BOB', periodicidad=Plan.Periodicidad.ANUAL,
                modulos_habilitados=['academico', 'reportes', 'asistencia'],
                limite_usuarios=1000, limite_unidades=2,
            )
        Suscripcion.objects.get_or_create(
            colegio=colegio, plan=plan,
            defaults={
                'precio_periodico': plan.precio, 'moneda': plan.moneda,
                'periodicidad': plan.periodicidad,
                'modulos_habilitados': list(plan.modulos_habilitados or []),
                'limite_usuarios': plan.limite_usuarios, 'limite_unidades': plan.limite_unidades,
                'fecha_inicio': FECHA_INICIO, 'fecha_vencimiento': date(2027, 12, 31),
                'estado': Suscripcion.Estado.ACTIVA,
            },
        )

        director_puesto, _ = Puesto.objects.get_or_create(nombre='Director')
        # El catálogo base usa este nombre sin tilde; los serializers y
        # permisos lo buscan por ``Secretaria``/``Secretaría``.
        secretaria_puesto, _ = Puesto.objects.get_or_create(nombre='Secretaria')

        director = self._usuario('dir2027', 'director2027@demo2027.edu.bo', *DIRECTOR_NOMBRE, 'DIR2027', admin_role, PASSWORDS['director'])
        Admin.objects.update_or_create(usuario=director, defaults={'colegio': colegio, 'puesto': director_puesto, 'unidad': None, 'estado': True})
        RegistroInstitucional.objects.get_or_create(
            usuario=director,
            defaults={'colegio': colegio, 'plan_seleccionado': plan, 'condiciones_aceptadas_at': director.date_joined, 'verificado_at': director.date_joined},
        )

        primaria = self._unidad(colegio, 'DEMO-2027-PRI', 'Unidad Educativa Primaria Demo 2027', 'PRIMARIA')
        secundaria = self._unidad(colegio, 'DEMO-2027-SEC', 'Unidad Educativa Secundaria Demo 2027', 'SECUNDARIA')
        secretaria_primaria = self._usuario('sec2027pri', 'secretaria.primaria2027@demo2027.edu.bo', *SECRETARIAS['PRI'], 'SEC2027PRI', admin_role, PASSWORDS['secretaria'])
        secretaria_secundaria = self._usuario('sec2027sec', 'secretaria.secundaria2027@demo2027.edu.bo', *SECRETARIAS['SEC'], 'SEC2027SEC', admin_role, PASSWORDS['secretaria'])
        Admin.objects.update_or_create(usuario=secretaria_primaria, defaults={'colegio': colegio, 'puesto': secretaria_puesto, 'unidad': primaria, 'estado': True})
        Admin.objects.update_or_create(usuario=secretaria_secundaria, defaults={'colegio': colegio, 'puesto': secretaria_puesto, 'unidad': secundaria, 'estado': True})

        resultados = []
        for unidad, nivel, prefijo in ((primaria, 'PRI', 'PRI'), (secundaria, 'SEC', 'SEC')):
            calendario = self._calendario(unidad)
            modulo, aulas = self._infraestructura(colegio, unidad)
            cursos = self._cursos(unidad, nivel, aulas)
            materias = self._materias(unidad)
            profesores = self._profesores(unidad, prefijo, profesor_role)
            self._asignar_materias(cursos, materias, profesores, calendario)
            self._asignar_tutores(cursos, profesores, calendario)
            self._estudiantes(cursos, unidad, prefijo, estudiante_role, director)
            self._horarios(cursos, aulas, calendario)
            resultados.append((unidad.nombre, len(cursos), len(materias), len(profesores)))

        self.stdout.write(self.style.SUCCESS(f'Colegio demo 2027 listo: {colegio.nombre}'))
        for unidad, cursos, materias, profesores in resultados:
            self.stdout.write(f'  {unidad}: {cursos} cursos, {materias} materias, {profesores} profesores')
        self.stdout.write('Credenciales: backend/CREDENCIALES_COLEGIO_2027.md')

    @staticmethod
    def _usuario(username, email, nombre, apellido, ci, rol, password):
        usuario, creado = Usuario.objects.get_or_create(
            username=username,
            defaults={'email': email, 'nombre': nombre, 'apellido': apellido, 'ci': ci, 'rol': rol, 'estado': True, 'is_active': True, 'debe_cambiar_password': False},
        )
        cambios = []
        for campo, valor in (('email', email), ('nombre', nombre), ('apellido', apellido), ('rol', rol)):
            actual = getattr(usuario, f'{campo}_id', None) if campo == 'rol' else getattr(usuario, campo)
            esperado = rol.pk if campo == 'rol' else valor
            if actual != esperado:
                setattr(usuario, campo, valor)
                cambios.append(campo)
        if cambios:
            usuario.save(update_fields=cambios)
        usuario.set_password(password)
        usuario.save(update_fields=['password'])
        return usuario

    @staticmethod
    def _unidad(colegio, codigo, nombre, nivel):
        unidad, _ = UnidadEducativa.objects.get_or_create(
            codigo_sie=codigo,
            defaults={'colegio': colegio, 'nombre': nombre, 'nivel': nivel, 'turno': UnidadEducativa.TURNOS[0][0], 'codigo_interno': codigo},
        )
        if unidad.colegio_id != colegio.pk:
            unidad.colegio = colegio
            unidad.save(update_fields=['colegio'])
        return unidad

    @staticmethod
    def _calendario(unidad):
        calendario, _ = CalendarioAcademico.objects.get_or_create(
            unidad_educativa=unidad, año=2027,
            defaults={'fecha_inicio': FECHA_INICIO, 'fecha_fin': FECHA_FIN, 'activo': True},
        )
        for numero, inicio, fin in ((1, date(2027, 2, 1), date(2027, 5, 15)), (2, date(2027, 5, 16), date(2027, 8, 31)), (3, date(2027, 9, 1), date(2027, 12, 15))):
            Periodo.objects.get_or_create(calendario=calendario, nombre=f'{numero}er Trimestre', defaults={'tipo_division': 'TRI', 'fecha_inicio': inicio, 'fecha_fin': fin, 'estado': 'PLA'})
        return calendario

    @staticmethod
    def _infraestructura(colegio, unidad):
        modulo, _ = Modulo.objects.get_or_create(unidad_educativa=unidad, nombre=f'Módulo {unidad.nivel} 2027', defaults={'colegio_fk': colegio, 'cantidad_aulas': 12, 'pisos': 2, 'descripcion': 'Módulo demo con aulas regulares.'})
        aulas = []
        for numero in range(1, 13):
            aula, _ = Aula.objects.get_or_create(modulo=modulo, nombre=f'Aula {numero:02d}', defaults={'capacidad': 35, 'tipo': 'AUL', 'piso': 1 if numero <= 6 else 2, 'estado': True})
            aulas.append(aula)
        return modulo, aulas

    @staticmethod
    def _cursos(unidad, nivel, aulas):
        definiciones = ((1, 'A'), (1, 'B'), (2, 'C'))
        cursos = []
        for indice, (numero, letra) in enumerate(definiciones):
            grado, _ = Grado.objects.get_or_create(unidad_educativa=unidad, nivel_educativo=nivel, numero=numero)
            paralelo, _ = Paralelo.objects.get_or_create(grado=grado, letra=letra)
            curso, _ = Curso.objects.get_or_create(paralelo=paralelo, defaults={'nombre': f'{numero}ro {letra} {"prim" if nivel == "PRI" else "sec"}'})
            cursos.append((curso, aulas[indice]))
        return cursos

    @staticmethod
    def _materias(unidad):
        return [Materia.objects.get_or_create(unidad_educativa=unidad, nombre=nombre, defaults={'estado': Materia.Estado.ACTIVO})[0] for nombre in MATERIAS]

    def _profesores(self, unidad, prefijo, rol):
        profesores = []
        for indice, nombre in enumerate(MATERIAS, 1):
            nombre, apellido = PROFESORES[prefijo][indice - 1]
            usuario = self._usuario(f'prof{prefijo.lower()}2027{indice}', f'profesor.{prefijo.lower()}{indice}.2027@demo2027.edu.bo', nombre, apellido, f'PRF{prefijo}{indice:02d}', rol, PASSWORDS['profesor'])
            profesor, _ = Profesor.objects.get_or_create(usuario=usuario, defaults={'unidad': unidad, 'estado': True})
            if profesor.unidad_id != unidad.pk:
                profesor.unidad = unidad
                profesor.save(update_fields=['unidad'])
            profesores.append(profesor)
        return profesores

    @staticmethod
    def _asignar_materias(cursos, materias, profesores, calendario):
        for curso, _ in cursos:
            for materia, profesor in zip(materias, profesores):
                relacion, _ = MateriaCurso.objects.get_or_create(curso=curso, materia=materia)
                if relacion.profesor_id != profesor.pk:
                    relacion.profesor = profesor
                    relacion.save(update_fields=['profesor'])
                AsignacionDocente.objects.get_or_create(tipo='MATERIA', calendario_academico=calendario, curso=curso, materia_curso=relacion, profesor=profesor, defaults={'fecha_inicio': FECHA_INICIO, 'fecha_fin': FECHA_FIN, 'horas_semanales': 2})

    @staticmethod
    def _asignar_tutores(cursos, profesores, calendario):
        for indice, (curso, _) in enumerate(cursos):
            AsignacionDocente.objects.get_or_create(tipo='TUTOR_CURSO', calendario_academico=calendario, curso=curso, profesor=profesores[indice], defaults={'fecha_inicio': FECHA_INICIO, 'fecha_fin': FECHA_FIN, 'horas_semanales': 1})
            if curso.tutor_id != profesores[indice].pk:
                curso.tutor = profesores[indice]
                curso.save(update_fields=['tutor'])

    def _estudiantes(self, cursos, unidad, prefijo, rol, director):
        for curso, _ in cursos:
            for numero in range(1, 11):
                username = f'est{prefijo.lower()}2027{curso.paralelo.letra.lower()}{curso.paralelo.grado.numero}{numero:02d}'
                email = f'{username}@demo2027.edu.bo'
                nombre, apellido = ESTUDIANTES[numero - 1]
                usuario = self._usuario(username, email, nombre, apellido, f'EST{prefijo}{curso.paralelo.grado.numero}{curso.paralelo.letra}{numero:02d}', rol, PASSWORDS['estudiante'])
                sexo = 'F' if numero % 2 == 0 else 'M'
                if usuario.sexo != sexo:
                    usuario.sexo = sexo
                    usuario.save(update_fields=['sexo'])
                estudiante, _ = Estudiante.objects.get_or_create(usuario=usuario, defaults={'rude': f'RUDE-2027-{prefijo}-{curso.paralelo.grado.numero}{curso.paralelo.letra}-{numero:02d}', 'unidad': unidad, 'curso': curso, 'estado': True})
                if estudiante.curso_id != curso.pk or estudiante.unidad_id != unidad.pk:
                    estudiante.curso, estudiante.unidad = curso, unidad
                    estudiante.save(update_fields=['curso', 'unidad'])
                HistorialInscripcion.objects.get_or_create(estudiante=estudiante, curso_nuevo=curso, unidad=unidad, defaults={'tipo_movimiento': 'NUEVA', 'usuario_registra': director, 'observaciones': 'Inscripción demo gestión 2027.'})

    @staticmethod
    def _horarios(cursos, aulas, calendario):
        for curso_index, (curso, aula) in enumerate(cursos):
            asignaciones = list(curso.asignaciones_docentes.filter(calendario_academico=calendario, tipo='MATERIA').order_by('id'))
            for materia_index, asignacion in enumerate(asignaciones):
                dia = (materia_index % 5) + 1
                bloque, _ = BloqueHorario.objects.get_or_create(unidad_educativa=aula.modulo.unidad_educativa, turno=aula.modulo.unidad_educativa.TURNOS[0][0], dia=dia, orden=curso_index + 1, defaults={'hora_inicio': time(8 + curso_index, 0), 'hora_fin': time(8 + curso_index, 45), 'tipo': 'CLASE', 'estado': 'ACTIVO'})
                HorarioClase.objects.get_or_create(asignacion_docente=asignacion, profesor=asignacion.profesor, curso=curso, aula=aula, bloque_horario=bloque, fecha_inicio=FECHA_INICIO, defaults={'fecha_fin': FECHA_FIN, 'estado': 'ACTIVO'})
