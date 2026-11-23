from uuid import uuid4


class AuditCorrelationMiddleware:
    """Asigna una correlación propia del servidor a cada solicitud HTTP."""

    header_name = 'X-Correlation-ID'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.audit_correlation_id = uuid4()
        response = self.get_response(request)
        response[self.header_name] = str(request.audit_correlation_id)
        return response
