"""
Pattern Day Trading (PDT) Rule Compliance Manager
Prevents violations of SEC PDT rules to avoid account restrictions
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)

@dataclass
class DayTrade:
    """Represents a single day trade (buy and sell of same stock on same day)"""
    symbol: str
    buy_time: datetime
    sell_time: datetime
    quantity: int
    buy_price: float
    sell_price: float
    pnl: float

class PDTManager:
    """
    Manages Pattern Day Trading rule compliance
    Tracks day trades and prevents violations that could restrict trading
    """
    
    def __init__(self):
        self.day_trades_history: List[DayTrade] = []
        self.open_positions_today: Dict[str, Dict] = {}  # Positions opened today
        self.last_reset_date = datetime.now().date()
        
    async def initialize(self, gateway):
        """Initialize PDT manager with current account and position data"""
        try:
            self.gateway = gateway
            
            # Get account info to check PDT status
            account = await self.gateway.get_account_safe()
            if account:
                # Check if account is flagged as PDT
                pattern_day_trader = getattr(account, 'pattern_day_trader', None)
                if pattern_day_trader:
                    logger.info("📊 Account is flagged as Pattern Day Trader")
                else:
                    logger.info("📊 Account is NOT flagged as Pattern Day Trader")
                
                # Get account equity to check PDT requirements
                equity = float(account.equity)
                if equity < 25000:
                    logger.warning("⚠️ Account equity below $25,000 - PDT rules apply strictly")
                else:
                    logger.info("💰 Account equity above $25,000 - PDT rules relaxed")
            
            # Initialize today's tracking
            await self._reset_daily_tracking()
            
            logger.info("✅ PDT Manager initialized")
            
        except Exception as e:
            logger.error(f"PDT Manager initialization failed: {e}")
    
    async def _reset_daily_tracking(self):
        """Reset daily tracking at market open"""
        current_date = datetime.now().date()
        
        if current_date != self.last_reset_date:
            logger.info(f"🔄 Resetting PDT tracking for new trading day: {current_date}")
            
            # Archive completed day trades from previous days
            self._archive_old_day_trades()
            
            # Reset today's position tracking
            self.open_positions_today = {}
            self.last_reset_date = current_date
    
    def _archive_old_day_trades(self):
        """Archive day trades older than 5 business days (PDT rolling window)"""
        cutoff_date = datetime.now() - timedelta(days=7)  # Keep extra days for safety
        
        original_count = len(self.day_trades_history)
        self.day_trades_history = [
            dt for dt in self.day_trades_history 
            if dt.buy_time >= cutoff_date
        ]
        
        archived_count = original_count - len(self.day_trades_history)
        if archived_count > 0:
            logger.info(f"📂 Archived {archived_count} old day trades")
    
    async def check_pdt_compliance_before_trade(self, symbol: str, side: str, quantity: int) -> Tuple[bool, str]:
        """
        Check if a trade would violate PDT rules
        Returns (can_trade, reason)
        """
        try:
            await self._reset_daily_tracking()
            
            # Get current PDT day trade count in rolling 5-day period
            recent_day_trades = self._get_recent_day_trades()
            local_day_trade_count = len(recent_day_trades)
            
            # Check account status and equity
            account = await self.gateway.get_account_safe()
            if not account:
                return False, "Cannot access account information"
            
            equity = float(account.equity)
            is_pdt_account = getattr(account, 'pattern_day_trader', False)
            
            # Use broker's actual day trade count if available (more reliable)
            # Try multiple possible field names for day trade count
            broker_day_trade_count = (
                getattr(account, 'day_trade_count', None) or
                getattr(account, 'daytrade_count', None) or
                getattr(account, 'dayTradeCount', None) or
                getattr(account, 'day_trades', None) or
                0
            )
            
            # Debug: log all account attributes to find the correct field
            if hasattr(account, '__dict__'):
                logger.info(f"🔍 Account fields: {list(account.__dict__.keys())}")
                # Also check for any fields containing 'day' or 'trade'
                day_trade_fields = {k: v for k, v in account.__dict__.items() if 'day' in k.lower() or 'trade' in k.lower()}
                if day_trade_fields:
                    logger.info(f"🎯 Day/trade related fields: {day_trade_fields}")
                else:
                    logger.info(f"🔍 No day/trade fields found in account object")
            
            current_day_trade_count = max(local_day_trade_count, broker_day_trade_count)
            
            logger.info(f"📊 Day trade status - Local: {local_day_trade_count}, Broker: {broker_day_trade_count}, Using: {current_day_trade_count}")
            
            # If we're at the PDT limit, be explicit about it
            if current_day_trade_count >= 3 and equity < 25000:
                logger.warning(f"⚠️ PDT LIMIT REACHED: {current_day_trade_count} day trades with equity ${equity:,.2f} < $25,000")
                logger.warning(f"⚠️ New day trades will be blocked until count drops below 3 or equity exceeds $25,000")
            
            # If buying, check PDT risk more carefully for small accounts
            if side.lower() == 'buy':
                # For accounts under $25K with existing day trades, be very conservative
                if current_day_trade_count >= 2 and equity < 25000:
                    logger.warning(f"⚠️ CONSERVATIVE PDT PREVENTION: {current_day_trade_count} day trades exist, blocking new positions to prevent PDT violation")
                    return False, f"PDT PREVENTION: Already have {current_day_trade_count} day trades. Avoiding new positions to prevent violations."
                
                # Check if we already have a position opened today (to prevent adding to day trade risk)
                if symbol in self.open_positions_today:
                    logger.info(f"⚠️ {symbol}: Already opened position today - adding could create larger day trade")
                
                # If we're at limit, only allow if we're sure it won't become a day trade
                if current_day_trade_count >= 3 and equity < 25000:
                    logger.warning(f"⚠️ AT PDT LIMIT: Only allowing buy if position will be held overnight")
                    return True, "Buy order approved with PDT limit warning - MUST hold overnight"
                
                return True, "Buy order approved"
            
            # If selling, check for potential day trade
            elif side.lower() == 'sell':
                # Check if we opened a position in this symbol today
                if symbol in self.open_positions_today:
                    # This would create a day trade
                    potential_day_trades = current_day_trade_count + 1
                    
                    # Allow up to 3 day trades (PDT limit is 4, be conservative at 3)
                    if current_day_trade_count >= 3 and equity < 25000:  # Allow 3 day trades, block at 4th
                        return False, f"PDT PREVENTION: Already have {current_day_trade_count} day trades. Cannot exceed 3 day trades with account equity ${equity:,.2f} < $25,000"
                    elif current_day_trade_count >= 4:
                        if equity < 25000:
                            return False, f"PDT VIOLATION RISK: Already have {current_day_trade_count} day trades in 5-day period. Account equity ${equity:,.2f} < $25,000 required for PDT."
                        elif not is_pdt_account:
                            return False, f"PDT FLAG RISK: {current_day_trade_count} day trades may trigger PDT flag. Consider waiting until tomorrow."
                    
                    # If we're under the conservative limit, allow but warn
                    logger.warning(f"⚠️ {symbol}: Sell would create day trade #{potential_day_trades} (being conservative due to small account)")
                    return True, f"Day trade #{potential_day_trades} approved (conservative limit)"
                
                # Selling a position not opened today - no PDT risk
                return True, "Sell order approved (no PDT risk)"
            
            return True, "Trade approved"
            
        except Exception as e:
            logger.error(f"PDT compliance check failed: {e}")
            return False, f"PDT check error: {e}"
    
    async def record_trade_execution(self, symbol: str, side: str, quantity: int, price: float, execution_time: datetime = None):
        """Record a trade execution for PDT tracking"""
        try:
            if execution_time is None:
                execution_time = datetime.now()
            
            await self._reset_daily_tracking()
            
            if side.lower() == 'buy':
                # Record position opened today
                if symbol not in self.open_positions_today:
                    self.open_positions_today[symbol] = []
                
                self.open_positions_today[symbol].append({
                    'quantity': quantity,
                    'price': price,
                    'time': execution_time
                })
                
                logger.info(f"📊 PDT tracking: {symbol} buy recorded ({quantity} shares @ ${price:.2f})")
            
            elif side.lower() == 'sell':
                # Check if this creates a day trade
                if symbol in self.open_positions_today:
                    # Find matching buy order(s) from today
                    buys_today = self.open_positions_today[symbol]
                    
                    # Create day trade record(s)
                    remaining_sell_qty = quantity
                    
                    for buy_record in buys_today:
                        if remaining_sell_qty <= 0:
                            break
                        
                        buy_qty = buy_record['quantity']
                        matched_qty = min(remaining_sell_qty, buy_qty)
                        
                        if matched_qty > 0:
                            # Create day trade record
                            day_trade = DayTrade(
                                symbol=symbol,
                                buy_time=buy_record['time'],
                                sell_time=execution_time,
                                quantity=matched_qty,
                                buy_price=buy_record['price'],
                                sell_price=price,
                                pnl=(price - buy_record['price']) * matched_qty
                            )
                            
                            self.day_trades_history.append(day_trade)
                            
                            # Update buy record
                            buy_record['quantity'] -= matched_qty
                            remaining_sell_qty -= matched_qty
                    
                    # Remove exhausted buy records
                    self.open_positions_today[symbol] = [
                        buy for buy in buys_today if buy['quantity'] > 0
                    ]
                    
                    # Remove symbol if no more buys today
                    if not self.open_positions_today[symbol]:
                        del self.open_positions_today[symbol]
                    
                    recent_day_trades = self._get_recent_day_trades()
                    day_trade_count = len(recent_day_trades)
                    
                    logger.info(f"🎯 PDT tracking: {symbol} day trade recorded. Total in 5-day period: {day_trade_count}")
                    
                    # Check for approaching PDT limits
                    if day_trade_count >= 3:
                        account = await self.gateway.get_account_safe()
                        if account and float(account.equity) < 25000:
                            logger.warning(f"⚠️ PDT WARNING: {day_trade_count} day trades in 5-day period. One more will trigger PDT flag.")
                
                else:
                    logger.info(f"📊 PDT tracking: {symbol} sell recorded (no day trade - position not opened today)")
        
        except Exception as e:
            logger.error(f"Failed to record trade execution for PDT tracking: {e}")
    
    def _get_recent_day_trades(self) -> List[DayTrade]:
        """Get day trades in the last 5 business days (PDT rolling window)"""
        cutoff_date = datetime.now() - timedelta(days=5)
        
        return [
            dt for dt in self.day_trades_history 
            if dt.buy_time >= cutoff_date
        ]
    
    async def get_pdt_status(self) -> Dict:
        """Get comprehensive PDT status and statistics"""
        try:
            await self._reset_daily_tracking()
            
            recent_day_trades = self._get_recent_day_trades()
            account = await self.gateway.get_account_safe()
            
            equity = float(account.equity) if account else 0
            is_pdt_account = getattr(account, 'pattern_day_trader', False) if account else False
            
            # Calculate day trade statistics
            day_trade_count = len(recent_day_trades)
            remaining_day_trades = max(0, 3 - day_trade_count) if equity < 25000 else float('inf')
            
            # Calculate P&L from recent day trades
            day_trade_pnl = sum(dt.pnl for dt in recent_day_trades)
            
            status = {
                'account_equity': equity,
                'is_pdt_account': is_pdt_account,
                'day_trades_in_5_days': day_trade_count,
                'remaining_day_trades': remaining_day_trades if remaining_day_trades != float('inf') else "Unlimited",
                'day_trade_pnl_5_days': day_trade_pnl,
                'positions_opened_today': len(self.open_positions_today),
                'pdt_restrictions_active': equity < 25000 and not is_pdt_account,
                'recent_day_trades': [
                    {
                        'symbol': dt.symbol,
                        'date': dt.buy_time.date().isoformat(),
                        'quantity': dt.quantity,
                        'pnl': dt.pnl
                    }
                    for dt in recent_day_trades
                ]
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get PDT status: {e}")
            return {'error': str(e)}
    
    async def check_for_pdt_violations(self) -> List[str]:
        """Check for potential PDT violations and return warnings"""
        try:
            warnings = []
            
            recent_day_trades = self._get_recent_day_trades()
            day_trade_count = len(recent_day_trades)
            
            account = await self.gateway.get_account_safe()
            if not account:
                warnings.append("Cannot access account information for PDT check")
                return warnings
            
            equity = float(account.equity)
            is_pdt_account = getattr(account, 'pattern_day_trader', False)
            
            # Check for violations
            if day_trade_count >= 4 and equity < 25000:
                warnings.append(f"🚨 PDT VIOLATION: {day_trade_count} day trades with equity ${equity:,.2f} < $25,000")
            
            elif day_trade_count == 3 and equity < 25000:
                warnings.append(f"⚠️ PDT WARNING: {day_trade_count} day trades - ONE MORE will trigger PDT restrictions")
            
            elif day_trade_count >= 2 and equity < 25000:
                warnings.append(f"📊 PDT CAUTION: {day_trade_count} day trades - monitor carefully")
            
            # Check for positions opened today that could become day trades
            if self.open_positions_today:
                symbols_at_risk = list(self.open_positions_today.keys())
                warnings.append(f"⚠️ Day trade risk: Positions opened today in {', '.join(symbols_at_risk)}")
            
            return warnings
            
        except Exception as e:
            logger.error(f"PDT violation check failed: {e}")
            return [f"PDT check error: {e}"]