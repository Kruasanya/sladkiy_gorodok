"""Ограничение доступа к данным организаций и обфускация цифр для тестового клиента.

Если у пользователя в профиле указана организация, он видит данные только этой
организации независимо от параметров запроса. Если профиль помечен как
is_test_client, числовые показатели в ответе искажаются:
- для Cash Flow — линейно (множитель + сдвиг), чтобы сохранить тренд для модели;
- везде остальное — псевдослучайно (правдоподобный разброс), чтобы не светить
  реальные суммы.
"""

from __future__ import annotations

import random
from decimal import Decimal


def get_profile(user):
    return getattr(user, "profile", None)


def scoped_organization_ids(request) -> list[str] | None:
    profile = get_profile(request.user)
    if profile and profile.organization_id:
        return [str(profile.organization_id)]
    return None


def is_test_client(user) -> bool:
    profile = get_profile(user)
    return bool(profile and profile.is_test_client)


def _user_seed(user) -> int:
    return hash(("obfuscation-seed", getattr(user, "id", 0))) & 0xFFFFFFFF


def linear_distortion_params(user) -> tuple[float, float]:
    rng = random.Random(_user_seed(user))
    multiplier = rng.uniform(0.7, 1.3)
    shift = rng.uniform(-5000, 5000)
    return multiplier, shift


AMOUNT_KEYS = {
    "amount",
    "amount_total",
    "gross_sales_total",
    "returns_total",
    "quantity_total",
    "gross_quantity_total",
    "returns_quantity_total",
    "quantity",
    "sales_total",
    "payments_total",
    "difference",
    "value",
    "inflow",
    "outflow",
    "net_cash_flow",
    "predicted_inflow",
    "predicted_outflow",
    "predicted_net_cash_flow",
}

CASHFLOW_KEYS = {"inflow", "outflow", "net_cash_flow", "predicted_inflow", "predicted_outflow", "predicted_net_cash_flow"}


def _jitter(value, rng: random.Random):
    if value in (None, 0, Decimal("0")):
        return value
    numeric = float(value)
    factor = rng.uniform(0.4, 1.8)
    return round(numeric * factor, 2)


def _distort(value, multiplier: float, shift: float):
    if value is None:
        return value
    numeric = float(value)
    return round(numeric * multiplier + shift, 2)


def _walk(data, keys, transform, rng_factory):
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key in keys and isinstance(value, (int, float, Decimal)):
                result[key] = transform(value, rng_factory(key))
            else:
                result[key] = _walk(value, keys, transform, rng_factory)
        return result
    if isinstance(data, list):
        return [_walk(item, keys, transform, rng_factory) for item in data]
    return data


def randomize_json(data, user):
    base_seed = _user_seed(user)
    counter = {"n": 0}

    def rng_factory(_key):
        counter["n"] += 1
        return random.Random(base_seed + counter["n"])

    return _walk(data, AMOUNT_KEYS, lambda v, rng: _jitter(v, rng), rng_factory)


def linear_distort_json(data, user):
    multiplier, shift = linear_distortion_params(user)

    def transform(value, _rng):
        return _distort(value, multiplier, shift)

    return _walk(data, CASHFLOW_KEYS, transform, lambda _key: None)


class TestClientObfuscationMixin:
    """Подмешивается в APIView, чтобы искажать суммы для тестового клиента."""

    cashflow_response = False

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        user = getattr(request, "user", None)
        if user is not None and is_test_client(user) and response.data is not None:
            if self.cashflow_response:
                response.data = linear_distort_json(response.data, user)
            else:
                response.data = randomize_json(response.data, user)
        return response
