import re
from hims_kb.settings import OPENAI_API_KEY
from product.models import *
from openai import OpenAI

client = OpenAI(api_key=OPENAI_API_KEY)

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
        for change in code_changes:
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
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Using mini here because it's fast, cheap, and excellent at structured extraction
                messages=[
                    {"role": "system", "content": "You are a technical data extraction engine."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1  # Keep it hyper-factual and strictly grounded in the code
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Structured summary generation failed: {e}")
            # Fallback format matching the structural vibe
            changed_files = [file.get('filename') for file in code_changes if file.get('filename')]
            files_str = ", ".join(changed_files)
            return f"## 1. High-Level Concept\n- **Core Objective**: {raw_description}\n\n## 2. Technical Deep-Dive\n- **Changed Files**: {files_str}"

    @classmethod
    def handle_github_changes(cls, repo_url, description, code_changes):
        repo_name = repo_url.rstrip('/').split('/')[-1]
        product = Product.objects.filter(name__iexact=repo_name).first()
        
        if not product:
            print(f"Product not found for repository: {repo_url}")
            return None

        # 1. Generate the dense blueprint data
        structured_blueprint = cls._generate_structured_data_summary(description, code_changes)

        # 2. Generate next version string
        next_version = cls.generate_next_version(product)

        # 3. Save the blueprint into the description field for future processing
        product_version = ProductVersion.objects.create(
            product=product,
            version=next_version,
            description=structured_blueprint
        )
        return product_version