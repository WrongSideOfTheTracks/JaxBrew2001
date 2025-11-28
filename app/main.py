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


class DBFermentable(Base):
    __tablename__ = "fermentables"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    type = Column(String(50), nullable=False)         # Grain / Adjunct / Extract
    subcategory = Column(String(50), nullable=True)   # Base Malt, Caramel Malt, Sugar, etc.
    srm_min = Column(Float, nullable=True)
    srm_max = Column(Float, nullable=True)
    batch_max_pct = Column(Float, nullable=True)      # e.g. 100.0 = 100%
    dp_min = Column(Float, nullable=True)             # diastatic power min
    dp_max = Column(Float, nullable=True)             # diastatic power max
    sg = Column(Float, nullable=True)                 # e.g. 1.037


class DBYeast(Base):
    __tablename__ = "yeasts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    lab = Column(String(100), nullable=True)          # White Labs, Wyeast, etc.
    type = Column(String(50), nullable=True)          # Ale, Lager, Wheat, Wine...
    form = Column(String(20), nullable=True)          # Liquid, Dry
    temp_min_f = Column(Float, nullable=True)         # e.g. 65.0
    temp_max_f = Column(Float, nullable=True)         # e.g. 70.0
    attenuation_pct = Column(Float, nullable=True)    # e.g. 75.0
    flocculation = Column(String(50), nullable=True)  # Low / Medium / High / Very High
    notes = Column(Text, nullable=True)

class DBHop(Base):
    __tablename__ = "hops"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), unique=True, index=True, nullable=False)
    origin = Column(String(100), nullable=True)
    alpha_acid = Column(Float, nullable=True)   # stored as % AA
    hop_type = Column(String(50), nullable=True)  # Aroma / Bittering / Both


# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

FERMENTABLE_SEED = [
    # name, type, subcategory, SRM, Batch Max, Diastatic Power, SG
    {"name": "2-Row Pale Malt", "type": "Grain", "subcategory": "Base Malt",
     "srm": "1.5-3.5", "batch_max": "100%", "dp": "50-150", "sg": "1.037"},
    {"name": "6-Row Pale Malt", "type": "Grain", "subcategory": "Base Malt",
     "srm": "2", "batch_max": "100%", "dp": "160", "sg": "1.035"},
    {"name": "Acidulated Malt", "type": "Grain", "subcategory": "Base Malt",
     "srm": "1.5-3", "batch_max": "10%", "dp": "0", "sg": "1.027"},
    {"name": "Amber Malt", "type": "Grain", "subcategory": "Caramel Malt",
     "srm": "22-30", "batch_max": "20%", "dp": "0", "sg": "1.032"},
    {"name": "Aromatic Malt", "type": "Grain", "subcategory": "Roasted Malt",
     "srm": "20-30", "batch_max": "10%", "dp": "20", "sg": "1.035"},
    {"name": "Biscuit Malt", "type": "Grain", "subcategory": "Roasted Malt",
     "srm": "28-30", "batch_max": "10%", "dp": "0", "sg": "1.035"},
    {"name": "Black (Patent) Malt", "type": "Grain", "subcategory": "Roasted Malt",
     "srm": "400-500", "batch_max": "10%", "dp": "0", "sg": "1.027"},
    {"name": "Black Barley", "type": "Grain", "subcategory": "Roasted Malt",
     "srm": "400-530", "batch_max": "10%", "dp": "0", "sg": "1.027"},
    {"name": "Brown Malt", "type": "Grain", "subcategory": "Roasted Malt",
     "srm": "65", "batch_max": "10%", "dp": "0", "sg": "1.034"},
    {"name": "Cara Ruby", "type": "Grain", "subcategory": "Caramel Malt",
     "srm": "17-22", "batch_max": "25%", "dp": "-", "sg": "1.033"},
    {"name": "Carafoam", "type": "Grain", "subcategory": "Caramel Malt",
     "srm": "1-2", "batch_max": "40%", "dp": "15-48", "sg": "1.035"},
    {"name": "Caramel/Crystal Malt", "type": "Grain", "subcategory": "Caramel Malt",
     "srm": "10-110", "batch_max": "15%", "dp": "0", "sg": "1.035"},
    {"name": "Carapils (Dextrin)", "type": "Grain", "subcategory": "Caramel Malt",
     "srm": "1-2", "batch_max": "5%", "dp": "0", "sg": "1.033"},
    {"name": "Chit Malt", "type": "Grain", "subcategory": "Raw Malt",
     "srm": "1-2", "batch_max": "15%", "dp": "75", "sg": "1.030"},
    {"name": "Chocolate Malt", "type": "Grain", "subcategory": "Roasted Malt",
     "srm": "350", "batch_max": "10%", "dp": "0", "sg": "1.025"},
    {"name": "Dextrose (Corn Sugar)", "type": "Adjunct", "subcategory": "Sugar",
     "srm": "0", "batch_max": "5%", "dp": "0", "sg": "1.041"},
    {"name": "Dry Malt Extract (DME)", "type": "Grain", "subcategory": "Extract",
     "srm": "3-18", "batch_max": "100%", "dp": "0", "sg": "1.044"},
    {"name": "Flaked Barley", "type": "Grain", "subcategory": "Raw Malt",
     "srm": "2", "batch_max": "20%", "dp": "0", "sg": "1.032"},
    {"name": "Flaked Corn (Maize)", "type": "Grain", "subcategory": "Raw Malt",
     "srm": "1", "batch_max": "10%", "dp": "0", "sg": "1.040"},
    {"name": "Flaked Oats", "type": "Grain", "subcategory": "Raw Malt",
     "srm": "1", "batch_max": "30%", "dp": "0", "sg": "1.033"},
    {"name": "Flaked Rice", "type": "Grain", "subcategory": "Raw Malt",
     "srm": "1", "batch_max": "40%", "dp": "0", "sg": "1.040"},
    {"name": "Flaked Rye", "type": "Grain", "subcategory": "Raw Malt",
     "srm": "2", "batch_max": "10%", "dp": "0", "sg": "1.036"},
    {"name": "Flaked Spelt", "type": "Grain", "subcategory": "Raw Malt",
     "srm": "1-2", "batch_max": "60%", "dp": "0", "sg": "1.032"},
    {"name": "Flaked Wheat", "type": "Grain", "subcategory": "Raw Malt",
     "srm": "2", "batch_max": "40%", "dp": "0", "sg": "1.034"},
    {"name": "Golden Promise", "type": "Grain", "subcategory": "Base Malt",
     "srm": "2-3", "batch_max": "100%", "dp": "75", "sg": "1.037"},
    {"name": "Grits", "type": "Grain", "subcategory": "Raw Malt",
     "srm": "1", "batch_max": "10%", "dp": "0", "sg": "1.037"},
    {"name": "Honey", "type": "Adjunct", "subcategory": "Sugar",
     "srm": "1", "batch_max": "100%", "dp": "0", "sg": "1.035"},
    {"name": "Honey Malt", "type": "Grain", "subcategory": "Caramel Malt",
     "srm": "25", "batch_max": "0%", "dp": "0", "sg": "1.035"},
    {"name": "Lactose (Milk Sugar)", "type": "Adjunct", "subcategory": "Sugar",
     "srm": "0", "batch_max": "10%", "dp": "0", "sg": "1.041"},
    {"name": "Liquid Malt Extract (LME)", "type": "Grain", "subcategory": "Extract",
     "srm": "3-18", "batch_max": "100%", "dp": "0", "sg": "1.037"},
    {"name": "Malted Oats", "type": "Grain", "subcategory": "Roasted Malt",
     "srm": "2-2.5", "batch_max": "10%", "dp": "0", "sg": "1.030"},
    {"name": "Maltodextrin", "type": "Adjunct", "subcategory": "Sugar",
     "srm": "0", "batch_max": "5%", "dp": "0", "sg": "1.040"},
    {"name": "Maple Syrup", "type": "Adjunct", "subcategory": "Sugar",
     "srm": "35", "batch_max": "10%", "dp": "0", "sg": "1.030"},
    {"name": "Maris Otter", "type": "Grain", "subcategory": "Base Malt",
     "srm": "2.5", "batch_max": "100%", "dp": "75", "sg": "1.038"},
    {"name": "Mild Malt", "type": "Grain", "subcategory": "Base Malt",
     "srm": "4", "batch_max": "100%", "dp": "50-65", "sg": "1.037"},
    {"name": "Molasses", "type": "Adjunct", "subcategory": "Sugar",
     "srm": "80", "batch_max": "5%", "dp": "0", "sg": "1.036"},
    {"name": "Munich Malt", "type": "Grain", "subcategory": "Base Malt",
     "srm": "10-20", "batch_max": "80%", "dp": "25-70", "sg": "1.038"},
    {"name": "Peat Smoked Malt", "type": "Grain", "subcategory": "Base Malt",
     "srm": "3", "batch_max": "10%", "dp": "120", "sg": "1.038"},
    {"name": "Pilsner Malt", "type": "Grain", "subcategory": "Base Malt",
     "srm": "1.5-2", "batch_max": "100%", "dp": "75-140", "sg": "1.037"},
    {"name": "Rice Hulls", "type": "Grain", "subcategory": "Raw Malt",
     "srm": "0", "batch_max": "5%", "dp": "0", "sg": "0"},
    {"name": "Roasted Barley", "type": "Grain", "subcategory": "Roasted Malt",
     "srm": "300-500", "batch_max": "10%", "dp": "0", "sg": "1.030"},
    {"name": "Roasted Wheat", "type": "Grain", "subcategory": "Roasted Malt",
     "srm": "425", "batch_max": "10%", "dp": "120", "sg": "1.034"},
    {"name": "Rye Malt", "type": "Grain", "subcategory": "Base Malt",
     "srm": "3-5", "batch_max": "15%", "dp": "105", "sg": "1.038"},
    {"name": "Smoked Malt", "type": "Grain", "subcategory": "Base Malt",
     "srm": "5", "batch_max": "100%", "dp": "90-140", "sg": "1.037"},
    {"name": "Special Roast", "type": "Grain", "subcategory": "Roasted Malt",
     "srm": "40-50", "batch_max": "10%", "dp": "0", "sg": "1.033"},
    {"name": "Table Sugar (Sucrose)", "type": "Adjunct", "subcategory": "Sugar",
     "srm": "1", "batch_max": "10%", "dp": "0", "sg": "1.046"},
    {"name": "Torrified Wheat", "type": "Grain", "subcategory": "Raw Malt",
     "srm": "2", "batch_max": "40%", "dp": "0", "sg": "1.037"},
    {"name": "Turbinado", "type": "Adjunct", "subcategory": "Sugar",
     "srm": "10", "batch_max": "10%", "dp": "0", "sg": "1.044"},
    {"name": "Vienna Malt", "type": "Grain", "subcategory": "Base Malt",
     "srm": "4", "batch_max": "90%", "dp": "50-80", "sg": "1.037"},
    {"name": "Wheat Malt", "type": "Grain", "subcategory": "Base Malt",
     "srm": "2-8", "batch_max": "50%", "dp": "60-170", "sg": "1.039"},
]

HOP_SEED = [
    {"name": "Admiral",               "origin": "UK",          "alpha_acid": 14.8, "hop_type": "Bittering"},
    {"name": "Ahtanum",               "origin": "US",          "alpha_acid": 6.0,  "hop_type": "Aroma"},
    {"name": "Amarillo Gold",         "origin": "US",          "alpha_acid": 8.5,  "hop_type": "Aroma"},
    {"name": "Aquila",                "origin": "US",          "alpha_acid": 6.5,  "hop_type": "Aroma"},
    {"name": "Banner",                "origin": "US",          "alpha_acid": 10.0, "hop_type": "Bittering"},
    {"name": "Bramling Cross",        "origin": "UK",          "alpha_acid": 6.0,  "hop_type": "Aroma"},
    {"name": "Brewers Gold",          "origin": "UK",          "alpha_acid": 8.0,  "hop_type": "Bittering"},
    {"name": "Bullion",               "origin": "UK",          "alpha_acid": 8.0,  "hop_type": "Bittering"},
    {"name": "Cascade",               "origin": "US",          "alpha_acid": 5.5,  "hop_type": "Both"},
    {"name": "Centennial",            "origin": "US",          "alpha_acid": 10.0, "hop_type": "Bittering"},
    {"name": "Challenger",            "origin": "UK",          "alpha_acid": 7.5,  "hop_type": "Aroma"},
    {"name": "Chinook",               "origin": "US",          "alpha_acid": 13.0, "hop_type": "Bittering"},
    {"name": "Cluster",               "origin": "US",          "alpha_acid": 7.0,  "hop_type": "Bittering"},
    {"name": "Columbia",              "origin": "UK",          "alpha_acid": 5.5,  "hop_type": "Bittering"},
    {"name": "Columbus (Tomahawk)",   "origin": "US",          "alpha_acid": 14.0, "hop_type": "Bittering"},
    {"name": "Comet",                 "origin": "US",          "alpha_acid": 9.5,  "hop_type": "Bittering"},
    {"name": "Crystal",               "origin": "US",          "alpha_acid": 3.5,  "hop_type": "Aroma"},
    {"name": "Eroica",                "origin": "US",          "alpha_acid": 13.0, "hop_type": "Bittering"},
    {"name": "First Gold",            "origin": "UK",          "alpha_acid": 7.5,  "hop_type": "Both"},
    {"name": "Fuggles",               "origin": "UK",          "alpha_acid": 4.5,  "hop_type": "Aroma"},
    {"name": "Galena",                "origin": "US",          "alpha_acid": 13.0, "hop_type": "Bittering"},
    {"name": "Glacier",               "origin": "US",          "alpha_acid": 5.6,  "hop_type": "Aroma"},
    {"name": "Goldings, B. C.",       "origin": "Canada",      "alpha_acid": 5.0,  "hop_type": "Aroma"},
    {"name": "Goldings, East Kent (EK)", "origin": "UK",       "alpha_acid": 5.0,  "hop_type": "Aroma"},
    {"name": "Green Bullet",          "origin": "New Zealand", "alpha_acid": 13.5, "hop_type": "Bittering"},
    {"name": "Hallertauer",           "origin": "Germany",     "alpha_acid": 4.8,  "hop_type": "Aroma"},
    {"name": "Hallertauer, Hersbrucker", "origin": "Germany",  "alpha_acid": 4.0,  "hop_type": "Aroma"},
    {"name": "Hallertauer, Mittelfrueh", "origin": "Germany",  "alpha_acid": 4.0,  "hop_type": "Aroma"},
    {"name": "Hallertauer, New Zealand", "origin": "New Zealand", "alpha_acid": 8.5, "hop_type": "Both"},
    {"name": "Herald",                "origin": "UK",          "alpha_acid": 12.0, "hop_type": "Bittering"},
    {"name": "Horizon",               "origin": "US",          "alpha_acid": 12.0, "hop_type": "Bittering"},
    {"name": "Liberty",               "origin": "US",          "alpha_acid": 4.3,  "hop_type": "Aroma"},
    {"name": "Lublin",                "origin": "Poland",      "alpha_acid": 5.0,  "hop_type": "Bittering"},
    {"name": "Magnum",                "origin": "Germany",     "alpha_acid": 14.0, "hop_type": "Bittering"},
    {"name": "Mt. Hood",              "origin": "US",          "alpha_acid": 6.0,  "hop_type": "Aroma"},
    {"name": "Northdown",             "origin": "UK",          "alpha_acid": 8.5,  "hop_type": "Both"},
    {"name": "Northern Brewer",       "origin": "Germany",     "alpha_acid": 8.5,  "hop_type": "Both"},
    {"name": "Nugget",                "origin": "US",          "alpha_acid": 13.0, "hop_type": "Bittering"},
    {"name": "Orion",                 "origin": "Germany",     "alpha_acid": 7.3,  "hop_type": "Both"},
    {"name": "Pacific Gem",           "origin": "New Zealand", "alpha_acid": 15.0, "hop_type": "Bittering"},
    {"name": "Pearle",                "origin": "Germany",     "alpha_acid": 8.0,  "hop_type": "Bittering"},
    {"name": "Phoenix",               "origin": "UK",          "alpha_acid": 8.0,  "hop_type": "Bittering"},
    {"name": "Pilgrim",               "origin": "UK",          "alpha_acid": 11.5, "hop_type": "Bittering"},
    {"name": "Pioneer",               "origin": "UK",          "alpha_acid": 9.0,  "hop_type": "Both"},
    {"name": "Pride of Ringwood",     "origin": "Australia",   "alpha_acid": 9.0,  "hop_type": "Bittering"},
    {"name": "Progress",              "origin": "UK",          "alpha_acid": 6.3,  "hop_type": "Aroma"},
    {"name": "Saaz",                  "origin": "Czech Rep",   "alpha_acid": 4.0,  "hop_type": "Aroma"},
    {"name": "Santiam",               "origin": "US",          "alpha_acid": 6.0,  "hop_type": "Aroma"},
    {"name": "Select Spalt",          "origin": "Germany",     "alpha_acid": 4.8,  "hop_type": "Aroma"},
    {"name": "Southern Cross",        "origin": "New Zealand", "alpha_acid": 13.0, "hop_type": "Both"},
    {"name": "Spalter",               "origin": "Germany",     "alpha_acid": 4.5,  "hop_type": "Aroma"},
    {"name": "Sterling",              "origin": "US",          "alpha_acid": 7.5,  "hop_type": "Both"},
    {"name": "Sticklebract",          "origin": "New Zealand", "alpha_acid": 13.5, "hop_type": "Both"},
    {"name": "Strisselspalt",         "origin": "France",      "alpha_acid": 4.0,  "hop_type": "Aroma"},
    {"name": "Styrian Goldings",      "origin": "Slovenia",    "alpha_acid": 5.4,  "hop_type": "Aroma"},
    {"name": "Sun",                   "origin": "US",          "alpha_acid": 14.0, "hop_type": "Bittering"},
    {"name": "Super Alpha",           "origin": "New Zealand", "alpha_acid": 13.0, "hop_type": "Bittering"},
    {"name": "Target",                "origin": "UK",          "alpha_acid": 11.0, "hop_type": "Bittering"},
    {"name": "Tettnang",              "origin": "Germany",     "alpha_acid": 4.5,  "hop_type": "Aroma"},
    {"name": "Tradition",             "origin": "Germany",     "alpha_acid": 6.0,  "hop_type": "Bittering"},
    {"name": "Ultra",                 "origin": "US",          "alpha_acid": 3.0,  "hop_type": "Aroma"},
    {"name": "Vanguard",              "origin": "US",          "alpha_acid": 5.5,  "hop_type": "Aroma"},
    {"name": "Warrior",               "origin": "US",          "alpha_acid": 15.0, "hop_type": "Both"},
    {"name": "Whitbread Golding Var (WGV)", "origin": "UK",    "alpha_acid": 6.0,  "hop_type": "Aroma"},
    {"name": "Willamette",            "origin": "US",          "alpha_acid": 5.5,  "hop_type": "Aroma"},
    {"name": "Zeus",                  "origin": "US",          "alpha_acid": 14.0, "hop_type": "Bittering"},
]

def _parse_range(value: str):
    if value is None:
        return None, None
    v = value.strip()
    if not v or v == "-":
        return None, None
    if "-" in v:
        a, b = v.split("-", 1)
        try:
            return float(a), float(b)
        except ValueError:
            return None, None
    try:
        x = float(v)
        return x, x
    except ValueError:
        return None, None


def _parse_pct(value: str):
    if value is None:
        return None
    v = value.strip().replace("%", "")
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _parse_float(value: str):
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def seed_fermentables_into_db():
    """If fermentables table is empty, seed it from FERMENTABLE_SEED."""
    db = SessionLocal()
    try:
        count = db.query(DBFermentable).count()
        if count == 0:
            for f in FERMENTABLE_SEED:
                srm_min, srm_max = _parse_range(f["srm"])
                dp_min, dp_max = _parse_range(f["dp"])
                batch_max = _parse_pct(f["batch_max"])
                sg_val = _parse_float(f["sg"])

                db_f = DBFermentable(
                    name=f["name"],
                    type=f["type"],
                    subcategory=f["subcategory"],
                    srm_min=srm_min,
                    srm_max=srm_max,
                    batch_max_pct=batch_max,
                    dp_min=dp_min,
                    dp_max=dp_max,
                    sg=sg_val,
                )
                db.add(db_f)
            db.commit()
            print("Seeded fermentables table from FERMENTABLE_SEED.")
    except Exception as e:
        print("Error seeding fermentables:", e)
    finally:
        db.close()


# Call this somewhere near your other seed calls, e.g. after suppliers/inventory seeds:
seed_fermentables_into_db()

YEAST_SEED = [
    # --- A few examples from your big HTML table ---
    {
        "name": "Frankenyeast",
        "lab": "Various",
        "type": "Ale",
        "form": "Liquid",
        "temp": "62-75",
        "attenuation": "75.0%",
        "flocculation": "Low",
        "notes": (
            "A blend of twenty-five yeast strains, most of which are English or Belgian in origin. "
            "Best for: Anything where interesting yeast character is desired."
        ),
    },
    {
        "name": "WLP001 California Ale",
        "lab": "White Labs",
        "type": "Ale",
        "form": "Liquid",
        "temp": "68-73",
        "attenuation": "76.5%",
        "flocculation": "High",
        "notes": (
            "Very clean flavour, balance and stability. Accentuates hop flavour. Versatile – can be used to make any style ale. "
            "Best for: American style ales, ambers, pale ales, brown ales, strong ales."
        ),
    },
    {
        "name": "WLP002 English Ale",
        "lab": "White Labs",
        "type": "Ale",
        "form": "Liquid",
        "temp": "65-68",
        "attenuation": "66.5%",
        "flocculation": "Very High",
        "notes": (
            "Classic ESB strain best for English style milds, bitters, porters and English style stouts. "
            "Leaves a clear beer with some residual sweetness."
        ),
    },
    {
        "name": "WLP004 Irish Ale",
        "lab": "White Labs",
        "type": "Ale",
        "form": "Liquid",
        "temp": "65-68",
        "attenuation": "71.5%",
        "flocculation": "Medium",
        "notes": (
            "Excellent for Irish stouts. Slight hint of diacetyl balanced by a light fruitiness and a slightly dry crispness. "
            "Best for: Irish ales, stouts, porters, browns, reds and pale ale."
        ),
    },
    {
        "name": "WLP530 Abbey Ale",
        "lab": "White Labs",
        "type": "Ale",
        "form": "Liquid",
        "temp": "66-72",
        "attenuation": "77.5%",
        "flocculation": "Medium",
        "notes": (
            "Used in two of six remaining Trappist breweries. Distinctive plum and fruitiness. Good for high gravity beers. "
            "Best for: Belgian Trappist ales, spiced ales, tripel, dubbel, grand cru."
        ),
    },
    {
        "name": "WLP565 Belgian Saison I",
        "lab": "White Labs",
        "type": "Ale",
        "form": "Liquid",
        "temp": "68-75",
        "attenuation": "70.0%",
        "flocculation": "Medium",
        "notes": (
            "Saison yeast from Wallonia. Earthy, spicy and peppery notes. Slightly sweet. "
            "Best for: Saison, Belgian ale, dubbel, tripel."
        ),
    },
    {
        "name": "WLP300 Hefeweizen Ale",
        "lab": "White Labs",
        "type": "Wheat",
        "form": "Liquid",
        "temp": "68-72",
        "attenuation": "74.0%",
        "flocculation": "Low",
        "notes": (
            "Produces the banana and clove nose traditionally associated with German wheat beers. Also produces the desired cloudy look. "
            "Best for: German-style wheat beers – Weiss, Weizen, Hefeweizen."
        ),
    },
    {
        "name": "S-04 SafAle English Ale",
        "lab": "DCL/Fermentis",
        "type": "Ale",
        "form": "Dry",
        "temp": "59-75.2",
        "attenuation": "73.0%",
        "flocculation": "Medium",
        "notes": (
            "Fast starting, fast fermenting yeast. Quick attenuation helps to produce a clean, crisp, clear ale. "
            "Best for: General-purpose English ales."
        ),
    },
    {
        "name": "US-05 Safale American",
        "lab": "DCL/Fermentis",
        "type": "Ale",
        "form": "Dry",
        "temp": "59-75",
        "attenuation": "76.5%",
        "flocculation": "Medium",
        "notes": (
            "American ale yeast that produces well-balanced beers with low diacetyl and a very clean, crisp end palate. "
            "Best for: American ales and other clean-finishing ales."
        ),
    },
    {
        "name": "T-58 SafBrew Specialty Ale",
        "lab": "DCL/Fermentis",
        "type": "Ale",
        "form": "Dry",
        "temp": "60-72",
        "attenuation": "73.0%",
        "flocculation": "Medium",
        "notes": (
            "Estery, somewhat spicy ale yeast. Solid yeast formation at end of fermentation. "
            "Best for: Complex ales, Belgian-inspired styles."
        ),
    },
    {
        "name": "S-23 SafLager West European Lager",
        "lab": "DCL/Fermentis",
        "type": "Lager",
        "form": "Dry",
        "temp": "46-50",
        "attenuation": "73.5%",
        "flocculation": "High",
        "notes": (
            "German lager yeast strain. Performs well at low temperature. High flocculation and attenuation for a clean German finish. "
            "Best for: German-style lagers and pilsners."
        ),
    },
    {
        "name": "W-34/70 Saflager Lager",
        "lab": "DCL/Fermentis",
        "type": "Lager",
        "form": "Dry",
        "temp": "48-59",
        "attenuation": "75.0%",
        "flocculation": "High",
        "notes": (
            "Famous strain from Weihenstephan, Germany. Very popular for lagers worldwide. "
            "Best for: European lagers."
        ),
    },
    {
        "name": "WB-06 Safbrew Wheat",
        "lab": "DCL/Fermentis",
        "type": "Wheat",
        "form": "Dry",
        "temp": "59-75",
        "attenuation": "68.0%",
        "flocculation": "Medium",
        "notes": (
            "Specialty yeast for wheat beer fermentation. Produces subtle estery and phenolic flavour typical of wheat beers. "
            "Best for: Wheat beers."
        ),
    },
    {
        "name": "Belle Saison",
        "lab": "Danstar",
        "type": "Ale",
        "form": "Dry",
        "temp": "63-77",
        "attenuation": "80.0%",
        "flocculation": "Low",
        "notes": (
            "Highly attenuative saison yeast. "
            "Best for: Saisons and Belgian farmhouse-style beers."
        ),
    },
    {
        "name": "Nottingham Ale",
        "lab": "Danstar",
        "type": "Ale",
        "form": "Dry",
        "temp": "57-70",
        "attenuation": "75.0%",
        "flocculation": "High",
        "notes": (
            "Highly flocculant, high attenuation. Produces relatively few fruity esters. "
            "Best for: Clean, neutral British-style ales and pseudo-lagers at low temps."
        ),
    },
]

def _parse_temp_simple(range_str: str):
    """
    Parse strings like '65-70' or '59-75.2' into (min_f, max_f).
    If anything goes wrong, returns (None, None).
    """
    if not range_str:
        return None, None
    v = range_str.strip().replace("°F", "").replace("F", "")
    if "-" not in v:
        try:
            x = float(v)
            return x, x
        except ValueError:
            return None, None
    lo, hi = v.split("-", 1)
    try:
        return float(lo), float(hi)
    except ValueError:
        return None, None


def seed_yeasts_into_db():
    """If yeasts table is empty, seed it from YEAST_SEED."""
    db = SessionLocal()
    try:
        count = db.query(DBYeast).count()
        if count == 0:
            for y in YEAST_SEED:
                t_min, t_max = _parse_temp_simple(y.get("temp", ""))  # in °F
                attenuation = _parse_pct(y.get("attenuation", ""))

                db_y = DBYeast(
                    name=y["name"],
                    lab=y.get("lab"),
                    type=y.get("type"),
                    form=y.get("form"),
                    temp_min_f=t_min,
                    temp_max_f=t_max,
                    attenuation_pct=attenuation,
                    flocculation=y.get("flocculation"),
                    notes=y.get("notes"),
                )
                db.add(db_y)
            db.commit()
            print("Seeded yeasts table from YEAST_SEED.")
    except Exception as e:
        print("Error seeding yeasts:", e)
    finally:
        db.close()


# Call once at startup (like the other seeders)
seed_yeasts_into_db()

def seed_hops_into_db():
    """If hops table is empty, seed it from HOP_SEED."""
    db = SessionLocal()
    try:
        if db.query(DBHop).count() == 0:
            for hop in HOP_SEED:
                db.add(DBHop(**hop))
            db.commit()
            print("Seeded hops table from HOP_SEED.")
    except Exception as e:
        print("Error seeding hops:", e)
    finally:
        db.close()

seed_hops_into_db()


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

@app.get("/fermentables", response_class=HTMLResponse)
async def fermentables_page(request: Request, db: Session = Depends(get_db)):
    ferments = (
        db.query(DBFermentable)
        .order_by(DBFermentable.name)
        .all()
    )
    return templates.TemplateResponse(
        "fermentables.html",
        {
            "request": request,
            "fermentables": ferments,
            "current_page": "fermentables",
        },
    )

@app.get("/yeasts", response_class=HTMLResponse)
async def yeasts_page(request: Request, db: Session = Depends(get_db)):
    yeasts = (
        db.query(DBYeast)
        .order_by(DBYeast.lab, DBYeast.name)
        .all()
    )
    return templates.TemplateResponse(
        "yeasts.html",
        {
            "request": request,
            "yeasts": yeasts,
            "current_page": "yeasts",
        },
    )

@app.get("/hops", response_class=HTMLResponse)
async def hops_page(
    request: Request,
    db: Session = Depends(get_db),
):
    hops = db.query(DBHop).order_by(DBHop.name).all()
    return templates.TemplateResponse(
        "hops.html",
        {
            "request": request,
            "hops": hops,
            "current_page": "hops",
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
