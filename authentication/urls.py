from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StaffViewSet, RoleViewSet, login, CookieTokenRefreshView

router = DefaultRouter()
router.register(r'staff', StaffViewSet, basename='staff')
router.register(r'roles', RoleViewSet, basename='role')

urlpatterns = [
    path('', include(router.urls)),
    path('login/', login, name='login'),
    path('token/refresh/', CookieTokenRefreshView.as_view(), name='token-refresh'),
]