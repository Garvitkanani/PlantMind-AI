"""
Email Filter Agent
Filters emails based on keywords and business logic
"""

from typing import Dict, List, Tuple

# Keywords to identify orders/enquiries (matches V1 specification)
ORDER_KEYWORDS = [
    "purchase order",
    "po",
    "p.o",
    "po no",
    "po #",
    "order",
    "requirement",
    "enquiry",
    "inquiry",
    "rfq",
    "request for quotation",
    "request for quote",
    "supply request",
    "material request",
]

# Keywords to skip (spam, newsletters, etc.)
SPAM_KEYWORDS = [
    "unsubscribe",
    "click here",
    "limited offer",
    "buy now",
    "special discount",
    "winner",
    "congratulations",
    "lottery",
    "prize",
    "winner alert",
    "free gift",
    "reward",
    "earn money",
    "work from home",
    "investment opportunity",
]

# Customer status keywords
POTENTIAL_CUSTOMER_PHRASES = [
    "new customer",
    "first order",
    "new enquiry",
    "beginner",
    "looking for",
    "interested in",
]

# Priority indicators
HIGH_PRIORITY_KEYWORDS = [
    "urgent",
    "high priority",
    "asap",
    "immediate",
    "紧急",
    "urgent delivery",
]

# Duplicate indicators
DUPLICATE_PHRASES = [
    "re:",
    "fw:",
    "fwd:",
]


class EmailFilterAgent:
    """
    Agent responsible for filtering emails based on business logic
    Decides whether to process or skip each email
    """

    def __init__(self):
        self.order_keywords = ORDER_KEYWORDS
        self.spam_keywords = SPAM_KEYWORDS
        self.high_priority_keywords = HIGH_PRIORITY_KEYWORDS
        self.duplicate_phrases = DUPLICATE_PHRASES
        self.potential_customer_phrases = POTENTIAL_CUSTOMER_PHRASES

    def filter_email(self, email_data: Dict) -> Dict:
        """
        Filter an email and determine processing decision
        Returns filter result with decision and reasons
        """
        subject = email_data.get("subject", "").lower()
        body = email_data.get("body", "").lower()
        from_email = email_data.get("from_email", "").lower()

        combined_text = f"{subject} {body}"

        # Initialize result
        filter_result = {
            "should_process": False,
            "should_skip": False,
            "priority": "normal",
            "needs_review": False,
            "reasons": [],
            "flags": [],
        }

        # Check for spam indicators first (hard skip)
        if self._contains_spam_keywords(combined_text):
            filter_result["should_skip"] = True
            filter_result["reasons"].append("Spam indicators detected")
            filter_result["flags"].append("spam")
            return filter_result

        # Flag reply/forward emails but do NOT skip them —
        # a customer replying "Re: PO #4521" is still a valid order email
        if self._is_reply_or_forward(subject):
            filter_result["flags"].append("reply_or_forward")

        # Check for order keywords
        has_order_keyword = self._contains_order_keywords(combined_text)
        if has_order_keyword:
            filter_result["should_process"] = True
            filter_result["reasons"].append("Order keyword found in subject/body")

            # Check for high priority
            if self._contains_high_priority_keywords(combined_text):
                filter_result["priority"] = "high"
                filter_result["reasons"].append("High priority order")
                filter_result["flags"].append("high_priority")

            # Check for potential new customer
            if self._contains_potential_customer_phrases(combined_text):
                filter_result["flags"].append("new_customer")

            # Check if email is already in our system
            if not from_email or not self._is_known_customer(from_email):
                filter_result["flags"].append("new_customer")

        # If no order keywords found, check body thoroughly
        if not filter_result["should_process"]:
            # Check if email body has order-related content
            if self._has_order_content(body):
                filter_result["should_process"] = True
                filter_result["reasons"].append("Order content found in email body")

            # Check if it's a potential order from new customer
            elif self._contains_potential_customer_phrases(combined_text):
                filter_result["should_process"] = False  # Flag for review
                filter_result["needs_review"] = True
                filter_result["reasons"].append("Potential new customer enquiry")
                filter_result["flags"].append("needs_review_new_customer")

        # Default decision
        if not filter_result["should_process"] and not filter_result["should_skip"]:
            filter_result["should_skip"] = True
            filter_result["reasons"].append("No order indicators found")

        return filter_result

    def _contains_order_keywords(self, text: str) -> bool:
        """Check if text contains order-related keywords"""
        text_lower = text.lower()

        for keyword in self.order_keywords:
            if keyword.lower() in text_lower:
                return True

        return False

    def _contains_spam_keywords(self, text: str) -> bool:
        """Check if text contains spam indicators"""
        text_lower = text.lower()

        for keyword in self.spam_keywords:
            if keyword.lower() in text_lower:
                return True

        return False

    def _contains_high_priority_keywords(self, text: str) -> bool:
        """Check if text contains high priority indicators"""
        text_lower = text.lower()

        for keyword in self.high_priority_keywords:
            if keyword.lower() in text_lower:
                return True

        return False

    def _contains_potential_customer_phrases(self, text: str) -> bool:
        """Check if text indicates a potential new customer"""
        text_lower = text.lower()

        for phrase in self.potential_customer_phrases:
            if phrase.lower() in text_lower:
                return True

        return False

    def _is_reply_or_forward(self, subject: str) -> bool:
        """Check if email is a reply or forward (informational flag only, not a skip reason)"""
        subject_lower = subject.lower().strip()

        for phrase in self.duplicate_phrases:
            if subject_lower.startswith(phrase):
                return True

        return False

    def _is_known_customer(self, email: str) -> bool:
        """Check if email belongs to a known customer in the database"""
        try:
            from src.database.connection import SessionLocal
            from src.database.models import Customer

            db = SessionLocal()
            try:
                exists = db.query(Customer).filter(Customer.email == email).first() is not None
                return exists
            finally:
                db.close()
        except Exception:
            # If DB is unavailable, assume unknown
            return False

    def _has_order_content(self, body: str) -> bool:
        """Check if email body has order-related content"""
        body_lower = body.lower()

        # Check for common order patterns
        order_patterns = [
            "i would like to order",
            "please quote",
            "we need",
            "required for",
            "delivery date",
            "quantity",
            "product",
            "item",
            "supplier",
        ]

        for pattern in order_patterns:
            if pattern in body_lower:
                return True

        return False

    def create_filter_summary(self, email_data: Dict, filter_result: Dict) -> str:
        """Create a summary string for filter decision"""
        from_email = email_data.get("from_email", "Unknown")
        subject = email_data.get("subject", "No Subject")

        summary = f"📧 {from_email} - {subject}\n"
        summary += f"   🔴 Skip: {filter_result['should_skip']}\n"
        summary += f"   🟢 Process: {filter_result['should_process']}\n"
        summary += f"   📝 Priority: {filter_result['priority']}\n"
        summary += f"   ⚠️ Needs Review: {filter_result['needs_review']}\n"
        summary += f"   💡 Reasons: {', '.join(filter_result['reasons'])}"

        return summary


# Test function
def test_email_filter():
    """Test the email filter agent"""
    filter_agent = EmailFilterAgent()

    # Test cases
    test_emails = [
        {
            "subject": "Purchase Order #PO-2024-001",
            "body": "Please find attached our purchase order for 5000 units of HDPE caps.",
            "from_email": "buyer@customer.com",
        },
        {
            "subject": "FW: Order Enquiry",
            "body": "We are looking to buy plastic products. Please send us your quotation.",
            "from_email": "newcustomer@company.com",
        },
        {
            "subject": "Urgent: Immediate Delivery Required",
            "body": "We need 10000 units delivered by Friday.",
            "from_email": "urgent@buyer.com",
        },
        {
            "subject": "Special Offer - Buy Now!",
            "body": "Click here to get your free gift!",
            "from_email": "marketing@spam.com",
        },
        {
            "subject": "Newsletter - Weekly Updates",
            "body": "Subscribe to our newsletter for weekly updates.",
            "from_email": "newsletter@site.com",
        },
    ]

    print("🧪 Testing Email Filter Agent\n" + "=" * 50)

    for i, email in enumerate(test_emails, 1):
        print(f"\n📧 Test Email {i}:")
        filter_result = filter_agent.filter_email(email)
        summary = filter_agent.create_filter_summary(email, filter_result)
        print(summary)

    print("\n" + "=" * 50)
    print("✅ Filter testing complete!")


if __name__ == "__main__":
    test_email_filter()
