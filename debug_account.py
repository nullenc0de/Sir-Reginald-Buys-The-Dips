#!/usr/bin/env python3
"""
Quick debug script to check account fields for PDT day trade count
"""
import asyncio
import os
from api_gateway import ResilientAlpacaGateway

async def debug_account():
    try:
        gateway = ResilientAlpacaGateway()
        account = await gateway.get_account_safe()
        
        if account:
            print("=== ACCOUNT OBJECT DEBUG ===")
            if hasattr(account, '__dict__'):
                for key, value in account.__dict__.items():
                    if 'day' in key.lower() or 'trade' in key.lower() or 'pdt' in key.lower():
                        print(f"🔍 {key}: {value}")
                        
            print(f"\n=== SPECIFIC CHECKS ===")
            print(f"day_trade_count: {getattr(account, 'day_trade_count', 'NOT FOUND')}")
            print(f"daytrade_count: {getattr(account, 'daytrade_count', 'NOT FOUND')}")
            print(f"dayTradeCount: {getattr(account, 'dayTradeCount', 'NOT FOUND')}")
            print(f"pattern_day_trader: {getattr(account, 'pattern_day_trader', 'NOT FOUND')}")
            print(f"equity: {getattr(account, 'equity', 'NOT FOUND')}")
            
            print(f"\n=== ALL FIELDS ===")
            if hasattr(account, '__dict__'):
                all_fields = list(account.__dict__.keys())
                print(f"Available fields: {all_fields}")
            
        else:
            print("❌ Failed to get account data")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    # Set environment variables if not already set
    if not os.getenv('APCA_API_KEY_ID'):
        os.environ['APCA_API_KEY_ID'] = 'PK4DVRCB6ERJ2VUD2Q0L'
    if not os.getenv('APCA_API_SECRET_KEY'):
        os.environ['APCA_API_SECRET_KEY'] = 'AvXfstm3WqFBujx3jha5Aeyr3wYd4m59Ey84opXL'
    
    asyncio.run(debug_account())