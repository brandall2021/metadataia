"""Tests de humo (FASE 1-2): verifican que la aplicacion, los modelos y la base de datos funcionan."""

from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal
from app.main import app
from app.models import Role, User

EXPECTED_TABLES = {
    "users",
    "roles",
    "permissions",
    "user_roles",
    "role_permissions",
    "ai_providers",
    "ai_models",
    "ai_agents",
    "ai_agent_versions",
    "document_types",
    "metadata_schemas",
    "metadata_fields",
    "document_type_metadata_fields",
    "vocabularies",
    "vocabulary_values",
    "repositories",
    "repository_collections",
    "documents",
    "document_pages",
    "processing_jobs",
    "extraction_runs",
    "metadata_records",
    "validation_results",
    "depositions",
    "audit_logs",
}


def test_modelos_requeridos_registrados():
    """Todas las tablas de la especificacion estan en el metadata de SQLAlchemy."""
    table_names = set(Base.metadata.tables.keys())
    missing = EXPECTED_TABLES - table_names
    assert not missing, f"Faltan tablas: {missing}"


def test_health_endpoint():
    """El endpoint /health responde."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_roundtrip_usuario_con_rol():
    """Se puede crear un usuario con rol y leerlo de vuelta."""
    db = SessionLocal()
    try:
        role = db.query(Role).filter_by(name="REVISOR").one()
        user = User(
            username="test_roundtrip",
            email="test_roundtrip@example.com",
            password_hash="hash-no-relevante",
            active=True,
        )
        user.roles.append(role)
        db.add(user)
        db.commit()
        db.refresh(user)

        fetched = db.query(User).filter_by(username="test_roundtrip").one()
        assert fetched.id == user.id
        assert [r.name for r in fetched.roles] == ["REVISOR"]
    finally:
        db.query(User).filter_by(username="test_roundtrip").delete()
        db.commit()
        db.close()