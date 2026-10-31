"""
Redemption Workflow Coordinator.

Orchestrates the 7-step guided claim workflow:
STEP 1: Select promotion (verified official promotions only)
STEP 2: Select device (connected physical Pixel, manual report, or browser probe)
STEP 3: Select country (user-saved or selected country profile)
STEP 4: Run comprehensive eligibility checks
STEP 5: Generate official redemption instructions & terms
STEP 6: User-controlled redemption on official Google interface
STEP 7: Verify redemption & record evidence
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from country_service import country_service
from database import get_db
from device_verification import DeviceTier, DeviceVerificationReport, device_verification_service
from eligibility_engine import EligibilityCode, EligibilityEvaluationReport, eligibility_engine
from google_account_flow import RedemptionInstruction, google_account_flow
from models import ClaimSession, ClaimState, Device, EligibilityCheck, Promotion
from promotion_catalog import PromotionItem, promotion_service
from redemption_verification import RedemptionStatus, VerificationAssessment, redemption_verification_service
from session_manager import SessionManager, session_manager

logger = logging.getLogger(__name__)


@dataclass
class WorkflowStepResult:
    current_state: ClaimState
    message: str
    can_proceed: bool
    data: Optional[Dict] = None


class RedemptionWorkflow:
    """Manages progression through the 7-step claim workflow."""

    def __init__(self, sm: Optional[SessionManager] = None):
        self.session_mgr = sm or session_manager

    def start_claim(self, telegram_id: int | str) -> Tuple[ClaimSession, str]:
        """Initiate or resume a claim session."""
        active = self.session_mgr.get_active_session(telegram_id)
        if active:
            state = ClaimState(active.current_state)
            return active, f"Resuming your active claim session ({active.session_uuid[:8]}...) at state: `{state.value}`."

        session = self.session_mgr.create_claim_session(telegram_id)
        return session, "Initialized new claim session. Step 1: Select an official Google promotion."

    def select_promotion(self, session_id: int, promotion_id: str) -> WorkflowStepResult:
        promo = promotion_service.get_promotion(promotion_id)
        if not promo:
            return WorkflowStepResult(
                current_state=ClaimState.IDLE,
                message=f"Promotion '{promotion_id}' not found in active catalog.",
                can_proceed=False,
            )

        with get_db() as db:
            p_record = db.query(Promotion).filter(Promotion.promotion_id == promotion_id).first()
            s_record = db.query(ClaimSession).filter(ClaimSession.id == session_id).first()
            if s_record and p_record:
                s_record.promotion_id = p_record.id

        new_state = self.session_mgr.transition_state(
            session_id=session_id,
            target_state=ClaimState.PROMOTION_SELECTED,
            step_name="STEP_1_SELECT_PROMOTION",
            notes=f"Selected promotion: {promo.promotion_name}",
        )
        return WorkflowStepResult(
            current_state=new_state,
            message=f"Selected: **{promo.promotion_name}** ({promo.duration_months} Months).\n\nStep 2: Select or verify your device.",
            can_proceed=True,
            data={"promotion": promo.to_dict()},
        )

    def select_device(
        self,
        session_id: int,
        manual_model: Optional[str] = None,
        use_adb: bool = False,
    ) -> WorkflowStepResult:
        device_report = device_verification_service.inspect_environment(manual_model=manual_model)

        with get_db() as db:
            s_record = db.query(ClaimSession).filter(ClaimSession.id == session_id).first()
            if s_record:
                dev = Device(
                    user_id=s_record.user_id,
                    device_type=device_report.device_tier.value,
                    manufacturer=device_report.reported_manufacturer,
                    model=device_report.reported_model,
                    android_version=device_report.android_version,
                    build_fingerprint=device_report.build_fingerprint,
                    is_hardware_verified=device_report.is_hardware_verified,
                    is_user_reported=device_report.is_user_reported,
                    bootloader_locked=device_report.bootloader_locked,
                    play_services_status="INSTALLED" if device_report.play_services_installed else "NOT_FOUND",
                    notes="; ".join(device_report.verification_notes),
                )
                db.add(dev)
                db.flush()
                s_record.device_id = dev.id

        new_state = self.session_mgr.transition_state(
            session_id=session_id,
            target_state=ClaimState.DEVICE_SELECTED,
            step_name="STEP_2_SELECT_DEVICE",
            notes=f"Device: {device_report.reported_model} ({device_report.device_tier.value})",
        )
        return WorkflowStepResult(
            current_state=new_state,
            message=(
                f"Device confirmed: **{device_report.reported_model}**\n"
                f"• Execution Tier: `{device_report.device_tier.value}`\n"
                f"• Hardware Verified: `{'Yes' if device_report.is_hardware_verified else 'No (USER_REPORTED / Unverified)'}`\n\n"
                "Step 3: Confirm your Google Play billing country."
            ),
            can_proceed=True,
            data={"device": device_report.to_dict()},
        )

    def select_country(self, session_id: int, country_code: str) -> WorkflowStepResult:
        clean_code = country_code.upper().strip()
        c_info = country_service.check_region_eligibility(clean_code)

        with get_db() as db:
            s_record = db.query(ClaimSession).filter(ClaimSession.id == session_id).first()
            if s_record:
                s_record.selected_country_code = clean_code

        new_state = self.session_mgr.transition_state(
            session_id=session_id,
            target_state=ClaimState.COUNTRY_SELECTED,
            step_name="STEP_3_SELECT_COUNTRY",
            notes=f"Country: {clean_code}",
        )
        return WorkflowStepResult(
            current_state=new_state,
            message=(
                f"Country configured: **{c_info.get('country_name', clean_code)} ({clean_code})**\n\n"
                "Step 4: Running eligibility evaluation across all parameters…"
            ),
            can_proceed=True,
            data={"country": c_info},
        )

    def run_eligibility_evaluation(
        self,
        session_id: int,
        account_type: str = "PERSONAL",
        has_active_google_one: bool = False,
    ) -> WorkflowStepResult:
        # Move to ELIGIBILITY_CHECKING
        self.session_mgr.transition_state(
            session_id=session_id,
            target_state=ClaimState.ELIGIBILITY_CHECKING,
            step_name="STEP_4_START_EVALUATION",
            notes="Starting eligibility engine",
        )

        with get_db() as db:
            s_record = db.query(ClaimSession).filter(ClaimSession.id == session_id).first()
            if not s_record or not s_record.promotion_id:
                return WorkflowStepResult(
                    current_state=ClaimState.ELIGIBILITY_BLOCKED,
                    message="Missing promotion information in session.",
                    can_proceed=False,
                )

            p_model = db.query(Promotion).filter(Promotion.id == s_record.promotion_id).first()
            promo_item = promotion_service.get_promotion(p_model.promotion_id)

            dev_model = s_record.device
            dev_report = DeviceVerificationReport(
                device_tier=DeviceTier(dev_model.device_type) if dev_model else DeviceTier.UNKNOWN,
                reported_model=dev_model.model if dev_model else "Unknown",
                reported_manufacturer=dev_model.manufacturer if dev_model else "Unknown",
                android_version=dev_model.android_version if dev_model else "Unknown",
                build_fingerprint=dev_model.build_fingerprint if dev_model else "Unknown",
                is_hardware_verified=dev_model.is_hardware_verified if dev_model else False,
                is_user_reported=dev_model.is_user_reported if dev_model else True,
                bootloader_locked=dev_model.bootloader_locked if dev_model else None,
                play_services_installed=True,
                play_store_installed=True,
                adb_connected=False,
            )

        report: EligibilityEvaluationReport = eligibility_engine.evaluate(
            promotion=promo_item,
            device_report=dev_report,
            country_code=s_record.selected_country_code or "US",
            account_type=account_type,
            has_active_google_one=has_active_google_one,
        )

        # Persist eligibility checks
        with get_db() as db:
            for check in report.assessments:
                db.add(
                    EligibilityCheck(
                        user_id=s_record.user_id,
                        session_id=session_id,
                        check_type=check.category,
                        result_code=check.code.value,
                        passed=check.passed,
                        confidence=check.confidence,
                        evidence=check.evidence,
                        details=check.summary,
                    )
                )

        target_state = (
            ClaimState.ELIGIBILITY_PASSED if report.is_eligible
            else ClaimState.ELIGIBILITY_UNKNOWN if report.primary_code in (EligibilityCode.DEVICE_UNKNOWN, EligibilityCode.ACCOUNT_UNKNOWN)
            else ClaimState.ELIGIBILITY_BLOCKED
        )

        new_state = self.session_mgr.transition_state(
            session_id=session_id,
            target_state=target_state,
            step_name="STEP_4_EVALUATION_RESULT",
            notes=f"Eligibility result: {report.primary_code.value} (Passed: {report.is_eligible})",
        )

        breakdown = "\n".join(
            [f"• **{c.category}:** `[{c.code.value}]` ({'Passed ✅' if c.passed else 'Failed ❌'})\n  _{c.summary}_" for c in report.assessments]
        )

        can_proceed = target_state in (ClaimState.ELIGIBILITY_PASSED, ClaimState.ELIGIBILITY_UNKNOWN)
        msg = (
            f"📋 *Eligibility Assessment Report*\n"
            f"Result: `[{report.primary_code.value}]`\n\n"
            f"{breakdown}\n\n"
            + ("Ready for Step 5: Generate official redemption instructions." if can_proceed else "❌ Cannot proceed with redemption due to blocking conditions.")
        )

        return WorkflowStepResult(
            current_state=new_state,
            message=msg,
            can_proceed=can_proceed,
            data={"report": report.to_dict()},
        )

    def generate_redemption_guide(self, session_id: int) -> WorkflowStepResult:
        with get_db() as db:
            s_record = db.query(ClaimSession).filter(ClaimSession.id == session_id).first()
            p_record = db.query(Promotion).filter(Promotion.id == s_record.promotion_id).first()
            promo = promotion_service.get_promotion(p_record.promotion_id)
            device_name = s_record.device.model if s_record.device else "Google Pixel"

        guide: RedemptionInstruction = google_account_flow.generate_redemption_guide(
            promotion_name=promo.promotion_name,
            target_device=device_name,
            country_code=s_record.selected_country_code or "US",
            official_terms_url=promo.official_terms_url,
            duration_months=promo.duration_months,
        )

        self.session_mgr.transition_state(
            session_id=session_id,
            target_state=ClaimState.REDEMPTION_READY,
            step_name="STEP_5_GENERATE_GUIDE",
            notes="Generated official redemption guide",
        )
        new_state = self.session_mgr.transition_state(
            session_id=session_id,
            target_state=ClaimState.USER_ACTION_REQUIRED,
            step_name="STEP_6_AWAIT_USER_ACTION",
            notes="Awaiting user action on official Google interface",
        )

        guide_steps = "\n".join(guide.steps)
        guide_notes = "\n".join(guide.important_notes)

        msg = (
            f"🎁 *Official Redemption Instructions: {guide.promotion_name}*\n\n"
            f"{guide_steps}\n\n"
            f"🔗 **Official Link:** {guide.official_url}\n\n"
            f"📌 **Important Information:**\n{guide_notes}\n\n"
            f"🔄 **Cancellation Policy:**\n_{guide.cancellation_terms}_\n\n"
            "Once you have attempted redemption on your device, report your result below."
        )

        return WorkflowStepResult(
            current_state=new_state,
            message=msg,
            can_proceed=True,
            data={"guide": guide.__dict__},
        )

    def submit_redemption_result(
        self,
        session_id: int,
        user_response: str,
        screenshot_path: Optional[str] = None,
    ) -> WorkflowStepResult:
        # Move to CLAIM_IN_PROGRESS
        try:
            self.session_mgr.transition_state(
                session_id=session_id,
                target_state=ClaimState.CLAIM_IN_PROGRESS,
                step_name="STEP_7_SUBMIT_RESULT",
                notes="Processing user reported result",
            )
        except Exception:
            pass

        assessment: VerificationAssessment = redemption_verification_service.evaluate_user_report(
            session_id=session_id,
            user_response=user_response,
            screenshot_path=screenshot_path,
        )

        target_state = (
            ClaimState.CLAIM_REPORTED_SUCCESS if assessment.status == RedemptionStatus.CLAIM_REPORTED_SUCCESS
            else ClaimState.CLAIM_FAILED if assessment.status == RedemptionStatus.CLAIM_FAILED
            else ClaimState.USER_ACTION_REQUIRED
        )

        new_state = self.session_mgr.transition_state(
            session_id=session_id,
            target_state=target_state,
            step_name="STEP_7_VERIFICATION_COMPLETE",
            notes=f"Verification status: {assessment.status.value}",
        )

        status_emoji = "🎉" if assessment.status == RedemptionStatus.CLAIM_REPORTED_SUCCESS else "⚠️" if assessment.status == RedemptionStatus.MANUAL_REVIEW_REQUIRED else "❌"
        msg = (
            f"{status_emoji} *Redemption Outcome: {assessment.status.value}*\n\n"
            f"• **Status:** `{assessment.status.value}` (Authoritative: {'Yes' if assessment.is_authoritative else 'No - USER_REPORTED'})\n"
            f"• **Analysis:** {assessment.explanation}\n"
            f"• **Next Step:** {assessment.recommended_action}"
        )

        return WorkflowStepResult(
            current_state=new_state,
            message=msg,
            can_proceed=(assessment.status == RedemptionStatus.CLAIM_REPORTED_SUCCESS),
            data={"assessment": assessment.__dict__},
        )


# Global instance
redemption_workflow = RedemptionWorkflow()
