import uuid
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from authentication.models import User
from articles.models import Articles, ArticlesVersion, Category, ArticleImage
from product.models import Product, ProductVersion
from chat.services import ChatbotService


class Command(BaseCommand):
    help = "Seed the database with realistic HMIS knowledge-base articles for testing and demos."

    def add_arguments(self, parser):
        parser.add_argument("--product-name", type=str, default="HMIS")
        parser.add_argument("--count", type=int, default=25)
        parser.add_argument("--force", action="store_true", help="Recreate the seed articles for the selected product.")

    def handle(self, *args, **options):
        product_name = options["product_name"]
        count = max(1, options["count"])
        force = options["force"]

        with transaction.atomic():
            product, _ = Product.objects.get_or_create(
                name=product_name,
                defaults={
                    "description": "Health Management Information System for patient, facility, and reporting workflows.",
                    "api_key": f"{slugify(product_name)}-demo-key-{uuid.uuid4().hex[:10]}",
                    "api_secret": "demo-secret",
                    "github_url": "https://github.com/example/hmis",
                },
            )

            user, _ = User.objects.get_or_create(
                email="admin@example.com",
                defaults={
                    "first_name": "System",
                    "last_name": "Administrator",
                    "password": "pbkdf2_sha256$260000$demo$demo",
                    "is_staff": True,
                    "is_superuser": True,
                },
            )

            if force:
                ArticleImage.objects.filter(article_version__product_version__product=product).delete()
                ArticlesVersion.objects.filter(product_version__product=product).delete()
                Articles.objects.filter(versions__product_version__product=product).distinct().delete()
                ProductVersion.objects.filter(product=product).delete()

            version, _ = ProductVersion.objects.get_or_create(
                product=product,
                version="1.0.0",
                defaults={
                    "description": "Initial production-ready HMIS knowledge base for patient care and operational workflows.",
                    "status": "approved",
                },
            )

            category_map = {}
            for category_name in [
                "Patient Care",
                "Operations",
                "Reporting",
                "Security",
                "Administration",
            ]:
                category, _ = Category.objects.get_or_create(name=category_name, defaults={"description": category_name})
                category_map[category_name] = category

            created = 0
            for index, article_data in enumerate(self.article_specs()[:count], start=1):
                category_name = article_data["category"]
                article, was_created = Articles.objects.get_or_create(
                    title=article_data["title"],
                    defaults={
                        "description": article_data["summary"],
                        "category": category_map[category_name],
                        "visibility": article_data.get("visibility", "PUBLIC"),
                        "status": article_data.get("article_status", "PUBLISHED"),
                    },
                )

                if not was_created:
                    article.description = article_data["summary"]
                    article.category = category_map[category_name]
                    article.visibility = article_data.get("visibility", article.visibility)
                    article.status = article_data.get("article_status", article.status)
                    article.save(update_fields=["description", "category", "visibility", "status", "updated_at"])

                content = self.build_content(article_data)
                article_version = ArticlesVersion.objects.create(
                    article=article,
                    product_version=version,
                    content=content,
                    changes=f"Seeded HMIS content for {article_data['title']}.",
                    status=article_data.get("version_status", "PUBLISHED"),
                    author=user,
                    reviewed_by=user,
                )

                image_path = article_data.get("image_path", f"/static/images/hmis/{slugify(article_data['title'])}.png")
                ArticleImage.objects.get_or_create(
                    article=article,
                    article_version=article_version,
                    defaults={
                        "file_name": f"{slugify(article_data['title'])}.png",
                        "file_path": image_path,
                        "file_size": 184200,
                        "mime_type": "image/png",
                        "alt_text": f"{article_data['title']} illustration",
                        "caption": article_data["summary"],
                        "display_order": 1,
                        "uploaded_by": user,
                    },
                )

                try:
                    ChatbotService.generate_article_embedding(article_version, force=True)
                except Exception:
                    self.stdout.write(self.style.WARNING(f"Embedding generation skipped for {article_data['title']} (AI config not available)."))

                created += 1
                self.stdout.write(self.style.SUCCESS(f"Created/updated article {index}: {article.title} [{article.visibility}] [{article.status}]"))

            self.stdout.write(self.style.SUCCESS(f"Seeded {created} HMIS articles for product '{product.name}'."))

    @staticmethod
    def article_specs():
        return [
            {
                "title": "Patient Registration",
                "summary": "How patients are officially registered, assigned to a clinic, and confirmed for service delivery.",
                "category": "Patient Care",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/patient-registration.png",
                "sections": [
                    "Patients can register using their national ID, phone number, birth date, or a hospital reference number to create a unique patient record.",
                    "The registration workflow validates identity, confirms demographic accuracy, assigns the patient to a facility or clinic, and checks whether they have an active appointment or pending visit.",
                    "After registration, the person is enrolled in the relevant service queue and the institution retains the legal identity, contact data, and consent history necessary for continuity of care.",
                    "If a patient already exists in the system, the workflow should prevent duplicate records by checking name, date of birth, and unique identifiers before creating a new entry.",
                    "The records created during this step form the foundation for all future clinical, laboratory, pharmacy, referral, and reporting actions.",
                ],
            },
            {
                "title": "Appointment Scheduling",
                "summary": "How clinics create, reschedule, and close patient appointments in HMIS.",
                "category": "Patient Care",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/appointment-scheduling.png",
                "sections": [
                    "Clinicians and reception teams open the schedule for a service point and assign a patient to a specific day, time slot, provider, and room.",
                    "The system tracks the appointment state from booked to checked in, attended, missed, rescheduled, or canceled so service flow can be monitored in real time.",
                    "A well-maintained appointment schedule helps reduce waiting times, prevents overcrowding in service points, and supports workload forecasting for clinicians and nurses.",
                    "The schedule also helps operational managers identify clinic bottlenecks and plan staffing based on demand patterns over the week or month.",
                ],
            },
            {
                "title": "Clinical Encounter Documentation",
                "summary": "How providers record visits, symptoms, findings, and treatment decisions in a structured workflow.",
                "category": "Patient Care",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/clinical-encounter.png",
                "sections": [
                    "During a patient encounter, a clinician records the reason for visit, current complaints, patient history, vital signs, diagnosis, and the care plan.",
                    "The workflow supports structured recording for standard clinical processes, while also allowing free text for detailed narrative observations or follow-up notes.",
                    "This information becomes part of the patient history and supports continuity of care across pharmacy, lab, referral, and follow-up events.",
                    "If a provider adds new findings or changes the diagnosis, the system should keep the updated note version visible for audit and continuity purposes.",
                ],
            },
            {
                "title": "Laboratory Result Review",
                "summary": "How lab results are received, assigned, and reviewed by clinicians for patient care decisions.",
                "category": "Patient Care",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/lab-result-review.png",
                "sections": [
                    "Lab results are attached to the patient record and linked to the exact ordered test request so clinicians can see the full context.",
                    "The workflow highlights critical values, abnormal ranges, and pending tests, triggering clinician review in cases that require urgent action.",
                    "Clinicians can record interpretation notes, decide whether additional testing is needed, and update the treatment plan accordingly.",
                    "This reduces delays in diagnosis and helps providers act quickly when a result changes patient management.",
                ],
            },
            {
                "title": "Referral Management",
                "summary": "How referrals between facilities and departments are initiated, tracked, and closed.",
                "category": "Operations",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/referral-management.png",
                "sections": [
                    "A referring facility creates a referral with the reason for referral, destination, urgency, and clinical notes for the receiving team.",
                    "The receiving unit tracks whether the referral was accepted, rejected, delayed, or completed and records the final outcome for the patient.",
                    "Clear referral tracking allows facilities to coordinate care across departments and reduce missed follow-ups or lost patient information.",
                    "This is especially important for complex cases such as emergency care, specialized diagnostics, surgical review, or long-term HIV or TB follow-up.",
                ],
            },
            {
                "title": "Medication Administration",
                "summary": "How medications are ordered, dispensed, and documented during patient care.",
                "category": "Patient Care",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/medication-administration.png",
                "sections": [
                    "Medication orders are linked to a patient, indication, prescriber, dose, route, and timing so staff can administer treatment correctly.",
                    "Dispensing and administration are logged in the system to support accountability, stock reconciliation, and patient safety checks.",
                    "Before a drug is given, the team compares the order, the patient identity, and the medication being administered to reduce medication errors.",
                    "The medication history also supports adverse-event review, adherence tracking, and continuity of treatment for chronic disease management.",
                ],
            },
            {
                "title": "Vaccination Tracking",
                "summary": "How immunization records are captured, scheduled, and monitored across outreach and facility service points.",
                "category": "Patient Care",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/vaccination-tracking.png",
                "sections": [
                    "Vaccination entries record the vaccine type, dose number, date administered, health worker responsible, and any contraindications or side effects noted.",
                    "The system supports catch-up planning, reminder workflows, and scheduling for the next dose to improve complete immunization outcomes.",
                    "Facility managers can review coverage by age group, service point, or community and identify under-immunized populations that require outreach.",
                    "This is critical for disease prevention programs and for maintaining reliable evidence for public health reporting.",
                ],
            },
            {
                "title": "Maternal Health Follow-up",
                "summary": "How mothers and newborns are tracked through antenatal, delivery, and postnatal care.",
                "category": "Patient Care",
                "visibility": "PRIVATE",
                "article_status": "REVIEW",
                "version_status": "REVIEW",
                "image_path": "/static/images/hmis/maternal-health-followup.png",
                "sections": [
                    "The system tracks antenatal visits, risk factors, planned delivery dates, and any complication warnings that require escalation to a senior clinician.",
                    "Clinical teams follow mothers through delivery and postpartum recovery, ensuring that newborn and maternal health checks are not missed.",
                    "Follow-up records support close monitoring and alert teams when a patient needs a repeat visit, counseling, or emergency referral.",
                    "These records are especially important for maternal morbidity reduction and for keeping patient history consistent across multiple visits.",
                ],
            },
            {
                "title": "Family Planning Counseling",
                "summary": "How family planning services, counseling, and method selection are captured in HMIS.",
                "category": "Patient Care",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/family-planning-counseling.png",
                "sections": [
                    "Counseling sessions record the contraceptive methods discussed, patient preferences, method chosen, and counseling notes provided by the health worker.",
                    "The service record supports replenishment planning, follow-up reminder scheduling, and the management of method-specific side effect reporting.",
                    "This improves service quality, ensures informed choice, and reduces dropout from reproductive health programs.",
                    "The system also makes it easier to track demand for different family planning methods across facilities and population groups.",
                ],
            },
            {
                "title": "HIV Treatment Continuity",
                "summary": "How ART enrollment, adherence, and treatment follow-up are monitored over time.",
                "category": "Patient Care",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/hiv-treatment-continuity.png",
                "sections": [
                    "ART enrollment records capture the treatment line, adherence status, pharmacy refill dates, and any history of interruptions in care.",
                    "The dashboard highlights clients who are at risk of treatment gaps, missed visits, or poor adherence so outreach teams can act early.",
                    "Clinical teams use the follow-up system to review resistance concerns, counseling flags, and patient needs before the next visit.",
                    "This supports retention in HIV care and improves long-term health outcomes for clients already enrolled in treatment.",
                ],
            },
            {
                "title": "TB Case Monitoring",
                "summary": "How tuberculosis cases are tracked from diagnosis through treatment completion.",
                "category": "Operations",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/tb-case-monitoring.png",
                "sections": [
                    "TB records capture diagnosis details, treatment start date, regimen, adverse events, and follow-up schedules for direct observation or supervised dose support.",
                    "Case managers can review whether a patient is adherent, missed treatment, or needs escalation due to poor response or toxicity.",
                    "The module also supports outcome reporting for treatment completion, cure, default, transfer, or death, ensuring that data is available for public health review.",
                    "This improves case management and helps facilities act promptly when a patient is at risk of defaulting from treatment.",
                ],
            },
            {
                "title": "NCD Care Plans",
                "summary": "How chronic disease patients are assigned care plans and tracked over time.",
                "category": "Patient Care",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/ncd-care-plans.png",
                "sections": [
                    "Providers create disease-specific care plans for hypertension, diabetes, asthma, and other chronic conditions with follow-up intervals and action items.",
                    "The system records medication changes, risk factors, symptoms, and treatment progress so the care plan remains current and consistent.",
                    "Long-term monitoring helps care teams reduce avoidable complications and build a clearer clinical summary for each patient.",
                    "This is especially useful in programs that require chronic disease registers, patient tracing, and regular follow-up visits.",
                ],
            },
            {
                "title": "Inventory Stock Ledger",
                "summary": "How facility stock, losses, and replenishment are maintained in the HMIS inventory module.",
                "category": "Operations",
                "visibility": "PRIVATE",
                "article_status": "REVIEW",
                "version_status": "REVIEW",
                "image_path": "/static/images/hmis/inventory-stock-ledger.png",
                "sections": [
                    "The stock ledger records receipts, issues, losses, transfers, and current balances for drugs, supplies, and equipment used in facility service delivery.",
                    "Facility teams reconcile actual stock with recorded usage and set minimum reorder thresholds so essential items are not exhausted unexpectedly.",
                    "This module helps identify stockouts, expired products, and unusual losses before they disrupt patient care or generate financial waste.",
                    "Accurate inventory trends also support procurement planning, vendor follow-up, and monthly stock review meetings.",
                ],
            },
            {
                "title": "Equipment Maintenance Log",
                "summary": "How medical equipment condition checks and maintenance actions are recorded.",
                "category": "Operations",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/equipment-maintenance-log.png",
                "sections": [
                    "Maintenance logs capture service dates, issue reports, repairs, equipment downtime, and next scheduled inspection dates for biomedical assets.",
                    "The system helps teams decide whether to repair, replace, or continue using a device depending on uptime and maintenance history.",
                    "This supports preventative maintenance programs and reduces the risk of service interruption caused by broken equipment.",
                    "Facilities can also review failure trends to identify recurring problems affecting specific equipment types or service points.",
                ],
            },
            {
                "title": "Quality Improvement Dashboard",
                "summary": "How facility performance, service quality, and target thresholds are reviewed.",
                "category": "Reporting",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/quality-improvement-dashboard.png",
                "sections": [
                    "The dashboard summarizes key service indicators such as waiting times, treatment completion rates, stockout incidences, and referral follow-up rates.",
                    "Managers compare actual performance against program targets and review outliers for corrective action and quality measurement.",
                    "This process gives facility leadership a clearer view of which processes need improvement and where interventions should be prioritized.",
                    "Data-driven review cycles help operational teams strengthen service delivery and close performance gaps over time.",
                ],
            },
            {
                "title": "Staff Attendance and Roster",
                "summary": "How staff schedules, attendance, and duty coverage are managed across departments.",
                "category": "Administration",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/staff-attendance-roster.png",
                "sections": [
                    "The roster tracks staff assignments, work shifts, leave plans, and actual duty coverage by role and service location.",
                    "Attendance records support payroll review, supervision, and operational planning when staffing shortages or leave patterns affect service access.",
                    "Facilities can easily identify which departments are understaffed and adjust coverage before patient queues become unmanageable.",
                    "This is a critical operational safeguard for facilities running multiple service areas with different staffing needs.",
                ],
            },
            {
                "title": "Client Consent Management",
                "summary": "How patient consent and information-sharing permissions are tracked and verified.",
                "category": "Security",
                "visibility": "PRIVATE",
                "article_status": "REVIEW",
                "version_status": "REVIEW",
                "image_path": "/static/images/hmis/client-consent-management.png",
                "sections": [
                    "Consent records document what the patient agreed to, when consent was given, and who captured it on behalf of the facility.",
                    "The module supports review and renewal for treatment consent, data-sharing permission, and sensitive diagnostic workflows.",
                    "When a patient’s consent status changes, the system can restrict access to records or flag the need for the clinician to re-confirm consent.",
                    "This protects privacy, supports legal compliance, and strengthens trust between patients and providers.",
                ],
            },
            {
                "title": "Data Quality Validation",
                "summary": "How incomplete, duplicate, or invalid records are identified and corrected.",
                "category": "Reporting",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/data-quality-validation.png",
                "sections": [
                    "Data validation rules check completeness, duplicate entries, valid coding, and mandatory fields before the record is included in recurring reports.",
                    "Clinicians and data officers can review issues that are flagged for correction before a monthly or quarterly submission is finalized.",
                    "This reduces errors in reporting and improves confidence in indicators used for planning and donor communication.",
                    "Timely correction also helps facility managers act on incomplete data before it affects patient care decisions.",
                ],
            },
            {
                "title": "Indicator Reporting and Export",
                "summary": "How monthly and quarterly indicators are generated, reviewed, and exported for internal or external use.",
                "category": "Reporting",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/indicator-reporting.png",
                "sections": [
                    "The reporting engine aggregates patient, service, and operational data into core indicators such as consultations, referrals, stockouts, and outputs by month.",
                    "Reports can be exported to spreadsheet, PDF, or dashboard-compatible formats to support internal review and submissions to higher authorities.",
                    "This helps leadership monitor progress against targets, compare service points, and communicate results to partners or funding agencies.",
                    "Strong reporting is critical for evidence-based planning, policy review, and operational accountability.",
                ],
            },
            {
                "title": "User Access and Roles",
                "summary": "How roles, permissions, and user access are assigned to secure HMIS functions.",
                "category": "Security",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/user-access-roles.png",
                "sections": [
                    "Each user profile is associated with a role such as clinician, data clerk, case manager, supervisor, or administrator, and the system restricts access accordingly.",
                    "Permission rules define which records, forms, and actions the individual can view, edit, or approve while reducing unauthorized use of patient information.",
                    "This helps ensure accountability and protects the integrity of clinical and administrative workflows.",
                    "Access controls are particularly important in systems handling sensitive patient information and operational reporting data.",
                ],
            },
            {
                "title": "System Integration Setup",
                "summary": "How external systems such as labs, EMR modules, or mobile tools are connected to HMIS.",
                "category": "Administration",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/system-integration-setup.png",
                "sections": [
                    "Integration setup defines the API endpoints, data mappings, and synchronization schedules needed for external systems to exchange information with HMIS.",
                    "The process checks data formatting, validation rules, and field compatibility before production rollout so system connectivity remains stable.",
                    "This allows HMIS to share information with lab systems, EMR modules, and mobile reporting tools without breaking clinical or operational routines.",
                    "Good integration design reduces duplicate entry, improves timeliness, and increases confidence in shared patient and reporting data.",
                ],
            },
            {
                "title": "Patient Discharge Summary",
                "summary": "How discharge information, follow-up instructions, and outcome notes are created for patients.",
                "category": "Patient Care",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/patient-discharge-summary.png",
                "sections": [
                    "A discharge summary captures the diagnosis, treatment received, medications issued, follow-up instructions, and the final disposition for each patient.",
                    "The record supports community follow-up care and helps the next service provider understand the patient’s recent treatment history and remaining care needs.",
                    "Clear discharge instructions reduce confusion for patients and improve continuity after leaving the facility.",
                    "This is essential for reducing readmissions and ensuring that patients know when to return, whom to contact, and what symptoms require urgent attention.",
                ],
            },
            {
                "title": "Emergency Triage and Escalation",
                "summary": "How emergency cases are prioritized, monitored, and escalated within the facility.",
                "category": "Operations",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/emergency-triage.png",
                "sections": [
                    "Emergency patients are assessed using triage categories and urgency scores so the most critical cases receive immediate attention.",
                    "Escalation rules notify the appropriate clinical team, trigger referral pathways, and ensure the patient is moved to the appropriate care area without delay.",
                    "The triage record also captures vital information that supports rapid decision making and improved patient safety in emergency workflows.",
                    "This reduces waiting time for high-risk patients and supports a better emergency response process across the department.",
                ],
            },
            {
                "title": "Data Backup and Recovery",
                "summary": "How HMIS data is protected, restored, and recovered during service interruption.",
                "category": "Security",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/data-backup-recovery.png",
                "sections": [
                    "Daily and incremental backups protect patient and operational records from accidental loss, corruption, or service interruption.",
                    "Recovery procedures define how staff restore the system to a known-good state after outages, hardware failure, or cyber incident disruption.",
                    "This minimizes downtime and helps facilities continue essential care while restoring normal database operations.",
                    "A strong backup and recovery plan is central to system reliability and to safeguarding patient information during infrastructure disruption.",
                ],
            },
            {
                "title": "Dashboard Alerts and Notifications",
                "summary": "How key events, exceptions, and service thresholds are surfaced to users through alerts.",
                "category": "Administration",
                "visibility": "PUBLIC",
                "article_status": "PUBLISHED",
                "version_status": "PUBLISHED",
                "image_path": "/static/images/hmis/dashboard-alerts.png",
                "sections": [
                    "Alert rules trigger notifications for missed appointments, low stock levels, abnormal lab values, or process delays requiring action.",
                    "Users can review the alert history, prioritize outstanding tasks, and decide which team should respond.",
                    "This helps operational teams act quickly on problems that could affect patient care or program performance if left unresolved.",
                    "A clear alert workflow improves responsiveness and helps facilities maintain continuity when problems arise unexpectedly.",
                ],
            },
            {
                "title": "Audit Trail and Digital Signatures",
                "summary": "How user actions, approvals, and sensitive record changes are tracked for accountability.",
                "category": "Security",
                "visibility": "PRIVATE",
                "article_status": "REVIEW",
                "version_status": "REVIEW",
                "image_path": "/static/images/hmis/audit-trail.png",
                "sections": [
                    "The audit trail records who changed a record, when the change occurred, and the previous versus new value for clinically or administratively sensitive updates.",
                    "Digital signatures support approval workflows for high-risk tasks such as medication review, critical data correction, or final reporting sign-off.",
                    "This strengthens traceability for quality assurance, compliance review, and internal accountability across the institution.",
                    "When used correctly, audit trails improve trust in both operational and clinical decision making.",
                ],
            },
        ]

    @staticmethod
    def build_content(article_data):
        title = article_data["title"]
        summary = article_data["summary"]
        sections = article_data.get("sections", [])

        html = [
            f"<article>",
            f"<h1>{title}</h1>",
            f"<p><strong>Overview:</strong> {summary}</p>",
            f"<h2>How this affects normal functioning</h2>",
            f"<p>This guidance explains how the {title.lower()} workflow supports day-to-day patient care, facility operations, reporting quality, and continuity of service in HMIS.</p>",
        ]

        for index, section in enumerate(sections, start=1):
            html.append(f"<h3>Step {index}</h3>")
            html.append(f"<p>{section}</p>")
        html.append("</article>")
        return "\n".join(html)
