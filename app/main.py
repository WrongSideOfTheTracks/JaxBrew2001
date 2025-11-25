import os
import smtplib
from email.message import EmailMessage

try:
    from twilio.rest import Client as TwilioClient  # optional
except ImportError:
    TwilioClient = None

from datetime import datetime
import random
import uuid

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

app = FastAPI(title="JaxBrew 2001")

# Static files (even if empty for now)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates folder
templates = Jinja2Templates(directory="templates")

# -------- CONFIG --------
DUMMY_MODE = True  # set False later when ESP telemetry is live
# --- ALERT CONFIG (from environment) ---
SMTP_HOST = os.getenv("JAXBREW_SMTP_HOST")
SMTP_PORT = int(os.getenv("JAXBREW_SMTP_PORT", "587"))
SMTP_USER = os.getenv("JAXBREW_SMTP_USER")
SMTP_PASS = os.getenv("JAXBREW_SMTP_PASS")

ALERT_EMAIL_FROM = os.getenv("JAXBREW_ALERT_EMAIL_FROM")
ALERT_EMAIL_TO = os.getenv("JAXBREW_ALERT_EMAIL_TO")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")
WHATSAPP_TO = os.getenv("JAXBREW_WHATSAPP_TO")
# --------------------------------------
def send_email_alert(subject: str, body: str):
    """Send a simple email alert if email settings are configured."""
    if not (SMTP_HOST and ALERT_EMAIL_FROM and ALERT_EMAIL_TO):
        return  # email not configured, silently skip

    msg = EmailMessage()
    msg["From"] = ALERT_EMAIL_FROM
    msg["To"] = ALERT_EMAIL_TO
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER and SMTP_PASS:
                server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
    except Exception as e:
        # In real life you might log this; for now we just print
        print("Error sending email alert:", e)


def send_whatsapp_alert(message: str):
    """Send a WhatsApp alert via Twilio if configured."""
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and
            TWILIO_WHATSAPP_FROM and WHATSAPP_TO and TwilioClient):
        return  # WhatsApp not configured

    try:
        client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=message,
            from_=TWILIO_WHATSAPP_FROM,
            to=WHATSAPP_TO,
        )
    except Exception as e:
        print("Error sending WhatsApp alert:", e)

# ------------------------


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
# -------- Suppliers & Inventory --------

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

SUPPLIERS = [
    {
        "id": new_guid(),
        "name": "BrewShop UK",
        "website": "https://example-brewshop.co.uk",
    },
    {
        "id": new_guid(),
        "name": "Yeast & Hops Ltd",
        "website": "https://example-yeastandhops.com",
    },
]

def check_alerts_for_vessel(v: dict):
    """
    Check if a vessel has moved into or out of tolerance
    and send alerts on state changes.
    """
    vs = vessel_with_status(v)
    current = vs["current_temp"]
    target = vs["target_temp"]
    tol = vs["tolerance_c"]
    in_tol = vs["in_tolerance"]

    # track last state on the vessel dict itself
    prev = v.get("last_in_tolerance")
    v["last_in_tolerance"] = in_tol

    # On first run, don't alert (no previous state to compare)
    if prev is None:
        return

    vessel_name = v.get("name", v.get("code", "Unknown vessel"))
    detail = (
        f"{vessel_name}: current {current:.1f}°C, "
        f"target {target:.1f}°C ± {tol:.1f}°C"
    )

    # Went from OK -> out of tolerance
    if prev is True and not in_tol:
        subject = f"JaxBrew ALERT: {vessel_name} out of tolerance"
        body = "Vessel has gone OUT of tolerance.\n\n" + detail
        send_email_alert(subject, body)
        send_whatsapp_alert(subject + " – " + detail)

    # Went from out -> back within tolerance (optional)
    elif prev is False and in_tol:
        subject = f"JaxBrew INFO: {vessel_name} back within tolerance"
        body = "Vessel is back WITHIN tolerance.\n\n" + detail
        send_email_alert(subject, body)
        send_whatsapp_alert(subject + " – " + detail)


def get_supplier(supplier_id: str):
    for s in SUPPLIERS:
        if s["id"] == supplier_id:
            return s
    return None


INVENTORY = [
    {
        "id": new_guid(),
        "code": "MALT-MO-25KG",
        "name": "Maris Otter Pale Malt 25kg",
        "category": "malt",
        "unit": "kg",
        "preferred_supplier_id": SUPPLIERS[0]["id"],
        "supplier_product_code": "MO-25",
        "current_stock": 50.0,   # kg
        "reorder_level": 25.0,   # kg
    },
    {
        "id": new_guid(),
        "code": "HOP-CITRA-100G",
        "name": "Citra 13% AA 100g",
        "category": "hop",
        "unit": "g",
        "preferred_supplier_id": SUPPLIERS[1]["id"],
        "supplier_product_code": "CIT-100",
        "current_stock": 400.0,  # g
        "reorder_level": 200.0,  # g
    },
    {
        "id": new_guid(),
        "code": "YEAST-US05",
        "name": "Safale US-05",
        "category": "yeast",
        "unit": "packet",
        "preferred_supplier_id": SUPPLIERS[1]["id"],
        "supplier_product_code": "US-05",
        "current_stock": 10.0,   # packets
        "reorder_level": 5.0,
    },
    {
        "id": new_guid(),
        "code": "CLEAN-STARSAN-1L",
        "name": "Starsan 1L",
        "category": "cleaning",
        "unit": "L",
        "preferred_supplier_id": SUPPLIERS[0]["id"],
        "supplier_product_code": "STAR-1L",
        "current_stock": 1.5,    # L
        "reorder_level": 0.5,
    },
    {
        "id": new_guid(),
        "code": "WATER-CAMPDEN",
        "name": "Campden Tablets (50)",
        "category": "water_treatment",
        "unit": "tablet",
        "preferred_supplier_id": SUPPLIERS[0]["id"],
        "supplier_product_code": "CAMP-50",
        "current_stock": 40.0,   # tablets
        "reorder_level": 10.0,
    },
]


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
@app.get("/", response_class=HTMLResponse)
async def welcome(request: Request):
    return templates.TemplateResponse("welcome.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "vessels": VESSELS, "pumps": PUMPS},
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
        },
    )



@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request):
    # Annotate products with supplier names for display convenience
    products_for_view = []
    for p in INVENTORY:
        supplier = get_supplier(p["preferred_supplier_id"])
        products_for_view.append(
            {
                **p,
                "preferred_supplier_name": supplier["name"] if supplier else "Unknown",
            }
        )

    return templates.TemplateResponse(
        "inventory.html",
        {
            "request": request,
            "products": products_for_view,
        },
    )



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

    # Check alerts (only if you want alerts during dummy mode)
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
# --------------------------------------

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

from datetime import datetime  # you probably already have this at the top

# ... rest of your imports & code ...


@app.get("/test-email")
async def test_email():
    """
    Simple endpoint to verify SMTP/Zoho settings.
    Calls send_email_alert but always returns HTTP 200.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    subject = "JaxBrew test email"
    body = (
        "This is a test email from JaxBrew 2001 on your server.\n\n"
        f"Time (server): {now}\n"
        "If you see this, SMTP is working."
    )

    # This uses the helper you already added earlier
    send_email_alert(subject, body)

    return {"ok": True, "sent_to": ALERT_EMAIL_TO, "server_time": now}

