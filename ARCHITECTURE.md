# ЯГК Schedule - Architecture Documentation

## 📐 System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     ЯГК Schedule System                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐    ┌──────────────────┐              │
│  │  Telegram Bot   │    │   Web Server     │              │
│  │  (bot_main.py)  │    │  (web_main.py)   │              │
│  └────────┬────────┘    └────────┬─────────┘              │
│           │                      │                         │
│           │    ┌────────────────┐│                         │
│           ├────┤  Core Logic    ││                         │
│           │    │  (core.py)     ││                         │
│           │    └────────────────┘│                         │
│           │                      │                         │
│           │    ┌────────────────┐│                         │
│           └────┤   Database     │┘                         │
│                │ (database.py)  │                          │
│                └────────────────┘                          │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                    External Services                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  • Telegram Bot API                                         │
│  • College Replacement HTML Page                           │
│  • SQLite Database (or PostgreSQL)                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 🏗️ Component Architecture

### 1. Core Module (`core.py`)

**Purpose:** Business logic for schedule management

**Key Classes:**

#### `ScheduleManager`
- Manages schedule operations
- Fetches and parses replacements
- Calculates week parity (numerator/denominator)
- Smart group name matching

**Key Methods:**
```python
load_base_schedule()              # Load schedule.json
get_week_parity(date)             # Calculate numerator/denominator
normalize_group_name(name)        # Normalize for matching
find_group_key(user_group)        # Smart group lookup
fetch_replacements()              # HTTP fetch with cache (TTL=5min)
parse_replacements_html(html)     # BeautifulSoup parsing
is_cancellation()                 # Detect cancelled vs replaced
get_schedule_for_date()           # Get schedule for specific date
get_week_schedule()               # Get full week
format_schedule_text()            # Format for Telegram
```

**Data Models (Pydantic):**
- `Lesson`: time, subject, teacher, room, flags
- `DaySchedule`: date, lessons[], is_weekend

**Caching Strategy:**
- Cache replacements in memory
- TTL: 5 minutes
- Shared between bot and web

**Group Matching Logic:**
```
User input: "ИС111" or "ИС1 11" or "ИС1-11"
Normalization: Remove spaces and hyphens → "ИС111"
Match against keys in schedule.json
Support slash notation: "ИС1-11/ИС1-12"
```

**Week Parity Calculation:**
```python
week_num = date.isocalendar()[1]
parity = "numerator" if week_num % 2 == 1 else "denominator"
```

**Cancellation Detection:**
```
Keywords: ["снято", "отменено", "нет пары"]
Logic:
  - If keyword present + short text (<15 chars) + no teacher/room → Cancelled (red)
  - If keyword + "п/гр" or long text → Replaced (yellow)
  - Otherwise → Normal (blue)
```

---

### 2. Database Module (`database.py`)

**Purpose:** Data persistence and ORM

**Technology Stack:**
- SQLAlchemy 2.0 (async)
- aiosqlite driver
- Connection pooling (pool_size=5)

**Database Schema:**

#### Table: `users`
```sql
user_id (BigInteger, PK)
username (String)
group_name (String)           # Selected group
full_name (String)            # Student name
last_notify_date (Date)       # Anti-spam
created_at (DateTime)
```

#### Table: `group_settings`
```sql
group_name (String, PK)
current_headman_id (BigInteger)
current_duty_id (BigInteger)  # Current duty student
notify_enabled (Boolean)
```

#### Table: `group_pins`
```sql
group_name (String, PK)
pin_code (String)             # PIN for headman access
created_by (BigInteger)
created_at (DateTime)
```

#### Table: `students`
```sql
id (Integer, PK, autoincrement)
group_name (String, indexed)
user_id (BigInteger, unique, indexed)
full_name (String)
is_headman (Boolean)
is_sick (Boolean)             # Illness flag
created_at (DateTime)
```

#### Table: `homework`
```sql
id (Integer, PK, autoincrement)
group_name (String, indexed)
subject_name (String)
homework_text (Text)
created_by (BigInteger)
created_at (DateTime)
```

**Key Methods:**

```python
# User operations
upsert_user()                 # Create or update user
get_user(user_id)             # Get by ID
mark_user_notified_today()    # Update spam protection
get_users_by_group()          # Get all group users

# Group settings
upsert_group_settings()       # Update settings
get_group_settings()          # Get by group name

# PIN management
set_group_pin()               # Set/update PIN
verify_pin()                  # Validate PIN
get_pin()                     # Get PIN object

# Student operations
upsert_student()              # Create or update
get_student()                 # Get by user_id
get_students_by_group()       # Get all students
reset_all_sick_flags()        # Daily reset

# Homework operations
set_homework()                # Add homework
get_homework_by_group()       # Get all for group
delete_homework()             # Delete by ID
clear_homework_by_subject()   # Clear subject homework
```

**Connection Pooling:**
```python
create_async_engine(
    pool_size=5,              # Max 5 connections
    max_overflow=10,          # Allow 10 overflow
    pool_pre_ping=True        # Check connections
)
```

---

### 3. Bot Module (`bot_main.py`)

**Purpose:** Telegram bot interface

**Technology Stack:**
- python-telegram-bot 21.0.1
- Async/await architecture
- ConversationHandler for flows
- JobQueue for scheduled tasks

**Bot Commands:**

| Command | Description | Access |
|---------|-------------|--------|
| `/start` | Registration + group selection | All |
| `/today` | Today's schedule | Registered |
| `/tomorrow` | Tomorrow's schedule | Registered |
| `/week` | Full week schedule | Registered |
| `/setpin <PIN>` | Set group PIN | Headman only |

**Conversation Flow:**

```
/start → SELECT_GROUP → ENTER_NAME → Done
         │               │
         │               └→ Save to DB
         │
         └→ Show inline keyboard with groups
```

**Subscription Middleware:**

```python
async def subscription_middleware(update, context):
    # Check if user subscribed to channel
    # If not: show button
    # If yes: proceed
```

**JobQueue Schedule:**

| Time | Job | Purpose |
|------|-----|---------|
| 12:05 | `job_smart_poll` | Check replacements, notify users |
| 14:00 | `job_autoset_duty` | Rotate duty student |
| 17:00 | `job_check_duty` | Remind current duty |
| 00:00 | `job_reset_sick` | Reset all illness flags |

**Job: Smart Poll**
```python
# Pseudo-code
fetch_replacements()
for each group with replacements:
    get_users_by_group()
    for each user not notified today:
        send_message(schedule)
        mark_notified()
        sleep(0.05)  # Rate limiting
```

**Job: Auto Set Duty**
```python
# Pseudo-code
for each group:
    get_healthy_students()  # Not sick
    find_current_duty()
    set_next_duty((current_index + 1) % count)
```

**Deep Linking:**
```
https://t.me/your_bot?start=ИС1-11
↓
/start with parameter "ИС1-11"
↓
Auto-set group for user
```

**Error Handling:**
- Catch `Forbidden` (user blocked bot)
- Catch `BadRequest` (invalid request)
- Log all errors
- Continue processing other users

---

### 4. Web Module (`web_main.py`)

**Purpose:** Web interface and REST API

**Technology Stack:**
- Starlette (ASGI framework)
- Uvicorn (ASGI server)
- Jinja2 (templates)
- CORS middleware

**Endpoints:**

#### HTML Pages
```
GET  /              → schedule_view_template.html
GET  /homework      → homework_form.html
GET  /headman       → headman_panel.html
```

#### REST API
```
GET  /api/schedule
     ?group=ИС1-11&date=15.02.2026
     → JSON schedule

GET  /api/homework
     ?group=ИС1-11&pin=1234
     → JSON homework list

POST /api/homework
     {group, pin, subject, text, mode}
     → Add homework

GET  /api/headman
     ?group=ИС1-11&pin=1234
     → JSON student list + settings

POST /api/headman
     {group, pin, action, ...}
     → Manage group
     Actions: set_duty, set_sick, send_message

GET  /api/kwgt/schedule
     ?group=ИС1-11
     → Simplified JSON for widgets
```

**PIN Authentication:**
```python
pin = request.query_params.get("pin")
if not await db.verify_pin(group, pin):
    return JSONResponse({"error": "Invalid PIN"}, 403)
```

**Telegram Message Sending:**
```python
async with httpx.AsyncClient() as client:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    await client.post(url, json={
        "chat_id": user_id,
        "text": message
    })
```

---

### 5. Templates

#### `schedule_view_template.html`
- PWA-compatible
- Telegram WebApp integration
- Tailwind CSS
- Local storage for favorites
- Date picker
- Color-coded lessons (blue/yellow/red)

**Features:**
- Mobile-first responsive design
- Telegram theme colors
- Back button support
- Offline capability (PWA)

#### `homework_form.html`
- Subject input
- Text area
- Overwrite/Append modes
- Homework list grouped by subject
- PIN authentication
- Local storage for credentials

#### `headman_panel.html`
- Student list with badges
- Duty assignment
- Sick/healthy toggle
- Broadcast messaging
- Statistics panel

---

## 🔄 Data Flow

### Schedule Request Flow

```
User → Telegram Bot → bot_main.py
                          ↓
                      core.py
                          ↓
        ┌─────────────────┴─────────────────┐
        ↓                                   ↓
  schedule.json                    Replacement HTML
  (base schedule)                  (fetch with cache)
        ↓                                   ↓
        └─────────────────┬─────────────────┘
                          ↓
                    Merge + Format
                          ↓
                    Send to User
```

### Replacement Notification Flow

```
12:05 JobQueue → job_smart_poll()
                       ↓
              Fetch replacements
                       ↓
         For each group with replacements
                       ↓
              Get users from DB
                       ↓
         Filter: not notified today
                       ↓
              Send notifications
                       ↓
         Mark users as notified
```

### Homework Submission Flow

```
User → Web Form → /api/homework (POST)
                       ↓
                  Verify PIN
                       ↓
        ┌──────────────┴──────────────┐
        ↓                             ↓
   Overwrite Mode              Append Mode
        ↓                             ↓
   Clear existing              Keep existing
        ↓                             ↓
        └──────────────┬──────────────┘
                       ↓
              Insert new homework
                       ↓
                  Return success
```

### Duty Rotation Flow

```
14:00 JobQueue → job_autoset_duty()
                       ↓
         Get all groups from schedule.json
                       ↓
         For each group:
             ↓
         Get healthy students (not sick)
             ↓
         Find current duty index
             ↓
         Calculate next: (current + 1) % count
             ↓
         Update group_settings
             ↓
         Log change
```

---

## 🔐 Security Architecture

### Authentication & Authorization

1. **Telegram Bot:**
   - Subscription check (middleware)
   - User registration required
   - Group-based access

2. **Web API:**
   - PIN-based authentication
   - Per-group PINs
   - No JWT/session (stateless)

3. **Headman Commands:**
   - Check `is_headman` flag in DB
   - PIN required for web access

### Data Validation

- All user inputs sanitized
- SQLAlchemy ORM (parameterized queries)
- Pydantic models for type validation
- PIN length/format validation

### Rate Limiting

- Bot: 0.05s delay between messages
- Web: No built-in (add reverse proxy)
- Telegram API: Built-in rate limits

### Security Best Practices

✅ No tokens in logs  
✅ No passwords in code  
✅ Environment variables  
✅ HTTPS for production  
✅ CORS configuration  
✅ Input validation  
✅ Error handling (don't leak internals)

---

## 📊 Performance Optimization

### Memory Constraints (512MB RAM)

**Strategies:**

1. **SQLite with Connection Pooling**
   - pool_size=5 (not 100)
   - max_overflow=10
   - No eager loading

2. **Caching**
   - Replacements: 5-minute TTL
   - In-memory only
   - Single instance cache

3. **Async/Await**
   - Non-blocking I/O
   - Concurrent requests
   - No thread overhead

4. **Minimal Dependencies**
   - No heavy frameworks (FastAPI → Starlette)
   - No ORM cache (expire_on_commit=False)

5. **Garbage Collection**
   - Explicit `await db.close()`
   - No circular references
   - Session lifecycle management

### Scalability Considerations

**Current Limits:**
- ~1000 users (SQLite)
- ~50 groups
- ~500 requests/min

**To Scale Up:**
1. Migrate to PostgreSQL
2. Add Redis for caching
3. Horizontal scaling (multiple instances)
4. Load balancer
5. CDN for static files

---

## 🧪 Testing Strategy

### Unit Tests (Recommended)

```python
# test_core.py
def test_week_parity()
def test_normalize_group_name()
def test_is_cancellation()

# test_database.py
async def test_upsert_user()
async def test_verify_pin()

# test_bot.py
def test_subscription_middleware()
```

### Integration Tests

```python
# Test full flow
async def test_schedule_request_flow()
async def test_homework_submission_flow()
async def test_duty_rotation()
```

### Manual Testing

```bash
# Test bot
/start
/today
/tomorrow
/week

# Test web
curl http://localhost:8000/api/schedule?group=ИС1-11
curl -X POST http://localhost:8000/api/homework ...
```

---

## 📈 Monitoring & Logging

### Log Files

- `logs/bot.log` - Bot activity
- `logs/web.log` - Web requests

### Log Format

```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

### Key Metrics to Monitor

- User registrations
- Schedule requests
- Notification delivery rate
- API response times
- Error rates
- Database query times

### Health Checks

```bash
# Bot status
ps aux | grep bot_main.py

# Web status
curl http://localhost:8000/

# Database status
sqlite3 ygk.db "SELECT COUNT(*) FROM users;"

# Logs
tail -f logs/bot.log | grep ERROR
```

---

## 🚀 Deployment Architecture

### Single Server Setup

```
┌──────────────────────────────────────┐
│         VPS (512MB RAM)              │
│                                      │
│  ┌────────────────────────────────┐ │
│  │  systemd                       │ │
│  │  ├── ygk-bot.service         │ │
│  │  └── ygk-web.service         │ │
│  └────────────────────────────────┘ │
│                                      │
│  ┌────────────────────────────────┐ │
│  │  nginx (reverse proxy)         │ │
│  │  Port 80/443 → 8000            │ │
│  └────────────────────────────────┘ │
│                                      │
│  ┌────────────────────────────────┐ │
│  │  SQLite Database               │ │
│  │  /var/lib/ygk/ygk.db      │ │
│  └────────────────────────────────┘ │
│                                      │
└──────────────────────────────────────┘
```

### Multi-Server Setup (Future)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Bot       │     │   Web       │     │  Database   │
│  Servers    │     │  Servers    │     │  (Postgres) │
│  (polling)  │     │  (ASGI)     │     │             │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┴───────────────────┘
                          │
                   ┌──────┴──────┐
                   │   Redis     │
                   │  (cache)    │
                   └─────────────┘
```

---

## 🔧 Configuration Management

### Environment Variables

```bash
# Required
BOT_TOKEN=              # From @BotFather
CHANNEL_USERNAME=       # @channel_name
REPLACEMENT_URL=        # HTML page URL

# Optional
DATABASE_URL=           # Default: sqlite+aiosqlite:///ygk.db
WEB_PORT=               # Default: 8000
```

### Configuration Files

- `schedule.json` - Base schedule
- `.env` - Environment variables
- `ygk-*.service` - systemd services

---

## 📚 External Dependencies

### Python Packages

| Package | Version | Purpose |
|---------|---------|---------|
| python-telegram-bot | 21.0.1 | Bot framework |
| starlette | 0.36.3 | Web framework |
| uvicorn | 0.27.1 | ASGI server |
| sqlalchemy | 2.0.27 | ORM |
| aiosqlite | 0.19.0 | SQLite driver |
| httpx | 0.27.0 | HTTP client |
| beautifulsoup4 | 4.12.3 | HTML parser |
| pydantic | 2.6.1 | Data validation |
| jinja2 | 3.1.3 | Templates |
| python-dotenv | 1.0.1 | .env loader |

### External Services

- Telegram Bot API
- College replacement HTML page
- (Optional) Telegram Mini Apps

---

## 🎯 Design Patterns

### Patterns Used

1. **Repository Pattern** (Database class)
2. **Singleton** (ScheduleManager cache)
3. **Middleware** (Subscription check)
4. **Template Method** (Job scheduling)
5. **Strategy** (Cancellation detection)
6. **Factory** (Lesson/DaySchedule models)
7. **Observer** (JobQueue)

### Async Patterns

- `async/await` throughout
- Context managers for sessions
- Async generators for streams
- Concurrent request handling

---

## 🔮 Future Enhancements

### Planned Features

- [ ] Multi-language support (i18n)
- [ ] Push notifications (webhook)
- [ ] Calendar integration (iCal)
- [ ] Mobile app (React Native)
- [ ] Admin dashboard
- [ ] Analytics dashboard
- [ ] Backup/restore system
- [ ] Migration from Excel/CSV
- [ ] Voice announcements
- [ ] QR code check-in

### Technical Debt

- [ ] Add unit tests
- [ ] Add integration tests
- [ ] Implement rate limiting
- [ ] Add prometheus metrics
- [ ] Add distributed tracing
- [ ] Implement feature flags
- [ ] Add database migrations (Alembic)

---

**Document Version:** 1.0  
**Last Updated:** February 2026  
**Maintainer:** ЯГК Schedule Team
