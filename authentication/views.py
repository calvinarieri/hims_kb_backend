from rest_framework.permissions import IsAdminUser
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from rest_framework.response import Response
from models import Role  
from serializers import *
import logging

logger = logging.getLogger(__name__)

@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def admin_role_view(request):

    if request.method == 'GET':
        logger.info(f"User {request.user} requested all roles.")
        try:
            roles = Role.objects.all()
            serializer = RoleSerializer(roles, many=True)
            
            logger.info(f"Successfully retrieved {len(roles)} roles.")
            return Response(
                {
                    'status_code': 200, 
                    'message': 'roles retrieved successfully', 
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:

            logger.error(f"Failed to retrieve roles. Error: {str(e)}", exc_info=True)
            return Response(
                {
                    'status_code': 500,
                    'message': 'Internal server error occurred while fetching roles.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )    
   
    if request.method == 'POST':
        logger.info(f"User {request.user} is attempting to create a new role. Payload: {request.data}")
        
        serializer = RoleSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            logger.info(f"Success, new role '{serializer.data.get('name', 'N/A')}' created by {request.user}!")
            return Response(
                {
                    'status_code': 201, 
                    'message': 'role created', 
                    'data': serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        
        logger.warning(f"Validation failed for role creation by {request.user}. Errors: {serializer.errors}")
        return Response(
            {
                'status_code': 400, 
                'message': 'validation failed', 
                'errors': serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    

@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def admin_product_view(request):

    if request.method == 'GET':
        logger.info(f"User {request.user} requested all products.")
        try:

            products = Product.objects.all().prefetch_related('versions')
            serializer = ProductSerializer(products, many=True)
            
            logger.info(f"Successfully retrieved {len(products)} products.")
            return Response(
                {
                    'status_code': 200, 
                    'message': 'products retrieved successfully', 
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Failed to retrieve products. Error: {str(e)}", exc_info=True)
            return Response(
                {
                    'status_code': 500,
                    'message': 'Internal server error occurred while fetching products.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    if request.method == 'POST':
        logger.info(f"User {request.user} is attempting to create a new product. Payload keys: {list(request.data.keys())}")
        
        serializer = ProductSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            logger.info(f"Success, new product '{serializer.data.get('name', 'N/A')}' (ID: {serializer.data.get('id')}) created by {request.user}!")
            return Response(
                {
                    'status_code': 201, 
                    'message': 'product created successfully', 
                    'data': serializer.data
                },
                status=status.HTTP_201_CREATED
            )

        logger.warning(f"Validation failed for product creation by {request.user}. Errors: {serializer.errors}")
        return Response(
            {
                'status_code': 400, 
                'message': 'validation failed', 
                'errors': serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def admin_product_version_view(request):

    if request.method == 'GET':
        logger.info(f"User {request.user} requested all product versions.")
        try:

            versions = ProductVersion.objects.all().select_related('product')
            serializer = ProductVersionSerializer(versions, many=True)
            
            logger.info(f"Successfully retrieved {len(versions)} product versions.")
            return Response(
                {
                    'status_code': 200, 
                    'message': 'product versions retrieved successfully', 
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Failed to retrieve product versions. Error: {str(e)}", exc_info=True)
            return Response(
                {
                    'status_code': 500,
                    'message': 'Internal server error occurred while fetching product versions.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
  
    if request.method == 'POST':
        logger.info(f"User {request.user} is attempting to create a new version. Payload: {request.data}")
        
        serializer = ProductVersionSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            
            version_name = serializer.data.get('version', 'N/A')
            product_id = serializer.data.get('product', 'N/A')
            
            logger.info(f"Success, version '{version_name}' for product ID {product_id} created by {request.user}!")
            return Response(
                {
                    'status_code': 201, 
                    'message': 'product version created successfully', 
                    'data': serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        
        logger.warning(f"Validation failed for version creation by {request.user}. Errors: {serializer.errors}")
        return Response(
            {
                'status_code': 400, 
                'message': 'validation failed', 
                'errors': serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )