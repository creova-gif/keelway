"""Demo Microservice for Keelway Governance Testing."""

def health_check():
    return {"status": "ok", "service": "demo_service", "version": "1.0.0"}

def calculate_discount(amount: float, discount_pct: float) -> float:
    if discount_pct < 0 or discount_pct > 100:
        raise ValueError("Invalid discount percentage")
    return round(amount * (1.0 - discount_pct / 100.0), 2)
