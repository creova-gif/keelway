import pytest
from app import health_check, calculate_discount

def test_health_check():
    res = health_check()
    assert res["status"] == "ok"
    assert res["service"] == "demo_service"

def test_calculate_discount():
    assert calculate_discount(100.0, 20.0) == 80.0
    assert calculate_discount(50.0, 10.0) == 45.0
