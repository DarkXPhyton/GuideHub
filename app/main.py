# main.py
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import List, Optional
import motor.motor_asyncio
from bson import ObjectId
import os

app = FastAPI(
    title="Self-Hosting Hub API",
    description="API für die Anleitungsplattform",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB Verbindung
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URL)
db = client.self_hosting_hub

# Pydantic Modelle
class Tag(BaseModel):
    name: str
    color: str = "blue"

class GuideBase(BaseModel):
    title: str
    description: str
    content: Optional[str] = None
    icon: str = "fas fa-book"
    color: str = "blue"
    tags: List[Tag] = []
    featured: bool = False

class GuideCreate(GuideBase):
    pass

class Guide(GuideBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        json_encoders = {ObjectId: str}

class CategoryBase(BaseModel):
    name: str
    description: str
    icon: str = "fas fa-tag"
    color: str = "blue"

class CategoryCreate(CategoryBase):
    pass

class Category(CategoryBase):
    id: str
    guide_count: int

    class Config:
        json_encoders = {ObjectId: str}

class NewsletterSubscriber(BaseModel):
    email: EmailStr
    subscribed_at: datetime = datetime.utcnow()

class Stats(BaseModel):
    guides: int
    categories: int
    technologies: int

# Hilfsfunktionen
async def get_guide_count():
    return await db.guides.count_documents({})

async def get_category_count():
    return await db.categories.count_documents({})

async def get_unique_technologies_count():
    pipeline = [
        {"$unwind": "$tags"},
        {"$group": {"_id": "$tags.name"}},
        {"$count": "count"}
    ]
    result = await db.guides.aggregate(pipeline).to_list(1)
    return result[0]["count"] if result else 0

# API Endpunkte
@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Self-Hosting Hub API"}

@app.get("/version", response_model=dict)
async def get_version():
    return {"version": "1.0.0"}

@app.get("/stats", response_model=Stats)
async def get_stats():
    return Stats(
        guides=await get_guide_count(),
        categories=await get_category_count(),
        technologies=await get_unique_technologies_count()
    )

@app.get("/guides/featured", response_model=Guide)
async def get_featured_guide():
    guide = await db.guides.find_one({"featured": True})
    if not guide:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No featured guide found"
        )
    return {**guide, "id": str(guide["_id"])}

@app.get("/categories", response_model=List[Category])
async def get_categories():
    categories = []
    async for category in db.categories.find():
        guide_count = await db.guides.count_documents({"category_id": str(category["_id"])})
        categories.append({
            **category,
            "id": str(category["_id"]),
            "guide_count": guide_count
        })
    return categories

@app.get("/guides/latest", response_model=List[Guide])
async def get_latest_guides(limit: int = 2):
    guides = []
    async for guide in db.guides.find().sort("created_at", -1).limit(limit):
        guides.append({
            **guide,
            "id": str(guide["_id"])
        })
    return guides

@app.post("/newsletter/subscribe", status_code=status.HTTP_201_CREATED)
async def subscribe_to_newsletter(email: EmailStr):
    existing = await db.subscribers.find_one({"email": email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already subscribed"
        )
    
    subscriber = {
        "email": email,
        "subscribed_at": datetime.utcnow()
    }
    result = await db.subscribers.insert_one(subscriber)
    
    if not result.inserted_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Subscription failed"
        )
    
    return {"message": "Subscription successful"}

# Initialdaten (für Entwicklung)
@app.on_event("startup")
async def startup_db_client():
    # Nur für Entwicklung - Initialdaten einfügen
    if await db.guides.count_documents({}) == 0:
        await db.guides.insert_many([
            {
                "title": "Nextcloud mit Redis & MySQL",
                "description": "Komplettanleitung für eine performante Nextcloud-Installation mit Docker, Redis Caching und MySQL-Datenbank.",
                "icon": "fas fa-cloud",
                "color": "blue",
                "tags": [
                    {"name": "Docker", "color": "blue"},
                    {"name": "MySQL", "color": "green"},
                    {"name": "Redis", "color": "red"}
                ],
                "featured": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            },
            {
                "title": "Sicherheit mit Fail2Ban",
                "description": "So schützt du deine Server vor Brute-Force-Angriffen mit Fail2Ban und automatisierten Regeln.",
                "icon": "fas fa-shield-alt",
                "color": "green",
                "tags": [
                    {"name": "Sicherheit", "color": "gray"},
                    {"name": "Ubuntu", "color": "yellow"}
                ],
                "featured": False,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
        ])
    
    if await db.categories.count_documents({}) == 0:
        await db.categories.insert_many([
            {
                "name": "Cloud & Storage",
                "description": "Nextcloud, Owncloud, Samba und andere Speicherlösungen für deine Daten.",
                "icon": "fas fa-cloud",
                "color": "blue"
            },
            {
                "name": "Datenbanken",
                "description": "MySQL, PostgreSQL, MongoDB und andere Datenbank-Systeme.",
                "icon": "fas fa-database",
                "color": "green"
            },
            {
                "name": "Container",
                "description": "Docker, Portainer, LXC und andere Container-Technologien.",
                "icon": "fas fa-boxes",
                "color": "purple"
            }
        ])