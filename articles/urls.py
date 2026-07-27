from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TagViewSet, CategoryViewSet, ArticlesViewSet,
    ArticleTagViewSet, ArticlesVersionViewSet, ArticleImageViewSet,
    ImmersiveSearchAPIView
)

router = DefaultRouter()
router.register(r'tags', TagViewSet, basename='tag')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'articles', ArticlesViewSet, basename='article')
router.register(r'article-tags', ArticleTagViewSet, basename='articletag')
router.register(r'versions', ArticlesVersionViewSet, basename='articlesversion')
router.register(r'images', ArticleImageViewSet, basename='articleimage')

urlpatterns = [
    # Search API Endpoint
    path('search/', ImmersiveSearchAPIView.as_view(), name='immersive-search'),
    
    # Router API Endpoints
    path('', include(router.urls)),
]