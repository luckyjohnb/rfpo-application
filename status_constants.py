"""
Centralized status constants for the RFPO approval workflow.

Provides frozen sets for validation and named constants to replace
bare string literals throughout the codebase (BUG-0043).
"""


class RFPOStatus:
    """RFPO-level statuses (title-case)."""
    DRAFT = "Draft"
    PENDING_APPROVAL = "Pending Approval"
    APPROVED = "Approved"
    REFUSED = "Refused"

    ALL = frozenset({DRAFT, PENDING_APPROVAL, APPROVED, REFUSED})
    TERMINAL = frozenset({APPROVED, REFUSED})


class InstanceStatus:
    """Approval instance statuses (lowercase)."""
    DRAFT = "draft"
    WAITING = "waiting"
    APPROVED = "approved"
    REFUSED = "refused"
    WITHDRAWN = "withdrawn"
    ERROR = "error"

    ALL = frozenset({DRAFT, WAITING, APPROVED, REFUSED, WITHDRAWN, ERROR})
    TERMINAL = frozenset({APPROVED, REFUSED, WITHDRAWN, ERROR})


class ActionStatus:
    """Approval action statuses (lowercase)."""
    PENDING = "pending"
    APPROVED = "approved"
    CONDITIONAL = "conditional"
    REFUSED = "refused"
    CANCELLED = "cancelled"

    ALL = frozenset({PENDING, APPROVED, CONDITIONAL, REFUSED, CANCELLED})
    COMPLETED = frozenset({APPROVED, CONDITIONAL, REFUSED, CANCELLED})
    TERMINAL = frozenset({APPROVED, CONDITIONAL, REFUSED, CANCELLED})
