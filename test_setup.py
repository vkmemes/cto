#!/usr/bin/env python3
"""
Test setup script to verify ЯГК Schedule installation.
"""
import asyncio
import sys
import os

def check_python_version():
    print("🔍 Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"   ✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"   ❌ Python {version.major}.{version.minor}.{version.micro} (required: 3.8+)")
        return False

def check_dependencies():
    print("🔍 Checking dependencies...")
    required = [
        'telegram',
        'starlette',
        'uvicorn',
        'sqlalchemy',
        'aiosqlite',
        'httpx',
        'bs4',
        'pydantic',
        'jinja2',
        'dotenv'
    ]
    
    missing = []
    for package in required:
        try:
            __import__(package)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} (missing)")
            missing.append(package)
    
    return len(missing) == 0

def check_env_file():
    print("🔍 Checking .env file...")
    if os.path.exists('.env'):
        print("   ✅ .env file exists")
        
        with open('.env', 'r') as f:
            content = f.read()
            
        required_vars = ['BOT_TOKEN', 'CHANNEL_USERNAME', 'REPLACEMENT_URL']
        for var in required_vars:
            if var in content and not content.split(f'{var}=')[1].split('\n')[0].strip() == '':
                print(f"   ✅ {var} is set")
            else:
                print(f"   ⚠️  {var} is not set or empty")
        
        return True
    else:
        print("   ❌ .env file not found")
        print("   💡 Run: cp .env.example .env")
        return False

def check_schedule_json():
    print("🔍 Checking schedule.json...")
    if os.path.exists('schedule.json'):
        import json
        try:
            with open('schedule.json', 'r') as f:
                data = json.load(f)
            
            groups = data.get('groups', {})
            print(f"   ✅ schedule.json is valid ({len(groups)} groups)")
            
            for group_name in list(groups.keys())[:3]:
                print(f"      - {group_name}")
            
            if len(groups) > 3:
                print(f"      ... and {len(groups) - 3} more")
            
            return True
        except json.JSONDecodeError as e:
            print(f"   ❌ schedule.json is invalid: {e}")
            return False
    else:
        print("   ❌ schedule.json not found")
        return False

def check_templates():
    print("🔍 Checking templates...")
    required_templates = [
        'templates/schedule_view_template.html',
        'templates/homework_form.html',
        'templates/headman_panel.html',
        'templates/manifest.json'
    ]
    
    all_exist = True
    for template in required_templates:
        if os.path.exists(template):
            print(f"   ✅ {os.path.basename(template)}")
        else:
            print(f"   ❌ {os.path.basename(template)} not found")
            all_exist = False
    
    return all_exist

def check_logs_directory():
    print("🔍 Checking logs directory...")
    if os.path.exists('logs') and os.path.isdir('logs'):
        print("   ✅ logs/ directory exists")
        return True
    else:
        print("   ⚠️  logs/ directory not found")
        try:
            os.makedirs('logs')
            print("   ✅ Created logs/ directory")
            return True
        except Exception as e:
            print(f"   ❌ Failed to create logs/ directory: {e}")
            return False

async def check_database():
    print("🔍 Checking database...")
    try:
        from database import Database
        db = Database()
        await db.init_db()
        print("   ✅ Database initialization successful")
        
        from sqlalchemy import select
        from database import User
        async with db.async_session() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()
            print(f"   ✅ Database accessible ({len(users)} users)")
        
        await db.close()
        return True
    except Exception as e:
        print(f"   ❌ Database error: {e}")
        return False

def check_core_imports():
    print("🔍 Checking core imports...")
    try:
        import core
        print("   ✅ core.py")
        
        import database
        print("   ✅ database.py")
        
        import bot_main
        print("   ✅ bot_main.py")
        
        import web_main
        print("   ✅ web_main.py")
        
        return True
    except Exception as e:
        print(f"   ❌ Import error: {e}")
        return False

async def main():
    print("=" * 60)
    print("🚀 ЯГК Schedule - Setup Test")
    print("=" * 60)
    print()
    
    results = []
    
    results.append(("Python Version", check_python_version()))
    print()
    
    results.append(("Dependencies", check_dependencies()))
    print()
    
    results.append(("Core Imports", check_core_imports()))
    print()
    
    results.append((".env File", check_env_file()))
    print()
    
    results.append(("schedule.json", check_schedule_json()))
    print()
    
    results.append(("Templates", check_templates()))
    print()
    
    results.append(("Logs Directory", check_logs_directory()))
    print()
    
    results.append(("Database", await check_database()))
    print()
    
    print("=" * 60)
    print("📊 Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} {name}")
    
    print()
    print(f"Result: {passed}/{total} checks passed")
    print()
    
    if passed == total:
        print("🎉 All checks passed! Your setup is ready.")
        print()
        print("Next steps:")
        print("1. python bot_main.py  # Start the bot")
        print("2. python web_main.py  # Start the web server")
        return 0
    else:
        print("⚠️  Some checks failed. Please fix the issues above.")
        print()
        print("For help, see:")
        print("- README.md")
        print("- QUICKSTART.md")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
