from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, ProductVersionViewSet

router = DefaultRouter()
router.register(r'actual', ProductViewSet, basename='admin-product')
router.register(r'products', ProductViewSet, basename='admin-products')
router.register(r'versions', ProductVersionViewSet, basename='admin-product-version')

urlpatterns = [
    path('', include(router.urls)),
]