"""
Market status manager for trading hours and market conditions
"""

import logging
from typing import Dict, Tuple
from datetime import datetime, time
import asyncio

logger = logging.getLogger(__name__)

class MarketStatusManager:
    """
    Manages market hours, holidays, and trading conditions
    """
    
    def __init__(self, trading_client):
        self.trading_client = trading_client
        self.market_status = None
        self.last_status_check = None
        self.extended_hours_monitoring = True  # Monitor positions outside market hours
        self.api_gateway = None  # Will be set by main.py
        
    async def should_start_trading(self) -> Tuple[bool, str]:
        """Determine if trading should start"""
        try:
            # First check with Alpaca API for accurate market status (includes holidays)
            if self.api_gateway:
                try:
                    clock = await self.api_gateway.get_clock()
                    if clock and hasattr(clock, 'is_open'):
                        if not clock.is_open:
                            # Get more specific reason
                            current_time = datetime.now()
                            if current_time.weekday() >= 5:
                                return False, "Weekend - market closed"
                            else:
                                # It's a weekday but market is closed - likely a holiday
                                return False, "Market closed (holiday or special closure)"
                        else:
                            return True, "Market is open for trading"
                except Exception as api_error:
                    logger.warning(f"API clock check failed, falling back to time-based check: {api_error}")
            
            # Fallback to time-based checking if API is unavailable
            current_time = datetime.now()
            
            # Check if it's a weekday
            if current_time.weekday() >= 5:  # Saturday = 5, Sunday = 6
                return False, "Weekend - market closed"
                
            # Check market hours (Eastern Time)
            market_open = time(9, 30)  # 9:30 AM ET
            market_close = time(16, 0)  # 4:00 PM ET
            current_time_only = current_time.time()
            
            if current_time_only < market_open:
                minutes_until_open = (datetime.combine(current_time.date(), market_open) - 
                                    datetime.combine(current_time.date(), current_time_only)).total_seconds() / 60
                return False, f"Market opens in {minutes_until_open:.0f} minutes"
                
            if current_time_only > market_close:
                return False, "Market closed for the day"
                
            # Market is open (but this is just time-based, may not account for holidays)
            logger.warning("Using time-based market check - holidays not detected")
            return True, "Market appears open (time-based check)"
            
        except Exception as e:
            logger.error(f"Market status check failed: {e}")
            return False, f"Error checking market status: {e}"
            
    async def wait_for_market_open(self):
        """Wait for market to open"""
        try:
            while True:
                should_trade, reason = await self.should_start_trading()
                
                if should_trade:
                    logger.info("📈 Market is open - ready to trade")
                    break
                    
                logger.info(f"⏰ {reason} - waiting...")
                await asyncio.sleep(60)  # Check every minute
                
        except KeyboardInterrupt:
            logger.info("Market open wait cancelled")
            raise
        except Exception as e:
            logger.error(f"Error waiting for market open: {e}")
            
    async def is_market_open(self) -> bool:
        """Quick check if market is currently open"""
        should_trade, _ = await self.should_start_trading()
        return should_trade
    
    def is_extended_hours(self) -> Tuple[bool, str]:
        """Check if we're in pre-market or after-hours period"""
        try:
            current_time = datetime.now()
            
            # Skip weekends entirely
            if current_time.weekday() >= 5:
                return False, "Weekend"
            
            current_time_only = current_time.time()
            
            # Extended hours periods
            premarket_start = time(4, 0)   # 4:00 AM ET
            market_open = time(9, 30)      # 9:30 AM ET  
            market_close = time(16, 0)     # 4:00 PM ET
            afterhours_end = time(20, 0)   # 8:00 PM ET
            
            if premarket_start <= current_time_only < market_open:
                return True, "Pre-market (4:00 AM - 9:30 AM ET)"
            elif market_close < current_time_only <= afterhours_end:
                return True, "After-hours (4:00 PM - 8:00 PM ET)"
            elif current_time_only > afterhours_end or current_time_only < premarket_start:
                return True, "Overnight (8:00 PM - 4:00 AM ET)"
            else:
                return False, "Regular market hours"
                
        except Exception as e:
            logger.error(f"Extended hours check failed: {e}")
            return False, "Error"
    
    def should_monitor_positions_extended_hours(self) -> bool:
        """Determine if we should monitor positions during extended hours"""
        is_extended, period = self.is_extended_hours()
        if is_extended and period != "Weekend":
            return True
        return False