import logging
import re
from django.db.models import Q

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from articles.models import Articles, ArticlesVersion, Category
from articles.impact_service import ArticleImpactService
from authentication.models import User
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

    @staticmethod
    def _extract_keywords(text):
        if not text:
            return []

        matches = re.findall(r"[A-Za-z][A-Za-z0-9\-/ ]{2,}", text)
        tokens = []
        for token in matches:
            clean = token.strip().lower().replace('-', ' ')
            if len(clean) < 3:
                continue
            clean = ' '.join(part for part in clean.split() if len(part) > 2)
            if clean:
                tokens.append(clean)
        return list(dict.fromkeys(tokens))[:12]

    @staticmethod
    def _tokenize(text):
        if not text:
            return []
        return [token for token in re.findall(r"[A-Za-z0-9]+", text.lower()) if len(token) > 2]

    @classmethod
    def _score_article_match(cls, article, description):
        latest_version = article.versions.order_by('-created_at').first()
        latest_content = latest_version.content if latest_version else ''
        content_text = ' '.join([
            article.description or '',
            latest_content,
            description or '',
        ])

        target_tokens = set(cls._tokenize(description or ''))
        article_tokens = set(cls._tokenize(content_text))

        overlap = len(target_tokens & article_tokens)
        if not overlap:
            return 0

        exact_phrase_match = any(term in (latest_content or '').lower() for term in cls._tokenize(description or ''))
        if exact_phrase_match:
            overlap += 2

        return overlap

    @staticmethod
    def _build_article_title(product, product_version, source_description):
        base = (product.name or 'Product').strip() or 'Product'
        text = (source_description or '').strip()
        if not text:
            return f"{base} {product_version.version} update"

        first_line = text.splitlines()[0].strip()
        short_summary = re.sub(r"\s+", " ", first_line)
        short_summary = short_summary[:38].strip()
        if len(short_summary) >= 38:
            short_summary = short_summary.rstrip() + '...'

        # Keep the title intentionally short and separate from the detailed description content.
        return f"{base}: {short_summary}" if short_summary else f"{base} {product_version.version} update"

    @staticmethod
    def _rewrite_workflow_from_change(previous_content, description):
        previous_text = (previous_content or '').strip()
        new_description = (description or '').strip()

        if new_description:
            return new_description

        if previous_text:
            return previous_text

        return 'The current process has been updated to match the latest product behaviour and should be followed in daily operations.'

    @classmethod
    def _format_openfront_article(cls, product, product_version, description, previous_content=None):
        clean_description = (description or '').strip()
        workflow_text = cls._rewrite_workflow_from_change(previous_content, clean_description)
        short_title = cls._build_article_title(product, product_version, clean_description)
        product_name = (product.name or 'Product').strip() or 'Product'

        previous_text = (previous_content or '').strip()
        base_context = previous_text if previous_text else "Use the latest product process and follow the updated workflow described below."

        return (
            f"<h1>{short_title}</h1>"
            f"<p>{workflow_text}</p>"
            f"<p>{clean_description if clean_description else 'The current product process should be followed in day-to-day operations.'}</p>"
            f"<p>Teams should follow this guidance when working in {product_name}. Use the current process instead of older instructions that may no longer match the live product behaviour.</p>"
            f"<p>{base_context}</p>"
        )

    def _is_article_affected(self, product, article, description):
        if not description:
            return False

        latest_version = article.versions.order_by('-created_at').first()
        latest_content = (latest_version.content if latest_version else '') or ''
        comparison_text = ' '.join([
            article.description or '',
            latest_content,
            description,
        ]).lower()

        description_tokens = set(self._tokenize(description))
        if not description_tokens:
            return False

        content_tokens = set(self._tokenize(comparison_text))
        overlap = len(description_tokens & content_tokens)
        if overlap > 0:
            return True

        return product.name.lower() in comparison_text

    def _sync_article_for_version(self, product, product_version, article, description, user):
        normalized_description = (description or '').strip()
        article_title = article.title or self._build_article_title(product, product_version, normalized_description)

        new_description = (article.description or '').strip()
        if normalized_description and normalized_description not in new_description:
            if new_description:
                article.description = f"{new_description}\n\n{normalized_description}"
            else:
                article.description = normalized_description

        article.status = 'REVIEW'
        article.title = article_title
        article.save(update_fields=['description', 'status', 'title', 'updated_at'])

        latest_version = article.versions.order_by('-created_at').first()
        previous_content = latest_version.content if latest_version else None
        html_content = self._format_openfront_article(product, product_version, normalized_description, previous_content=previous_content)

        if latest_version:
            latest_version.content = html_content
            latest_version.changes = f"Synced from product version {product_version.version} using OpenFront article structure"
            latest_version.status = 'REVIEW'
            latest_version.save(update_fields=['content', 'changes', 'status', 'updated_at'])
        else:
            latest_version = ArticlesVersion.objects.create(
                article=article,
                product_version=product_version,
                content=html_content,
                changes=f"Synced from product version {product_version.version} using OpenFront article structure",
                status='REVIEW',
                author=user,
                reviewed_by=user if user.is_staff else None,
            )

        if hasattr(latest_version, 'article') and latest_version.article:
            latest_version.article.description = article.description
            latest_version.article.save(update_fields=['description', 'status', 'title', 'updated_at'])

        return article

    def _create_article_for_version(self, product, product_version, description, user):
        category = Category.objects.order_by('id').first()
        if not category:
            category = Category.objects.create(
                name='General',
                description='Auto-generated product documentation'
            )

        article_body = self._format_openfront_article(product, product_version, description)

        article = Articles.objects.create(
            title=self._build_article_title(product, product_version, description),
            description=description,
            category=category,
            visibility='PUBLIC',
            status='REVIEW',
        )

        ArticlesVersion.objects.create(
            article=article,
            product_version=product_version,
            content=article_body,
            changes=f"Created from product version {product_version.version} using OpenFront article structure",
            status='REVIEW',
            author=user,
            reviewed_by=user if user.is_staff else None,
        )
        return article

    @action(detail=False, methods=['post'], url_path='semantic-impact')
    def semantic_impact(self, request, *args, **kwargs):
        change_description = request.data.get('description') or request.data.get('change_description')
        product_id = request.data.get('product_id')
        limit = request.data.get('limit', 20)

        if not change_description:
            return Response({
                'status_code': status.HTTP_400_BAD_REQUEST,
                'message': 'A change description is required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            limit_value = int(limit)
        except (TypeError, ValueError):
            limit_value = 20

        if product_id:
            try:
                Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                return Response({
                    'status_code': status.HTTP_404_NOT_FOUND,
                    'message': 'Product not found.'
                }, status=status.HTTP_404_NOT_FOUND)

        result = ArticleImpactService.process_change(change_description, product_id=product_id, limit=limit_value)
        return Response({
            'status_code': status.HTTP_200_OK,
            'message': 'Semantic impact analysis completed.',
            **result,
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='sync-articles')
    def sync_articles(self, request, *args, **kwargs):
        product_id = request.data.get('product_id')
        product_version_id = request.data.get('product_version_id')
        edited_description = request.data.get('description')

        if not product_id or not product_version_id:
            return Response({
                'status_code': status.HTTP_400_BAD_REQUEST,
                'message': 'Both product_id and product_version_id are required.'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({
                'status_code': status.HTTP_404_NOT_FOUND,
                'message': 'Product not found.'
            }, status=status.HTTP_404_NOT_FOUND)

        try:
            product_version = ProductVersion.objects.get(id=product_version_id, product=product)
        except ProductVersion.DoesNotExist:
            return Response({
                'status_code': status.HTTP_404_NOT_FOUND,
                'message': 'Product version not found for this product.'
            }, status=status.HTTP_404_NOT_FOUND)

        description = (edited_description or product_version.description or '').strip() or (
            f"{product.name} version {product_version.version} introduced an update."
        )

        result = ArticleImpactService.process_change(
            description,
            product_id=str(product.id),
            limit=20,
        )

        if result.get('affected_articles', 0) == 0 and result.get('candidates_found', 0) == 0:
            article = self._create_article_for_version(product, product_version, description, request.user or User.objects.order_by('id').first())
            return Response({
                'status_code': status.HTTP_201_CREATED,
                'message': 'No affected product article was found, so a new review article was created.',
                'product_id': str(product.id),
                'product_version_id': str(product_version.id),
                'created_articles': 1,
                'updated_articles': 0,
                'affected_articles': 0,
                'candidates_found': 0,
                'article': {
                    'id': str(article.id),
                    'title': article.title,
                    'description': article.description,
                    'status': article.status,
                }
            }, status=status.HTTP_201_CREATED)

        if result.get('affected_articles', 0) == 0:
            return Response({
                'status_code': status.HTTP_200_OK,
                'message': 'Semantically relevant candidates were reviewed, but no article in this product was determined to be affected.',
                'product_id': str(product.id),
                'product_version_id': str(product_version.id),
                'updated_articles': 0,
                'created_articles': 0,
                'affected_articles': 0,
                'candidates_found': result.get('candidates_found', 0),
                'description_used': description,
            }, status=status.HTTP_200_OK)

        updated_ids = []
        for entry in result.get('analysis', []):
            version = entry.get('version')
            if entry.get('impact') == 'AFFECTED' and version is not None and getattr(version.article, 'product_version', None) is not None:
                updated_ids.append(str(version.article.id))

        return Response({
            'status_code': status.HTTP_200_OK,
            'message': 'Affected product articles were updated with OpenFront review content from the new version.',
            'product_id': str(product.id),
            'product_version_id': str(product_version.id),
            'updated_articles': result.get('updated_articles', 0),
            'created_articles': 0,
            'affected_articles': result.get('affected_articles', 0),
            'candidates_found': result.get('candidates_found', 0),
            'affected_article_ids': updated_ids,
            'failed_articles': result.get('failed_articles', []),
            'description_used': description,
        }, status=status.HTTP_200_OK)

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