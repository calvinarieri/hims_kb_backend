import re
from django.conf import settings
from django.db import models
from product.models import Product, ProductVersion
from openai import OpenAI

api_key = getattr(settings, 'OPENROUTER_API_KEY', None) or getattr(settings, 'OPENAI_API_KEY', None)
client = OpenAI(
    api_key=api_key or "dummy-key-for-init",
    base_url=getattr(settings, 'OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1'),
)


class ProductUpdates:
    @staticmethod
    def generate_next_version(product):
        latest_version_obj = product.versions.order_by('-created_at').first()
        if not latest_version_obj:
            return "1.0.0"
        
        version_str = latest_version_obj.version
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version_str)
        if match:
            major, minor, patch = map(int, match.groups())
            return f"{major}.{minor}.{patch + 1}"
        
        return f"{version_str}.1"

    @staticmethod
    def _generate_structured_data_summary(raw_description, code_changes):
        """
        Prompts the LLM to analyze the diffs and create a dense, highly structured
        technical summary optimized for future article generation.
        """
        changes_context = ""
        for change in (code_changes or []):
            filename = change.get('filename', 'Unknown File')
            patch = change.get('patch', '') 
            changes_context += f"\nFile: {filename}\nChanges:\n{patch}\n"

        prompt = (
            "You are an advanced technical analyst. Your job is to process a pull request description "
            "and raw code diffs, then generate a comprehensive, structured technical summary. This summary "
            "will be saved in a database and used later by an AI copywriter to write long-form articles.\n\n"
            f"### PR/Commit Description:\n{raw_description}\n\n"
            f"### Raw Code Diffs:\n{changes_context}\n\n"
            "### Output Format Instructions:\n"
            "Generate your response using the following precise Markdown schema:\n\n"
            "## 1. High-Level Concept\n"
            "- **Core Objective**: (What problem does this update solve in plain English?)\n"
            "- **Business/User Impact**: (Why should a non-technical user care?)\n\n"
            "## 2. Technical Deep-Dive\n"
            "- **Architectural Changes**: (What components, modules, or databases were touched?)\n"
            "- **Key Code Logic**: (Explain the actual logic changes found in the diffs, focusing on the 'how')\n\n"
            "## 3. Keywords & Entities\n"
            "- **Technologies Used**: (List libraries, frameworks, APIs, or database queries updated)\n"
            "- **Key Terms**: (Any domain-specific terms relevant to this change)\n\n"
            "Strictly follow this layout. Keep the technical details incredibly precise and factual. "
            "Do not hallucinate features not explicitly present in the description or code diffs."
        )

        try:
            model_name = getattr(settings, 'OPENROUTER_MODEL', 'openai/gpt-5-mini')
            fallback_models = [
                item.strip()
                for item in getattr(settings, 'OPENROUTER_FALLBACK_MODELS', 'meta-llama/llama-3.1-8b-instruct,openai/gpt-5-mini').split(',')
                if item.strip()
            ]
            candidate_models = [model_name] + [m for m in fallback_models if m and m != model_name]

            last_error = None
            for candidate in candidate_models:
                try:
                    response = client.chat.completions.create(
                        model=candidate,
                        messages=[
                            {"role": "system", "content": "You are a technical data extraction engine."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.1,
                        max_tokens=2000,
                    )
                    return response.choices[0].message.content.strip()
                except Exception as exc:
                    last_error = exc
                    status_code = getattr(getattr(exc, 'response', None), 'status_code', None)
                    message_text = str(exc).lower()
                    if status_code == 404 and 'unavailable for free' in message_text:
                        continue
                    raise

            if last_error is not None:
                raise last_error
        except Exception as e:
            print(f"Structured summary generation failed: {e}")
            changed_files = [file.get('filename') for file in (code_changes or []) if file.get('filename')]
            files_str = ", ".join(changed_files) if changed_files else "None"
            return f"## 1. High-Level Concept\n- **Core Objective**: {raw_description}\n\n## 2. Technical Deep-Dive\n- **Changed Files**: {files_str}"

    @classmethod
    def handle_github_changes_for_product(cls, product, description, code_changes):
        if not product:
            return None

        if getattr(settings, 'TESTING', False):
            structured_blueprint = f"## 1. High-Level Concept\n- **Core Objective**: {description}"
        else:
            structured_blueprint = cls._generate_structured_data_summary(description, code_changes)

        next_version = cls.generate_next_version(product)

        product_version = ProductVersion.objects.create(
            product=product,
            version=next_version,
            description=structured_blueprint
        )
        return product_version

    @classmethod
    def handle_github_changes(cls, repo_url, description, code_changes):
        repo_name = repo_url.rstrip('/').split('/')[-1] if repo_url else ''
        product = Product.objects.filter(
            models.Q(github_url__iexact=repo_url) | models.Q(name__iexact=repo_name)
        ).first()
        
        if not product:
            print(f"Product not found for repository: {repo_url}")
            return None

        return cls.handle_github_changes_for_product(product, description, code_changes)