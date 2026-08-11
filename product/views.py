import logging
from rest_framework import viewsets, status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from .models import Product, ProductVersion
from .serializers import ProductSerializer, ProductVersionSerializer

logger = logging.getLogger(__name__)


class ProductViewSet(viewsets.ModelViewSet):
    """
    ViewSet providing full CRUD functionality for Products:
    - GET /api/products/          -> List products
    - POST /api/products/         -> Create product
    - GET /api/products/{id}/     -> Retrieve product details
    - PUT/PATCH /api/products/{id}/ -> Update product
    - DELETE /api/products/{id}/  -> Delete product
    """
    queryset = Product.objects.all().prefetch_related('versions')
    serializer_class = ProductSerializer
    permission_classes = [IsAdminUser]

    def list(self, request, *args, **kwargs):
        logger.info(f"User {request.user} requested all products.")
        response = super().list(request, *args, **kwargs)
        return Response({
            'status_code': status.HTTP_200_OK,
            'message': 'Products retrieved successfully',
            'data': response.data
        }, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        logger.info(f"User {request.user} attempting to create product with payload keys: {list(request.data.keys())}")
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            self.perform_create(serializer)
            logger.info(f"Success, product '{serializer.data.get('name', 'N/A')}' (ID: {serializer.data.get('id')}) created by {request.user}!")
            return Response({
                'status_code': status.HTTP_201_CREATED,
                'message': 'Product created successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        
        logger.warning(f"Validation failed for product creation by {request.user}. Errors: {serializer.errors}")
        return Response({
            'status_code': status.HTTP_400_BAD_REQUEST,
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class ProductVersionViewSet(viewsets.ModelViewSet):
    """
    ViewSet providing full CRUD functionality for Product Versions:
    - GET /api/product-versions/          -> List product versions
    - POST /api/product-versions/         -> Create product version
    - GET /api/product-versions/{id}/     -> Retrieve version details
    - PUT/PATCH /api/product-versions/{id}/ -> Update version
    - DELETE /api/product-versions/{id}/  -> Delete version
    """
    queryset = ProductVersion.objects.all().select_related('product')
    serializer_class = ProductVersionSerializer
    permission_classes = [IsAdminUser]

    def list(self, request, *args, **kwargs):
        logger.info(f"User {request.user} requested all product versions.")
        response = super().list(request, *args, **kwargs)
        return Response({
            'status_code': status.HTTP_200_OK,
            'message': 'Product versions retrieved successfully',
            'data': response.data
        }, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        logger.info(f"User {request.user} attempting to create version. Payload: {request.data}")
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            self.perform_create(serializer)
            logger.info(f"Success, version created by {request.user}!")
            return Response({
                'status_code': status.HTTP_201_CREATED,
                'message': 'Product version created successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
            
        logger.warning(f"Validation failed for version creation by {request.user}. Errors: {serializer.errors}")
        return Response({
            'status_code': status.HTTP_400_BAD_REQUEST,
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)