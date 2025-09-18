#!/usr/bin/env python3
"""
Force cleanup of all stale orders in the trading system
"""

import asyncio
import os
from datetime import datetime

# Load environment variables
if os.path.exists('.env'):
    with open('.env') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value

from api_gateway import ResilientAlpacaGateway

async def force_cleanup_stale_orders():
    """Force cleanup of all stale orders"""
    print("\n" + "="*60)
    print("FORCE CLEANUP OF STALE ORDERS")
    print("="*60 + "\n")

    gateway = ResilientAlpacaGateway()

    try:
        print("1. Fetching all open orders...")
        open_orders = await gateway.get_orders(status='open')

        if not open_orders:
            print("   No open orders found - system is clean!")
            return

        print(f"   Found {len(open_orders)} open orders")

        stale_orders = []
        from datetime import timezone

        print("\n2. Analyzing orders...")
        for order in open_orders:
            order_id = getattr(order, 'id', None)
            symbol = getattr(order, 'symbol', 'unknown')
            status = getattr(order, 'status', 'unknown')
            created_at = getattr(order, 'created_at', None)
            order_type = getattr(order, 'type', 'unknown')
            side = getattr(order, 'side', 'unknown')

            age_str = "unknown"
            is_stale = False

            if created_at:
                try:
                    order_age = (datetime.now(timezone.utc) - created_at).total_seconds()
                    age_minutes = order_age / 60
                    age_str = f"{age_minutes:.1f} min"

                    # Mark as stale if status is 'new' and older than 5 minutes
                    if status == 'new' and age_minutes > 5:
                        is_stale = True
                        stale_orders.append((order_id, symbol, order_type, side, age_str))
                        print(f"   ⚠️  STALE: {symbol} - {order_type} {side}, status: {status}, age: {age_str}")
                    else:
                        print(f"   ✓ ACTIVE: {symbol} - {order_type} {side}, status: {status}, age: {age_str}")
                except Exception as e:
                    print(f"   ? ERROR: {symbol} - Could not determine age: {e}")

        if not stale_orders:
            print("\n✅ No stale orders found!")
            return

        print(f"\n3. Found {len(stale_orders)} stale orders to cancel")
        print("\n4. Cancelling stale orders...")

        cancelled = 0
        failed = 0

        for order_id, symbol, order_type, side, age in stale_orders:
            try:
                print(f"   Cancelling {symbol} {order_type} {side} order (age: {age})...")
                response = await gateway.cancel_order(order_id)
                if response and response.success:
                    print(f"   ✅ Successfully cancelled order for {symbol}")
                    cancelled += 1
                else:
                    print(f"   ❌ Failed to cancel order for {symbol}: {response.error if response else 'No response'}")
                    failed += 1
            except Exception as e:
                print(f"   ❌ Error cancelling order for {symbol}: {e}")
                failed += 1

        print(f"\n5. Cleanup Results:")
        print(f"   ✅ Successfully cancelled: {cancelled} orders")
        if failed > 0:
            print(f"   ❌ Failed to cancel: {failed} orders")

        # Verify cleanup
        print("\n6. Verifying cleanup...")
        await asyncio.sleep(2)
        remaining = await gateway.get_orders(status='open')
        remaining_count = len(remaining) if remaining else 0
        print(f"   Remaining open orders: {remaining_count}")

        if remaining_count > 0:
            print("\n   Remaining orders:")
            for order in remaining[:5]:  # Show first 5
                symbol = getattr(order, 'symbol', 'unknown')
                status = getattr(order, 'status', 'unknown')
                order_type = getattr(order, 'type', 'unknown')
                side = getattr(order, 'side', 'unknown')
                print(f"   - {symbol}: {order_type} {side}, status: {status}")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*60)
    print("CLEANUP COMPLETE")
    print("="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(force_cleanup_stale_orders())