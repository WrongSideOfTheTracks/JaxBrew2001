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


# -------- Pydantic models for API --------
class Telemetry(BaseModel):
    vesselId: str   # GUID
    temperature: float
    unit: str = "C"


class Setpoint(BaseModel):
    targetTemp: float
# -----------------------------------------


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

    return templates.TemplateResponse(
        "vessel_detail.html",
        {"request": request, "vessel": vessel},
    )
# --------------------------------


# -------- JSON API: live data --------
@app.get("/api/vessels")
async def api_get_vessels():
    simulate_temps()
    return VESSELS


@app.get("/api/vessels/{vessel_id}")
async def api_get_vessel(vessel_id: str):
    simulate_temps()
    v = get_vessel(vessel_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Unknown vessel")
    return v


@app.post("/api/telemetry")
async def api_telemetry(data: Telemetry):
    v = get_vessel(data.vesselId)
    if v is None:
        raise HTTPException(status_code=404, detail="Unknown vessel")

    if data.temperature < -10 or data.temperature > 120:
        raise HTTPException(status_code=400, detail="Temperature out of range")

    v["current_temp"] = data.temperature
    v["last_update"] = datetime.now()
    v.setdefault("target_temp", data.temperature)
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
