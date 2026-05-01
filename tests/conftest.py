"""
PlantMind AI - Test Configuration
Pytest fixtures and utilities for comprehensive testing
"""

import os
import sys
import tempfile
import importlib
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.database.connection import Base, get_db
from src.database.models import (
    Customer, EmailLog, Order, User,
    Supplier, RawMaterial, Product, Machine,
    ProductionSchedule, ProductionProgress, ReorderLog
)
from src.app import app


# Test database (in-memory SQLite for complete isolation)
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def engine():
    """Create test database engine (function-scoped for isolation)."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(engine):
    """Create fresh database session for each test."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function", autouse=True)
def patch_test_sessionlocal(db_session):
    """Patch SessionLocal references so app/tests share one DB."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=db_session.get_bind()
    )

    db_connection = importlib.import_module("src.database.connection")
    v1_processor_module = importlib.import_module("src.processors.v1_email_processor")
    v1_routes = importlib.import_module("src.routes.v1_routes")
    v2_routes = importlib.import_module("src.routes.v2_routes")
    owner_routes = importlib.import_module("src.routes.owner_router")

    original_connection_session = db_connection.SessionLocal
    original_v1_processor_session = v1_processor_module.SessionLocal
    original_v1_routes_session = v1_routes.SessionLocal
    original_v2_routes_session = v2_routes.SessionLocal
    original_owner_routes_session = owner_routes.SessionLocal

    db_connection.SessionLocal = TestingSessionLocal
    v1_processor_module.SessionLocal = TestingSessionLocal
    v2_routes.SessionLocal = TestingSessionLocal
    v1_routes.SessionLocal = TestingSessionLocal
    owner_routes.SessionLocal = TestingSessionLocal
    v1_routes._login_attempts.clear()
    try:
        yield
    finally:
        db_connection.SessionLocal = original_connection_session
        v1_processor_module.SessionLocal = original_v1_processor_session
        v1_routes.SessionLocal = original_v1_routes_session
        v2_routes.SessionLocal = original_v2_routes_session
        owner_routes.SessionLocal = original_owner_routes_session
        v1_routes._login_attempts.clear()


@pytest.fixture(scope="function")
def client(db_session, patch_test_sessionlocal):
    """Create test client with overridden database dependency."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    # Override session middleware for testing
    from starlette.middleware.sessions import SessionMiddleware
    from src.security import SecurityHeadersMiddleware
    
    # Create fresh app for each test
    from src.routes.v1_routes import create_v1_app
    test_app = create_v1_app()
    test_app.add_middleware(
        SessionMiddleware,
        secret_key="test-secret-key-for-testing-only",
        session_cookie="plantmind_test_session",
        max_age=28800,
        same_site="lax",
        https_only=False,
    )
    test_app.add_middleware(SecurityHeadersMiddleware)
    
    with TestClient(test_app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_customer(db_session):
    """Create sample customer for testing."""
    customer = Customer(
        name="Test Customer",
        email="test@example.com",
        phone="1234567890",
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


@pytest.fixture
def sample_order(db_session, sample_customer):
    """Create sample order for testing."""
    order = Order(
        customer_id=sample_customer.customer_id,
        product_name="HDPE Cap 50mm",
        quantity=5000,
        required_delivery_date=datetime(2025, 6, 15).date(),
        special_instructions="Food-grade certified",
        status="new",
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture
def sample_flagged_order(db_session, sample_customer):
    """Create sample flagged order for testing."""
    order = Order(
        customer_id=sample_customer.customer_id,
        product_name="Unknown Product",
        quantity=0,
        required_delivery_date=None,
        special_instructions="",
        status="needs_review",
        created_at=datetime.now(timezone.utc)
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture
def authenticated_client(client):
    """Create authenticated test client."""
    import bcrypt
    from src.database.connection import SessionLocal
    import uuid
    
    # Generate unique username to avoid conflicts
    unique_id = str(uuid.uuid4())[:8]
    username = f"testuser_{unique_id}"
    
    db = SessionLocal()
    
    # Clean up any existing test users with this pattern
    db.query(User).filter(User.username.like("testuser_%")).delete(synchronize_session=False)
    db.commit()
    
    # Create new test user
    hashed_pw = bcrypt.hashpw("testpass123".encode(), bcrypt.gensalt()).decode()
    user = User(
        username=username,
        password_hash=hashed_pw,
        role="office_staff",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    
    # Login
    response = client.post(
        "/login",
        data={"username": username, "password": "testpass123"},
        follow_redirects=False
    )
    assert response.status_code == 303, f"Login failed: {response.text}"
    
    yield client
    
    # Cleanup after test
    db = SessionLocal()
    db.query(User).filter(User.username == username).delete(synchronize_session=False)
    db.commit()
    db.close()


@pytest.fixture
def temp_pdf_file():
    """Create temporary PDF file for testing."""
    # Minimal valid PDF content
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids []\n/Count 0\n>>\nendobj\nxref\n0 3\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \ntrailer\n<<\n/Size 3\n/Root 1 0 R\n>>\nstartxref\n109\n%%EOF"
    
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_content)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_docx_file():
    """Create temporary DOCX file for testing."""
    # Minimal valid DOCX (ZIP with XML)
    import zipfile
    import io
    
    docx_buffer = io.BytesIO()
    with zipfile.ZipFile(docx_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # [Content_Types].xml
        zf.writestr('[Content_Types].xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>''')
        
        # _rels/.rels
        zf.writestr('_rels/.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>''')
        
        # word/_rels/document.xml.rels
        zf.writestr('word/_rels/document.xml.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>''')
        
        # word/document.xml
        zf.writestr('word/document.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body>
<w:p>
<w:r>
<w:t>Purchase Order PO-2024-001</w:t>
</w:r>
</w:p>
<w:p>
<w:r>
<w:t>Customer: Rajesh Polymers</w:t>
</w:r>
</w:p>
<w:p>
<w:r>
<w:t>Product: HDPE Cap 50mm</w:t>
</w:r>
</w:p>
<w:p>
<w:r>
<w:t>Quantity: 10000 units</w:t>
</w:r>
</w:p>
<w:p>
<w:r>
<w:t>Delivery Date: 2025-06-15</w:t>
</w:r>
</w:p>
</w:body>
</w:document>''')
    
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        f.write(docx_buffer.getvalue())
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


class MockEmailReader:
    """Mock email reader for testing without Gmail API."""
    
    def __init__(self, emails=None):
        self.emails = emails or []
        self.marked_as_read = []
    
    def get_unread_emails(self, max_results=50):
        return self.emails[:max_results]
    
    def mark_email_as_read(self, message_id):
        self.marked_as_read.append(message_id)
        return True
    
    def download_attachment_data(self, message_id, attachment_id):
        return b"Test attachment content"


@pytest.fixture
def mock_emails():
    """Sample emails for testing."""
    return [
        {
            "id": "msg_001",
            "message_id": "gmail_001",
            "from": "buyer@customer.com",
            "from_email": "buyer@customer.com",
            "to": "factory@plantmind.com",
            "to_email": "factory@plantmind.com",
            "subject": "Purchase Order #PO-2024-001 - HDPE Caps",
            "body": "Please find attached our purchase order for 5000 units of HDPE caps.",
            "attachments": [{"filename": "PO-2024-001.pdf", "mimeType": "application/pdf", "attachmentId": "att_001"}],
            "date": "Mon, 15 Jan 2024 10:00:00 +0000",
        },
        {
            "id": "msg_002",
            "message_id": "gmail_002",
            "from": "spam@marketing.com",
            "from_email": "spam@marketing.com",
            "to": "factory@plantmind.com",
            "subject": "Special Offer! Buy Now!",
            "body": "Click here for amazing discounts! Limited time only!",
            "attachments": [],
            "date": "Mon, 15 Jan 2024 11:00:00 +0000",
        },
        {
            "id": "msg_003",
            "message_id": "gmail_003",
            "from": "new@customer.com",
            "from_email": "new@customer.com",
            "to": "factory@plantmind.com",
            "subject": "Requirement for Plastic Containers",
            "body": "We are a new customer looking for 2000 plastic containers. Please quote.",
            "attachments": [],
            "date": "Mon, 15 Jan 2024 12:00:00 +0000",
        },
    ]


# V2 Fixtures
@pytest.fixture
def sample_supplier(db_session):
    """Create a sample supplier for testing."""
    from src.database.models import Supplier
    import uuid
    
    supplier = Supplier(
        name=f"Test Supplier {uuid.uuid4().hex[:8]}",
        email="supplier@test.com",
        phone="9876543210",
        address="123 Test Street, Mumbai",
        material_supplied="HDPE, PP, LDPE"
    )
    db_session.add(supplier)
    db_session.commit()
    return supplier


@pytest.fixture
def sample_material(db_session, sample_supplier):
    """Create a sample raw material for testing."""
    from src.database.models import RawMaterial
    
    material = RawMaterial(
        name="HDPE Test Material",
        type="HDPE",
        current_stock_kg=1000.0,
        reorder_level_kg=200.0,
        reorder_quantity_kg=500.0,
        unit_price_per_kg=150.0,
        supplier_id=sample_supplier.supplier_id
    )
    db_session.add(material)
    db_session.commit()
    return material
