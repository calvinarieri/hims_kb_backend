import logging

from django.core.management.base import BaseCommand

from articles.models import ArticlesVersion
from chat.services import ChatbotService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Generate embeddings for existing article versions if they are missing or stale."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Regenerate embeddings even when already present.")
        parser.add_argument("--limit", type=int, default=0, help="Maximum versions to process (0 = all).")

    def handle(self, *args, **options):
        queryset = ArticlesVersion.objects.select_related("article").order_by("created_at")
        if options["limit"]:
            queryset = queryset[: options["limit"]]

        processed = 0
        missing_or_stale = 0
        for version in queryset:
            if options["force"] or not getattr(version, "embedding", None):
                missing_or_stale += 1
                text = getattr(version.article, "title", "") + "\n\n" + (getattr(version, "content", "") or "")
                if text.strip():
                    ChatbotService.generate_article_embedding(version, force=True)
                    processed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {processed} article version embeddings; {missing_or_stale} versions needed embedding generation."
            )
        )
