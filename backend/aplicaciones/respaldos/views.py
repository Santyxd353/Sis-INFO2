import hashlib
import re
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from aplicaciones.institucion.models import Colegio
from aplicaciones.usuarios.auditoria import registrar_evento
from aplicaciones.usuarios.tenancy import es_superadmin, resolver_alcance, ErrorAlcanceInstitucional
from .models import ConfiguracionRespaldo, Respaldo
from .servicios import encolar, raiz_segura

class RespaldoSerializer(serializers.ModelSerializer):
    colegio_nombre = serializers.CharField(source='colegio.nombre', read_only=True, allow_null=True)
    class Meta:
        model = Respaldo
        fields = ['id','alcance','colegio','colegio_nombre','origen','estado','solicitado_at','iniciado_at','finalizado_at','tamano','sha256','version_formato','metadatos','error']
        read_only_fields = fields

class ConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionRespaldo
        fields = ['activo','hora','zona_horaria','ultima_fecha_programada']
        read_only_fields = ['ultima_fecha_programada']
    def validate_zona_horaria(self, value):
        try: ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError): raise serializers.ValidationError('Indique una zona horaria válida.')
        return value

def _contexto(user):
    try: return resolver_alcance(user)
    except ErrorAlcanceInstitucional: return None

def _visible(request):
    qs = Respaldo.objects.select_related('colegio')
    if es_superadmin(request.user): return qs
    ctx = _contexto(request.user)
    return qs.filter(alcance='COLEGIO', colegio_id=ctx['colegio_id']) if ctx and ctx['tipo']=='COLEGIO' else qs.none()

@api_view(['GET','POST'])
@permission_classes([IsAuthenticated])
def respaldos(request):
    ctx = _contexto(request.user)
    if request.method == 'GET':
        if not es_superadmin(request.user) and (not ctx or ctx['tipo'] != 'COLEGIO'):
            return Response({'detail':'No tiene permisos para consultar respaldos.'}, status=403)
        return Response(RespaldoSerializer(_visible(request)[:200], many=True).data)
    if not es_superadmin(request.user) and (not ctx or ctx['tipo'] != 'COLEGIO'):
        return Response({'detail':'No tiene permisos para solicitar respaldos.'}, status=403)
    alcance = str(request.data.get('alcance') or ('GLOBAL' if es_superadmin(request.user) else 'COLEGIO')).upper()
    if not es_superadmin(request.user) and alcance != 'COLEGIO':
        return Response({'detail': 'El Director solo puede solicitar respaldos de su colegio.'}, status=403)
    colegio = None
    if alcance == 'COLEGIO':
        colegio_id = request.data.get('colegio') or (ctx or {}).get('colegio_id')
        if not es_superadmin(request.user) and colegio_id != ctx['colegio_id']:
            return Response({'detail':'No puede solicitar respaldos de otro colegio.'}, status=403)
        try: colegio = Colegio.objects.get(pk=colegio_id)
        except (Colegio.DoesNotExist, TypeError, ValueError): return Response({'detail':'El colegio indicado no es válido.'}, status=400)
    elif alcance != 'GLOBAL' or request.data.get('colegio') is not None:
        return Response({'detail':'Alcance o colegio inconsistente.'}, status=400)
    registro = encolar('MANUAL', request.user, alcance=alcance, colegio=colegio)
    if registro is None: return Response({'detail':'Ya existe un respaldo pendiente o en ejecución para ese alcance.'}, status=409)
    registrar_evento(accion='CREAR', entidad='RESPALDO', request=request, entidad_id=str(registro.pk))
    return Response(RespaldoSerializer(registro).data, status=status.HTTP_202_ACCEPTED)

@api_view(['GET','PUT'])
@permission_classes([IsAuthenticated])
def configuracion(request):
    if not es_superadmin(request.user): return Response({'detail':'No tiene permisos para administrar la programación.'}, status=403)
    config, _ = ConfiguracionRespaldo.objects.get_or_create(pk=1)
    if request.method == 'GET': return Response(ConfigSerializer(config).data)
    serializer = ConfigSerializer(config, data=request.data); serializer.is_valid(raise_exception=True); serializer.save()
    registrar_evento(accion='ACTUALIZAR', entidad='RESPALDO', request=request, entidad_id='configuracion')
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def descargar(request, pk):
    ctx = _contexto(request.user)
    if not es_superadmin(request.user) and (not ctx or ctx['tipo'] != 'COLEGIO'):
        return Response({'detail':'No tiene permisos para descargar respaldos.'}, status=403)
    respaldo = get_object_or_404(_visible(request), pk=pk, estado='COMPLETADO')
    extension = 'edubackup' if respaldo.archivo.endswith('.edubackup') else ('jsonl' if respaldo.archivo.endswith('.jsonl') else 'zip')
    valido_nuevo = re.fullmatch(r'respaldo_(global|colegio)_\d+(?:_\d+)?_?\d*\.edubackup', respaldo.archivo)
    valido_legacy = re.fullmatch(r'[a-f0-9]{32}\.(zip|jsonl)', respaldo.archivo)
    if not (valido_nuevo or valido_legacy):
        return Response({'detail':'El archivo no está disponible.'}, status=404)
    ruta = raiz_segura() / respaldo.archivo
    if ruta.is_symlink() or not ruta.is_file(): return Response({'detail':'El archivo no está disponible.'}, status=404)
    digest = hashlib.sha256()
    with ruta.open('rb') as stream:
        for bloque in iter(lambda: stream.read(1024*1024), b''): digest.update(bloque)
    if respaldo.tamano != ruta.stat().st_size or respaldo.sha256 != digest.hexdigest():
        registrar_evento(accion='EXPORTAR', entidad='RESPALDO', request=request, entidad_id=str(pk), cambios={'resultado':'integridad_fallida'})
        return Response({'detail':'El archivo no está disponible.'}, status=409)
    registrar_evento(accion='EXPORTAR', entidad='RESPALDO', request=request, entidad_id=str(pk))
    prefijo = 'global' if respaldo.alcance == Respaldo.ALCANCE_GLOBAL else f'colegio_{respaldo.colegio_id}'
    response = FileResponse(ruta.open('rb'), as_attachment=True, filename=f'respaldo_{prefijo}_{respaldo.solicitado_at:%Y%m%d_%H%M}.edubackup.zip', content_type='application/zip')
    response['Cache-Control']='no-store'; response['X-Content-Type-Options']='nosniff'; return response

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalle(request, pk):
    ctx = _contexto(request.user)
    if not es_superadmin(request.user) and (not ctx or ctx['tipo'] != 'COLEGIO'):
        return Response({'detail': 'No tiene permisos para consultar respaldos.'}, status=403)
    return Response(RespaldoSerializer(get_object_or_404(_visible(request), pk=pk)).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def estado_procesador(request):
    if not es_superadmin(request.user) and (_contexto(request.user) or {}).get('tipo') != 'COLEGIO':
        return Response({'detail': 'No tiene permisos para consultar respaldos.'}, status=403)
    marca = raiz_segura() / '.worker-heartbeat'
    ultima = None
    if marca.is_file() and not marca.is_symlink():
        try:
            valor = marca.read_text(encoding='ascii').strip()
            ultima = timezone.datetime.fromisoformat(valor)
        except (OSError, ValueError):
            ultima = None
    disponible = bool(ultima and timezone.now() - ultima <= timedelta(seconds=45))
    return Response({'estado': 'DISPONIBLE' if disponible else 'NO_DISPONIBLE', 'ultima_actividad': ultima.isoformat() if ultima else None})
