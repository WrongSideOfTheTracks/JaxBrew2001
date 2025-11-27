import os
from datetime import datetime
import random
import uuid

from fastapi import FastAPI, Request, HTTPException, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from sqlalchemy import create_engine, Column, Integer, String, Text, Float, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, Session, relationship


app = FastAPI(title="JaxBrew 2001")

# Static files (even if empty for now)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates folder
templates = Jinja2Templates(directory="templates")

# -------- CONFIG --------
DUMMY_MODE = True  # set False later when ESP telemetry is live

# Stubbed alerts (currently disabled)
def send_email_alert(subject: str, body: str):
    """Alerts currently disabled (stub)."""
    return


def send_whatsapp_alert(message: str):
    """WhatsApp alerts currently disabled (stub)."""
    return


# -------- DATABASE (MySQL via SQLAlchemy) --------
DB_URL = os.getenv(
    "JAXBREW_DB_URL",
    "mysql+pymysql://jaxbrew:StrongPass123!@localhost:3306/jaxbrew2001",
)

engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


class DBCustomer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), nullable=True)
    phone = Column(String(50), nullable=True)
    billing_address = Column(Text, nullable=True)
    shipping_address = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)


class DBSupplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), nullable=True)
    phone = Column(String(50), nullable=True)
    website = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)


class DBInventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    category = Column(String(50), nullable=False)
    unit = Column(String(20), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    supplier_product_code = Column(String(100), nullable=True)
    current_stock = Column(Float, nullable=False, default=0.0)
    reorder_level = Column(Float, nullable=False, default=0.0)

    supplier = relationship("DBSupplier")


# Create tables if they don't exist
Base.metadata.create_all(bind=engine)




def get_db() -> Session:
    """FastAPI dependency to get a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# --------------------------------------


def new_guid() -> str:
    """Generate a new GUID (UUID4) as a string."""
    return str(uuid.uuid4())



# -------- In-memory brewery layout + live fields --------
VESSELS = [
    {
        "id": new_guid(),          # GUID
        "code": "hlt",             # human short code
        "name": "Hot Liquor Tank",
        "type": "HLT",
        "volume_l": 100,
        "heated": True,
        "notes": "Electric – main strike & sparge water.",
        "current_temp": 20.0,
        "target_temp": 65.0,
        "tolerance_c": 2.0,
        "last_update": datetime.now(),
    },
    {
        "id": new_guid(),
        "code": "mash",
        "name": "Mash Tun",
        "type": "Mash tun",
        "volume_l": 100,
        "heated": False,
        "notes": "Mash and recirculation.",
        "current_temp": 20.0,
        "target_temp": 66.0,
        "tolerance_c": 2.0,
        "last_update": datetime.now(),
    },
    {
        "id": new_guid(),
        "code": "kettle",
        "name": "Kettle",
        "type": "Kettle",
        "volume_l": 100,
        "heated": False,
        "notes": "Gas fired – manually controlled boil.",
        "current_temp": 20.0,
        "target_temp": 100.0,
        "tolerance_c": 2.0,
        "last_update": datetime.now(),
    },
    {
        "id": new_guid(),
        "code": "fermenter-1",
        "name": "Fermenter 1",
        "type": "Fermenter",
        "volume_l": 100,
        "heated": False,
        "notes": "Primary fermentation.",
        "current_temp": 18.5,
        "target_temp": 19.0,
        "tolerance_c": 2.0,
        "last_update": datetime.now(),
    },
    {
        "id": new_guid(),
        "code": "fermenter-2",
        "name": "Fermenter 2",
        "type": "Fermenter",
        "volume_l": 100,
        "heated": False,
        "notes": "Primary fermentation.",
        "current_temp": 18.0,
        "target_temp": 19.0,
        "tolerance_c": 2.0,
        "last_update": datetime.now(),
    },
    {
        "id": new_guid(),
        "code": "fermenter-3",
        "name": "Fermenter 3",
        "type": "Fermenter",
        "volume_l": 100,
        "heated": False,
        "notes": "Primary fermentation.",
        "current_temp": 17.5,
        "target_temp": 19.0,
        "tolerance_c": 2.0,
        "last_update": datetime.now(),
    },
]

PUMPS = [
    {
        "id": new_guid(),
        "code": "pump-1",
        "name": "Pump 1",
        "role": "HLT → Mash",
    },
    {
        "id": new_guid(),
        "code": "pump-2",
        "name": "Pump 2",
        "role": "Mash → Kettle",
    },
    {
        "id": new_guid(),
        "code": "pump-3",
        "name": "Pump 3",
        "role": "Fermenter transfers",
    },
]


def get_vessel(vessel_id: str):
    """Find a vessel by GUID id."""
    for v in VESSELS:
        if v["id"] == vessel_id:
            return v
    return None


def get_vessel_by_code(code: str):
    """Find a vessel by human-friendly code (hlt, mash, fermenter-1...)."""
    for v in VESSELS:
        if v["code"] == code:
            return v
    return None


def simulate_temps():
    """Jitter current_temp slightly towards target_temp (dummy mode)."""
    if not DUMMY_MODE:
        return

    now = datetime.now()
    for v in VESSELS:
        cur = v.get("current_temp", 20.0)
        target = v.get("target_temp", cur)

        diff = target - cur
        step = random.uniform(-0.3, 0.3) + diff * 0.05
        new_temp = cur + step

        # Clamp ranges
        if v["type"] == "Fermenter":
            new_temp = max(15.0, min(25.0, new_temp))
        else:
            new_temp = max(0.0, min(100.0, new_temp))

        v["current_temp"] = round(new_temp, 2)
        v["last_update"] = now


def vessel_with_status(v: dict) -> dict:
    """Return a copy of the vessel dict with in_tolerance flag added."""
    current = v.get("current_temp")
    target = v.get("target_temp")
    tol = v.get("tolerance_c")

    in_tolerance = False
    if current is not None and target is not None and tol is not None:
        diff = abs(current - target)
        in_tolerance = diff <= tol   # e.g. target 65, tol 5: 61 in, 58 out

    return {**v, "in_tolerance": in_tolerance}


# -------- Suppliers & Inventory --------
SUPPLIERS = [
    {
        "id": new_guid(),
        "code": "SUP-BREWSHOP",
        "name": "BrewShop UK",
        "email": "sales@brewshop.example",
        "phone": "",
        "website": "https://example-brewshop.co.uk",
        "notes": "Main malt & hops supplier.",
    },
    {
        "id": new_guid(),
        "code": "SUP-YEASTHOPS",
        "name": "Yeast & Hops Ltd",
        "email": "orders@yeastandhops.example",
        "phone": "",
        "website": "https://example-yeastandhops.com",
        "notes": "Yeast and speciality hops.",
    },
]

def seed_suppliers_into_db():
    """If DB suppliers table is empty, seed it from the in-memory SUPPLIERS list."""
    db = SessionLocal()
    try:
        count = db.query(DBSupplier).count()
        if count == 0:
            for s in SUPPLIERS:
                sup = DBSupplier(
                    code=s["code"],
                    name=s["name"],
                    email=s["email"],
                    phone=s["phone"],
                    website=s["website"],
                    notes=s["notes"],
                )
                db.add(sup)
            db.commit()
            print("Seeded suppliers table from SUPPLIERS list.")
    except Exception as e:
        print("Error seeding suppliers:", e)
    finally:
        db.close()


# Run seeding once at startup
seed_suppliers_into_db()




def check_alerts_for_vessel(v: dict):
    """
    Check if a vessel has moved into or out of tolerance.
    Currently just updates last_in_tolerance; alerts are disabled.
    """
    vs = vessel_with_status(v)
    in_tol = vs["in_tolerance"]
    v["last_in_tolerance"] = in_tol
    # No alerting while parked


def get_supplier(supplier_id: str):
    for s in SUPPLIERS:
        if s["id"] == supplier_id:
            return s
    return None


INVENTORY_SEED = [
    {
        "code": "MALT-MO-25KG",
        "name": "Maris Otter Pale Malt 25kg",
        "category": "malt",
        "unit": "kg",
        "supplier_code": "SUP-BREWSHOP",
        "supplier_product_code": "MO-25",
        "current_stock": 50.0,   # kg
        "reorder_level": 25.0,   # kg
    },
    {
        "code": "HOP-CITRA-100G",
        "name": "Citra 13% AA 100g",
        "category": "hop",
        "unit": "g",
        "supplier_code": "SUP-YEASTHOPS",
        "supplier_product_code": "CIT-100",
        "current_stock": 400.0,  # g
        "reorder_level": 200.0,  # g
    },
    {
        "code": "YEAST-US05",
        "name": "Safale US-05",
        "category": "yeast",
        "unit": "packet",
        "supplier_code": "SUP-YEASTHOPS",
        "supplier_product_code": "US-05",
        "current_stock": 10.0,   # packets
        "reorder_level": 5.0,
    },
    {
        "code": "CLEAN-STARSAN-1L",
        "name": "Starsan 1L",
        "category": "cleaning",
        "unit": "L",
        "supplier_code": "SUP-BREWSHOP",
        "supplier_product_code": "STAR-1L",
        "current_stock": 1.5,    # L
        "reorder_level": 0.5,
    },
    {
        "code": "WATER-CAMPDEN",
        "name": "Campden Tablets (50)",
        "category": "water_treatment",
        "unit": "tablet",
        "supplier_code": "SUP-BREWSHOP",
        "supplier_product_code": "CAMP-50",
        "current_stock": 40.0,   # tablets
        "reorder_level": 10.0,
    },
]

def seed_inventory_into_db():
    """If inventory_items table is empty, seed it from INVENTORY_SEED."""
    db = SessionLocal()
    try:
        count = db.query(DBInventoryItem).count()
        if count == 0:
            for item in INVENTORY_SEED:
                supplier_id = None
                if item.get("supplier_code"):
                    supplier = (
                        db.query(DBSupplier)
                        .filter(DBSupplier.code == item["supplier_code"])
                        .first()
                    )
                    if supplier:
                        supplier_id = supplier.id

                db_item = DBInventoryItem(
                    code=item["code"],
                    name=item["name"],
                    category=item["category"],
                    unit=item["unit"],
                    supplier_id=supplier_id,
                    supplier_product_code=item["supplier_product_code"],
                    current_stock=item["current_stock"],
                    reorder_level=item["reorder_level"],
                )
                db.add(db_item)
            db.commit()
            print("Seeded inventory_items table from INVENTORY_SEED.")
    except Exception as e:
        print("Error seeding inventory:", e)
    finally:
        db.close()


# Run seeding once at startup
seed_inventory_into_db()


# -------- Pydantic models for API --------
class Telemetry(BaseModel):
    vesselId: str   # GUID
    temperature: float
    unit: str = "C"


class Setpoint(BaseModel):
    targetTemp: float


class InventoryItem(BaseModel):
    id: str
    code: str
    name: str
    category: str
    unit: str
    preferred_supplier_id: str
    supplier_product_code: str
    current_stock: float
    reorder_level: float


class ToleranceUpdate(BaseModel):
    toleranceC: float


# -------- Routes: pages --------
# -------- Routes: pages --------
@app.get("/", response_class=HTMLResponse)
async def welcome(request: Request):
    return templates.TemplateResponse(
        "welcome.html",
        {"request": request, "current_page": "home"},
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "vessels": VESSELS, "pumps": PUMPS, "current_page": "dashboard"},
    )


@app.get("/vessels/{code}", response_class=HTMLResponse)
async def vessel_detail(code: str, request: Request):
    vessel = get_vessel_by_code(code)
    if vessel is None:
        raise HTTPException(status_code=404, detail="Vessel not found")

    vessel_view = vessel_with_status(vessel)

    return templates.TemplateResponse(
        "vessel_detail.html",
        {
            "request": request,
            "vessel": vessel_view,
            "current_page": "dashboard",  # or "vessels" if you add it to navbar
        },
    )


@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, db: Session = Depends(get_db)):
    items = (
        db.query(DBInventoryItem)
        .order_by(DBInventoryItem.category, DBInventoryItem.name)
        .all()
    )
    suppliers_db = db.query(DBSupplier).order_by(DBSupplier.name).all()

    # Flatten items for the template
    products = []
    for item in items:
        supplier_name = item.supplier.name if item.supplier else "Unknown"
        products.append(
            {
                "id": item.id,
                "code": item.code,
                "name": item.name,
                "category": item.category,
                "unit": item.unit,
                "current_stock": item.current_stock,
                "reorder_level": item.reorder_level,
                "supplier_id": item.supplier_id,
                "supplier_name": supplier_name,
                "supplier_product_code": item.supplier_product_code,
            }
        )

    return templates.TemplateResponse(
        "inventory.html",
        {
            "request": request,
            "products": products,
            "suppliers": suppliers_db,   # for dropdown in the form
            "current_page": "inventory",
        },
    )

@app.post("/inventory/create")
async def create_inventory_item(
    name: str = Form(...),
    code: str = Form(...),
    category: str = Form(""),
    unit: str = Form(""),
    supplier_id: str = Form(""),
    supplier_product_code: str = Form(""),
    current_stock: str = Form("0"),
    reorder_level: str = Form("0"),
    db: Session = Depends(get_db),
):
    # Parse supplier_id
    supplier_id_int = None
    if supplier_id.strip():
        try:
            supplier_id_int = int(supplier_id)
        except ValueError:
            supplier_id_int = None

    # Parse numbers safely
    try:
        current_stock_val = float(current_stock)
    except ValueError:
        current_stock_val = 0.0

    try:
        reorder_level_val = float(reorder_level)
    except ValueError:
        reorder_level_val = 0.0

    item = DBInventoryItem(
        code=code.strip(),
        name=name.strip(),
        category=category.strip() or "other",
        unit=unit.strip() or "",
        supplier_id=supplier_id_int,
        supplier_product_code=supplier_product_code.strip(),
        current_stock=current_stock_val,
        reorder_level=reorder_level_val,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return RedirectResponse(url="/inventory", status_code=303)


@app.get("/inventory/{item_id}/edit", response_class=HTMLResponse)
async def edit_inventory_item_page(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    item = (
        db.query(DBInventoryItem)
        .filter(DBInventoryItem.id == item_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    suppliers = db.query(DBSupplier).order_by(DBSupplier.name).all()

    return templates.TemplateResponse(
        "inventory_edit.html",
        {
            "request": request,
            "item": item,
            "suppliers": suppliers,
            "current_page": "inventory",
        },
    )

@app.post("/inventory/{item_id}/edit")
async def update_inventory_item(
    item_id: int,
    name: str = Form(...),
    code: str = Form(...),
    category: str = Form(""),
    unit: str = Form(""),
    supplier_id: str = Form(""),
    supplier_product_code: str = Form(""),
    current_stock: str = Form("0"),
    reorder_level: str = Form("0"),
    db: Session = Depends(get_db),
):
    item = (
        db.query(DBInventoryItem)
        .filter(DBInventoryItem.id == item_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    supplier_id_int = None
    if supplier_id.strip():
        try:
            supplier_id_int = int(supplier_id)
        except ValueError:
            supplier_id_int = None

    try:
        current_stock_val = float(current_stock)
    except ValueError:
        current_stock_val = 0.0

    try:
        reorder_level_val = float(reorder_level)
    except ValueError:
        reorder_level_val = 0.0

    item.code = code.strip()
    item.name = name.strip()
    item.category = category.strip() or "other"
    item.unit = unit.strip() or ""
    item.supplier_id = supplier_id_int
    item.supplier_product_code = supplier_product_code.strip()
    item.current_stock = current_stock_val
    item.reorder_level = reorder_level_val

    db.commit()

    return RedirectResponse(url="/inventory", status_code=303)

@app.post("/inventory/{item_id}/delete")
async def delete_inventory_item(
    item_id: int,
    db: Session = Depends(get_db),
):
    item = (
        db.query(DBInventoryItem)
        .filter(DBInventoryItem.id == item_id)
        .first()
    )
    if not item:
        return RedirectResponse(url="/inventory", status_code=303)

    db.delete(item)
    db.commit()
    return RedirectResponse(url="/inventory", status_code=303)


@app.get("/suppliers", response_class=HTMLResponse)
async def suppliers_page(request: Request, db: Session = Depends(get_db)):
    suppliers = db.query(DBSupplier).order_by(DBSupplier.name).all()
    return templates.TemplateResponse(
        "suppliers.html",
        {
            "request": request,
            "suppliers": suppliers,
            "current_page": "suppliers",
        },
    )


@app.post("/suppliers/create")
async def create_supplier(
    name: str = Form(...),
    code: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    website: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    supplier = DBSupplier(
        code=code.strip() or None,
        name=name.strip(),
        email=email.strip(),
        phone=phone.strip(),
        website=website.strip(),
        notes=notes.strip(),
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)

    return RedirectResponse(url="/suppliers", status_code=303)


@app.get("/suppliers/{supplier_id}/edit", response_class=HTMLResponse)
async def edit_supplier_page(
    supplier_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    supplier = (
        db.query(DBSupplier)
        .filter(DBSupplier.id == supplier_id)
        .first()
    )
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    return templates.TemplateResponse(
        "supplier_edit.html",
        {
            "request": request,
            "supplier": supplier,
            "current_page": "suppliers",
        },
    )


@app.post("/suppliers/{supplier_id}/edit")
async def update_supplier(
    supplier_id: int,
    name: str = Form(...),
    code: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    website: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    supplier = (
        db.query(DBSupplier)
        .filter(DBSupplier.id == supplier_id)
        .first()
    )
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    supplier.code = code.strip() or None
    supplier.name = name.strip()
    supplier.email = email.strip()
    supplier.phone = phone.strip()
    supplier.website = website.strip()
    supplier.notes = notes.strip()

    db.commit()

    return RedirectResponse(url="/suppliers", status_code=303)


@app.post("/suppliers/{supplier_id}/delete")
async def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
):
    supplier = (
        db.query(DBSupplier)
        .filter(DBSupplier.id == supplier_id)
        .first()
    )
    if not supplier:
        return RedirectResponse(url="/suppliers", status_code=303)

    db.delete(supplier)
    db.commit()
    return RedirectResponse(url="/suppliers", status_code=303)


# ... then:

@app.get("/customers", response_class=HTMLResponse)
async def customers_page(request: Request, db: Session = Depends(get_db)):
    customers = db.query(DBCustomer).order_by(DBCustomer.name).all()
    return templates.TemplateResponse(
        "customers.html",
        {
            "request": request,
            "customers": customers,
            "current_page": "customers",
        },
    )



@app.post("/customers/create")
async def create_customer(
    name: str = Form(...),
    code: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    billing_address: str = Form(""),
    shipping_address: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    customer = DBCustomer(
        code=code.strip() or None,
        name=name.strip(),
        email=email.strip(),
        phone=phone.strip(),
        billing_address=billing_address.strip(),
        shipping_address=shipping_address.strip(),
        notes=notes.strip(),
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    return RedirectResponse(url="/customers", status_code=303)

@app.get("/customers/{customer_id}/edit", response_class=HTMLResponse)
async def edit_customer_page(
    customer_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    customer = (
        db.query(DBCustomer)
        .filter(DBCustomer.id == customer_id)
        .first()
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    return templates.TemplateResponse(
        "customer_edit.html",
        {
            "request": request,
            "customer": customer,
            "current_page": "customers",
        },
    )


@app.post("/customers/{customer_id}/edit")
async def update_customer(
    customer_id: int,
    name: str = Form(...),
    code: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    billing_address: str = Form(""),
    shipping_address: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    customer = (
        db.query(DBCustomer)
        .filter(DBCustomer.id == customer_id)
        .first()
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer.code = code.strip() or None
    customer.name = name.strip()
    customer.email = email.strip()
    customer.phone = phone.strip()
    customer.billing_address = billing_address.strip()
    customer.shipping_address = shipping_address.strip()
    customer.notes = notes.strip()

    db.commit()

    return RedirectResponse(url="/customers", status_code=303)


@app.post("/customers/{customer_id}/delete")
async def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
):
    customer = (
        db.query(DBCustomer)
        .filter(DBCustomer.id == customer_id)
        .first()
    )
    if not customer:
        # Already gone; just redirect
        return RedirectResponse(url="/customers", status_code=303)

    db.delete(customer)
    db.commit()
    return RedirectResponse(url="/customers", status_code=303)


# -------- JSON API: live data --------
@app.get("/api/vessels")
async def api_get_vessels():
    simulate_temps()
    return [vessel_with_status(v) for v in VESSELS]


@app.get("/api/vessels/{vessel_id}")
async def api_get_vessel(vessel_id: str):
    simulate_temps()
    v = get_vessel(vessel_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Unknown vessel")
    return vessel_with_status(v)


@app.post("/api/telemetry")
async def api_telemetry(data: Telemetry):
    v = get_vessel(data.vesselId)
    if v is None:
        raise HTTPException(status_code=404, detail="Unknown vessel")

    # Basic sanity
    if data.temperature < -10 or data.temperature > 120:
        raise HTTPException(status_code=400, detail="Temperature out of range")

    v["current_temp"] = data.temperature
    v["last_update"] = datetime.now()
    v.setdefault("target_temp", data.temperature)
    v.setdefault("tolerance_c", 0.0)          # ensure key exists
    v.setdefault("last_in_tolerance", None)   # start state

    check_alerts_for_vessel(v)

    return {"ok": True}


@app.post("/api/vessels/{vessel_id}/setpoint")
async def api_set_setpoint(vessel_id: str, sp: Setpoint):
    v = get_vessel(vessel_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Unknown vessel")

    if sp.targetTemp < 0 or sp.targetTemp > 100:
        raise HTTPException(status_code=400, detail="Target temperature out of range")

    v["target_temp"] = sp.targetTemp
    v["last_update"] = datetime.now()
    return {"ok": True, "targetTemp": sp.targetTemp}


@app.post("/api/vessels/{vessel_id}/tolerance")
async def api_set_tolerance(vessel_id: str, body: ToleranceUpdate):
    v = get_vessel(vessel_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Unknown vessel")

    if body.toleranceC < 0 or body.toleranceC > 50:
        raise HTTPException(status_code=400, detail="Tolerance out of range")

    v["tolerance_c"] = body.toleranceC
    v["last_update"] = datetime.now()
    return {"ok": True, "toleranceC": body.toleranceC}
