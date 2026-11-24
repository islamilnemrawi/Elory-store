#!/usr/bin/env python3
"""Make dashboard payment badges distinguish cash, card, wallet, and failed payments."""
from pathlib import Path
import os

ROOT = Path(os.environ["PROJECT_DIR"]).resolve()

def replace_once(relative: str, old: str, new: str, label: str) -> None:
    path = ROOT / relative
    if not path.is_file():
        raise SystemExit(f"Missing {relative} for {label}")
    source = path.read_text(encoding="utf-8")
    if new in source:
        print(f"Already applied: {label}")
        return
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count} in {relative}")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")
    print("PASS:", label)

MODEL = "app/src/main/java/com/pinky/dashboard/domain/model/Order.kt"
REPOSITORY = "app/src/main/java/com/pinky/dashboard/data/repository/RepositoriesImpl.kt"

replace_once(
    MODEL,
    """    COD("الدفع عند الاستلام"),
    INSTAPAY("إنستاباي (InstaPay)"),
    VODAFONE_CASH("فودافون كاش / محافظ إلكترونية"),
    CREDIT_CARD("بطاقة بنكية / فيزا"),
    INSTAPAY_WALLET("إنستاباي / محفظة إلكترونية"),
    ONLINE_CARD("دفع إلكتروني");""",
    """    COD("كاش - الدفع عند الاستلام"),
    INSTAPAY("أونلاين - إنستاباي"),
    VODAFONE_CASH("أونلاين - فودافون كاش"),
    CREDIT_CARD("أونلاين - فيزا"),
    INSTAPAY_WALLET("أونلاين - إنستاباي / محفظة إلكترونية"),
    ONLINE_CARD("أونلاين");""",
    "show cash versus online method in order cards and details"
)

replace_once(
    REPOSITORY,
    """                            val unpaid = status in setOf("جاري الدفع", "فشل الدفع", "فشل إنشاء الدفع", "payment pending", "pending payment", "payment failed", "failed payment")
                            if (status in setOf("تم التسليم", "delivered") || (online && !unpaid)) "PAID" else "PENDING" """.rstrip(),
    """                            val failed = status in setOf("فشل الدفع", "فشل إنشاء الدفع", "payment failed", "failed payment", "failed to create payment")
                            val unpaid = status in setOf("جاري الدفع", "payment pending", "pending payment")
                            when {
                                failed -> "FAILED"
                                status in setOf("تم التسليم", "delivered") || (online && !unpaid) -> "PAID"
                                else -> "PENDING"
                            }""",
    "map Paymob failures to PaymentStatus.FAILED instead of pending"
)

model = (ROOT / MODEL).read_text(encoding="utf-8")
repository = (ROOT / REPOSITORY).read_text(encoding="utf-8")
for marker in ("COD(\"كاش - الدفع عند الاستلام\")", "VODAFONE_CASH(\"أونلاين - فودافون كاش\")", "CREDIT_CARD(\"أونلاين - فيزا\")"):
    if marker not in model:
        raise SystemExit("Payment method label verification failed: " + marker)
for marker in ('failed -> "FAILED"', "val failed = status in setOf"):
    if marker not in repository:
        raise SystemExit("Payment status verification failed: " + marker)
print("PASS: dashboard distinguishes cash/online payment methods and marks failed Paymob payments as FAILED.")
