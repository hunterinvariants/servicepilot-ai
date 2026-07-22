"""Initial multi-tenant service operations schema."""
from alembic import op
from app.database import Base
import app.models  # noqa: F401

revision = "20260722_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    Base.metadata.create_all(bind=op.get_bind())
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'audit_events is append-only'; END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER audit_events_append_only BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_mutation();
        """)


def downgrade():
    Base.metadata.drop_all(bind=op.get_bind())

