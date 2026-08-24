import logging
import re
from typing import List, Tuple

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
    def _detect_chapter_boundaries(text: str) -> List[Tuple[int, str]]:
        """
        Detect chapter boundaries by looking for common chapter patterns.
        Returns list of (start_position, chapter_title) tuples.
        """
        boundaries = []
        
        # Pattern 1: "Chapter N" or "CHAPTER N"
        for match in re.finditer(r'^(chapter\s+\d+|CHAPTER\s+\d+)[:\s]*(.*?)$', text, re.MULTILINE | re.IGNORECASE):
            boundaries.append((match.start(), match.group(2).strip() or match.group(1)))
        
        # Pattern 2: Numbered sections like "1.", "2.", etc. at line start
        for match in re.finditer(r'^(\d{1,2})[.\s]+([^\n]+?)$', text, re.MULTILINE):
            if int(match.group(1)) <= 100:  # Reasonable chapter limit
                boundaries.append((match.start(), match.group(2).strip()))
        
        # Pattern 3: All-caps headings (potential chapter titles)
        for match in re.finditer(r'^([A-Z][A-Z0-9\s]{3,}?)$', text, re.MULTILINE):
            title = match.group(1).strip()
            if len(title.split()) >= 2:  # At least 2 words
                boundaries.append((match.start(), title))
        
        # Remove duplicates and sort by position
        boundaries = list(set(boundaries))
        boundaries.sort(key=lambda x: x[0])
        
        return boundaries

    @classmethod
    def _split_by_chapters(cls, text: str) -> List[Tuple[str, str]]:
        """
        Split text into chapters. Returns list of (chapter_title, chapter_content) tuples.
        If no chapters detected, treats entire text as one chapter.
        """
        text = (text or "").strip()
        if not text:
            return []

        boundaries = cls._detect_chapter_boundaries(text)
        
        # If no boundaries detected, treat entire text as one chapter
        if not boundaries:
            title = cls._best_title_from_text(text)
            return [(title, text)]
        
        chapters = []
        for i, (start_pos, title) in enumerate(boundaries):
            # Find the end position (start of next chapter or end of text)
            end_pos = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
            
            # Extract chapter content
            content = text[start_pos:end_pos].strip()
            
            # Skip if content is too short
            if len(content) > 50:
                chapters.append((title, content))
        
        # If all chapters were filtered out, return original text
        if not chapters:
            title = cls._best_title_from_text(text)
            return [(title, text)]
        
        return chapters

    @staticmethod
    def _best_title_from_text(text: str) -> str:
        candidates = [line.strip() for line in text.splitlines() if line.strip()]
        for candidate in candidates[:8]:
            cleaned = re.sub(r"\s+", " ", candidate)
            if len(cleaned.split()) <= 12 and len(cleaned) <= 80:
                return cleaned
        title = re.sub(r"\s+", " ", candidates[0][:80]).strip() if candidates else ""
        return title or "Imported knowledge article"

    @staticmethod
    def _article_html_from_text(title: str, body_text: str) -> str:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", body_text) if p.strip()]
        if not paragraphs:
            return f"<h1>{title}</h1>"

        html_parts = [f"<h1>{title}</h1>"]
        for paragraph in paragraphs[:50]:  # Increased from 8 to accommodate full chapters
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
        chapters = cls._split_by_chapters(text)
        if not chapters:
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
            for chapter_title, chapter_content in chapters:
                # Use provided chapter title or extract from content
                title = chapter_title if chapter_title and len(chapter_title) > 3 else cls._best_title_from_text(chapter_content)
                
                article = Articles.objects.create(
                    title=title,
                    description=(chapter_content[:500] if chapter_content else '').strip(),
                    category=category,
                    visibility='PUBLIC',
                    status='REVIEW',
                )

                article_html = cls._article_html_from_text(title, chapter_content)
                version = ArticlesVersion.objects.create(
                    article=article,
                    product_version=product_version,
                    content=article_html,
                    changes=f"Imported from uploaded PDF document as a chapter.",
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
            'chapter_count': len(chapters),
            'articles': created_articles,
        }