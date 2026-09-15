"""Redis-backed async-status resolution, shared by all 6 domains
(transfer, purchase, card_payment, card_payment_settlement, deposit,
withdrawal). See `interfaces/status_registry.py` for the port every router
and Kafka consumer depends on, and `repositories/` for the concrete
Redis/fake adapters.
"""
