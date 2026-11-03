"""
Official Google Account Flow (Non-Custodial).

Provides official, safe Google redemption URLs and guidance for users to
authenticate and claim offers directly on their own device.

SECURITY DIRECTIVE:
Never asks for, enters, or stores Google passwords, 2FA codes, recovery seeds,
or browser cookies.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)

OFFICIAL_ONE_BENEFITS_URL = "https://one.google.com/benefits"
OFFICIAL_ONE_PLANS_URL = "https://one.google.com/about/plans"
OFFICIAL_PAYMENTS_URL = "https://payments.google.com/"
OFFICIAL_STORE_TERMS_URL = "https://store.google.com/terms/pixel_ai_promotion"


@dataclass
class RedemptionInstruction:
    promotion_name: str
    target_device: str
    official_url: str
    steps: list[str]
    important_notes: list[str]
    cancellation_terms: str
    expiration_warning: str


class GoogleAccountFlow:
    """Generates verified official guidance for user-controlled redemption."""

    def generate_redemption_guide(
        self,
        promotion_name: str,
        target_device: str,
        country_code: str = "US",
        official_terms_url: Optional[str] = None,
        duration_months: int = 12,
    ) -> RedemptionInstruction:
        terms_url = official_terms_url or OFFICIAL_STORE_TERMS_URL

        steps = [
            f"1. On your physical **{target_device}**, ensure you are logged into your primary personal Google Account.",
            "2. Open the native **Google One app** (or download it from the Google Play Store if not installed).",
            "3. If an offer banner appears on the home tab, tap **'Get perk'** or **'Claim offer'**.",
            "4. If not visible on the home screen, navigate to the **'Benefits'** tab or tap **Settings ➔ Check for offers**.",
            f"5. Review the offer details: **{duration_months} Months Google AI Pro (5 TB) subscription at $0/month** (Offer for {target_device}).",
            "6. Select or confirm an on-file payment method (Google Play billing) to authorize the free trial setup.",
            "7. Tap **'Start trial'** or **'Subscribe'** to finalize activation directly through Google Play.",
            "8. Upon confirmation, Google Play will display **'Payment successful'** and ask **'Require authentication for purchases?'**. Select 'Yes, always' or 'No, thanks' and tap **OK**.",
        ]

        notes = [
            "🔒 **Security Guarantee**: You are authenticating directly on Google's official interface. The bot never accesses your credentials.",
            "💳 **Billing Notice**: A valid payment method is required by Google for auto-renewal, but your card will NOT be charged during the promotional period.",
            "📱 **Hardware Binding**: Hardware promotions must be redeemed through the app on the eligible device to pass Google Play Integrity checks.",
        ]

        cancellation = (
            "You can cancel auto-renewal anytime before the trial ends by visiting "
            "`Google Play Store ➔ Profile ➔ Payments & subscriptions ➔ Subscriptions`. "
            "Your benefits will remain active until the full promotional trial concludes."
        )

        expiration = f"Refer to the official terms for your campaign redemption cutoff: {terms_url}"

        return RedemptionInstruction(
            promotion_name=promotion_name,
            target_device=target_device,
            official_url=OFFICIAL_ONE_BENEFITS_URL,
            steps=steps,
            important_notes=notes,
            cancellation_terms=cancellation,
            expiration_warning=expiration,
        )


# Global instance
google_account_flow = GoogleAccountFlow()

