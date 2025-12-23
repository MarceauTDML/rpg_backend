from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime, timezone, date
import uuid

# --- CONFIGURATION INITIALE ---
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()

# --- AJOUT ICI : ROUTE POUR LE PING (UPTIMEROBOT) ---
# Cette route permet à UptimeRobot de "réveiller" le serveur à la racine "/"
@app.get("/")
async def health_check():
    return {"status": "alive", "message": "Le serveur RPG ne dort jamais !"}

api_router = APIRouter(prefix="/api")

# --- DEFINITION DES RANGS (TITRES) ---
SKILL_RANKS = {
    "tech": {
        1: "Noob", 2: "Script Kiddie", 3: "Debugger", 4: "Codeur", 5: "Développeur",
        6: "Ingénieur", 7: "Hacker", 8: "Tech Lead", 9: "Architecte", 10: "Deus Ex Machina"
    },
    "sport": {
        1: "Canapé", 2: "Promeneur", 3: "Échauffé", 4: "Actif", 5: "Athlète",
        6: "Compétiteur", 7: "Spartiate", 8: "Titan", 9: "Olympien", 10: "Demi-Dieu"
    },
    "cooking": {
        1: "Micro-ondes", 2: "Commis", 3: "Cuistot", 4: "Gourmet", 5: "Cuisinier",
        6: "Chef de Partie", 7: "Sous-Chef", 8: "Chef", 9: "Chef Étoilé", 10: "Gordon Ramsay"
    },
    "cleaning": {
        1: "Bordélique", 2: "Balayeur", 3: "Rangeur", 4: "Propre", 5: "Organisé",
        6: "Méticuleux", 7: "Minimaliste", 8: "Purificateur", 9: "Maniac", 10: "Sanctuaire"
    },
    "culture": {
        1: "Ignorant", 2: "Curieux", 3: "Lecteur", 4: "Cultivé", 5: "Érudit",
        6: "Intellectuel", 7: "Savant", 8: "Philosophe", 9: "Encyclopédie", 10: "Sage"
    },
    "communication": {
        1: "Timide", 2: "Observateur", 3: "Bavard", 4: "Sociable", 5: "Négociateur",
        6: "Charismatique", 7: "Orateur", 8: "Diplomate", 9: "Leader", 10: "Voix d'Or"
    },
    "music": {
        1: "Sourd", 2: "Auditeur", 3: "Rythmique", 4: "Amateur", 5: "Interprète",
        6: "Musicien", 7: "Compositeur", 8: "Soliste", 9: "Maestro", 10: "Virtuose"
    },
    "languages": {
        1: "Touriste", 2: "Élève", 3: "Débrouillard", 4: "Intermédiaire", 5: "Opérationnel",
        6: "Fluide", 7: "Avancé", 8: "Bilingue", 9: "Polyglotte", 10: "Tour de Babel"
    },
    "health": {
        1: "Fragile", 2: "Vivant", 3: "Équilibré", 4: "Reposé", 5: "Tonique",
        6: "Robuste", 7: "Résistant", 8: "Vigoureux", 9: "Inébranlable", 10: "Immortel"
    }
}

# --- MODELES DE DONNEES ---

class UserStats(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hp: int = 100
    max_hp: int = 100
    coins: int = 0
    streak: int = 0
    streak_active: bool = True
    last_streak_update: str = Field(default_factory=lambda: datetime.now(timezone.utc).date().isoformat())
    has_shield: bool = False
    last_damage_taken: int = 0 

class Habit(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    skill: str
    coin_reward: int
    exp_reward: int
    completed_today: bool = False
    completion_history: List[str] = []

class Mission(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str = ""
    date: str
    crucial: bool = False
    completed: bool = False
    skill: str

class Skill(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    level: int = 1
    exp: int = 0
    max_exp: int = 100
    rank: str = "Novice"

class ShopItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    description: str
    price: int
    type: str
    image_url: str

class Achievement(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    description: str
    condition: str
    unlocked: bool = False

class DailyReview(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: str
    notes: str

# --- FONCTIONS UTILITAIRES & LOGIQUE ---

def get_rank(skill_id: str, level: int) -> str:
    specific_ranks = SKILL_RANKS.get(skill_id, {})
    if level >= 10:
        return specific_ranks.get(10, "Maître")
    return specific_ranks.get(level, "Novice")

async def check_and_unlock_achievements():
    """Vérifie et débloque les succès"""
    stats = await db.user_stats.find_one({})
    if not stats: return

    habits = await db.habits.find({}).to_list(1000)
    skills = await db.skills.find({}).to_list(1000)
    
    total_completed_habits = sum(1 for h in habits if h['completed_today'] or len(h.get('completion_history', [])) > 0)
    current_streak = stats['streak']
    current_coins = stats['coins']

    updates = []
    # 1. Habitudes
    if total_completed_habits >= 1: updates.append("first_habit")
    # 2. Streak
    if current_streak >= 7: updates.append("streak_7")
    if current_streak >= 14: updates.append("streak_14")
    if current_streak >= 30: updates.append("streak_30")
    if current_streak >= 90: updates.append("streak_90")
    if current_streak >= 365: updates.append("streak_365")
    # 3. Économie
    if current_coins >= 2500: updates.append("coins_2500")
    if current_coins >= 5500: updates.append("coins_5500")
    if current_coins >= 10000: updates.append("coins_10000")
    if current_coins >= 25000: updates.append("coins_25000")
    if current_coins >= 50000: updates.append("coins_50000")
    # 4. Skills
    max_level = max([s['level'] for s in skills]) if skills else 0
    if max_level >= 2: updates.append("skill_lvl_2")
    if max_level >= 5: updates.append("skill_lvl_5")
    if max_level >= 8: updates.append("skill_lvl_8")
    if max_level >= 10: updates.append("skill_lvl_10")

    if updates:
        await db.achievements.update_many(
            {"id": {"$in": updates}, "unlocked": False},
            {"$set": {"unlocked": True}}
        )

async def process_daily_reset(stats):
    """Calcule les dégâts de la veille et reset les habitudes"""
    today = datetime.now(timezone.utc).date().isoformat()
    last_update = stats.get("last_streak_update", today)
    
    # Si on est toujours le même jour, on ne fait rien
    if last_update == today:
        return stats

    print(f"🔄 Passage au jour suivant. Bilan du : {last_update}")
    
    # 1. Calcul dégâts Habitudes (-2 PV par habitude non faite)
    habits = await db.habits.find({}).to_list(1000)
    missed_habits_count = sum(1 for h in habits if not h['completed_today'])
    damage_habits = missed_habits_count * 2
    
    # 2. Calcul dégâts Missions (-5 Cruciale, -2 Classique)
    past_missions = await db.missions.find({"date": last_update}).to_list(1000)
    damage_missions = 0
    for m in past_missions:
        if not m.get('completed', False):
            if m.get('crucial', False):
                damage_missions += 5
            else:
                damage_missions += 2
    
    total_potential_damage = damage_habits + damage_missions
    
    # 3. Application des dégâts
    new_hp = stats['hp']
    new_has_shield = stats['has_shield']
    new_streak = stats['streak']
    actual_damage_taken = 0
    
    if total_potential_damage > 0:
        if new_has_shield:
            print("🛡️ Bouclier utilisé ! Aucun dégât subi.")
            new_has_shield = False # Le bouclier casse
            actual_damage_taken = 0
            # Streak sauvé mais pas augmenté
        else:
            print(f"💥 Dégâts subis : {total_potential_damage}")
            actual_damage_taken = total_potential_damage
            new_hp = max(0, new_hp - total_potential_damage)
            new_streak = 0 # Streak brisé
    else:
        # Journée parfaite (Aucun dégât) -> Streak augmente
        print("🔥 Journée parfaite ! Streak +1")
        new_streak += 1

    # 4. Gestion de la Mort (HP = 0)
    new_coins = stats['coins']
    if new_hp == 0:
        print("💀 Mort du personnage. Résurrection et pénalité.")
        new_hp = 50 
        new_coins = int(new_coins * 0.9)
        new_streak = 0
        
    # 5. Reset des habitudes
    await db.habits.update_many({}, {"$set": {"completed_today": False}})
    
    # 6. Sauvegarde
    await db.user_stats.update_one(
        {}, 
        {"$set": {
            "hp": new_hp, 
            "coins": new_coins,
            "last_streak_update": today,
            "has_shield": new_has_shield,
            "streak": new_streak,
            "last_damage_taken": actual_damage_taken
        }}
    )
    
    stats['hp'] = new_hp
    stats['coins'] = new_coins
    stats['last_streak_update'] = today
    stats['has_shield'] = new_has_shield
    stats['streak'] = new_streak
    stats['last_damage_taken'] = actual_damage_taken
        
    return stats

# --- ROUTES API ---

@api_router.get("/")
async def root():
    return {"message": "Objectif 1% API"}

@api_router.get("/stats", response_model=UserStats)
async def get_stats():
    stats = await db.user_stats.find_one({}, {"_id": 0})
    if not stats:
        default_stats = UserStats()
        await db.user_stats.insert_one(default_stats.model_dump())
        return default_stats
    
    # --- DAILY RESET ---
    updated_stats = await process_daily_reset(stats)
    # -------------------
    
    return UserStats(**updated_stats)

@api_router.patch("/stats")
async def update_stats(hp: Optional[int] = None, coins: Optional[int] = None, streak: Optional[int] = None, streak_active: Optional[bool] = None, has_shield: Optional[bool] = None):
    update_fields = {}
    if hp is not None:
        update_fields["hp"] = hp
    if coins is not None:
        update_fields["coins"] = coins
    if streak is not None:
        update_fields["streak"] = streak
    if streak_active is not None:
        update_fields["streak_active"] = streak_active
        if streak_active:
            update_fields["last_streak_update"] = datetime.now(timezone.utc).date().isoformat()
    if has_shield is not None:
        update_fields["has_shield"] = has_shield
    
    await db.user_stats.update_one({}, {"$set": update_fields})
    
    if hp is not None and hp == 100:
        await db.achievements.update_one(
            {"id": "heal_hp", "unlocked": False},
            {"$set": {"unlocked": True}}
        )
        
    return {"success": True}

@api_router.get("/habits", response_model=List[Habit])
async def get_habits():
    habits = await db.habits.find({}, {"_id": 0}).to_list(1000)
    return [Habit(**h) for h in habits]

@api_router.post("/habits", response_model=Habit)
async def create_habit(habit: Habit):
    habit_dict = habit.model_dump()
    await db.habits.insert_one(habit_dict)
    return habit

@api_router.patch("/habits/{habit_id}")
async def update_habit(habit_id: str, completed_today: Optional[bool] = None):
    update_fields = {}
    if completed_today is not None:
        update_fields["completed_today"] = completed_today
        if completed_today:
            today = datetime.now(timezone.utc).date().isoformat()
            habit = await db.habits.find_one({"id": habit_id}, {"_id": 0})
            if habit:
                history = habit.get("completion_history", [])
                if today not in history:
                    history.append(today)
                    update_fields["completion_history"] = history
    
    await db.habits.update_one({"id": habit_id}, {"$set": update_fields})
    
    if completed_today:
        await check_and_unlock_achievements()
        
    return {"success": True}

@api_router.delete("/habits/{habit_id}")
async def delete_habit(habit_id: str):
    await db.habits.delete_one({"id": habit_id})
    return {"success": True}

@api_router.get("/missions", response_model=List[Mission])
async def get_missions(date: Optional[str] = None):
    query = {} if not date else {"date": date}
    missions = await db.missions.find(query, {"_id": 0}).to_list(1000)
    return [Mission(**m) for m in missions]

@api_router.post("/missions", response_model=Mission)
async def create_mission(mission: Mission):
    existing_missions = await db.missions.find({"date": mission.date}).to_list(100)
    
    crucial_count = sum(1 for m in existing_missions if m['crucial'])
    normal_count = sum(1 for m in existing_missions if not m['crucial'])

    if mission.crucial:
        if crucial_count >= 3:
            raise HTTPException(status_code=400, detail="Limite atteinte : Max 3 missions cruciales par jour.")
    else:
        if normal_count >= 7:
            raise HTTPException(status_code=400, detail="Limite atteinte : Max 7 missions classiques par jour.")

    mission_dict = mission.model_dump()
    await db.missions.insert_one(mission_dict)
    return mission

@api_router.patch("/missions/{mission_id}")
async def update_mission(mission_id: str, completed: Optional[bool] = None):
    mission = await db.missions.find_one({"id": mission_id})
    if not mission:
        raise HTTPException(status_code=404, detail="Mission introuvable")

    update_fields = {}
    
    if completed is not None:
        update_fields["completed"] = completed
        
        current_status = mission.get("completed", False)
        
        if completed != current_status:
            is_crucial = mission.get("crucial", False)
            coin_reward = 50 if is_crucial else 20
            exp_reward = 30 if is_crucial else 10 
            
            stats = await db.user_stats.find_one({})
            skill_id = mission.get("skill")
            skill = await db.skills.find_one({"id": skill_id})
            
            if stats and skill:
                if completed:
                    new_coins = stats["coins"] + coin_reward
                    await db.user_stats.update_one({}, {"$set": {"coins": new_coins}})
                    
                    new_exp = skill["exp"] + exp_reward
                    level = skill["level"]
                    max_exp = skill["max_exp"]
                    
                    while new_exp >= max_exp:
                        new_exp -= max_exp
                        level += 1
                        max_exp = int(max_exp * 1.5)
                    
                    rank = get_rank(skill_id, level)
                    
                    await db.skills.update_one(
                        {"id": skill_id}, 
                        {"$set": {"exp": new_exp, "level": level, "max_exp": max_exp, "rank": rank}}
                    )
                else:
                    new_coins = max(0, stats["coins"] - coin_reward)
                    await db.user_stats.update_one({}, {"$set": {"coins": new_coins}})
                    
                    current_exp_loss = max(0, skill["exp"] - exp_reward)
                    await db.skills.update_one(
                        {"id": skill_id}, 
                        {"$set": {"exp": current_exp_loss}}
                    )

    if update_fields:
        await db.missions.update_one({"id": mission_id}, {"$set": update_fields})
    
    if completed:
        await check_and_unlock_achievements()
        
    return {"success": True}

@api_router.delete("/missions/{mission_id}")
async def delete_mission(mission_id: str):
    await db.missions.delete_one({"id": mission_id})
    return {"success": True}

@api_router.get("/skills", response_model=List[Skill])
async def get_skills():
    skills = await db.skills.find({}, {"_id": 0}).to_list(1000)
    return [Skill(**s) for s in skills]

@api_router.patch("/skills/{skill_id}")
async def update_skill(skill_id: str, exp: int):
    skill = await db.skills.find_one({"id": skill_id}, {"_id": 0})
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    
    new_exp = skill["exp"] + exp
    level = skill["level"]
    max_exp = skill["max_exp"]
    
    while new_exp >= max_exp:
        new_exp -= max_exp
        level += 1
        max_exp = int(max_exp * 1.5)
    
    rank = get_rank(skill_id, level)
    
    await db.skills.update_one(
        {"id": skill_id},
        {"$set": {"exp": new_exp, "level": level, "max_exp": max_exp, "rank": rank}}
    )
    await check_and_unlock_achievements()
    return {"success": True}

@api_router.get("/shop", response_model=List[ShopItem])
async def get_shop_items():
    items = await db.shop_items.find({}, {"_id": 0}).to_list(1000)
    return [ShopItem(**i) for i in items]

@api_router.post("/shop/purchase")
async def purchase_item(item_id: str):
    item = await db.shop_items.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    stats = await db.user_stats.find_one({}, {"_id": 0})
    if not stats:
        raise HTTPException(status_code=404, detail="Stats not found")
    
    if stats["coins"] < item["price"]:
        raise HTTPException(status_code=400, detail="Pas assez de coins")
    
    new_coins = stats["coins"] - item["price"]
    await db.user_stats.update_one({}, {"$set": {"coins": new_coins}})
    
    if item["type"] == "shield":
        await db.user_stats.update_one({}, {"$set": {"has_shield": True}})
    elif item["type"] == "potion":
        new_hp = min(stats["hp"] + 30, stats["max_hp"])
        await db.user_stats.update_one({}, {"$set": {"hp": new_hp}})
    
    return {"success": True, "remaining_coins": new_coins}

@api_router.get("/achievements", response_model=List[Achievement])
async def get_achievements():
    achievements = await db.achievements.find({}, {"_id": 0}).to_list(1000)
    return [Achievement(**a) for a in achievements]

@api_router.get("/reviews", response_model=List[DailyReview])
async def get_reviews():
    reviews = await db.daily_reviews.find({}, {"_id": 0}).sort("date", -1).to_list(100)
    return [DailyReview(**r) for r in reviews]

@api_router.post("/reviews", response_model=DailyReview)
async def create_review(review: DailyReview):
    review_dict = review.model_dump()
    await db.daily_reviews.insert_one(review_dict)
    return review

# --- INITIALISATION DES DONNEES (RESET) ---
@api_router.post("/init-demo-data")
async def init_demo_data():
    await db.user_stats.delete_many({})
    await db.habits.delete_many({})
    await db.missions.delete_many({})
    await db.skills.delete_many({})
    await db.shop_items.delete_many({})
    await db.achievements.delete_many({})
    await db.daily_reviews.delete_many({})
    
    stats = UserStats(hp=100, coins=0, streak=0, streak_active=True, last_damage_taken=0)
    await db.user_stats.insert_one(stats.model_dump())
    
    demo_habits = []
    demo_missions = []
    
    demo_skills = [
        Skill(id="tech", name="Technologie", level=1, exp=0, max_exp=100, rank=get_rank("tech", 1)),
        Skill(id="sport", name="Sport", level=1, exp=0, max_exp=100, rank=get_rank("sport", 1)),
        Skill(id="culture", name="Culture", level=1, exp=0, max_exp=100, rank=get_rank("culture", 1)),
        Skill(id="communication", name="Communication", level=1, exp=0, max_exp=100, rank=get_rank("communication", 1)),
        Skill(id="cooking", name="Cuisine", level=1, exp=0, max_exp=100, rank=get_rank("cooking", 1)),
        Skill(id="cleaning", name="Nettoyage", level=1, exp=0, max_exp=100, rank=get_rank("cleaning", 1)),
        Skill(id="music", name="Musique", level=1, exp=0, max_exp=100, rank=get_rank("music", 1)),
        Skill(id="languages", name="Langues vivantes", level=1, exp=0, max_exp=100, rank=get_rank("languages", 1)),
        Skill(id="health", name="Santé", level=1, exp=0, max_exp=100, rank=get_rank("health", 1)),
    ]
    for s in demo_skills:
        await db.skills.insert_one(s.model_dump())
    
    demo_shop_items = [
        # SURVIE
        ShopItem(id="health_potion", name="Potion de Soin", description="Restaure 30 PV.", price=150, type="potion", image_url="https://images.unsplash.com/photo-1515593630686-2a8d11c47317?auto=format&fit=crop&q=80"),
        ShopItem(id="streak_shield", name="Bouclier de Streak", description="Sauve ta flamme une fois.", price=1000, type="shield", image_url="https://images.unsplash.com/photo-1469502744111-a8377758784c?auto=format&fit=crop&q=80"),
        
        # PETITS PLAISIRS
        ShopItem(id="bakery", name="Boulangerie", description="Un croissant ou pain au chocolat.", price=150, type="reward", image_url="https://images.unsplash.com/photo-1555507036-ab1f4038808a?auto=format&fit=crop&q=80"),
        ShopItem(id="drink", name="Apéro / Bière", description="Un verre en terrasse ou une bière.", price=400, type="reward", image_url="https://images.unsplash.com/photo-1514933651103-005eec06c04b?auto=format&fit=crop&q=80"),
        ShopItem(id="tv_episode", name="Épisode Série", description="45 min de détente.", price=300, type="reward", image_url="https://images.unsplash.com/photo-1522869635100-9f4c5e86aa37?auto=format&fit=crop&q=80"),
        
        # MOYENS & GROS OBJECTIFS
        ShopItem(id="gaming_1h", name="1h de Jeu Vidéo", description="Session gaming autorisée.", price=500, type="reward", image_url="https://images.unsplash.com/photo-1538481199705-c710c4e965fc?auto=format&fit=crop&q=80"),
        ShopItem(id="cheat_meal", name="Repas Plaisir", description="Commande ou resto.", price=800, type="reward", image_url="https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?auto=format&fit=crop&q=80"),
        ShopItem(id="cinema", name="Sortie Cinéma", description="Une place pour un film.", price=1200, type="reward", image_url="https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&q=80"),
    ]
    for i in demo_shop_items:
        await db.shop_items.insert_one(i.model_dump())
    
    demo_achievements = [
        Achievement(id="first_habit", name="Premier Pas", description="Complète ta première habitude.", condition="habit_1", unlocked=False),
        Achievement(id="streak_7", name="Semaine de Fer", description="Maintiens ta flamme 7 jours de suite.", condition="streak_7", unlocked=False),
        Achievement(id="streak_14", name="Persévérance", description="Maintiens ta flamme 14 jours de suite.", condition="streak_14", unlocked=False),
        Achievement(id="streak_30", name="Légende Mensuelle", description="Maintiens ta flamme 30 jours de suite.", condition="streak_30", unlocked=False),
        Achievement(id="streak_90", name="Trimestre d'Acier", description="Maintiens ta flamme 90 jours de suite.", condition="streak_90", unlocked=False),
        Achievement(id="streak_365", name="L'Immortel", description="Maintiens ta flamme 365 jours de suite.", condition="streak_365", unlocked=False),
        Achievement(id="coins_2500", name="Épargnant", description="Possède 2 500 coins en réserve.", condition="coins_2500", unlocked=False),
        Achievement(id="coins_5500", name="Aisé", description="Possède 5 500 coins en réserve.", condition="coins_5500", unlocked=False),
        Achievement(id="coins_10000", name="Prospère", description="Possède 10 000 coins en réserve.", condition="coins_10000", unlocked=False),
        Achievement(id="coins_25000", name="Investisseur", description="Possède 25 000 coins en réserve.", condition="coins_25000", unlocked=False),
        Achievement(id="coins_50000", name="Millionnaire", description="Possède 50 000 coins en réserve.", condition="coins_50000", unlocked=False),
        Achievement(id="skill_lvl_2", name="Déclic", description="Atteins le niveau 2 dans une compétence.", condition="skill_lvl_2", unlocked=False),
        Achievement(id="skill_lvl_5", name="Expertise", description="Atteins le niveau 5 dans une compétence.", condition="skill_lvl_5", unlocked=False),
        Achievement(id="skill_lvl_8", name="Maîtrise", description="Atteins le niveau 8 dans une compétence.", condition="skill_lvl_8", unlocked=False),
        Achievement(id="skill_lvl_10", name="Sommet", description="Atteins le niveau 10 dans une compétence.", condition="skill_lvl_10", unlocked=False),
        Achievement(id="heal_hp", name="Rédemption", description="Restaure tes PV après avoir été blessé.", condition="heal_hp", unlocked=False),
        Achievement(id="perfect_1", name="Jour de Grâce", description="Fais 1 journée parfaite.", condition="perfect_1", unlocked=False),
        Achievement(id="perfect_7", name="Semaine Divine", description="Fais 7 journées parfaites.", condition="perfect_7", unlocked=False),
        Achievement(id="perfect_30", name="Mois d'Or", description="Fais 30 journées parfaites.", condition="perfect_30", unlocked=False),
        Achievement(id="perfect_50", name="Demi-Cent", description="Fais 50 journées parfaites.", condition="perfect_50", unlocked=False),
        Achievement(id="perfect_100", name="Centenaire", description="Fais 100 journées parfaites.", condition="perfect_100", unlocked=False),
    ]
    for a in demo_achievements:
        await db.achievements.insert_one(a.model_dump())
    
    return {"success": True, "message": "Initialisation RPG terminée : Prêt pour l'aventure !"}

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()