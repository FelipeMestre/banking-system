from fastapi import APIRouter

from openbankapi.api.v1.routers import customer_router, account_router, location_router, branch_router, transfer_router

api_router = APIRouter()
api_router.include_router(customer_router.router)
api_router.include_router(account_router.router)
api_router.include_router(location_router.router)
api_router.include_router(branch_router.router)
api_router.include_router(transfer_router.router)
