from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ProfesorViewSet


router = DefaultRouter()
router.register('profesores', ProfesorViewSet, basename='profesor')

urlpatterns = [
    path('', include(router.urls)),
]
