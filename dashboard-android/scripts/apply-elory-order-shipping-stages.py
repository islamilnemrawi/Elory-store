#!/usr/bin/env python3
"""Add distinct shipping-in-progress and shipped states and payment-aware labels."""
from pathlib import Path
import os

ROOT = Path(os.environ["PROJECT_DIR"]).resolve()

def replace_once(relative, old, new, label):
    path = ROOT / relative
    source = path.read_text(encoding="utf-8")
    if new in source:
        print("Already applied:", label)
        return
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count} in {relative}")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")
    print("PASS:", label)

MODEL = "app/src/main/java/com/pinky/dashboard/domain/model/Order.kt"
replace_once(
    MODEL,
'''    PREPARING("جاري التحضير"),
    SHIPPED("جاري الشحن"),
    DELIVERED("تم التسليم"),''',
'''    PREPARING("جاري التحضير"),
    SHIPPING("جاري الشحن"),
    SHIPPED("تم الشحن"),
    DELIVERED("تم التسليم"),''',
    "separate shipping in progress from shipped"
)
replace_once(
    MODEL,
'''    CANCELLED("ملغي");

    companion object {''',
'''    CANCELLED("ملغي");

    fun displayLabel(paymentMethod: PaymentMethod?): String =
        if (this == DELIVERED && paymentMethod != null && paymentMethod != PaymentMethod.COD) "تم التوصيل" else arabicLabel

    companion object {''',
    "place COD display label on each enum value"
)
replace_once(
    MODEL,
'''        val fulfillmentStatuses: List<OrderStatus> = listOf(CONFIRMING, PREPARING, SHIPPED, DELIVERED, CANCELLED)''',
'''        val fulfillmentStatuses: List<OrderStatus> = listOf(CONFIRMING, PREPARING, SHIPPING, SHIPPED, DELIVERED, CANCELLED)''',
    "include both shipping stages in status filters"
)
replace_once(
    MODEL,
'''        fun availableFor(paymentMethod: PaymentMethod): List<OrderStatus> =
            if (paymentMethod == PaymentMethod.COD) fulfillmentStatuses
            else fulfillmentStatuses.filterNot { it == CONFIRMING }

        fun fromString(value: String): OrderStatus {''',
'''        fun availableFor(paymentMethod: PaymentMethod): List<OrderStatus> =
            if (paymentMethod == PaymentMethod.COD) fulfillmentStatuses
            else fulfillmentStatuses.filterNot { it == CONFIRMING }

        fun fromString(value: String): OrderStatus {''',
    "show COD preparation as جاري التجهيز"
)
replace_once(
    MODEL,
'''                "تم الشحن", "جاري الشحن", "shipped" -> SHIPPED''',
'''                "جاري الشحن", "shipping" -> SHIPPING
                "تم الشحن", "shipped" -> SHIPPED''',
    "parse distinct shipping statuses"
)
replace_once(
    MODEL,
'''                "تم التسليم", "delivered" -> DELIVERED''',
'''                "تم التسليم", "تم التوصيل", "delivered" -> DELIVERED''',
    "accept online delivery wording as the delivered state"
)

COMMON = "app/src/main/java/com/pinky/dashboard/ui/components/CommonComponents.kt"
replace_once(
    COMMON,
'''import com.pinky.dashboard.domain.model.OrderStatus''',
'''import com.pinky.dashboard.domain.model.OrderStatus
import com.pinky.dashboard.domain.model.PaymentMethod''',
    "import payment method for COD badge labels"
)
replace_once(
    COMMON,
'''fun OrderStatusBadge(
    status: OrderStatus,
    modifier: Modifier = Modifier
) {
    val (bgColor, textColor) = when (status) {
        OrderStatus.NEW -> StatusNew.copy(alpha = 0.18f) to StatusNew
        OrderStatus.CONFIRMING -> StatusConfirming.copy(alpha = 0.18f) to StatusConfirming
        OrderStatus.PREPARING -> StatusPreparing.copy(alpha = 0.18f) to StatusPreparing
        OrderStatus.SHIPPED -> StatusShipped.copy(alpha = 0.18f) to StatusShipped
        OrderStatus.DELIVERED -> StatusDelivered.copy(alpha = 0.18f) to StatusDelivered
        OrderStatus.CANCELLED -> StatusCancelled.copy(alpha = 0.18f) to StatusCancelled
    }''',
'''fun OrderStatusBadge(
    status: OrderStatus,
    paymentMethod: PaymentMethod? = null,
    modifier: Modifier = Modifier
) {
    val (bgColor, textColor) = when (status) {
        OrderStatus.NEW -> StatusNew.copy(alpha = 0.18f) to StatusNew
        OrderStatus.CONFIRMING -> StatusConfirming.copy(alpha = 0.18f) to StatusConfirming
        OrderStatus.PREPARING -> StatusPreparing.copy(alpha = 0.18f) to StatusPreparing
        OrderStatus.SHIPPING -> StatusShipped.copy(alpha = 0.18f) to StatusShipped
        OrderStatus.SHIPPED -> StatusShipped.copy(alpha = 0.18f) to StatusShipped
        OrderStatus.DELIVERED -> StatusDelivered.copy(alpha = 0.18f) to StatusDelivered
        OrderStatus.CANCELLED -> StatusCancelled.copy(alpha = 0.18f) to StatusCancelled
    }''',
    "support distinct shipping statuses in status badge"
)
replace_once(
    COMMON,
'''            text = status.arabicLabel,''',
'''            text = status.displayLabel(paymentMethod),''',
    "render COD preparation label correctly"
)

TEST = "app/src/test/java/com/pinky/dashboard/EloryProductOptionsAndOrderStatusTest.kt"
replace_once(
    TEST,
'''import com.pinky.dashboard.domain.model.OrderStatus''',
'''import com.pinky.dashboard.domain.model.OrderStatus
import com.pinky.dashboard.domain.model.PaymentMethod''',
    "import PaymentMethod into order lifecycle regression tests"
)
replace_once(
    TEST,
'''import org.junit.Assert.assertEquals''',
'''import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse''',
    "import assertFalse into order lifecycle regression tests"
)

replace_once(
    TEST,
'''    @Test
    fun oldOrderStatusesMapToThreeCurrentFulfillmentStages() {
        assertEquals(OrderStatus.PREPARING, OrderStatus.fromString("طلب جديد"))
        assertEquals(OrderStatus.PREPARING, OrderStatus.fromString("جاري التجهيز"))
        assertEquals(OrderStatus.SHIPPED, OrderStatus.fromString("تم الشحن"))
        assertEquals(OrderStatus.SHIPPED, OrderStatus.fromString("جاري الشحن"))
        assertEquals(OrderStatus.DELIVERED, OrderStatus.fromString("تم التسليم"))
    }''',
'''    @Test
    fun orderStatusesKeepConfirmationShippingAndShipmentAsSeparateStages() {
        assertEquals(OrderStatus.CONFIRMING, OrderStatus.fromString("جاري التأكيد"))
        assertEquals(OrderStatus.PREPARING, OrderStatus.fromString("طلب جديد"))
        assertEquals(OrderStatus.PREPARING, OrderStatus.fromString("جاري التحضير"))
        assertEquals(OrderStatus.SHIPPING, OrderStatus.fromString("جاري الشحن"))
        assertEquals(OrderStatus.SHIPPED, OrderStatus.fromString("تم الشحن"))
        assertEquals(OrderStatus.DELIVERED, OrderStatus.fromString("تم التسليم"))
        assertEquals(PaymentMethod.CREDIT_CARD, PaymentMethod.fromString("card"))
        assertEquals(PaymentMethod.VODAFONE_CASH, PaymentMethod.fromString("vodafone_cash"))
        assertEquals("جاري التحضير", OrderStatus.PREPARING.displayLabel(PaymentMethod.COD))
        assertEquals("جاري التحضير", OrderStatus.PREPARING.displayLabel(PaymentMethod.CREDIT_CARD))
        assertEquals("تم التسليم", OrderStatus.DELIVERED.displayLabel(PaymentMethod.COD))
        assertEquals("تم التوصيل", OrderStatus.DELIVERED.displayLabel(PaymentMethod.CREDIT_CARD))
        assertEquals("تم التوصيل", OrderStatus.DELIVERED.displayLabel(PaymentMethod.VODAFONE_CASH))
        assertEquals(OrderStatus.DELIVERED, OrderStatus.fromString("تم التوصيل"))
        assertEquals(OrderStatus.CONFIRMING, OrderStatus.fromString("جاري التأكيد"))
        assertEquals(listOf(OrderStatus.CONFIRMING, OrderStatus.PREPARING, OrderStatus.SHIPPING, OrderStatus.SHIPPED, OrderStatus.DELIVERED, OrderStatus.CANCELLED), OrderStatus.availableFor(PaymentMethod.COD))
        assertFalse(OrderStatus.availableFor(PaymentMethod.CREDIT_CARD).contains(OrderStatus.CONFIRMING))
    }''',
    "update regression tests for the explicit payment-aware order lifecycle"
)

CHART = "app/src/main/java/com/pinky/dashboard/ui/components/AnalyticsChart.kt"
replace_once(
    CHART,
'''                                        OrderStatus.PREPARING -> StatusPreparing
                                        OrderStatus.SHIPPED -> StatusShipped''',
'''                                        OrderStatus.PREPARING -> StatusPreparing
                                        OrderStatus.SHIPPING -> StatusShipped
                                        OrderStatus.SHIPPED -> StatusShipped''',
    "analytics donut status color for shipping in progress"
)
replace_once(
    CHART,
'''                                OrderStatus.PREPARING -> StatusPreparing
                                OrderStatus.SHIPPED -> StatusShipped''',
'''                                OrderStatus.PREPARING -> StatusPreparing
                                OrderStatus.SHIPPING -> StatusShipped
                                OrderStatus.SHIPPED -> StatusShipped''',
    "analytics legend status color for shipping in progress"
)

SHIPPING = "app/src/main/java/com/pinky/dashboard/ui/screens/shipping/ShippingScreen.kt"
replace_once(
    SHIPPING,
'''orders.count { it.status == OrderStatus.SHIPPED || it.status == OrderStatus.DELIVERED }''',
'''orders.count { it.status == OrderStatus.SHIPPING || it.status == OrderStatus.SHIPPED || it.status == OrderStatus.DELIVERED }''',
    "include in-transit and shipped orders in shipping totals"
)

ORDERS = "app/src/main/java/com/pinky/dashboard/ui/screens/orders/OrdersScreen.kt"
replace_once(
    ORDERS,
'''OrderStatusBadge(
                        status = order.status,
                        modifier = Modifier.clickable { showStatusMenu = true }
                    )''',
'''OrderStatusBadge(
                        status = order.status,
                        paymentMethod = order.paymentMethod,
                        modifier = Modifier.clickable { showStatusMenu = true }
                    )''',
    "show payment-aware COD badge in order list"
)
replace_once(
    ORDERS,
'''text = { Text(status.arabicLabel) },
                                onClick = {
                                    onQuickStatusChange(status)''',
'''text = { Text(status.displayLabel(order.paymentMethod)) },
                                onClick = {
                                    onQuickStatusChange(status)''',
    "show distinct status labels in quick status menu"
)

DETAIL = "app/src/main/java/com/pinky/dashboard/ui/screens/orders/OrderDetailDialog.kt"
replace_once(
    DETAIL,
'''OrderStatusBadge(status = order.status)''',
'''OrderStatusBadge(status = order.status, paymentMethod = order.paymentMethod)''',
    "show payment-aware status in order details"
)
replace_once(
    DETAIL,
'''text = { Text(status.arabicLabel) },
                                                onClick = {''',
'''text = { Text(status.displayLabel(order.paymentMethod)) },
                                                onClick = {''',
    "show distinct status labels in order detail selector"
)

DASH = "app/src/main/java/com/pinky/dashboard/ui/screens/dashboard/DashboardScreen.kt"
replace_once(
    DASH,
'''OrderStatusBadge(status = order.status)''',
'''OrderStatusBadge(status = order.status, paymentMethod = order.paymentMethod)''',
    "show payment-aware COD badge on dashboard"
)

checks = {
    MODEL: ("SHIPPING(\"جاري الشحن\")", "SHIPPED(\"تم الشحن\")", "fun displayLabel(paymentMethod: PaymentMethod?)", '"جاري الشحن", "shipping" -> SHIPPING'),
    COMMON: ("OrderStatus.SHIPPING -> StatusShipped", "status.displayLabel(paymentMethod)"),
    CHART: ("OrderStatus.SHIPPING -> StatusShipped",),
    SHIPPING: ("OrderStatus.SHIPPING || it.status == OrderStatus.SHIPPED",),
    ORDERS: ("status.displayLabel(order.paymentMethod)", "paymentMethod = order.paymentMethod"),
    DETAIL: ("status.displayLabel(order.paymentMethod)", "paymentMethod = order.paymentMethod"),
    DASH: ("paymentMethod = order.paymentMethod",)
}
for relative, markers in checks.items():
    source = (ROOT / relative).read_text(encoding="utf-8")
    missing = [m for m in markers if m not in source]
    if missing:
        raise SystemExit(f"Shipping-state verification failed in {relative}: {missing}")
print("PASS: Dashboard now exposes جاري التأكيد (COD), payment-specific preparation label, جاري الشحن, تم الشحن, delivery, and cancellation.")
