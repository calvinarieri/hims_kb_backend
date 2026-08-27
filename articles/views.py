import hashlib
import logging
from django.core.cache import cache
from django.db.models import Q, Avg, Count
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import *
from .permision import CanReadArticle, IsAuthorOrAdminForWrite, IsStaffOrAdminUser, CanApproveArticle
from .serializers import (
    ArticleDetailSerializer,
    ArticleImageSerializer,
    ArticlesSerializer,
    ArticlesVersionSerializer,
    ArticleTagSerializer,
    CategorySerializer,
    TagSerializer,
)
from feedback.serializers import ArticleFeedbackSerializer
from feedback.models import ArticleFeedback
from chat.models import ChatFeedback, ChatMessage
from .pdf_article_service import PDFArticleImportService


logger = logging.getLogger(__name__)

CACHE_TTL = 3600  


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class ArticlesViewSet(viewsets.ModelViewSet):
    queryset = Articles.objects.select_related('category').prefetch_related(
        'article_tags__tag', 'versions', 'images'
    )

    def get_permissions(self):
        if self.action == 'submit_for_review':
            return [IsStaffOrAdminUser(), IsAuthorOrAdminForWrite()]
        if self.action == 'approve':
            return [CanApproveArticle()]
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsStaffOrAdminUser(), IsAuthorOrAdminForWrite()]
        return [CanReadArticle()]

    def get_serializer_class(self):
        if self.action in ['retrieve', 'list', 'staff_articles']:
            return ArticleDetailSerializer
        return ArticlesSerializer

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()

        if not (user and user.is_authenticated and user.is_staff):
            return qs.filter(visibility='PUBLIC', status='PUBLISHED')

        return qs

    def retrieve(self, request, *args, **kwargs):
        article_pk = kwargs.get('pk')
        cache_key = f"article_detail_{article_pk}"
        
        try:
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.debug(f"Cache HIT for article detail. Key: {cache_key}")
                return Response(cached_data)
        except Exception:
            logger.exception(f"Error fetching cache for key: {cache_key}")

        logger.debug(f"Cache MISS for article detail. Key: {cache_key}")
        response = super().retrieve(request, *args, **kwargs)
        
        try:
            cache.set(cache_key, response.data, CACHE_TTL)
        except Exception:
            logger.exception(f"Error setting cache for key: {cache_key}")

        return response

    @action(detail=False, methods=['get'], permission_classes=[IsStaffOrAdminUser], url_path='staff-articles')
    def staff_articles(self, request):
        user = request.user

        if not user or not user.is_authenticated:
            logger.warning("Unauthenticated access attempt to staff_articles endpoint.")
            return Response(
                {"detail": "Authentication credentials were not provided."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        cache_key = f"staff_articles_user_{user.id if not user.is_superuser else 'admin_all'}"
        
        try:
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.debug(f"Cache HIT for staff_articles. User ID: {user.id}")
                return Response(cached_data, status=status.HTTP_200_OK)
        except Exception:
            logger.exception(f"Error checking cache for staff_articles. Key: {cache_key}")

        logger.info(f"Generating staff articles response for User ID: {user.id} (Superuser: {user.is_superuser})")

        if user.is_superuser:
            articles = self.get_queryset()
        else:
            articles = self.get_queryset().filter(versions__author=user).distinct()

        serializer = ArticleDetailSerializer(articles, many=True)
        data = serializer.data

        try:
            cache.set(cache_key, data, CACHE_TTL)
        except Exception:
            logger.exception(f"Error saving staff_articles to cache. Key: {cache_key}")

        return Response(data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsStaffOrAdminUser, IsAuthorOrAdminForWrite], url_path='submit-for-review')
    def submit_for_review(self, request, pk=None):
        article = self.get_object()
        
        # Enforce at least 2 tags attached before submission
        tag_count = article.article_tags.count()
        if tag_count < 2:
            return Response(
                {
                    'status_code': status.HTTP_400_BAD_REQUEST,
                    'detail': f"Article must have at least 2 tags attached before submitting for review/approval (currently has {tag_count})."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info(f"User {request.user} is submitting article ID {article.id} ('{article.title}') for approval/review.")
        
        article.status = 'REVIEW'
        article.save()

        # Update draft versions to REVIEW status
        article.versions.filter(status='DRAFT').update(status='REVIEW')

        serializer = ArticleDetailSerializer(article)
        return Response(
            {
                'status_code': status.HTTP_200_OK,
                'message': f"Article '{article.title}' submitted for approval successfully.",
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], permission_classes=[CanApproveArticle], url_path='approve')
    def approve(self, request, pk=None):
        article = self.get_object()
        logger.info(f"User {request.user} is approving article ID {article.id} ('{article.title}') for publication.")
        
        article.status = 'PUBLISHED'
        article.save()

        # Mark draft/review versions as published
        article.versions.filter(status__in=['DRAFT', 'REVIEW']).update(
            status='PUBLISHED',
            reviewed_by=request.user
        )

        serializer = ArticleDetailSerializer(article)
        return Response(
            {
                'status_code': status.HTTP_200_OK,
                'message': f"Article '{article.title}' approved and published successfully.",
                'data': serializer.data
            },
            status=status.HTTP_200_OK
        )


class ArticleTagViewSet(viewsets.ModelViewSet):
    queryset = ArticleTag.objects.select_related('article', 'tag').all()
    serializer_class = ArticleTagSerializer
    permission_classes = [IsStaffOrAdminUser]


class ArticlesVersionViewSet(viewsets.ModelViewSet):
    queryset = ArticlesVersion.objects.select_related('article', 'product_version', 'author', 'reviewed_by').all()
    serializer_class = ArticlesVersionSerializer
    permission_classes = [IsStaffOrAdminUser]


class ArticleImageViewSet(viewsets.ModelViewSet):
    queryset = ArticleImage.objects.select_related('article', 'article_version', 'uploaded_by').all()
    serializer_class = ArticleImageSerializer
    permission_classes = [IsStaffOrAdminUser]


class ImmersiveSearchAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        query = request.query_params.get('q', '').strip()
        user = request.user
        
        if not query:
            logger.info("Search requested without query parameter 'q'.")
            return Response(
                {"detail": "Please provide a search term using the 'q' parameter."},
                status=status.HTTP_400_BAD_REQUEST
            )

        is_staff = bool(user and user.is_authenticated and user.is_staff)
        cache_hash = hashlib.md5(f"{query}_{is_staff}".encode('utf-8')).hexdigest()
        cache_key = f"search_results_{cache_hash}"

        try:
            cached_response = cache.get(cache_key)
            if cached_response:
                logger.debug(f"Cache HIT for search term: '{query}' (is_staff={is_staff})")
                return Response(cached_response, status=status.HTTP_200_OK)
        except Exception:
            logger.exception(f"Error retrieving search cache for key: {cache_key}")

        logger.info(f"Executing database search query: '{query}' (is_staff={is_staff})")

        base_filter = Q(status='PUBLISHED')

        if not is_staff:
            base_filter &= Q(visibility='PUBLIC')
        else:
            base_filter &= Q(visibility__in=['PUBLIC', 'PRIVATE'])

        search_filter = base_filter & (
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query) |
            Q(article_tags__tag__name__icontains=query) |
            Q(versions__content__icontains=query) |
            Q(versions__changes__icontains=query)
        )

        results = (
            Articles.objects
            .filter(search_filter)
            .select_related('category')
            .prefetch_related('article_tags__tag', 'versions', 'images')
            .distinct()
        )

        serializer = ArticleDetailSerializer(results, many=True)
        response_data = {
            "query": query,
            "results_count": results.count(),
            "results": serializer.data
        }

        try:
            cache.set(cache_key, response_data, CACHE_TTL)
        except Exception:
            logger.exception(f"Failed to cache search results for query: '{query}'")

        return Response(response_data, status=status.HTTP_200_OK)


class DashboardAPIView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request, *args, **kwargs):
        # Basic counts
        total_articles = Articles.objects.count()
        chat_requests = ChatMessage.objects.count()

        # Chat feedback average and distribution
        chat_avg = ChatFeedback.objects.aggregate(avg=Avg('rating'))['avg']
        rating_distribution = (
            ChatFeedback.objects
            .values('rating')
            .annotate(count=Count('id'))
            .order_by('-rating')
        )

        # Article status breakdown
        status_breakdown = (
            Articles.objects
            .values('status')
            .annotate(count=Count('id'))
        )

        # Top/lowest rated articles (based on ArticleFeedback)
        top_articles = (
            ArticleFeedback.objects
            .values('article__id', 'article__title')
            .annotate(avg_rating=Avg('rating'), requests=Count('id'))
            .order_by('-avg_rating')[:5]
        )

        lowest_articles = (
            ArticleFeedback.objects
            .values('article__id', 'article__title')
            .annotate(avg_rating=Avg('rating'), requests=Count('id'))
            .order_by('avg_rating')[:5]
        )

        return Response({
            'total_articles': total_articles,
            'chat_requests': chat_requests,
            'chat_average_rating': chat_avg,
            'chat_rating_distribution': list(rating_distribution),
            'status_breakdown': list(status_breakdown),
            'top_articles': list(top_articles),
            'lowest_articles': list(lowest_articles),
        })


class PDFImportAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        uploaded_file = request.FILES.get('file') or request.FILES.get('pdf')
        if uploaded_file is None:
            return Response(
                {'detail': 'A PDF file is required in the request as "file" or "pdf".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not uploaded_file.name.lower().endswith('.pdf'):
            return Response(
                {'detail': 'Only PDF files are supported.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        product_id = request.data.get('product_id')
        product_version_id = request.data.get('product_version_id')
        category_name = request.data.get('category_name', 'General')

        try:
            result = PDFArticleImportService.import_pdf_to_articles(
                uploaded_file=uploaded_file,
                user=request.user,
                product_id=product_id,
                product_version_id=product_version_id,
                category_name=category_name,
            )
        except (ValueError, ImportError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:  # pragma: no cover
            logger.exception('Failed to import PDF into articles.')
            return Response({'detail': f'Failed to process the PDF: {str(exc)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'status_code': status.HTTP_201_CREATED,
            'message': 'PDF content was split and converted into article records.',
            'data': result,
        }, status=status.HTTP_201_CREATED)


class ArticleFeedbackAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, article_id, *args, **kwargs):
        data = request.data.copy()
        data['article'] = article_id
        serializer = ArticleFeedbackSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        feedback = serializer.save()
        return Response(ArticleFeedbackSerializer(feedback).data, status=status.HTTP_201_CREATED)