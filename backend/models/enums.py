import enum


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    DEPT_ADMIN = "DEPT_ADMIN"
    EMPLOYEE = "EMPLOYEE"


class CompanyType(str, enum.Enum):
    SERVICE_BASED = "service_based"
    PRODUCT_BASED = "product_based"
    HYBRID = "hybrid"


class Industry(str, enum.Enum):
    """Fixed list rather than free text so analytics/filtering stays sane -
    OTHER is the escape hatch for anything that doesn't fit.
    """

    IT_SOFTWARE = "it_software"
    FINANCE_BANKING = "finance_banking"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    RETAIL_ECOMMERCE = "retail_ecommerce"
    MANUFACTURING = "manufacturing"
    REAL_ESTATE = "real_estate"
    HOSPITALITY_TRAVEL = "hospitality_travel"
    MEDIA_ENTERTAINMENT = "media_entertainment"
    TELECOMMUNICATIONS = "telecommunications"
    LOGISTICS_TRANSPORTATION = "logistics_transportation"
    CONSTRUCTION = "construction"
    ENERGY_UTILITIES = "energy_utilities"
    AGRICULTURE = "agriculture"
    GOVERNMENT_PUBLIC_SECTOR = "government_public_sector"
    NON_PROFIT = "non_profit"
    CONSULTING = "consulting"
    LEGAL = "legal"
    OTHER = "other"


class CompanySize(str, enum.Enum):
    """Employee count bands rather than an exact headcount - accurate enough
    for org-level defaults (e.g. leave policy templates) without needing to
    stay in sync with actual headcount changes.
    """

    SIZE_1_10 = "1-10"
    SIZE_11_50 = "11-50"
    SIZE_51_200 = "51-200"
    SIZE_201_500 = "201-500"
    SIZE_501_1000 = "501-1000"
    SIZE_1000_PLUS = "1000+"


class LeaveStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class KBSourceType(str, enum.Enum):
    POLICY_DOC = "policy_doc"
    FAQ = "faq"
    MANUAL_ENTRY = "manual_entry"


class ChatMessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
