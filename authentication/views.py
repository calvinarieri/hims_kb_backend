from rest_framework.permissions import IsAdminUser, AllowAny
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from models import Role  
from serializers import *
import logging

logger = logging.getLogger(__name__)

@api_view(['POST', 'GET'])
@permission_classes([IsAdminUser])
def admin_staff_view(request):

    if request.method == 'GET':
        logger.info(f"User {request.user} requested all staff members.")
        try:
            staff = User.objects.filter(is_staff=True)
            serializer = UserSerializer(staff, many=True)

            logger.info(f"Successfully retrieved {len(staff)} staff members.")
            return Response(
                {
                    'status_code': 200,
                    'message': 'staff members retrieved successfully',
                    'data': serializer.data
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Failed to retrieve staff members. Error: {str(e)}", exc_info=True)
            return Response(
                {
                    'status_code': 500,
                    'message': 'Internal server error occurred while fetching staff members.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
  
    if request.method == 'POST':
        logger.info(f"User {request.user} is attempting to create a new staff account.")
        
        serializer = UserSerializer(data=request.data)

        if serializer.is_valid():

            serializer.save(is_staff=True)            
            username = serializer.data.get('email', 'N/A')
            logger.info(f"Success, new staff account '{username}' created by {request.user}!")
            return Response(
                {
                    'status_code': 201,
                    'message': 'staff member created successfully',
                    'data': serializer.data
                },
                status=status.HTTP_201_CREATED
            )

        logger.warning(f"Validation failed for staff creation by {request.user}. Errors: {serializer.errors}")
        return Response(
            {
                'status_code': 400,
                'message': 'validation failed',
                'errors': serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    data = request.data
    email = data.get('email', None)
    password = data.get('password', None)

    if not (email and password):
        logger.error('Credentials not provided')
        return Response(
            data={'status_code': 400, 'message': 'Missing credentials'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = User.objects.get(email=email)
        
        if user.check_password(password):
            if not user.is_active:
                logger.warning(f"Login rejected: Account is inactive for email: {email}")
                return Response(
                    data={'status_code': 403, 'message': 'Account is disabled.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            logger.info(f"User {email} authenticated successfully. Generating tokens... ")
            
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)

            response = Response(
                data={
                    'status_code': 200, 
                    'message': 'Login successful',
                    'user': {
                        'id': user.id,
                        'email': user.email
                    }
                },
                status=status.HTTP_200_OK
            )

            response.set_cookie(
                key='access_token',
                value=access_token,
                httponly=True,        
                secure=False,         
                samesite='Lax',       
                max_age=15 * 60   # TODO: Match your token lifetime     
            )
        
            response.set_cookie(
                key='refresh_token',
                value=refresh_token,
                httponly=True,
                secure=False,         
                samesite='Lax',
                max_age=24 * 60 * 60  # TODO: Match your token lifetime 
            )

            logger.info(f"Cookies baked and set successfully for {email}!")
            return response

        else:
            logger.warning(f"Login failed: Incorrect password for email {email}.")
            return Response(
                data={'status_code': 401, 'message': 'Invalid email or password.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

    except User.DoesNotExist:
        # Keep response generic for security reasons (prevents account harvesting)
        logger.warning(f"Login failed: Email {email} does not exist.")
        return Response(
            data={'status_code': 401, 'message': 'Invalid email or password.'},
            status=status.HTTP_401_UNAUTHORIZED
        )
        
    except Exception as e:
        logger.error(f"Unexpected error during login execution: {str(e)}", exc_info=True)
        return Response(
            data={'status_code': 500, 'message': 'Internal server error occurred.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

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