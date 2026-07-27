from django.urls import path
from .views import (
    login,
    admin_staff_view,
    admin_role_view,
    admin_product_view,
    admin_product_version_view,
    CookieTokenRefreshView,
)
from rest_framework_simplejwt.views import (
    TokenBlacklistView
)

urlpatterns = [
    path('login/', login, name='login'),
    path('admin/staff/', admin_staff_view, name='admin-staff'),
    path('admin/roles/', admin_role_view, name='admin-roles'),
    path('admin/products/', admin_product_view, name='admin-products'),
    path('refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', TokenBlacklistView.as_view(), name='token_blacklist'),
    path('admin/product-versions/', admin_product_version_view, name='admin-product-versions'),
] 