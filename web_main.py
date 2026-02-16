import os
import json
import logging
from datetime import date
from typing import Optional
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse, HTMLResponse, Response
from starlette.requests import Request
from starlette.staticfiles import StaticFiles
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.templating import Jinja2Templates
import httpx

from database import Database
from core import ScheduleManager

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("logs/web.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
REPLACEMENT_URL = os.getenv("REPLACEMENT_URL", "https://example.com/replacements.html")

http_client: Optional[httpx.AsyncClient] = None

db = Database()
schedule_manager = ScheduleManager(replacement_url=REPLACEMENT_URL)
templates = Jinja2Templates(directory="templates")

async def startup():
    global http_client
    await db.init_db()
    http_client = httpx.AsyncClient(timeout=10.0)
    logger.info("Database initialized")

async def shutdown():
    global http_client
    await db.close()
    await schedule_manager.close()
    if http_client:
        await http_client.aclose()
        http_client = None
    logger.info("Database closed")

async def index(request: Request):
    return templates.TemplateResponse("schedule_view_template.html", {"request": request})

async def homework_form(request: Request):
    return templates.TemplateResponse("homework_form.html", {"request": request})

async def headman_panel(request: Request):
    return templates.TemplateResponse("headman_panel.html", {"request": request})

async def api_schedule(request: Request):
    group_name = request.query_params.get("group")
    date_str = request.query_params.get("date")
    
    if not group_name:
        return JSONResponse({"error": "group parameter required"}, status_code=400)
    
    try:
        if date_str:
            parts = date_str.split(".")
            target_date = date(int(parts[2]), int(parts[1]), int(parts[0]))
        else:
            target_date = date.today()
        
        day_schedule = await schedule_manager.get_schedule_for_date(group_name, target_date)
        
        if not day_schedule:
            return JSONResponse({"error": "Schedule not found"}, status_code=404)
        
        return JSONResponse({
            "date": day_schedule.date_str,
            "is_weekend": day_schedule.is_weekend,
            "lessons": [lesson.dict() for lesson in day_schedule.lessons]
        })
    
    except Exception as e:
        logger.error(f"Error in api_schedule: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_homework_get(request: Request):
    group_name = request.query_params.get("group")
    pin = request.query_params.get("pin")
    
    if not group_name or not pin:
        return JSONResponse({"error": "group and pin required"}, status_code=400)
    
    if not await db.verify_pin(group_name, pin):
        return JSONResponse({"error": "Invalid PIN"}, status_code=403)
    
    try:
        homeworks = await db.get_homework_by_group(group_name)
        
        result = []
        for hw in homeworks:
            result.append({
                "id": hw.id,
                "subject": hw.subject_name,
                "text": hw.homework_text,
                "created_at": hw.created_at.isoformat() if hw.created_at else None
            })
        
        return JSONResponse({"homework": result})
    
    except Exception as e:
        logger.error(f"Error in api_homework_get: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_homework_post(request: Request):
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    
    group_name = data.get("group")
    pin = data.get("pin")
    subject = data.get("subject")
    text = data.get("text")
    mode = data.get("mode", "overwrite")
    
    if not group_name or not pin or not subject or not text:
        return JSONResponse({"error": "group, pin, subject, text required"}, status_code=400)
    
    if not await db.verify_pin(group_name, pin):
        return JSONResponse({"error": "Invalid PIN"}, status_code=403)
    
    try:
        if mode == "overwrite":
            await db.clear_homework_by_subject(group_name, subject)
        
        homework = await db.set_homework(group_name, subject, text)
        
        return JSONResponse({
            "success": True,
            "homework_id": homework.id
        })
    
    except Exception as e:
        logger.error(f"Error in api_homework_post: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_headman_get(request: Request):
    group_name = request.query_params.get("group")
    pin = request.query_params.get("pin")
    
    if not group_name or not pin:
        return JSONResponse({"error": "group and pin required"}, status_code=400)
    
    if not await db.verify_pin(group_name, pin):
        return JSONResponse({"error": "Invalid PIN"}, status_code=403)
    
    try:
        students = await db.get_students_by_group(group_name)
        settings = await db.get_group_settings(group_name)
        
        students_list = []
        for s in students:
            students_list.append({
                "user_id": s.user_id,
                "full_name": s.full_name,
                "is_headman": s.is_headman,
                "is_sick": s.is_sick
            })
        
        result = {
            "students": students_list,
            "current_duty_id": settings.current_duty_id if settings else None,
            "notify_enabled": settings.notify_enabled if settings else True
        }
        
        return JSONResponse(result)
    
    except Exception as e:
        logger.error(f"Error in api_headman_get: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_headman_post(request: Request):
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    
    group_name = data.get("group")
    pin = data.get("pin")
    action = data.get("action")
    
    if not group_name or not pin or not action:
        return JSONResponse({"error": "group, pin, action required"}, status_code=400)
    
    if not await db.verify_pin(group_name, pin):
        return JSONResponse({"error": "Invalid PIN"}, status_code=403)
    
    try:
        if action == "set_duty":
            user_id = data.get("user_id")
            if not user_id:
                return JSONResponse({"error": "user_id required"}, status_code=400)
            
            await db.upsert_group_settings(group_name, current_duty_id=user_id)
            return JSONResponse({"success": True})
        
        elif action == "set_sick":
            user_id = data.get("user_id")
            is_sick = data.get("is_sick", True)
            if not user_id:
                return JSONResponse({"error": "user_id required"}, status_code=400)
            
            student = await db.get_student(user_id)
            if student:
                await db.upsert_student(
                    student.group_name,
                    student.user_id,
                    student.full_name,
                    student.is_headman,
                    is_sick
                )
            
            return JSONResponse({"success": True})
        
        elif action == "send_message":
            message = data.get("message")
            if not message:
                return JSONResponse({"error": "message required"}, status_code=400)
            
            users = await db.get_users_by_group(group_name)
            sent_count = 0
            client = http_client
            if not client:
                return JSONResponse({"error": "HTTP client not initialized"}, status_code=500)
            
            for user in users:
                try:
                    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
                    payload = {
                        "chat_id": user.user_id,
                        "text": message
                    }
                    response = await client.post(url, json=payload)
                    if response.status_code == 200:
                        sent_count += 1
                except Exception as e:
                    logger.warning(f"Cannot send to user {user.user_id}: {e}")
            
            return JSONResponse({"success": True, "sent_count": sent_count})
        
        else:
            return JSONResponse({"error": "Unknown action"}, status_code=400)
    
    except Exception as e:
        logger.error(f"Error in api_headman_post: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_kwgt_schedule(request: Request):
    group_name = request.query_params.get("group")
    
    if not group_name:
        return JSONResponse({"error": "group parameter required"}, status_code=400)
    
    try:
        today = date.today()
        day_schedule = await schedule_manager.get_schedule_for_date(group_name, today)
        
        if not day_schedule:
            return JSONResponse({"error": "Schedule not found"}, status_code=404)
        
        lessons_simple = []
        for lesson in day_schedule.lessons:
            lessons_simple.append({
                "time": lesson.time,
                "subject": lesson.subject,
                "room": lesson.room
            })
        
        return JSONResponse({
            "date": day_schedule.date_str,
            "lessons": lessons_simple
        })
    
    except Exception as e:
        logger.error(f"Error in api_kwgt_schedule: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

routes = [
    Route("/", index),
    Route("/homework", homework_form),
    Route("/headman", headman_panel),
    Route("/api/schedule", api_schedule),
    Route("/api/homework", api_homework_get, methods=["GET"]),
    Route("/api/homework", api_homework_post, methods=["POST"]),
    Route("/api/headman", api_headman_get, methods=["GET"]),
    Route("/api/headman", api_headman_post, methods=["POST"]),
    Route("/api/kwgt/schedule", api_kwgt_schedule),
]

middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"]
    )
]

app = Starlette(
    debug=True,
    routes=routes,
    middleware=middleware,
    on_startup=[startup],
    on_shutdown=[shutdown]
)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("WEB_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
