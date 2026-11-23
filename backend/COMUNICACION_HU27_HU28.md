# Comunicación institucional y alertas (HU27/HU28)

Aplicar `python manage.py migrate` antes de iniciar el servidor. Las migraciones
`comunicacion.0001_initial` y `0002_permiso_director` crean tablas independientes
de la notificación heredada y conceden `comunicacion/gestionar` al puesto Director.
La señal de Puesto concede el mismo permiso a nuevos puestos Director. El backend
exige además rol Admin activo, perfil administrativo Director activo y alcance
institucional válido; el permiso por sí solo no permite publicar ni concede
operaciones académicas al SuperAdmin. Se conserva la política de suscripciones.

## API JWT: `/api/comunicacion/`

Los listados usan `{count,next,previous,results}`, veinte filas por página.

| Ruta | Métodos / comportamiento |
| --- | --- |
| `comunicados/` | GET listados visibles; POST borrador con `titulo,cuerpo,unidad_educativa,curso` (nullable), `prioridad` NORMAL/URGENTE y `requiere_confirmacion` |
| `comunicados/{id}/` | GET detalle; PATCH únicamente borrador y por director autorizado |
| `comunicados/{id}/publicar/` | POST fija audiencia, publica y crea bandeja; repetir no reenvía |
| `comunicados/{id}/archivar/` | POST archiva publicado conservando audiencia y lecturas |
| `comunicados/{id}/leer/` | POST confirma lectura explícita, conserva primera fecha y marca su aviso leído |
| `notificaciones/` | GET bandeja propia, filtros `no_leidas=true` y `tipo=FALTA` (u otra categoría) |
| `notificaciones/{id}/` | GET aviso propio |
| `notificaciones/{id}/leer/` | POST conserva primera fecha de lectura; no confirma lectura del comunicado |
| `notificaciones/resumen/` | GET `{no_leidas:number}` |
| `preferencias/` | GET/PATCH booleanos COMUNICADO,FALTA,ATRASO,NOTA_BAJA,PAGO,CONTINGENCIA,CITACION,BOLETIN; categorías desconocidas o valores no booleanos producen 400 |
| `alertas/` | POST autorizado PAGO/CONTINGENCIA; datos abajo; devuelve 201 `{creadas:number}` |

Los comunicados incluyen `leido_at`, `puede_gestionar`, `es_destinatario` y
`estadisticas`. `es_destinatario` es verdadero únicamente para usuarios incluidos
en la audiencia fijada al publicar que conservan afiliación activa y coherente a
la unidad del comunicado. Un director puede ser simultáneamente gestor y
destinatario de un comunicado institucional; la interfaz debe usar este booleano
para ofrecer confirmación de lectura. Un gestor ajeno a la audiencia de un curso
obtiene falso. Borradores también devuelven falso. Sólo los
gestores reciben estadísticas `{destinatarios,leidos,porcentaje_lectura}`; los
destinatarios reciben `null`. Borradores no se exponen a receptores. Los filtros
opcionales `unidad_educativa`, `curso` y `estado` nunca amplían el alcance.

La audiencia institucional comprende usuarios activos de la unidad; por curso,
estudiantes activos y sus tutores. Se exige `Usuario.unidad` coincidente y perfiles
coherentes con esa unidad: un vínculo tutor/estudiante de otra institución no
concede acceso. La publicación fija usuarios únicos, incluso si luego cambian de
curso. Si cambia su unidad, el receptor pierde acceso a la información anterior.
Un usuario incorporado después de publicar no recibe el comunicado anterior.

## Integración administrativa de pagos y contingencias

No existe un módulo de cobros de familias en este cambio. `suscripciones.Pago`
representa pagos del colegio por la plataforma y **no** se usa para inferir deudas
de estudiantes. Un director puede emitir un aviso administrativo verificable:

```json
{
  "estudiante": 123,
  "tipo": "PAGO",
  "titulo": "Aviso administrativo",
  "cuerpo": "Consulte con administración el detalle de su pago.",
  "clave_evento": "cuota-2026-11-123"
}
```

La misma clave para el mismo estudiante, unidad, tipo y destinatario devuelve
`creadas:0` en un reintento. Utilizar una clave diferente para un nuevo evento.
`CONTINGENCIA` utiliza el mismo formato. Tanto estudiante como tutores válidos
reciben bandeja durable aunque deshabiliten esa categoría de push.

Un módulo financiero futuro puede invocar el servicio interno desde una
transacción que ya autorizó al actor y validó la operación financiera:

```python
from django.db import transaction
from aplicaciones.comunicacion.servicios import emitir_alerta_estudiante

with transaction.atomic():
    # Actualizar el evento financiero real y autorizar al actor en su módulo.
    emitir_alerta_estudiante(
        estudiante=estudiante,
        unidad=unidad_del_evento,
        tipo='PAGO',
        titulo='Aviso administrativo',
        cuerpo='Consulte el detalle del pago con administración.',
        clave_evento=f'finanzas:cuota:{cuota.pk}:vencimiento',
        datos={'referencia_pago': cuota.pk},
    )
```

El servicio interno es para llamadores confiables: la API pública realiza la
autorización de director. El servicio exige coherencia del estudiante, usuario,
curso y unidad de origen; no crea cargos, saldos ni pagos. La clave debe ser
estable, no sensible, de hasta 200 caracteres y con prefijo propio del módulo.

## Eventos y entrega

Las señales `post_save` emiten FALTA/ATRASO desde DetalleAsistencia y
AsistenciaEstudiante; NOTA_BAJA desde ResultadoTrimestral usa `nota_aprobacion`
activa del calendario y nivel (51 si falta configuración). CITACION se integra
con AccionDisciplinaria pendiente y BOLETIN con DocumentoAcademicoEmitido.
No se duplica el antiguo push directo de boletines. Guardados repetidos del mismo
evento/destinatario no crean nuevos avisos. Cambiar de FALTA a ATRASO representa
dos categorías de evento. Fuentes de otra unidad o relaciones incoherentes se
excluyen. Nuevas integraciones deben usar `save`/`update_or_create` o invocar el
servicio explícitamente: `bulk_create`, `bulk_update` y QuerySet.update no
disparan señales Django.

La publicación usa bloqueo de fila; la unicidad de base de datos protege
destinatarios y eventos concurrentes. Avisos y lecturas son transaccionales.
Los callbacks push se registran mediante `transaction.on_commit`, revalidan
afiliación y preferencias y envían sólo texto genérico con datos
`{notificacion_id,comunicado_id,tipo}`. La bandeja autenticada contiene el detalle.
Expo se fragmenta en lotes de hasta 100 mensajes; una falla de red no revierte el
evento ni elimina su aviso. No hay broker ni reintento persistente de push: la
bandeja es el canal durable y puede consultarse tras una falla del proveedor.

Creación, edición, publicación, archivo, confirmación y emisión manual generan
auditoría institucional sin copiar título/cuerpo privados al evento de auditoría.

## Verificación

```text
python manage.py test aplicaciones.usuarios.test_comunicacion_hu27 aplicaciones.usuarios.test_notificaciones_push aplicaciones.estudiantes.test_boletines_hu19 --noinput
python manage.py makemigrations --check --dry-run
python manage.py check
```

Las pruebas aíslan datos sintéticos, verifican concurrencia sobre PostgreSQL y
sustituyen el transporte HTTP de Expo. La validación push en dispositivo requiere
un token real registrado por la app y no se realiza desde los tests.
