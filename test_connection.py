"""
Simple connection test script to verify setup before running the full collector.
"""
import asyncio
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from config.settings import settings
from src.database.writer import SupabaseWriter
from src.collectors.kalshi_auth import KalshiAuth, KalshiRestClient
from src.utils.logger import setup_logging
import structlog

# Setup logging
setup_logging()
logger = structlog.get_logger()


async def test_supabase_connection():
    """Test Supabase connection."""
    print("\n🔍 Testing Supabase connection...")
    try:
        db = SupabaseWriter()

        # Try to get markets
        markets = await db.get_active_markets()

        print(f"✅ Supabase connection successful!")
        print(f"   Found {len(markets)} active markets in database")

        await db.close()
        return True

    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        return False


async def test_kalshi_auth():
    """Test Kalshi authentication."""
    print("\n🔍 Testing Kalshi authentication...")
    try:
        auth = KalshiAuth()
        success = await auth.login()

        if success:
            print(f"✅ Kalshi authentication successful!")
            print(f"   Token acquired and valid")
        else:
            print(f"❌ Kalshi authentication failed")
            return False

        await auth.close()
        return True

    except Exception as e:
        print(f"❌ Kalshi authentication failed: {e}")
        return False


async def test_market_fetch():
    """Test fetching markets from Kalshi."""
    print("\n🔍 Testing market data fetch...")
    try:
        auth = KalshiAuth()
        await auth.login()

        client = KalshiRestClient(auth)

        # Fetch NFL markets
        markets = await client.get_markets(series_ticker="NFL", limit=5)

        print(f"✅ Market fetch successful!")
        print(f"   Found {len(markets)} NFL markets")

        if markets:
            print(f"\n   Sample market:")
            market = markets[0]
            print(f"   - Ticker: {market.get('ticker')}")
            print(f"   - Title: {market.get('title')}")
            print(f"   - Status: {market.get('status')}")

        await client.close()
        await auth.close()
        return True

    except Exception as e:
        print(f"❌ Market fetch failed: {e}")
        return False


async def test_all():
    """Run all connection tests."""
    print("=" * 60)
    print("🚀 Kalshi Data Collector - Connection Test")
    print("=" * 60)

    print(f"\n📋 Configuration:")
    print(f"   Environment: {settings.environment}")
    print(f"   Target Sports: {', '.join(settings.target_sports_list)}")
    print(f"   Collection Interval: {settings.collection_interval_seconds}s")
    print(f"   Supabase URL: {settings.supabase_url}")
    print(f"   Kalshi API URL: {settings.kalshi_base_url}")

    # Run tests
    results = []

    results.append(("Supabase", await test_supabase_connection()))
    results.append(("Kalshi Auth", await test_kalshi_auth()))
    results.append(("Market Fetch", await test_market_fetch()))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {test_name}")

    all_passed = all(success for _, success in results)

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All tests passed! You're ready to start collecting data.")
        print("\nNext steps:")
        print("1. Run locally: ./run_local.sh")
        print("2. Or deploy to Railway (see DEPLOYMENT.md)")
    else:
        print("⚠️  Some tests failed. Please check your configuration:")
        print("1. Verify .env file has correct credentials")
        print("2. Check Supabase project is active")
        print("3. Verify Kalshi API credentials are correct")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    result = asyncio.run(test_all())
    sys.exit(0 if result else 1)
