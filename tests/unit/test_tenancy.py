from app.core.tenancy import DEFAULT_TENANT_ID
from app.db.models import Image, ModelCall, Post


def test_core_records_have_tenant_ownership_columns() -> None:
    assert "tenant_id" in Image.__table__.c
    assert "tenant_id" in Post.__table__.c
    assert "tenant_id" in ModelCall.__table__.c


def test_post_idempotency_is_scoped_to_a_tenant() -> None:
    constraint_names = {constraint.name for constraint in Post.__table__.constraints}

    assert "uq_posts_tenant_idempotency_key" in constraint_names
    assert Post.tenant_id.default is not None
    assert Post.tenant_id.default.arg == DEFAULT_TENANT_ID
