import asyncio
import sys
from database import Database

async def migrate():
    print("Starting database migration...")
    db = Database()
    
    try:
        await db.init_db()
        print("✅ Database schema created/updated successfully!")
        print("\nTables created:")
        print("  - users")
        print("  - group_settings")
        print("  - group_pins")
        print("  - students")
        print("  - homework")
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        sys.exit(1)
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(migrate())
