#!/usr/bin/env python3
"""
Test script for stale order cleanup functionality
Tests the new automatic cancellation of stuck orders
"""

import asyncio
import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
if os.path.exists('.env'):
    with open('.env') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value

from main import IntelligentTradingSystem

async def test_stale_order_cleanup():
    """Test the stale order cleanup functionality"""
    print("\n" + "="*60)
    print("STALE ORDER CLEANUP TEST")
    print("="*60 + "\n")

    # Initialize the trading system
    system = IntelligentTradingSystem()

    try:
        print("1. Checking for existing open orders...")
        open_orders = await system.gateway.get_orders(status='open')

        if open_orders:
            print(f"   Found {len(open_orders)} open orders")

            # Display orders
            stale_count = 0
            from datetime import timezone

            for order in open_orders:
                symbol = getattr(order, 'symbol', 'unknown')
                status = getattr(order, 'status', 'unknown')
                order_type = getattr(order, 'type', 'unknown')
                side = getattr(order, 'side', 'unknown')
                created_at = getattr(order, 'created_at', None)

                age_str = "unknown age"
                if created_at:
                    try:
                        order_age = (datetime.now(timezone.utc) - created_at).total_seconds()
                        age_str = f"{order_age/60:.1f} minutes"
                        if status == 'new' and order_age > 300:
                            stale_count += 1
                            print(f"   ⚠️  STALE: {symbol} - {order_type} {side} order, status: {status}, age: {age_str}")
                        else:
                            print(f"   ✓ {symbol} - {order_type} {side} order, status: {status}, age: {age_str}")
                    except:
                        print(f"   ? {symbol} - {order_type} {side} order, status: {status}, age: {age_str}")
                else:
                    print(f"   ? {symbol} - {order_type} {side} order, status: {status}, age: {age_str}")

            print(f"\n2. Found {stale_count} stale orders (status 'new' > 5 minutes old)")

            if stale_count > 0:
                print("\n3. Running cleanup...")
                cancelled = await system._cleanup_all_stale_orders()
                print(f"   Cleanup complete: {cancelled} orders cancelled")

                # Verify cleanup
                print("\n4. Verifying cleanup...")
                await asyncio.sleep(2)
                remaining_orders = await system.gateway.get_orders(status='open')
                print(f"   Remaining open orders: {len(remaining_orders) if remaining_orders else 0}")
            else:
                print("\n3. No stale orders found - system is clean!")

                # Test the check function for a specific symbol
                print("\n4. Testing order check for sample positions...")
                positions = await system.gateway.get_all_positions()
                if positions:
                    test_symbol = positions[0].symbol if hasattr(positions[0], 'symbol') else None
                    if test_symbol:
                        print(f"   Testing order check for {test_symbol}...")
                        has_orders = await system._check_actual_open_orders_for_symbol(test_symbol)
                        print(f"   Result: {'Has blocking orders' if has_orders else 'No blocking orders'}")
        else:
            print("   No open orders found")
            print("\n2. System is clean - no stale orders to clear!")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(test_stale_order_cleanup())