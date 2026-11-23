from django.urls import path
from .views import FamiliaView, PanelDirectorView

urlpatterns = [
    path('familia/', FamiliaView.as_view(), name='portal-familia'),
    path('panel-director/', PanelDirectorView.as_view(), name='portal-panel-director'),
]
