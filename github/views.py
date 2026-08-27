import requests
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from product.models import Product
from .utils import ProductUpdates


class GithubMergeWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, webhook_token=None):
        payload = request.data or {}

        # 1. Identify product by webhook_token identifier or fallback lookup
        product = None
        if webhook_token:
            product = Product.objects.filter(webhook_token=webhook_token).first()

        if not product:
            repo_url = payload.get('repository', {}).get('html_url', '')
            if repo_url:
                repo_name = repo_url.rstrip('/').split('/')[-1]
                product = Product.objects.filter(
                    Q(github_url__iexact=repo_url) | Q(name__iexact=repo_name)
                ).first()

        if not product:
            return Response(
                {"detail": "Product not found for the provided webhook identifier."},
                status=status.HTTP_404_NOT_FOUND
            )

        # 2. Check event header
        github_event = request.META.get('HTTP_X_GITHUB_EVENT', 'pull_request')
        if github_event == 'ping':
            return Response({"status": "Pong! Webhook active for product.", "product": product.name}, status=status.HTTP_200_OK)

        action = payload.get('action')
        pull_request = payload.get('pull_request', {})
        is_merged = pull_request.get('merged', False)

        # Allow test payloads or PR closed & merged events
        if (action == 'closed' and is_merged) or payload.get('test_mode', False):
            pr_description = pull_request.get('body', '') or payload.get('description', '')
            files_url = pull_request.get('url', '') + '/files' if pull_request.get('url') else None

            code_changes = []
            if files_url:
                try:
                    headers = {'Accept': 'application/vnd.github+json'}
                    files_response = requests.get(files_url, headers=headers, timeout=5)
                    if files_response.status_code == 200:
                        raw_files = files_response.json()
                        for file_data in raw_files:
                            code_changes.append({
                                'filename': file_data.get('filename'),
                                'patch': file_data.get('patch')
                            })
                except Exception:
                    pass

            if not code_changes and 'code_changes' in payload:
                code_changes = payload.get('code_changes')
                if isinstance(code_changes, dict):
                    code_changes = [code_changes]

            product_version = ProductUpdates().handle_github_changes_for_product(
                product=product,
                description=pr_description,
                code_changes=code_changes
            )

            return Response(
                {
                    "status": "Processed merge successfully",
                    "product": product.name,
                    "version": product_version.version if product_version else None
                },
                status=status.HTTP_200_OK
            )

        return Response(status=status.HTTP_204_NO_CONTENT)
