import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from .utils import ProductUpdates

class GithubMergeWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        github_event = request.META.get('HTTP_X_GITHUB_EVENT')
        if github_event != 'pull_request':
            return Response(status=status.HTTP_204_NO_CONTENT)

        payload = request.data
        action = payload.get('action')
        pull_request = payload.get('pull_request', {})
        is_merged = pull_request.get('merged', False)

        if action == 'closed' and is_merged:
            repo_url = payload.get('repository', {}).get('html_url', '')

            pr_description = pull_request.get('body', '')
            files_url = pull_request.get('url', '') + '/files'
            
            headers = {
                'Accept': 'application/vnd.github+json' , 
                # if security is required goes here
            }
            files_response = requests.get(files_url, headers=headers)
            code_changes = files_response.json() if files_response.status_code == 200 else []

            for file_data in code_changes:
                filename = file_data.get('filename')
                patch = file_data.get('patch')
            ProductUpdates().handle_github_changes(
                repo_url=repo_url, 
                description=pr_description, 
                code_changes= {
                    'filename': filename,
                    'patch' : patch
                }
                )
            return Response({"status": "Processed merge successfully"}, status=status.HTTP_200_OK)

        return Response(status=status.HTTP_204_NO_CONTENT)
