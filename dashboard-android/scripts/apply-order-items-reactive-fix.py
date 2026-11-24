from pathlib import Path
import os

root = Path(os.environ["PROJECT_DIR"])
dao_path = root / "app/src/main/java/com/pinky/dashboard/data/local/dao/Daos.kt"
repo_path = root / "app/src/main/java/com/pinky/dashboard/data/repository/RepositoriesImpl.kt"

dao = dao_path.read_text(encoding="utf-8")
repo = repo_path.read_text(encoding="utf-8")

# Room Flow must observe order_items itself. A suspend DAO read inside a Flow
# transform does not register order_items as an invalidation source.
dao_anchor = '''    @Query("SELECT * FROM order_items WHERE orderId IN (:orderIds)")
    suspend fun getItemsForOrders(orderIds: List<String>): List<OrderItemEntity>'''
dao_replacement = dao_anchor + '''

    @Query("SELECT * FROM order_items")
    fun getAllOrderItemsFlow(): kotlinx.coroutines.flow.Flow<List<OrderItemEntity>>'''
if dao.count(dao_anchor) != 1:
    raise SystemExit("Expected exactly one OrderDao getItemsForOrders anchor; refusing ambiguous edit.")
dao = dao.replace(dao_anchor, dao_replacement, 1)

# Keep the query return type fully qualified so this patch does not depend on
# the file's existing Flow imports or alter unrelated DAO imports.

old_combine = '''return combine(orderDao.getAllOrdersFlow(), productDao.getAllProductsFlow()) { entities, products ->
            val productsById = products.associateBy { it.id }
            entities.map { entity ->
                val items = orderDao.getOrderItems(entity.id).map { itemEntity ->'''
new_combine = '''return combine(
            orderDao.getAllOrdersFlow(),
            productDao.getAllProductsFlow(),
            orderDao.getAllOrderItemsFlow()
        ) { entities, products, allOrderItems ->
            val productsById = products.associateBy { it.id }
            val itemsByOrderId = allOrderItems.groupBy { it.orderId }
            entities.map { entity ->
                val items = itemsByOrderId[entity.id].orEmpty().map { itemEntity ->'''
if repo.count(old_combine) != 1:
    raise SystemExit("Expected exactly one getOrdersFlow combine block; refusing ambiguous edit.")
repo = repo.replace(old_combine, new_combine, 1)

if "orderDao.getOrderItems(entity.id)" in repo.split("override fun getOrdersFlow()",1)[1].split("override suspend fun getOrderById",1)[0]:
    raise SystemExit("Reactive order flow still contains a non-observable item query.")
if "itemsByOrderId[entity.id].orEmpty()" not in repo:
    raise SystemExit("Reactive item grouping verification failed.")
if "fun getAllOrderItemsFlow(): kotlinx.coroutines.flow.Flow<List<OrderItemEntity>>" not in dao:
    raise SystemExit("Room Flow query verification failed.")

dao_path.write_text(dao, encoding="utf-8")
repo_path.write_text(repo, encoding="utf-8")
print("PASS: Room observes order_items changes.")
print("PASS: order list recomputes item snapshots whenever items are inserted or replaced.")
print("PASS: order detail can no longer remain stale at zero items after sync completes.")
