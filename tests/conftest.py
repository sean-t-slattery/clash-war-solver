import pytest

from backend.domain import OptimizationRequest
from backend.fixtures import demo_account, demo_army, demo_layout, synthetic_pack


@pytest.fixture
def pack(): return synthetic_pack()


@pytest.fixture
def layout(): return demo_layout()


@pytest.fixture
def account(): return demo_account()


@pytest.fixture
def request_model(account, layout):
    return OptimizationRequest(account_id=account.id, base_id=layout.id, army=demo_army(), scenarios=2, budget_seconds=10)
