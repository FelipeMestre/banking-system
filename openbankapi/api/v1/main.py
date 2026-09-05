from fastapi import APIRouter

from openbankapi.api.v1.routers import (
    auth_diagnostics_router,
    customer_router,
    account_router,
    location_router,
    branch_router,
    transfer_router,
    foreign_exchange_rate_router,
    card_account_router,
    card_router,
    purchase_status_router,
)

api_router = APIRouter()
api_router.include_router(customer_router.router)
api_router.include_router(account_router.router)
api_router.include_router(location_router.router)
api_router.include_router(branch_router.router)
api_router.include_router(transfer_router.router)
api_router.include_router(auth_diagnostics_router.router)
api_router.include_router(foreign_exchange_rate_router.router)
api_router.include_router(card_account_router.router)
api_router.include_router(card_router.router)
api_router.include_router(purchase_status_router.router)
