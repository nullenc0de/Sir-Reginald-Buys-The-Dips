#!/usr/bin/env python3
"""
Test script to verify holiday detection is working properly
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api_gateway import ResilientAlpacaGateway
from market_status_manager import MarketStatusManager
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_holiday_detection():
    """Test if the market status properly detects holidays"""
    
    print("\n🔍 Testing Market Holiday Detection\n" + "="*50)
    
    # Initialize components
    gateway = ResilientAlpacaGateway()
    
    # Initialize the gateway (required for API connection)
    print("Initializing API gateway...")
    init_success = await gateway.initialize()
    if not init_success:
        print("❌ Failed to initialize API gateway")
        return
    
    market_status = MarketStatusManager(gateway.trading_client)
    market_status.api_gateway = gateway
    
    # Test the should_start_trading method
    print("\n1. Testing should_start_trading():")
    should_trade, reason = await market_status.should_start_trading()
    print(f"   Should trade: {should_trade}")
    print(f"   Reason: {reason}")
    
    # Test the API clock directly
    print("\n2. Testing Alpaca Clock API directly:")
    try:
        clock = await gateway.get_clock()
        if clock:
            print(f"   Market is open: {clock.is_open}")
            print(f"   Current time: {clock.timestamp}")
            print(f"   Next open: {clock.next_open}")
            print(f"   Next close: {clock.next_close}")
        else:
            print("   Failed to get clock data")
    except Exception as e:
        print(f"   Error getting clock: {e}")
    
    # Test extended hours check
    print("\n3. Testing extended hours detection:")
    is_extended, period = market_status.is_extended_hours()
    print(f"   Is extended hours: {is_extended}")
    print(f"   Period: {period}")
    
    print("\n" + "="*50)
    print("✅ Holiday detection test complete!")
    print("\nNOTE: Today is Labor Day (Sept 2, 2024)")
    print("The market should be CLOSED if detection is working properly.")
    
    # Clean up
    await gateway.cleanup()
    
if __name__ == "__main__":
    asyncio.run(test_holiday_detection())