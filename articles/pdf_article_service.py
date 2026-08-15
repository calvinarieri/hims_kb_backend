import logging
import re
from typing import List

from django.db import transaction

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

from articles.models import Articles, ArticlesVersion, Category
from product.models import Product, ProductVersion

logger = logging.getLogger(__name__)


class PDFArticleImportService:
    @staticmethod
    def _clean_text(raw_text: str) -> str:
        text = (raw_text or "").replace("\x00", "")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @classmethod
    def extract_text_from_pdf(cls, uploaded_file) -> str:
        if uploaded_file is None:
            raise ValueError("A PDF file is required.")

        if PdfReader is None:
            raise ImportError("The PDF parser dependency is not installed. Add 'pypdf' to requirements.txt and install dependencies.")

        reader = PdfReader(uploaded_file)
        pages = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append(page_text)

        text = "\n\n".join(pages)
        cleaned_text = cls._clean_text(text)
        if not cleaned_text:
            raise ValueError("The uploaded PDF could not be parsed into readable text.")
        return cleaned_text

    @staticmethod
    def _split_sections(text: str, max_chars: int = 2500) -> List[str]:
        text = (text or "").strip()
        if not text:
            return []

        chunks = []
        current = ""
        for block in re.split(r"\n\s*\n+", text):
            block = block.strip()
            if not block:
                continue
            if len(current) + len(block) + 2 <= max_chars:
                current = f"{current}\n\n{block}" if current else block
            else:
                if current:
                    chunks.append(current)
                current = block

        if current:
            chunks.append(current)

        if not chunks:
            chunks = [text]

        return chunks

    @staticmethod
    def _best_title_from_text(text: str) -> str:
        candidates = [line.strip() for line in text.splitlines() if line.strip()]
        for candidate in candidates[:8]:
            cleaned = re.sub(r"\s+", " ", candidate)
            if len(cleaned.split()) <= 12 and len(cleaned) <= 80:
                return cleaned
        title = re.sub(r"\s+", " ", candidates[0][:80]).strip()
        return title or "Imported knowledge article"

    @staticmethod
    def _article_html_from_text(title: str, body_text: str) -> str:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", body_text) if p.strip()]
        if not paragraphs:
            return f"<h1>{title}</h1>"

        html_parts = [f"<h1>{title}</h1>"]
        for paragraph in paragraphs[:8]:
            text = re.sub(r"\s+", " ", paragraph)
            html_parts.append(f"<p>{text}</p>")
        return "".join(html_parts)

    @classmethod
    def resolve_product_version(cls, product_id=None, product_version_id=None):
        if product_version_id:
            return ProductVersion.objects.select_related('product').get(id=product_version_id)

        if product_id:
            product = Product.objects.get(id=product_id)
            return product.versions.order_by('-created_at').first() or ProductVersion.objects.create(
                product=product,
                version='PDF-import',
                description='Auto-created from imported PDF document.',
            )

        raise ValueError("A product_id or product_version_id is required.")

    @classmethod
    def import_pdf_to_articles(cls, uploaded_file, user, product_id=None, product_version_id=None, category_name='General'):
        text = cls.extract_text_from_pdf(uploaded_file)
        sections = cls._split_sections(text)
        if not sections:
            raise ValueError("The uploaded PDF did not contain readable content.")

        product_version = cls.resolve_product_version(product_id=product_id, product_version_id=product_version_id)
        category = Category.objects.filter(name=category_name).first()
        if not category:
            category = Category.objects.create(
                name=category_name,
                description='Auto-generated content from uploaded PDF documents.'
            )

        created_articles = []
        with transaction.atomic():
            for section in sections[:10]:
                title = cls._best_title_from_text(section)
                article = Articles.objects.create(
                    title=title,
                    description=(section[:500] if section else '').strip(),
                    category=category,
                    visibility='PUBLIC',
                    status='REVIEW',
                )

                article_html = cls._article_html_from_text(title, section)
                version = ArticlesVersion.objects.create(
                    article=article,
                    product_version=product_version,
                    content=article_html,
                    changes=f"Imported from uploaded PDF document and split into an article.",
                    status='REVIEW',
                    author=user,
                    reviewed_by=user if getattr(user, 'is_staff', False) else None,
                )

                created_articles.append({
                    'id': str(article.id),
                    'title': article.title,
                    'status': article.status,
                    'version_id': str(version.id),
                    'content': article_html,
                })

        return {
            'product_id': str(product_version.product_id),
            'product_version_id': str(product_version.id),
            'section_count': len(sections),
            'articles': created_articles,
        }
