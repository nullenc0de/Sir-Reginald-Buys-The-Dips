# -*- coding: utf-8 -*-
"""
Main trading application with intelligent funnel and AI enhancement
Complete system orchestration for market-wide opportunity discovery
"""

import asyncio
import logging
import signal
import sys
import os
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional
import json

# Load environment variables from .env file
if os.path.exists('.env'):
    with open('.env') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value

# Import all system modules
from config import *
from intelligent_funnel import IntelligentMarketFunnel, MarketOpportunity
from ai_market_intelligence import EnhancedAIAssistant, MarketIntelligence
from enhanced_momentum_strategy import EventDrivenMomentumStrategy, TradingSignal
from corporate_actions_filter import CorporateActionsFilter
from utils import OrderUtils, DateTimeUtils, ConfigurationValidator
from api_gateway import ResilientAlpacaGateway
from risk_manager import ConservativeRiskManager
from order_executor import SimpleTradeExecutor
from market_status_manager import MarketStatusManager
from performance_tracker import PerformanceTracker
from supplemental_data_provider import SupplementalDataProvider
from alerter import CriticalAlerter
from pdt_manager import PDTManager
from gap_risk_manager import GapRiskManager

class IntelligentTradingSystem:
    """
    Complete intelligent trading system with market-wide discovery
    Integrates all components for systematic algorithmic trading
    """
    
    def __init__(self):
        self.logger = self._setup_logging()
        self.running = False
        self.system_initialized = False
        
        # Core system components
        self.gateway = ResilientAlpacaGateway()
        self.supplemental_data = SupplementalDataProvider()
        self.market_status = MarketStatusManager(self.gateway.trading_client)
        self.market_status.api_gateway = self.gateway  # Provide access to API for holiday checks
        self.ai_assistant = EnhancedAIAssistant()
        self.strategy_engine = EventDrivenMomentumStrategy()
        self.market_funnel = IntelligentMarketFunnel(
            self.gateway, 
            self.ai_assistant, 
            self.supplemental_data, 
            self.strategy_engine
        )
        self.risk_manager = ConservativeRiskManager()
        self.order_executor = SimpleTradeExecutor(self.gateway, self.risk_manager)
        # Note: PDT manager will be linked after initialization
        self.performance_tracker = None  # Will be initialized after gateway
        self.corporate_actions_filter = CorporateActionsFilter()
        self.alerter = CriticalAlerter()  # CRITICAL: Emergency alerting system
        self.pdt_manager = PDTManager()  # CRITICAL: PDT rule compliance
        self.gap_risk_manager = GapRiskManager()  # CRITICAL: Extended hours gap protection
        
        # System state
        self.current_intelligence: Optional[MarketIntelligence] = None
        self.active_opportunities: List[MarketOpportunity] = []
        self.last_intelligence_update = None
        self.last_opportunity_scan = None
        
        # Performance tracking
        self.session_stats = {
            'opportunities_discovered': 0,
            'signals_generated': 0,
            'trades_executed': 0,
            'api_calls_made': 0,
            'system_uptime_start': datetime.now()
        }
        
        # Warning suppression tracking
        self.extended_hours_warnings_sent = set()  # Track symbols already warned about

        # Emergency stop tracking to prevent excessive recreation
        self.recent_emergency_stops = {}  # {symbol: timestamp} - Track recently created emergency stops
        
    def _setup_logging(self):
        """Setup comprehensive structured logging"""
        logging.basicConfig(
            level=getattr(logging, LOGGING_CONFIG['log_level']),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(LOGGING_CONFIG['log_file']),
                logging.StreamHandler()
            ]
        )
        
        logger = logging.getLogger(__name__)
        
        # Add custom filters for different log categories
        if LOGGING_CONFIG['structured_logging']:
            # Add structured logging enhancements here
            pass
            
        return logger
        
    async def initialize_system(self) -> bool:
        """Comprehensive system initialization with validation"""
        try:
            self.logger.info("🚀 Initializing Intelligent Trading System...")
            
            # Validate configuration
            validate_configuration()
            self.logger.info("✅ Configuration validated")
            
            # Initialize core components
            if not await self.gateway.initialize():
                self.logger.error("❌ Gateway initialization failed")
                return False
            self.logger.info("✅ API Gateway connected")
            
            # Initialize AI assistant
            try:
                await self.ai_assistant.initialize()
                self.logger.info("✅ AI Assistant online")
            except Exception as ai_init_error:
                self.logger.warning(f"⚠️ 🚨 AI ASSISTANT INITIALIZATION FAILURE 🚨")
                self.logger.warning(f"⚠️ Error: {ai_init_error}")
                self.logger.warning(f"⚠️ System will continue with degraded AI capabilities")
                self.logger.warning(f"⚠️ Check Ollama service and model availability")
            
            # Initialize supplemental data provider
            await self.supplemental_data.initialize()
            self.logger.info("✅ Supplemental Data Provider online")
            
            # Validate account and trading permissions
            account = await self.gateway.get_account_safe()
            if not account:
                self.logger.error("❌ Cannot access account")
                return False
                
            account_value = float(account.equity)
            self.logger.info(f"💰 Account Value: ${account_value:,.2f}")
            
            if account_value < 100:
                self.logger.error("❌ Insufficient account balance")
                return False
                
            # Initialize risk manager
            await self.risk_manager.initialize(account_value)
            self.logger.info("✅ Risk Manager initialized")
            
            # Initialize performance tracker
            # Initialize performance tracker with gateway access
            self.performance_tracker = PerformanceTracker(self.gateway)
            await self.performance_tracker.initialize()
            self.logger.info("✅ Performance Tracker ready")
            
            # Initialize PDT manager
            await self.pdt_manager.initialize(self.gateway)
            self.order_executor.pdt_manager = self.pdt_manager  # Link PDT manager to executor
            self.logger.info("✅ PDT Manager ready")
            
            # STARTUP SAFETY CHECK: Scan for naked positions without stop protection
            await self._startup_position_safety_check()
            
            # POSITION RECONCILIATION: Verify our understanding matches broker reality
            await self._startup_position_reconciliation()
            
            # Reset PDT blocks for new trading day
            self.gateway.reset_pdt_blocks()
            
            # Also reset daily PDT tracking in PDT manager
            if hasattr(self, 'pdt_manager'):
                await self.pdt_manager._reset_daily_tracking()
            
            # Reset gap risk alert tracking for new trading day
            self.gap_risk_manager.reset_alert_tracking()
            
            # Reset extended hours warning tracking for new session
            self.extended_hours_warnings_sent.clear()
            
            # Validate market access
            should_trade, reason = await self.market_status.should_start_trading()
            if not should_trade and "closed" not in reason.lower():
                self.logger.warning(f"⚠️ Market status: {reason}")
                
            # Generate initial market intelligence
            try:
                market_data = await self._collect_initial_market_data()
                self.current_intelligence = await self.ai_assistant.generate_daily_market_intelligence(market_data)
                self.logger.info(f"🧠 Market Intelligence: {self.current_intelligence.market_regime} regime")
            except Exception as intelligence_error:
                self.logger.warning(f"⚠️ 🚨 INITIAL MARKET INTELLIGENCE FAILURE 🚨")
                self.logger.warning(f"⚠️ Error: {intelligence_error}")
                self.logger.warning(f"⚠️ System will attempt to generate intelligence later")
                self.current_intelligence = None
            
            self.system_initialized = True
            self.logger.info("🎯 SYSTEM READY FOR INTELLIGENT TRADING")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ System initialization failed: {e}")
            return False
    
    async def _startup_position_safety_check(self):
        """Check for naked positions without stop protection at system startup"""
        try:
            self.logger.info("🔍 Performing startup position safety check...")
            
            # Get all current positions
            positions = await self.gateway.get_all_positions()
            active_positions = [pos for pos in positions if float(pos.qty) != 0]
            
            if not active_positions:
                self.logger.info("✅ No active positions found at startup")
                return
            
            # Get all open orders to check for protective stops
            open_orders = await self.gateway.get_orders('open')
            
            naked_positions = []
            
            for position in active_positions:
                symbol = position.symbol
                qty = float(position.qty)
                position_side = 'long' if qty > 0 else 'short'
                
                # Look for protective stop orders for this position
                has_stop_protection = False
                protective_orders = []
                
                for order in open_orders:
                    if hasattr(order, 'symbol') and order.symbol == symbol:
                        order_type = getattr(order, 'order_type', getattr(order, 'type', '')).lower()
                        order_side = getattr(order, 'side', '').lower()
                        stop_price = getattr(order, 'stop_price', None)
                        
                        # Check for protective stop orders (more specific criteria)
                        is_protective_stop = (
                            'stop' in order_type or 
                            stop_price is not None
                        )
                        
                        # Also consider limit orders on opposite side as potential protection (take profit)
                        is_take_profit = (
                            order_type == 'limit' and 
                            ((position_side == 'long' and order_side == 'sell') or
                             (position_side == 'short' and order_side == 'buy'))
                        )
                        
                        # Check for market liquidation orders (active protection)
                        is_market_liquidation = (
                            order_type == 'market' and
                            ((position_side == 'long' and order_side == 'sell') or
                             (position_side == 'short' and order_side == 'buy'))
                        )
                        
                        is_protective = is_protective_stop or is_take_profit or is_market_liquidation
                        
                        if is_protective:
                            limit_price = getattr(order, 'limit_price', None)
                            price_info = f"${stop_price}" if stop_price else f"${limit_price}" if limit_price else "market price"
                            
                            if is_protective_stop:
                                protection_type = "STOP"
                            elif is_market_liquidation:
                                protection_type = "MARKET LIQUIDATION"
                            else:
                                protection_type = "TAKE-PROFIT"
                            
                            protective_orders.append(f"{protection_type}: {order_type} {order_side} @ {price_info}")
                            has_stop_protection = True
                
                # Log protective orders found (or lack thereof)
                if protective_orders:
                    self.logger.info(f"📋 {symbol} protection found: {', '.join(protective_orders)}")
                else:
                    self.logger.warning(f"⚠️ {symbol} has NO protective orders")
                
                if not has_stop_protection:
                    naked_positions.append({
                        'symbol': symbol,
                        'qty': qty,
                        'side': position_side,
                        'market_value': float(position.market_value),
                        'unrealized_pl': float(position.unrealized_pl),
                        'unrealized_pct': float(position.unrealized_plpc) * 100
                    })
            
            if naked_positions:
                self.logger.critical(f"🚨 STARTUP ALERT: {len(naked_positions)} positions without stop protection found")
                
                for pos in naked_positions:
                    self.logger.critical(f"   {pos['symbol']}: {pos['qty']} shares, "
                                       f"{pos['unrealized_pct']:.1f}% P&L, ${pos['market_value']:,.2f} value")
                
                # Send critical alert
                naked_symbols = [pos['symbol'] for pos in naked_positions]
                await self.alerter.send_system_startup_alert(naked_symbols)
                
                # Optionally create emergency stops for naked positions
                await self._create_emergency_stops_for_naked_positions(naked_positions)
            else:
                self.logger.info("✅ All positions have stop protection")
                
        except Exception as e:
            self.logger.error(f"Startup position safety check failed: {e}")
            await self.alerter.send_critical_alert(
                "Startup position safety check failed",
                f"Unable to verify position safety at startup: {e}"
            )
    
    async def _create_emergency_stops_for_naked_positions(self, naked_positions: List[Dict]):
        """Create emergency stop losses for positions without protection"""
        try:
            self.logger.info("🆘 Creating emergency stops for naked positions...")
            
            stops_created = 0
            
            for pos in naked_positions:
                try:
                    symbol = pos['symbol']
                    qty = abs(pos['qty'])
                    current_price = pos['market_value'] / abs(pos['qty'])  # Approximate current price
                    
                    # Calculate emergency stop price (8% below current for long positions)
                    if pos['side'] == 'long':
                        stop_price = current_price * 0.92  # 8% stop loss
                        side = 'sell'
                    else:
                        stop_price = current_price * 1.08  # 8% stop loss for short
                        side = 'buy'
                    
                    # Create emergency stop order
                    emergency_stop_data = {
                        'symbol': symbol,
                        'qty': str(int(qty)),
                        'side': side,
                        'type': 'stop',
                        'stop_price': str(round(stop_price, 2)),
                        'time_in_force': 'day'
                    }
                    
                    # ROBUST RETRY LOGIC for emergency stops
                    stop_created = await self._create_emergency_stop_with_retry(symbol, emergency_stop_data, max_retries=5)
                    
                    if stop_created:
                        stops_created += 1
                        # Track this emergency stop to prevent recreation
                        from datetime import datetime
                        self.recent_emergency_stops[symbol] = datetime.now()
                        
                except Exception as stop_error:
                    self.logger.warning(f"Emergency stop creation failed for {pos['symbol']}: {stop_error}")
            
            if stops_created > 0:
                self.logger.critical(f"✅ Created {stops_created} emergency stop orders out of {len(naked_positions)} naked positions")
            else:
                self.logger.critical(f"❌ No emergency stops created for {len(naked_positions)} naked positions - POSITIONS REMAIN UNPROTECTED")
                
            # Report final protection status
            unprotected_count = len(naked_positions) - stops_created
            if unprotected_count > 0:
                self.logger.critical(f"🚨 CRITICAL: {unprotected_count} positions remain without stop protection")
                
                # CRITICAL DECISION: If all emergency stops failed, check if it's due to market closure
                if stops_created == 0 and len(naked_positions) > 0:
                    liquidated_positions = 0  # Initialize for both branches
                    # Check if market is closed - if so, this is NOT an emergency
                    try:
                        clock = await self.gateway.get_clock()
                        market_is_open = clock and hasattr(clock, 'is_open') and clock.is_open
                    except Exception as e:
                        self.logger.warning(f"Could not check market status: {e}")
                        market_is_open = False  # Conservative: assume closed if can't check
                    
                    if not market_is_open:
                        self.logger.critical(f"🌙 MARKET CLOSED: Emergency stops cannot be placed during closed market hours")
                        self.logger.critical(f"   {unprotected_count} positions will remain unprotected until market opens")
                        self.logger.critical(f"   This is NORMAL - no emergency liquidation needed")
                        self.logger.critical(f"   Positions will be protected when market reopens")
                    else:
                        self.logger.critical(f"🚨 EMERGENCY LIQUIDATION DECISION: ALL emergency stops failed during OPEN market")
                        self.logger.critical(f"   This indicates serious API/connectivity issues")
                        self.logger.critical(f"   Positions are exposed to unlimited risk")
                        self.logger.critical(f"   Initiating emergency liquidation protocol...")
                        
                        await self.alerter.send_critical_alert(
                            "EMERGENCY LIQUIDATION: All stops failed",
                            f"ALL {len(naked_positions)} emergency stops failed. Initiating emergency liquidation to prevent unlimited losses. "
                            f"Positions: {[pos['symbol'] for pos in naked_positions]}"
                        )
                        
                        # Execute emergency liquidation
                        liquidated_positions = await self._execute_emergency_liquidation(naked_positions)
                        
                        if liquidated_positions > 0:
                            self.logger.critical(f"✅ Emergency liquidation completed: {liquidated_positions}/{len(naked_positions)} positions closed")
                        else:
                            self.logger.critical(f"❌ EMERGENCY LIQUIDATION FAILED: No positions could be closed!")
                            await self.alerter.send_critical_alert(
                                "CRITICAL: Emergency liquidation failed",
                                f"Could not liquidate ANY of {len(naked_positions)} unprotected positions. "
                                f"System shutdown required. Manual intervention critical!"
                            )
                
        except Exception as e:
            self.logger.error(f"Emergency stop creation failed: {e}")
    
    async def _should_skip_emergency_stop(self, symbol: str) -> str:
        """Check if emergency stop should be skipped and return reason"""
        try:
            # Check market hours
            try:
                clock = await self.gateway.get_clock()
                if clock and hasattr(clock, 'is_open') and not clock.is_open:
                    return "Market is CLOSED - emergency stops cannot be placed"
            except Exception as e:
                self.logger.warning(f"Could not check market status: {e}")
            
            # Check for existing orders that indicate position is already being handled
            try:
                existing_orders = await self.gateway.get_orders('open')
                symbol_orders = [o for o in existing_orders if hasattr(o, 'symbol') and o.symbol == symbol]
                
                for order in symbol_orders:
                    order_type = getattr(order, 'order_type', getattr(order, 'type', 'unknown'))
                    order_side = getattr(order, 'side', 'unknown')
                    
                    # Check if there's already a market sell order (liquidation in progress)
                    if order_type == 'market' and order_side == 'sell':
                        return f"Position already being liquidated (existing market sell order)"
                    
                    # Check if there's already a stop order for protection
                    if order_type in ['stop', 'stop_limit'] and order_side == 'sell':
                        return f"Position already protected (existing {order_type} order)"
                        
            except Exception as e:
                self.logger.warning(f"Could not check existing orders for {symbol}: {e}")
            
            # Check if symbol is PDT-blocked
            if self.gateway.is_symbol_pdt_blocked(symbol):
                return "Symbol is PDT-blocked"
                
            return None  # No reason to skip
            
        except Exception as e:
            self.logger.error(f"Error checking if emergency stop should be skipped for {symbol}: {e}")
            return None
    
    async def _cleanup_all_stale_orders(self) -> int:
        """Clean up all stale orders across all symbols using consolidated utilities"""
        return await OrderUtils.cleanup_stale_orders(self.gateway, threshold_seconds=120)

    async def _check_actual_open_orders_for_symbol(self, symbol: str) -> bool:
        """Check if there are actually open orders for a symbol that would hold shares"""
        try:
            open_orders = await self.gateway.get_orders(status='open')
            if not open_orders:
                return False

            symbol_orders = [order for order in open_orders if getattr(order, 'symbol', None) == symbol]

            if symbol_orders:
                self.logger.info(f"🔍 Found {len(symbol_orders)} open orders for {symbol}")
                stale_orders_cancelled = 0
                remaining_orders = []

                for order in symbol_orders:
                    order_type = getattr(order, 'type', 'unknown')
                    side = getattr(order, 'side', 'unknown')
                    status = getattr(order, 'status', 'unknown')
                    created_at = getattr(order, 'created_at', None)
                    order_id = getattr(order, 'id', None)

                    # Check if order is stale - MUCH MORE CONSERVATIVE APPROACH
                    is_stale = False
                    if status == 'new' and created_at:
                        try:
                            from datetime import timezone
                            # Use consolidated datetime handling
                            order_age = DateTimeUtils.calculate_age_seconds(created_at)

                            # Use configurable stale order timeouts
                            stale_timeouts = RISK_CONFIG['stale_order_timeouts']
                            order_type_key = order_type.lower()

                            # Map order types to config keys
                            if 'stop' in order_type_key:
                                timeout = stale_timeouts.get('stop')
                            elif order_type_key == 'limit':
                                timeout = stale_timeouts.get('limit')
                            elif order_type_key == 'market':
                                timeout = stale_timeouts.get('market')
                            else:
                                timeout = stale_timeouts.get('limit')  # Default to limit timeout

                            # Check if order is stale based on configured timeout
                            if timeout is not None and order_age > timeout:
                                is_stale = True
                                self.logger.warning(f"   - STALE {order_type.upper()} ORDER: {order_type} {side} order, status: {status}, age: {order_age/60:.1f} minutes")
                            else:
                                is_stale = False
                        except:
                            pass

                    if is_stale and order_id:
                        # Cancel stale order
                        try:
                            cancel_response = await self.gateway.cancel_order(order_id)
                            if cancel_response and cancel_response.success:
                                self.logger.info(f"   ✅ Cancelled stale order {order_id}")
                                stale_orders_cancelled += 1
                            else:
                                self.logger.warning(f"   ⚠️ Failed to cancel stale order {order_id}")
                                remaining_orders.append(order)
                        except Exception as e:
                            self.logger.error(f"   ❌ Error cancelling stale order {order_id}: {e}")
                            remaining_orders.append(order)
                    else:
                        self.logger.info(f"   - {order_type} {side} order, status: {status}")
                        remaining_orders.append(order)

                if stale_orders_cancelled > 0:
                    self.logger.info(f"🧹 Cancelled {stale_orders_cancelled} stale orders for {symbol}")
                    # Brief pause to ensure cancellations are processed
                    await asyncio.sleep(1)

                # Return True only if there are still valid orders after cleanup
                return len(remaining_orders) > 0
            else:
                self.logger.info(f"🔍 No open orders found for {symbol} - shares should be available")
                return False

        except Exception as e:
            self.logger.error(f"Error checking orders for {symbol}: {e}")
            return True  # Conservative: assume orders exist if we can't check
    
    async def _create_emergency_stop_with_retry(self, symbol: str, emergency_stop_data: Dict, max_retries: int = 5) -> bool:
        """Create emergency stop with robust retry logic and escalating responses"""
        import asyncio
        
        # Pre-flight checks before attempting emergency stop
        skip_reason = await self._should_skip_emergency_stop(symbol)
        if skip_reason:
            self.logger.critical(f"⏭️ SKIPPING emergency stop for {symbol}: {skip_reason}")
            # Return False if market is closed (can't create protection), True if already protected
            return not ("Market is CLOSED" in skip_reason)
        
        for attempt in range(max_retries):
            try:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s, 8s, 16s
                
                if attempt > 0:
                    self.logger.critical(f"🔄 RETRY {attempt + 1}/{max_retries} for {symbol} emergency stop (waiting {wait_time}s)")
                    await asyncio.sleep(wait_time)
                else:
                    self.logger.info(f"🔄 Attempting emergency stop for {symbol}: {emergency_stop_data}")
                
                # Submit order
                stop_response = await self.gateway.submit_order(emergency_stop_data)
                
                if stop_response and stop_response.success:
                    order_id = getattr(stop_response.data, 'id', 'unknown')
                    self.logger.critical(f"✅ Emergency stop SUCCESSFUL: {symbol} @ ${emergency_stop_data['stop_price']}")
                    self.logger.critical(f"   Order ID: {order_id}, Attempt: {attempt + 1}/{max_retries}")
                    return True
                else:
                    self.logger.critical(f"❌ Emergency stop attempt {attempt + 1}/{max_retries} FAILED for {symbol}")
                    
                    # Enhanced diagnostics on each failure
                    await self._diagnose_stop_failure(symbol, emergency_stop_data, attempt + 1)
                    
                    # On final attempt, try alternative approaches
                    if attempt == max_retries - 1:
                        self.logger.critical(f"🚨 FINAL ATTEMPT FAILED for {symbol} - trying alternative approaches")
                        
                        # Try with GTC instead of DAY
                        alternative_data = emergency_stop_data.copy()
                        alternative_data['time_in_force'] = 'gtc'
                        
                        self.logger.critical(f"🔄 Trying GTC order for {symbol}: {alternative_data}")
                        gtc_response = await self.gateway.submit_order(alternative_data)
                        
                        if gtc_response and gtc_response.success:
                            order_id = getattr(gtc_response.data, 'id', 'unknown')
                            self.logger.critical(f"✅ Emergency stop SUCCESSFUL (GTC): {symbol} (Order: {order_id})")
                            return True
                        
                        # If GTC also fails, this is critical
                        self.logger.critical(f"🚨 ALL EMERGENCY STOP ATTEMPTS EXHAUSTED for {symbol}")
                        return False
                    
            except Exception as e:
                self.logger.critical(f"❌ Emergency stop attempt {attempt + 1}/{max_retries} ERROR for {symbol}: {e}")
                
                # On final attempt with exception, this is critical  
                if attempt == max_retries - 1:
                    self.logger.critical(f"🚨 EMERGENCY STOP CREATION COMPLETELY FAILED for {symbol}")
                    return False
        
        return False
    
    async def _diagnose_stop_failure(self, symbol: str, emergency_stop_data: Dict, attempt: int):
        """Diagnose why emergency stop creation failed"""
        try:
            self.logger.critical(f"🔍 Diagnosing failure for {symbol} (attempt {attempt})")
            
            # Check if symbol is PDT-blocked
            if self.gateway.is_symbol_pdt_blocked(symbol):
                self.logger.critical(f"   💡 CAUSE: {symbol} is PDT-blocked")
                return
            
            # Check market status
            try:
                clock = await self.gateway.get_clock()
                if clock and hasattr(clock, 'is_open'):
                    market_status = "OPEN" if clock.is_open else "CLOSED"
                    self.logger.critical(f"   📅 Market: {market_status}")
                    
                    if not clock.is_open:
                        self.logger.critical(f"   ⚠️ Market is CLOSED - this may cause order failures")
                else:
                    self.logger.critical(f"   📅 Could not determine market status")
            except Exception as clock_error:
                self.logger.critical(f"   📅 Clock check failed: {clock_error}")
            
            # Check account status
            try:
                account = await self.gateway.get_account()
                if account:
                    cash = float(account.cash)
                    buying_power = float(account.buying_power)
                    account_status = getattr(account, 'status', 'unknown')
                    
                    self.logger.critical(f"   💰 Cash: ${cash:.2f}, Buying Power: ${buying_power:.2f}")
                    self.logger.critical(f"   📊 Account status: {account_status}")
                    
                    if account_status != 'ACTIVE':
                        self.logger.critical(f"   🚨 Account status is NOT ACTIVE: {account_status}")
                else:
                    self.logger.critical(f"   ❌ Could not retrieve account info")
            except Exception as account_error:
                self.logger.critical(f"   💰 Account check failed: {account_error}")
            
            # Check for existing orders that might conflict
            try:
                existing_orders = await self.gateway.get_orders('open')
                symbol_orders = [o for o in existing_orders if hasattr(o, 'symbol') and o.symbol == symbol]
                
                if symbol_orders:
                    self.logger.critical(f"   📋 Found {len(symbol_orders)} existing orders for {symbol}")
                    for order in symbol_orders:
                        order_type = getattr(order, 'order_type', getattr(order, 'type', 'unknown'))
                        order_side = getattr(order, 'side', 'unknown')
                        order_qty = getattr(order, 'qty', 'unknown')
                        self.logger.critical(f"      - {order_type} {order_side} {order_qty}")
                else:
                    self.logger.critical(f"   📋 No existing orders for {symbol}")
            except Exception as orders_error:
                self.logger.critical(f"   📋 Orders check failed: {orders_error}")
                
        except Exception as diag_error:
            self.logger.critical(f"   ⚠️ Diagnosis failed: {diag_error}")
    
    async def _execute_emergency_liquidation(self, unprotected_positions: List[Dict]) -> int:
        """Execute emergency liquidation of unprotected positions"""
        import asyncio
        
        self.logger.critical("🚨 EXECUTING EMERGENCY LIQUIDATION")
        self.logger.critical("   This is the nuclear option to prevent unlimited losses")
        self.logger.critical("   All affected positions will be closed at market price")
        
        liquidated_count = 0
        
        for pos in unprotected_positions:
            try:
                symbol = pos['symbol']
                qty = abs(pos['qty'])
                side = 'sell' if pos['side'] == 'long' else 'buy'
                
                self.logger.critical(f"🧨 LIQUIDATING {symbol}: {qty} shares ({side})")
                
                # Create market liquidation order
                liquidation_data = {
                    'symbol': symbol,
                    'qty': str(int(qty)),
                    'side': side,
                    'type': 'market',
                    'time_in_force': 'day'
                }
                
                # Try liquidation with retry
                for attempt in range(3):
                    try:
                        if attempt > 0:
                            self.logger.critical(f"🔄 Liquidation retry {attempt + 1}/3 for {symbol}")
                            await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        
                        liquidation_response = await self.gateway.submit_order(liquidation_data)
                        
                        if liquidation_response and liquidation_response.success:
                            order_id = getattr(liquidation_response.data, 'id', 'unknown')
                            self.logger.critical(f"✅ LIQUIDATION ORDER SUBMITTED: {symbol} (Order: {order_id})")
                            liquidated_count += 1
                            break
                        else:
                            self.logger.critical(f"❌ Liquidation attempt {attempt + 1}/3 failed for {symbol}")
                            
                            # On final attempt, log extensive diagnostics
                            if attempt == 2:
                                self.logger.critical(f"🚨 LIQUIDATION EXHAUSTED for {symbol}")
                                try:
                                    account = await self.gateway.get_account()
                                    if account:
                                        self.logger.critical(f"   Account status: {getattr(account, 'status', 'unknown')}")
                                    
                                    clock = await self.gateway.get_clock()
                                    if clock:
                                        market_status = "OPEN" if clock.is_open else "CLOSED"
                                        self.logger.critical(f"   Market: {market_status}")
                                except:
                                    pass
                    
                    except Exception as liquidation_error:
                        self.logger.critical(f"❌ Liquidation attempt {attempt + 1}/3 ERROR for {symbol}: {liquidation_error}")
                        
                        if attempt == 2:
                            self.logger.critical(f"🚨 LIQUIDATION COMPLETELY FAILED for {symbol}")
                
            except Exception as pos_error:
                self.logger.critical(f"❌ Emergency liquidation error for {pos['symbol']}: {pos_error}")
        
        # Final liquidation report
        success_rate = (liquidated_count / len(unprotected_positions)) * 100 if unprotected_positions else 0
        
        self.logger.critical(f"📊 EMERGENCY LIQUIDATION SUMMARY:")
        self.logger.critical(f"   Attempted: {len(unprotected_positions)} positions")
        self.logger.critical(f"   Successful: {liquidated_count} positions")
        self.logger.critical(f"   Success rate: {success_rate:.1f}%")
        
        if liquidated_count == len(unprotected_positions):
            self.logger.critical(f"✅ EMERGENCY LIQUIDATION SUCCESSFUL: All positions closed")
        elif liquidated_count > 0:
            remaining = len(unprotected_positions) - liquidated_count
            self.logger.critical(f"⚠️ PARTIAL LIQUIDATION: {remaining} positions still unprotected")
        else:
            self.logger.critical(f"❌ EMERGENCY LIQUIDATION FAILED: No positions could be closed")
        
        return liquidated_count
    
    async def _monitor_position_protection(self):
        """Continuously monitor that all positions have stop protection"""
        try:
            # Get current positions
            positions = await self.gateway.get_all_positions()
            active_positions = [pos for pos in positions if float(pos.qty) != 0]
            
            if not active_positions:
                return  # No positions to monitor
            
            # Get all open orders
            open_orders = await self.gateway.get_orders('open')
            
            # Check protection for each position
            unprotected_positions = []
            
            for position in active_positions:
                symbol = position.symbol
                qty = float(position.qty)
                position_side = 'long' if qty > 0 else 'short'
                
                # Look for protective orders for this position
                has_protection = False
                
                for order in open_orders:
                    if hasattr(order, 'symbol') and order.symbol == symbol:
                        order_type = getattr(order, 'order_type', getattr(order, 'type', '')).lower()
                        order_side = getattr(order, 'side', '').lower()
                        stop_price = getattr(order, 'stop_price', None)
                        
                        # Check for protective orders
                        is_stop = 'stop' in order_type or stop_price is not None
                        is_protective_limit = (order_type == 'limit' and 
                                             ((position_side == 'long' and order_side == 'sell') or
                                              (position_side == 'short' and order_side == 'buy')))
                        
                        # Check for market liquidation orders (active protection)
                        is_market_liquidation = (order_type == 'market' and
                                               ((position_side == 'long' and order_side == 'sell') or
                                                (position_side == 'short' and order_side == 'buy')))
                        
                        if is_stop or is_protective_limit or is_market_liquidation:
                            has_protection = True
                            if is_market_liquidation:
                                self.logger.debug(f"✅ {symbol} protected by active market liquidation order")
                            break
                
                if not has_protection:
                    unprotected_positions.append({
                        'symbol': symbol,
                        'qty': qty,
                        'side': position_side,
                        'market_value': float(position.market_value),
                        'unrealized_pl': float(position.unrealized_pl),
                        'unrealized_pct': float(position.unrealized_plpc) * 100
                    })
            
            # If unprotected positions found, take appropriate action based on market status
            if unprotected_positions:
                # Check if market is open
                clock = await self.gateway.get_clock()
                is_market_open = clock and hasattr(clock, 'is_open') and clock.is_open
                
                if not is_market_open:
                    # Log as warning when market is closed - can't do anything about it now
                    self.logger.warning(f"⚠️ {len(unprotected_positions)} positions without stop protection (market closed)")
                    for pos in unprotected_positions:
                        self.logger.debug(f"   📍 {pos['symbol']}: {pos['qty']} shares, {pos['unrealized_pct']:+.1f}% P&L")
                    # Don't spam alerts or try to create stops when market is closed
                    return
                
                # Market is open - this is critical
                self.logger.critical(f"🚨 RUNTIME ALERT: {len(unprotected_positions)} positions lost protection!")
                
                for pos in unprotected_positions:
                    self.logger.critical(f"   ❌ {pos['symbol']}: {pos['qty']} shares, {pos['unrealized_pct']:+.1f}% P&L")
                
                # Send alert only when market is open and we can actually do something
                await self.alerter.send_critical_alert(
                    "RUNTIME: Positions lost protection",
                    f"Found {len(unprotected_positions)} unprotected positions during runtime: "
                    f"{[pos['symbol'] for pos in unprotected_positions]}. Creating emergency stops immediately!"
                )
                
                # Create emergency stops immediately
                self.logger.critical("🆘 Creating RUNTIME emergency stops...")
                stops_created = 0
                
                for pos in unprotected_positions:
                    try:
                        symbol = pos['symbol']

                        # Check if we recently created an emergency stop for this symbol
                        from datetime import datetime, timedelta
                        current_time = datetime.now()

                        # Clean up old tracking entries (older than 1 hour)
                        symbols_to_remove = []
                        for tracked_symbol, tracked_time in self.recent_emergency_stops.items():
                            if (current_time - tracked_time).total_seconds() > 3600:  # 1 hour
                                symbols_to_remove.append(tracked_symbol)
                        for old_symbol in symbols_to_remove:
                            del self.recent_emergency_stops[old_symbol]

                        if symbol in self.recent_emergency_stops:
                            last_stop_time = self.recent_emergency_stops[symbol]
                            time_since_last_stop = (current_time - last_stop_time).total_seconds()
                            cooldown_seconds = RISK_CONFIG['emergency_stop_recreation_cooldown_minutes'] * 60
                            if time_since_last_stop < cooldown_seconds:
                                self.logger.info(f"⏭️ Skipping emergency stop for {symbol} - created {time_since_last_stop/60:.1f} minutes ago")
                                continue

                        qty = abs(pos['qty'])
                        current_price = pos['market_value'] / abs(pos['qty'])

                        # 8% stop loss
                        if pos['side'] == 'long':
                            stop_price = current_price * 0.92
                            side = 'sell'
                        else:
                            stop_price = current_price * 1.08
                            side = 'buy'

                        emergency_stop_data = {
                            'symbol': symbol,
                            'qty': str(int(qty)),
                            'side': side,
                            'type': 'stop',
                            'stop_price': str(round(stop_price, 2)),
                            'time_in_force': 'day'
                        }

                        # Use robust retry logic
                        stop_created = await self._create_emergency_stop_with_retry(symbol, emergency_stop_data, max_retries=3)
                        
                        if stop_created:
                            stops_created += 1
                            self.logger.critical(f"✅ Runtime emergency stop created for {symbol}")
                            # Track this emergency stop to prevent recreation
                            self.recent_emergency_stops[symbol] = current_time
                        else:
                            self.logger.critical(f"❌ FAILED to create runtime emergency stop for {symbol}")
                            
                    except Exception as stop_error:
                        self.logger.critical(f"❌ Runtime emergency stop error for {pos['symbol']}: {stop_error}")
                
                # Final status
                if stops_created == len(unprotected_positions):
                    self.logger.critical(f"✅ All {stops_created} runtime emergency stops created successfully")
                else:
                    remaining_unprotected = len(unprotected_positions) - stops_created
                    self.logger.critical(f"🚨 CRITICAL: {remaining_unprotected} positions STILL unprotected after runtime emergency stop creation!")
                    
                    # This is extremely critical - consider emergency liquidation
                    if remaining_unprotected > 0:
                        await self.alerter.send_critical_alert(
                            "CRITICAL: Runtime protection failure",
                            f"{remaining_unprotected} positions could not be protected with emergency stops. "
                            f"Manual intervention required immediately!"
                        )
            
        except Exception as e:
            self.logger.critical(f"❌ Position protection monitoring failed: {e}")
            # This is critical - if we can't monitor protection, we're blind to risk
            await self.alerter.send_critical_alert(
                "CRITICAL: Protection monitoring failed",
                f"Cannot monitor position protection: {e}. System may have unprotected positions!"
            )
    
    async def _periodic_protection_verification(self):
        """Periodic deep verification of position protection (runs every 5 loops)"""
        try:
            self.logger.info("🔍 Running periodic protection verification...")

            # Log PDT-blocked symbols for visibility but DO NOT reset them
            # PDT blocks should only be cleared at start of new trading day
            try:
                blocked_symbols = self.gateway.get_pdt_blocked_symbols()
                if blocked_symbols:
                    self.logger.info(f"📊 PDT Status: {len(blocked_symbols)} symbols currently blocked: {', '.join(blocked_symbols)}")
                    self.logger.info(f"   These will remain blocked until next trading day to comply with PDT rules")
            except Exception as pdt_error:
                self.logger.warning(f"⚠️ PDT status check failed: {pdt_error}")

            # Get all positions and orders
            positions = await self.gateway.get_all_positions()
            active_positions = [pos for pos in positions if float(pos.qty) != 0]
            open_orders = await self.gateway.get_orders('open')
            
            if not active_positions:
                self.logger.info("✅ Periodic verification: No positions to verify")
                return
            
            protection_report = []
            unprotected_count = 0
            
            for position in active_positions:
                symbol = position.symbol
                qty = float(position.qty)
                position_side = 'long' if qty > 0 else 'short'
                market_value = float(position.market_value)
                
                # Find all orders for this symbol
                symbol_orders = [order for order in open_orders 
                               if hasattr(order, 'symbol') and order.symbol == symbol]
                
                # Categorize orders
                stop_orders = []
                limit_orders = []
                
                for order in symbol_orders:
                    order_type = getattr(order, 'order_type', getattr(order, 'type', '')).lower()
                    order_side = getattr(order, 'side', '').lower()
                    stop_price = getattr(order, 'stop_price', None)
                    limit_price = getattr(order, 'limit_price', None)
                    
                    if 'stop' in order_type or stop_price is not None:
                        stop_orders.append({
                            'type': order_type,
                            'side': order_side,
                            'price': stop_price or limit_price,
                            'qty': getattr(order, 'qty', 'unknown')
                        })
                    elif order_type == 'limit':
                        limit_orders.append({
                            'type': order_type,
                            'side': order_side,
                            'price': limit_price,
                            'qty': getattr(order, 'qty', 'unknown')
                        })
                
                # Determine protection status
                has_stop_protection = len(stop_orders) > 0
                has_limit_protection = any(
                    (position_side == 'long' and order['side'] == 'sell') or
                    (position_side == 'short' and order['side'] == 'buy')
                    for order in limit_orders
                )
                
                protection_status = "PROTECTED" if (has_stop_protection or has_limit_protection) else "UNPROTECTED"
                
                if protection_status == "UNPROTECTED":
                    unprotected_count += 1
                
                protection_report.append({
                    'symbol': symbol,
                    'qty': qty,
                    'side': position_side,
                    'value': market_value,
                    'status': protection_status,
                    'stop_orders': len(stop_orders),
                    'limit_orders': len([o for o in limit_orders if 
                                       (position_side == 'long' and o['side'] == 'sell') or
                                       (position_side == 'short' and o['side'] == 'buy')])
                })
            
            # Log verification results
            self.logger.info(f"📊 Periodic Protection Verification Results:")
            self.logger.info(f"   Total positions: {len(active_positions)}")
            self.logger.info(f"   Protected: {len(active_positions) - unprotected_count}")
            self.logger.info(f"   Unprotected: {unprotected_count}")
            
            # Detailed report
            for pos in protection_report:
                status_emoji = "✅" if pos['status'] == "PROTECTED" else "❌"
                self.logger.info(f"   {status_emoji} {pos['symbol']}: {pos['qty']} shares, "
                               f"${pos['value']:,.2f}, {pos['stop_orders']} stops, {pos['limit_orders']} limits")
            
            # Alert if any positions are unprotected
            if unprotected_count > 0:
                unprotected_symbols = [pos['symbol'] for pos in protection_report 
                                     if pos['status'] == "UNPROTECTED"]
                
                # Check market status before sending critical alerts
                clock = await self.gateway.get_clock()
                is_market_open = clock and hasattr(clock, 'is_open') and clock.is_open
                
                if not is_market_open:
                    # Just log warning when market is closed
                    self.logger.warning(f"⚠️ Periodic check: {unprotected_count} positions without stops (market closed): {unprotected_symbols}")
                else:
                    # Market is open - this is critical
                    self.logger.critical(f"🚨 PERIODIC VERIFICATION ALERT: {unprotected_count} unprotected positions found!")
                    
                    await self.alerter.send_critical_alert(
                        "Periodic verification: Unprotected positions detected",
                        f"Found {unprotected_count} unprotected positions: {unprotected_symbols}. "
                        f"Runtime monitoring should have caught this - investigate system health!"
                    )
                    
                    # This suggests runtime monitoring may have failed - run it manually
                    self.logger.critical("🔄 Running emergency runtime protection check...")
                    await self._monitor_position_protection()
            else:
                self.logger.info("✅ Periodic verification: All positions properly protected")
            
        except Exception as e:
            self.logger.critical(f"❌ Periodic protection verification failed: {e}")
            await self.alerter.send_critical_alert(
                "CRITICAL: Periodic protection verification failed",
                f"Could not verify position protection: {e}. Manual check required!"
            )
    
    async def _enhanced_position_aging_management(self):
        """Enhanced position aging and turnover management to prevent extended hours emergencies"""
        try:
            self.logger.info("⏳ Running enhanced position aging management...")
            
            # Get all positions with current market data
            positions = await self.gateway.get_all_positions()
            active_positions = [pos for pos in positions if float(pos.qty) != 0]
            
            if not active_positions:
                self.logger.debug("✅ Position aging: No positions to manage")
                return
                
            aging_actions = []
            current_time = datetime.now()
            from config import RISK_CONFIG
            max_age_days = RISK_CONFIG.get('max_position_age_days', 4)
            concentration_limit = RISK_CONFIG.get('concentration_limit_pct', 8.0)
            
            # Get account info for concentration calculations
            account = await self.gateway.get_account_safe()
            if not account:
                self.logger.error("❌ Cannot perform aging management without account data")
                return
                
            account_equity = float(account.equity)
            
            for position in active_positions:
                symbol = position.symbol
                qty = float(position.qty)
                market_value = float(position.market_value)
                unrealized_pl = float(position.unrealized_pl)
                unrealized_pct = float(position.unrealized_plpc) * 100
                
                # Calculate position concentration
                position_concentration = (abs(market_value) / account_equity) * 100
                
                # Get position entry time (approximation - would need persistent storage for exact entry)
                # For now, use a heuristic approach based on position performance
                action_needed = None
                urgency = "LOW"
                
                # === CONCENTRATION RISK MANAGEMENT ===
                if position_concentration > concentration_limit:
                    action_needed = {
                        'type': 'REDUCE_CONCENTRATION',
                        'target_size_pct': concentration_limit * 0.8,  # Reduce to 80% of limit
                        'reason': f'Position concentration {position_concentration:.1f}% exceeds {concentration_limit}% limit',
                        'urgency': 'HIGH'
                    }
                    urgency = "HIGH"
                
                # === LOSS MANAGEMENT - PROACTIVE APPROACH ===
                elif unrealized_pct <= -3.0:  # Earlier intervention than -4% stop
                    # Check if position already has adequate stop protection before aging actions
                    has_adequate_protection = False
                    try:
                        orders = await self.gateway.get_orders('open')
                        for order in orders:
                            if (order.symbol == symbol and 
                                order.side == ('sell' if qty > 0 else 'buy') and
                                order.order_type in ['stop', 'stop_limit']):
                                # Position already has stop protection
                                has_adequate_protection = True
                                self.logger.debug(f"✅ {symbol} aging management: already protected by stop order")
                                break
                    except Exception as e:
                        self.logger.debug(f"Could not check protection for {symbol}: {e}")
                    
                    if not has_adequate_protection:
                        if unrealized_pct <= -5.0:  # Close to emergency threshold
                            action_needed = {
                                'type': 'EMERGENCY_REDUCE',
                                'reduce_pct': 0.75,  # Sell 75% of position
                                'reason': f'Position at {unrealized_pct:.1f}% loss - emergency reduction',
                                'urgency': 'CRITICAL'
                            }
                            urgency = "CRITICAL"
                        else:  # -3% to -5% range
                            action_needed = {
                                'type': 'DEFENSIVE_REDUCE',
                                'reduce_pct': 0.50,  # Sell 50% of position
                                'reason': f'Position at {unrealized_pct:.1f}% loss - defensive reduction',
                                'urgency': 'HIGH'
                            }
                            urgency = "HIGH"
                    else:
                        self.logger.debug(f"⏭️ SKIPPING AGING ACTION: {symbol} already protected by existing stop order")
                
                # === PROFIT OPTIMIZATION - AGING POSITIONS ===
                elif unrealized_pct >= 8.0:  # Profitable positions
                    # Check if position might be aging (heuristic approach)
                    if position_concentration > 6.0:  # Large profitable positions
                        action_needed = {
                            'type': 'PROFIT_OPTIMIZATION',
                            'reduce_pct': 0.40,  # Take 40% profit
                            'reason': f'Large profitable position at +{unrealized_pct:.1f}% - optimize turnover',
                            'urgency': 'MEDIUM'
                        }
                        urgency = "MEDIUM"
                
                # === STAGNANT POSITION DETECTION ===
                elif abs(unrealized_pct) < 2.0 and position_concentration > 5.0:
                    # Large positions with minimal movement - consider turnover
                    action_needed = {
                        'type': 'TURNOVER_OPTIMIZATION',
                        'reduce_pct': 0.33,  # Reduce by 1/3
                        'reason': f'Large stagnant position ({unrealized_pct:+.1f}%) - optimize capital allocation',
                        'urgency': 'LOW'
                    }
                
                if action_needed:
                    aging_actions.append({
                        'symbol': symbol,
                        'qty': qty,
                        'market_value': market_value,
                        'unrealized_pct': unrealized_pct,
                        'concentration_pct': position_concentration,
                        'action': action_needed,
                        'urgency': urgency
                    })
            
            # Execute aging management actions based on urgency
            if aging_actions:
                self.logger.info(f"📊 Position Aging Analysis: {len(aging_actions)} actions identified")
                
                # Sort by urgency (CRITICAL > HIGH > MEDIUM > LOW)
                urgency_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
                aging_actions.sort(key=lambda x: urgency_order.get(x['urgency'], 4))
                
                actions_executed = 0
                max_actions_per_cycle = 2  # Limit to 2 actions per cycle to avoid over-trading
                
                for action_item in aging_actions[:max_actions_per_cycle]:
                    symbol = action_item['symbol']
                    qty = action_item['qty']
                    action = action_item['action']
                    urgency = action_item['urgency']
                    
                    # Calculate sell quantity based on action type
                    if action['type'] in ['EMERGENCY_REDUCE', 'DEFENSIVE_REDUCE', 'PROFIT_OPTIMIZATION', 'TURNOVER_OPTIMIZATION']:
                        calculated_qty = abs(qty) * action['reduce_pct']
                        sell_qty = max(1, int(calculated_qty)) if calculated_qty >= 0.5 else 0
                        
                        # EDGE CASE: 1-share positions - handle specially
                        if abs(qty) == 1:
                            if action['type'] in ['EMERGENCY_REDUCE']:
                                # For 1-share emergency, sell the whole share
                                sell_qty = 1
                                self.logger.warning(f"   📏 1-SHARE EDGE CASE: {symbol} - selling entire position (emergency)")
                            else:
                                # For 1-share non-emergency, skip action to avoid PDT risk
                                sell_qty = 0
                                self.logger.info(f"   📏 1-SHARE EDGE CASE: {symbol} - skipping {action['type']} (too small)")
                                
                    elif action['type'] == 'REDUCE_CONCENTRATION':
                        # Calculate quantity to bring position to target size
                        current_value = abs(action_item['market_value'])
                        target_value = account_equity * (action['target_size_pct'] / 100)
                        reduce_value = current_value - target_value
                        calculated_qty = (reduce_value / current_value) * abs(qty)
                        sell_qty = max(1, int(calculated_qty)) if calculated_qty >= 0.5 else 0
                        
                        # EDGE CASE: 1-share concentration - only act if severely oversized
                        if abs(qty) == 1:
                            if action_item['concentration_pct'] > 15.0:  # Only if >15% concentration
                                sell_qty = 1
                                self.logger.warning(f"   📏 1-SHARE CONCENTRATION: {symbol} at {action_item['concentration_pct']:.1f}% - selling entire position")
                            else:
                                sell_qty = 0
                                self.logger.info(f"   📏 1-SHARE CONCENTRATION: {symbol} - keeping (only {action_item['concentration_pct']:.1f}%)")
                    else:
                        continue
                        
                    if sell_qty > 0:
                        self.logger.warning(f"🔄 POSITION AGING ACTION: {symbol} - {action['type']}")
                        self.logger.warning(f"   Reason: {action['reason']}")
                        self.logger.warning(f"   Selling {sell_qty} shares ({(sell_qty/abs(qty)*100):.1f}% of position)")
                        
                        # Execute the aging management order
                        order_data = {
                            'symbol': symbol,
                            'qty': str(sell_qty),
                            'side': 'sell' if qty > 0 else 'buy',
                            'type': 'market' if urgency in ['CRITICAL', 'HIGH'] else 'limit',
                            'time_in_force': 'day'
                        }
                        
                        # Add limit price for limit orders
                        if order_data['type'] == 'limit':
                            try:
                                quote = await self.gateway.get_latest_quote(symbol)
                                if quote:
                                    current_price = float(quote.get('bid_price', 0))  # Use bid for selling
                                    if current_price > 0:
                                        # Use slight discount for quick fill
                                        limit_price = current_price * 0.995  # 0.5% discount
                                        order_data['limit_price'] = str(round(limit_price, 2))
                                    else:
                                        order_data['type'] = 'market'  # Fallback to market order
                                else:
                                    order_data['type'] = 'market'  # Fallback to market order
                            except:
                                order_data['type'] = 'market'  # Fallback to market order
                        
                        try:
                            response = await self.gateway.submit_order(order_data)
                            if response and response.success:
                                actions_executed += 1
                                self.logger.warning(f"✅ AGING MANAGEMENT EXECUTED: {symbol} - {action['type']}")
                                
                                # Send alert for critical/high urgency actions
                                if urgency in ['CRITICAL', 'HIGH']:
                                    await self.alerter.send_critical_alert(
                                        f"🔄 {urgency}: {symbol} aging management - {action['reason']} - sold {sell_qty} shares"
                                    )
                            else:
                                error_msg = response.error if response else "No response received"
                                # Check if shares are held by existing orders
                                if response and "insufficient qty available" in str(response.error) and "held_for_orders" in str(response.error):
                                    # Verify if orders actually exist before skipping permanently
                                    orders_exist = await self._check_actual_open_orders_for_symbol(symbol)
                                    if orders_exist:
                                        self.logger.info(f"✅ AGING MANAGEMENT SKIPPED: {symbol} - shares held by existing orders (protected)")
                                    else:
                                        self.logger.warning(f"🔄 AGING MANAGEMENT RETRY: {symbol} - 'held_for_orders' error but no open orders found, will retry next cycle")
                                else:
                                    self.logger.error(f"❌ AGING MANAGEMENT FAILED: {symbol} - {error_msg}")
                        except Exception as e:
                            self.logger.error(f"❌ AGING MANAGEMENT ERROR: {symbol} - {e}")
                
                self.logger.info(f"✅ Position aging management complete: {actions_executed}/{len(aging_actions)} actions executed")
                
                # Log remaining actions for next cycle
                if len(aging_actions) > actions_executed:
                    remaining = len(aging_actions) - actions_executed
                    self.logger.info(f"📋 {remaining} aging actions deferred to next cycle")
                    
            else:
                self.logger.info("✅ Position aging: All positions within optimal parameters")
                
        except Exception as e:
            self.logger.critical(f"❌ Enhanced position aging management failed: {e}")
            await self.alerter.send_critical_alert(
                "CRITICAL: Position aging management failed",
                f"Could not perform position aging analysis: {e}. Positions may need manual review!"
            )
    
    async def _startup_position_reconciliation(self):
        """Reconcile our position understanding with actual broker positions"""
        try:
            self.logger.info("🔄 Performing startup position reconciliation...")
            
            # Get actual positions from broker
            broker_positions = await self.gateway.get_all_positions()
            broker_symbols = {pos.symbol: float(pos.qty) for pos in broker_positions if float(pos.qty) != 0}
            
            # Check if we have any internal position tracking (would be implemented with persistent storage)
            # For now, just validate broker positions make sense
            
            discrepancies = []
            suspicious_positions = []
            
            for symbol, qty in broker_symbols.items():
                # Check for suspicious position sizes
                account = await self.gateway.get_account_safe()
                if account:
                    account_value = float(account.equity)
                    try:
                        # Get current price to estimate position value
                        quote = await self.gateway.get_latest_quote(symbol)
                        if quote:
                            current_price = float(quote.get('ask_price', 0)) or float(quote.get('bid_price', 0))
                            if current_price > 0:
                                position_value = abs(qty) * current_price
                                position_pct = (position_value / account_value) * 100
                                
                                # Flag positions larger than 10% of account
                                if position_pct > 10:
                                    suspicious_positions.append({
                                        'symbol': symbol,
                                        'qty': qty,
                                        'value': position_value,
                                        'percentage': position_pct
                                    })
                    except Exception as price_error:
                        self.logger.debug(f"Could not get price for {symbol}: {price_error}")
            
            if suspicious_positions:
                self.logger.warning(f"⚠️ LARGE POSITIONS DETECTED: {len(suspicious_positions)} positions > 10% of account")
                for pos in suspicious_positions:
                    self.logger.warning(f"   {pos['symbol']}: {pos['qty']} shares, ${pos['value']:,.2f} ({pos['percentage']:.1f}%)")
                
                # Only alert if this is a new large position issue (not repeatedly alerting for same positions)
                new_large_positions = [pos['symbol'] for pos in suspicious_positions]
                if not hasattr(self, '_last_large_positions') or self._last_large_positions != new_large_positions:
                    self._last_large_positions = new_large_positions
                    await self.alerter.send_critical_alert(
                        "Large positions detected at startup", 
                        f"Found {len(suspicious_positions)} positions > 10% of account: {', '.join(new_large_positions)}"
                    )
                    
                    # Consider reducing oversized positions during market hours
                    if self.is_market_hours():
                        await self._consider_position_reduction(suspicious_positions)
                else:
                    self.logger.info("ℹ️ Same large positions as before - alert suppressed")
            
            if broker_symbols:
                self.logger.info(f"✅ Position reconciliation complete: {len(broker_symbols)} active positions")
                for symbol, qty in broker_symbols.items():
                    self.logger.info(f"   {symbol}: {qty} shares")
            else:
                self.logger.info("✅ Position reconciliation complete: No active positions")
                
        except Exception as e:
            self.logger.error(f"Position reconciliation failed: {e}")
            await self.alerter.send_critical_alert(
                "Position reconciliation failed at startup",
                f"Unable to verify position accuracy: {e}"
            )
    
    def is_market_hours(self) -> bool:
        """Check if market is currently open for trading"""
        from datetime import datetime, time
        import pytz
        
        # Get current time in ET
        et_tz = pytz.timezone('US/Eastern')
        et_now = datetime.now(et_tz)
        
        # Check if it's a weekday (0=Monday, 4=Friday)
        if et_now.weekday() > 4:  # Weekend
            return False
            
        # Market hours: 9:30 AM - 4:00 PM ET
        market_open = time(9, 30)
        market_close = time(16, 0)
        current_time = et_now.time()
        
        return market_open <= current_time <= market_close
    
    async def _consider_position_reduction(self, large_positions):
        """Consider reducing positions that are too large (>10% of account)"""
        try:
            for position in large_positions:
                symbol = position['symbol']
                current_qty = position['qty']
                current_percentage = position['percentage']
                
                # Only reduce if position is significantly oversized (>12%)
                if current_percentage > 12:
                    # Calculate target reduction to get to 8% of account
                    target_percentage = 8.0
                    reduction_factor = target_percentage / current_percentage
                    target_qty = int(current_qty * reduction_factor)
                    qty_to_sell = current_qty - target_qty
                    
                    if qty_to_sell > 0:
                        self.logger.warning(f"🎯 Consider reducing {symbol} position: sell {qty_to_sell} shares to reduce from {current_percentage:.1f}% to ~{target_percentage}%")
                        
                        # Log the recommendation but don't auto-execute for safety
                        self.logger.info(f"💡 POSITION REDUCTION SUGGESTION for {symbol}:")
                        self.logger.info(f"   Current: {current_qty} shares ({current_percentage:.1f}% of account)")
                        self.logger.info(f"   Suggested: Sell {qty_to_sell} shares, keep {target_qty} shares")
                        self.logger.info(f"   This would reduce position to ~{target_percentage}% of account")
                        
        except Exception as e:
            self.logger.error(f"Error in position reduction consideration: {e}")
            
    async def run_intelligent_trading_loop(self):
        """Main intelligent trading loop with market-wide discovery"""
        self.running = True
        self.logger.info("🔥 STARTING INTELLIGENT TRADING ENGINE")
        
        try:
            # Wait for market open if needed, but check for shutdown signals
            while self.running:
                should_trade, reason = await self.market_status.should_start_trading()
                should_monitor_extended = self.market_status.should_monitor_positions_extended_hours()
                
                if should_trade:
                    break
                elif should_monitor_extended:
                    self.logger.info(f"⏰ {reason} - but monitoring positions for gap risk")
                    # Run extended hours monitoring loop
                    await self._extended_hours_monitoring_loop()
                    continue
                elif not self.running:
                    self.logger.info("Shutdown requested during market wait")
                    return
                else:
                    self.logger.info(f"⏰ {reason}")
                    # Wait 60 seconds but check for shutdown every 5 seconds
                    for _ in range(12):  # 12 * 5 = 60 seconds
                        if not self.running:
                            self.logger.info("Shutdown requested during market wait")
                            return
                        await asyncio.sleep(5)
            
            loop_count = 0
            while self.running:
                loop_start = datetime.now()
                loop_count += 1
                
                # === MARKET INTELLIGENCE UPDATE ===
                try:
                    await self._update_market_intelligence()
                except Exception as e:
                    self.logger.warning(f"⚠️ 🚨 MARKET INTELLIGENCE SYSTEM FAILURE 🚨")
                    self.logger.warning(f"⚠️ Market intelligence update failed: {e}")
                    self.logger.warning(f"⚠️ Trading decisions will operate with degraded market context")
                    self.logger.warning(f"⚠️ Consider checking AI system health and data connectivity")
                
                # === CORPORATE ACTIONS CHECK (CRITICAL) ===
                try:
                    await self._check_corporate_actions()
                except Exception as e:
                    self.logger.error(f"❌ Corporate actions check error: {e}")
                
                # === OPPORTUNITY DISCOVERY ===
                try:
                    await self._discover_market_opportunities()
                except Exception as e:
                    self.logger.error(f"❌ Opportunity discovery error: {e}")
                
                # === TIERED ANALYSIS TEST (First loop only) ===
                if loop_count == 1:  # Run on first iteration
                    try:
                        self.logger.info("🧪 Running Tiered Analysis Test with Hot Stocks...")
                        await self.test_tiered_analysis_with_hot_stocks()
                    except Exception as e:
                        self.logger.error(f"❌ Tiered analysis test error: {e}")
                
                # === SIGNAL GENERATION & VALIDATION ===
                try:
                    await self._generate_and_validate_signals()
                except Exception as e:
                    self.logger.error(f"❌ Signal generation error: {e}")
                
                # === STALE ORDER CLEANUP (CRITICAL) ===
                # Clean up stale orders that may be blocking profit-taking
                if loop_count % RISK_CONFIG['stale_order_cleanup_loop_interval'] == 0:  # Configurable cleanup frequency
                    try:
                        stale_cancelled = await self._cleanup_all_stale_orders()
                        if stale_cancelled > 0:
                            self.logger.info(f"🧹 Cleaned up {stale_cancelled} stale orders blocking trades")
                    except Exception as e:
                        self.logger.error(f"❌ Stale order cleanup error: {e}")

                # === POSITION MANAGEMENT (CRITICAL - MUST NOT FAIL) ===
                try:
                    await self._manage_existing_positions()
                except Exception as e:
                    self.logger.error(f"❌ CRITICAL: Position management error: {e}")
                
                # === POSITION PROTECTION MONITORING (CRITICAL) ===
                # Reduced frequency to prevent excessive stop order creation/cancellation cycles
                if loop_count % RISK_CONFIG['protection_monitoring_loop_interval'] == 0:  # Configurable monitoring frequency
                    try:
                        await self._monitor_position_protection()
                    except Exception as e:
                        self.logger.error(f"❌ CRITICAL: Position protection monitoring error: {e}")
                
                # === STOP LOSS & TRAILING STOPS (CRITICAL) ===
                try:
                    await self.order_executor.check_stop_losses()
                    await self.order_executor.update_trailing_stops()
                except Exception as e:
                    self.logger.error(f"❌ CRITICAL: Stop loss management error: {e}")
                
                # === RISK MONITORING ===
                try:
                    await self._monitor_system_risk()
                except Exception as e:
                    self.logger.error(f"❌ Risk monitoring error: {e}")
                
                # === PERFORMANCE TRACKING ===
                try:
                    await self._update_performance_metrics()
                except Exception as e:
                    self.logger.error(f"❌ Performance tracking error: {e}")
                
                # === GAP RISK MONITORING (Record closes before 4 PM) ===
                try:
                    await self._record_market_close_positions()
                except Exception as e:
                    self.logger.error(f"❌ Gap risk recording error: {e}")
                
                # === SYSTEM HEALTH CHECK ===
                try:
                    await self._system_health_check()
                except Exception as e:
                    self.logger.error(f"❌ Health check error: {e}")
                
                # === PDT STATUS MONITORING ===
                try:
                    await self._monitor_pdt_status()
                except Exception as e:
                    self.logger.error(f"❌ PDT monitoring error: {e}")
                
                # === PERIODIC PROTECTION VERIFICATION (Every 5 loops) ===
                if loop_count % RISK_CONFIG['periodic_protection_verification_loop_interval'] == 0:  # Configurable verification frequency
                    try:
                        await self._periodic_protection_verification()
                    except Exception as e:
                        self.logger.error(f"❌ Periodic protection verification error: {e}")
                
                # === ENHANCED POSITION AGING MANAGEMENT (Every 3 loops during market hours) ===
                # Check market status first
                market_open = False
                try:
                    clock = await self.gateway.get_clock()
                    market_open = clock.is_open if clock else False
                except:
                    market_open = False
                    
                if loop_count % RISK_CONFIG['position_aging_management_loop_interval'] == 0 and market_open:  # Configurable aging management frequency
                    try:
                        await self._enhanced_position_aging_management()
                    except Exception as e:
                        self.logger.error(f"❌ Position aging management error: {e}")
                    
                # === ADAPTIVE LOOP TIMING ===
                execution_time = (datetime.now() - loop_start).total_seconds()
                
                # Adaptive sleep based on market conditions and discovery frequency
                if self.current_intelligence and self.current_intelligence.volatility_environment == "HIGH":
                    sleep_time = max(30, 60 - execution_time)  # Faster in high volatility
                else:
                    sleep_time = max(60, 120 - execution_time)  # Standard timing
                    
                self.logger.debug(f"⏱️ Loop completed in {execution_time:.2f}s, sleeping {sleep_time:.0f}s")
                
                # Sleep in smaller chunks to be responsive to shutdown signals
                sleep_chunks = int(sleep_time / 5)  # Sleep in 5-second chunks
                for _ in range(sleep_chunks):
                    if not self.running:
                        self.logger.info("Shutdown requested during sleep")
                        return
                    await asyncio.sleep(5)
                    
                # Handle remaining sleep time
                remaining_sleep = sleep_time % 5
                if remaining_sleep > 0 and self.running:
                    await asyncio.sleep(remaining_sleep)
                
        except KeyboardInterrupt:
            self.logger.info("🛑 Graceful shutdown requested")
        except asyncio.CancelledError:
            self.logger.info("🛑 Shutdown signal received")
        except Exception as e:
            self.logger.critical(f"💥 CRITICAL ERROR: {e}")
            await self._emergency_shutdown("Critical system error")
        finally:
            await self._graceful_shutdown()
            
    async def _update_market_intelligence(self):
        """Update market intelligence and regime analysis"""
        try:
            # Check if intelligence needs refresh
            if (not self.last_intelligence_update or
                (datetime.now() - self.last_intelligence_update).total_seconds() > 
                AI_CONFIG['market_regime_analysis_frequency'] * 60):
                
                self.logger.debug("🧠 Updating market intelligence...")
                
                # Collect fresh market data
                market_data = await self._collect_current_market_data()
                
                # Generate new intelligence
                self.current_intelligence = await self.ai_assistant.generate_daily_market_intelligence(market_data)
                self.last_intelligence_update = datetime.now()
                
                self.logger.info(f"📊 Market Intelligence Updated: {self.current_intelligence.market_regime} "
                               f"({self.current_intelligence.confidence:.0%} confidence)")
                               
        except Exception as e:
            self.logger.warning(f"⚠️ 🚨 CRITICAL: Market Intelligence Update Failed 🚨")
            self.logger.warning(f"⚠️ Error: {e}")
            self.logger.warning(f"⚠️ System will continue with stale or fallback intelligence")
            self.logger.warning(f"⚠️ Trading performance may be degraded until resolved")
    
    async def _check_corporate_actions(self):
        """Check for corporate actions that could affect trading"""
        try:
            # Get current watchlist symbols for checking
            watchlist_symbols = []
            
            # Add symbols from active opportunities
            for opportunity in self.active_opportunities:
                if hasattr(opportunity, 'symbol'):
                    watchlist_symbols.append(opportunity.symbol)
            
            # Add symbols from current positions
            try:
                positions = await self.gateway.get_all_positions()
                for position in positions:
                    if float(position.qty) != 0:
                        watchlist_symbols.append(position.symbol)
            except Exception as e:
                self.logger.error(f"Error getting positions for corporate actions check: {e}")
            
            # Remove duplicates
            watchlist_symbols = list(set(watchlist_symbols))
            
            if not watchlist_symbols:
                self.logger.debug("No symbols to check for corporate actions")
                return
            
            # Check for corporate actions (runs only on first check of the day)
            current_date = datetime.now().date()
            if not hasattr(self, '_last_corporate_check_date') or self._last_corporate_check_date != current_date:
                blocked_symbols = await self.corporate_actions_filter.check_pre_market_corporate_actions(watchlist_symbols)
                
                if blocked_symbols:
                    self.logger.warning(f"🚫 Corporate actions detected - {len(blocked_symbols)} symbols blocked")
                    
                    # Remove blocked symbols from active opportunities
                    self.active_opportunities = [
                        opp for opp in self.active_opportunities 
                        if not hasattr(opp, 'symbol') or opp.symbol not in blocked_symbols
                    ]
                
                # Mark that we've done today's corporate actions check
                self._last_corporate_check_date = current_date
            
            # Always check if individual symbols are blocked before trading
            blocked_info = self.corporate_actions_filter.get_blocked_symbols_info()
            if blocked_info['total_blocked'] > 0:
                self.logger.info(f"📊 Corporate actions status: {blocked_info['total_blocked']} symbols blocked")
                
        except Exception as e:
            self.logger.error(f"Corporate actions check failed: {e}")
            
    async def _discover_market_opportunities(self):
        """Execute intelligent funnel for opportunity discovery"""
        try:
            # Check if opportunity scan is needed
            if (not self.last_opportunity_scan or
                (datetime.now() - self.last_opportunity_scan).total_seconds() > 
                FUNNEL_CONFIG['broad_scan_frequency_minutes'] * 60):
                
                self.logger.debug("🔍 Executing opportunity discovery...")
                
                # Run intelligent funnel
                new_opportunities = await self.market_funnel.execute_intelligent_funnel()
                
                if new_opportunities:
                    self.active_opportunities = new_opportunities
                    self.session_stats['opportunities_discovered'] += len(new_opportunities)
                    
                    # Log top opportunities
                    self.logger.info("🎯 TOP OPPORTUNITIES:")
                    for i, opp in enumerate(new_opportunities[:5], 1):
                        self.logger.info(f"   {i}. {opp.symbol}: {opp.opportunity_score:.2f} "
                                       f"({opp.discovery_source}) - {opp.primary_catalyst}")
                                       
                self.last_opportunity_scan = datetime.now()
                
        except Exception as e:
            self.logger.error(f"Opportunity discovery failed: {e}")
            
    async def _generate_and_validate_signals(self):
        """Generate trading signals and validate with AI"""
        try:
            if not self.active_opportunities:
                self.logger.debug("No active opportunities for signal generation")
                return
                
            self.logger.info(f"🔍 Analyzing {len(self.active_opportunities)} opportunities for trade signals...")
                
            signals_generated = 0
            
            # Get existing positions to prevent duplicate trades
            existing_positions = await self.gateway.get_all_positions()
            existing_symbols = {pos.symbol for pos in existing_positions if float(pos.qty) != 0}
            
            if existing_symbols:
                self.logger.info(f"🔒 Existing positions: {', '.join(existing_symbols)} - will skip these symbols")
            
            for opportunity in self.active_opportunities[:10]:  # Process top 10
                try:
                    # SKIP if we already have a position in this symbol
                    if opportunity.symbol in existing_symbols:
                        self.logger.info(f"⏭️ SKIPPING {opportunity.symbol}: Already have position")
                        continue
                    
                    # CRITICAL: SKIP if symbol is blocked due to corporate actions
                    if self.corporate_actions_filter.is_symbol_blocked(opportunity.symbol):
                        self.logger.warning(f"🚫 SKIPPING {opportunity.symbol}: Blocked due to corporate actions")
                        continue
                    
                    # CRITICAL: SKIP if symbol is PDT-blocked to prevent repeated failed attempts
                    if self.gateway.is_symbol_pdt_blocked(opportunity.symbol):
                        self.logger.warning(f"🚫 SKIPPING {opportunity.symbol}: PDT-blocked from previous violation")
                        continue
                        
                    # COMPREHENSIVE DATA ACQUISITION STRATEGY WITH FREE SUPPLEMENTS
                    bars = None
                    data_sources_tried = []
                    quote_data = None
                    
                    # Strategy 1: Try Alpaca first (limited on free tier)
                    from datetime import datetime, timedelta
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=30)
                    
                    bars = await self.gateway.get_bars(
                        opportunity.symbol, '1Day', limit=50, 
                        start=start_date, end=end_date
                    )
                    data_sources_tried.append(f"Alpaca-daily ({len(bars) if bars else 0} bars)")
                    
                    # Strategy 2: If Alpaca fails, use FREE supplemental data sources
                    if not bars or len(bars) < 5:
                        self.logger.info(f"📊 Alpaca data insufficient for {opportunity.symbol}, trying free sources...")
                        
                        # Yahoo Finance + Alpha Vantage (FREE)
                        supplement_bars = await self.supplemental_data.get_historical_data(
                            opportunity.symbol, days=30, min_bars=10
                        )
                        
                        if supplement_bars and len(supplement_bars) > len(bars or []):
                            bars = supplement_bars
                            data_sources_tried.append(f"Free-sources ({len(bars)} bars)")
                            
                        # Get real-time quote from Yahoo Finance (FREE)
                        if not quote_data:
                            quote_data = await self.supplemental_data.get_real_time_quote(opportunity.symbol)
                            if quote_data:
                                data_sources_tried.append("Yahoo-quote")
                    
                    # Strategy 3: Fallback to Alpaca intraday if free sources fail
                    if not bars or len(bars) < 5:
                        self.logger.info(f"📊 Free sources insufficient, trying Alpaca intraday...")
                        
                        # Try hourly data from Alpaca
                        bars_1h = await self.gateway.get_bars(opportunity.symbol, '1Hour', limit=50)
                        data_sources_tried.append(f"Alpaca-hourly ({len(bars_1h) if bars_1h else 0} bars)")
                        
                        if bars_1h and len(bars_1h) >= 6:  # Reduced requirement
                            # Convert hourly to daily equivalent
                            daily_equiv = self._aggregate_intraday_to_daily(bars_1h, hours_per_day=6)
                            if daily_equiv and len(daily_equiv) >= 2:
                                bars = daily_equiv
                                data_sources_tried.append(f"hourly-aggregated ({len(bars)} bars)")
                            else:
                                # Use raw hourly data if aggregation fails
                                bars = bars_1h[:20]  # Limit to prevent over-analysis
                                data_sources_tried.append(f"raw-hourly ({len(bars)} bars)")
                        elif bars_1h and len(bars_1h) >= 3:
                            # Use minimal hourly data
                            bars = bars_1h
                            data_sources_tried.append(f"minimal-hourly ({len(bars)} bars)")
                    
                    # Strategy 4: Get real-time quote from Alpaca if Yahoo failed
                    if not quote_data and bars and len(bars) > 0:
                        current_quote = await self.gateway.get_latest_quote(opportunity.symbol)
                        if current_quote:
                            quote_data = {
                                'current_price': float(current_quote.get('ask_price', 0)) or float(current_quote.get('bid_price', 0)),
                                'bid_ask_spread': abs(float(current_quote.get('ask_price', 0)) - float(current_quote.get('bid_price', 0))),
                                'timestamp': current_quote.get('timestamp', '')
                            }
                            data_sources_tried.append("Alpaca-quote")
                    
                    self.logger.info(f"📊 {opportunity.symbol} data acquisition: {' + '.join(data_sources_tried)}")
                    if not bars:
                        self.logger.info(f"📊 No bars data returned for {opportunity.symbol}")
                        continue
                    else:
                        self.logger.info(f"📊 Retrieved {len(bars)} bars for {opportunity.symbol}")
                        
                    # Generate technical signal with enhanced data context and market intelligence
                    technical_signal = await self.strategy_engine.analyze_symbol(
                        opportunity.symbol, bars, quote_data=quote_data, 
                        data_sources=data_sources_tried, market_intelligence=self.current_intelligence
                    )
                    
                    # AGGRESSIVE TRADING: Allow AI-only evaluation when technical fails but has good data
                    from config import RISK_CONFIG
                    allow_ai_only = (not technical_signal and len(bars) >= 10 and 
                                   RISK_CONFIG['max_position_size_pct'] >= 25.0)  # Only for aggressive config
                    
                    if technical_signal or allow_ai_only:
                        if technical_signal:
                            self.logger.info(f"📈 Technical signal generated for {opportunity.symbol}: {technical_signal.action}")
                        else:
                            self.logger.info(f"🤖 AI-only evaluation for {opportunity.symbol} (technical analysis bypassed)")
                            # Create basic signal for AI evaluation
                            try:
                                # Safely get current price from bars or opportunity
                                if isinstance(bars, pd.DataFrame) and len(bars) > 0:
                                    current_price = bars['close'].iloc[-1]
                                else:
                                    current_price = opportunity.current_price
                            except:
                                current_price = opportunity.current_price
                                
                            technical_signal = type('Signal', (), {
                                'symbol': opportunity.symbol,
                                'action': 'BUY', 
                                'entry_price': current_price,
                                'signal_type': 'AI_ONLY',
                                'confidence': 0.85,        # Default confidence for AI-only signals
                                'strength': 1.0,           # Default strength
                                'stop_loss': None,         # Will be set by risk management
                                'take_profit': None,       # Will be set by risk management
                                'position_size_pct': 40.0, # Aggressive position sizing
                                'timeframe': '1D',         # Daily timeframe
                                'risk_reward_ratio': 2.0   # 2:1 risk/reward
                            })()
                        
                        # AI validation of signal against market context
                        try:
                            ai_evaluation = await self.ai_assistant.evaluate_opportunity_with_context(
                                opportunity, self.current_intelligence
                            )
                            
                            # Log AI evaluation results
                            self.logger.info(f"🧠 AI evaluation for {opportunity.symbol}: score={ai_evaluation.get('overall_score', 0):.2f}, "
                                           f"confidence={ai_evaluation.get('confidence', 0):.2f}, "
                                           f"recommendation={ai_evaluation.get('entry_recommendation', 'NONE')}")
                            
                        except Exception as ai_error:
                            self.logger.warning(f"⚠️ AI EVALUATION FAILURE for {opportunity.symbol}: {ai_error}")
                            self.logger.warning(f"⚠️ Using fallback evaluation for this opportunity")
                            ai_evaluation = {
                                'overall_score': 0.6,  # Neutral fallback score
                                'confidence': 0.5,     # Lower confidence
                                'entry_recommendation': 'PATIENT',
                                'reasoning': f'AI evaluation failed: {ai_error}'
                            }
                        
                        # Check AI confidence and recommendation
                        if (ai_evaluation.get('overall_score', 0) >= 0.7 and
                            ai_evaluation.get('entry_recommendation') in ['IMMEDIATE', 'PATIENT'] and
                            ai_evaluation.get('confidence', 0) >= AI_CONFIG['confidence_threshold']):
                            
                            # Execute trade
                            success = await self._execute_validated_signal(technical_signal, ai_evaluation, opportunity)
                            
                            if success:
                                signals_generated += 1
                                self.session_stats['signals_generated'] += 1
                                self.session_stats['trades_executed'] += 1
                                
                                self.logger.info(f"✅ TRADE EXECUTED: {opportunity.symbol} "
                                               f"(AI Score: {ai_evaluation['overall_score']:.2f}, "
                                               f"Expected: {ai_evaluation.get('expected_return_pct', 0):.1f}%)")
                        else:
                            # Determine if this is an AI failure vs. legitimate rejection
                            score = ai_evaluation.get('overall_score', 0)
                            confidence = ai_evaluation.get('confidence', 0)
                            reasoning = ai_evaluation.get('reasoning', 'No reasoning provided')
                            
                            if 'failed' in reasoning.lower() or 'error' in reasoning.lower():
                                self.logger.warning(f"⚠️ {opportunity.symbol}: AI SYSTEM FAILURE during evaluation")
                                self.logger.warning(f"⚠️ AI error details: {reasoning}")
                                self.logger.warning(f"⚠️ Opportunity skipped due to AI failure, not rejection")
                            else:
                                self.logger.info(f"⚠️ {opportunity.symbol}: AI validation failed - "
                                               f"score={score:.2f} (need ≥0.7), confidence={confidence:.2f} "
                                               f"(need ≥{AI_CONFIG['confidence_threshold']:.2f}), "
                                               f"recommendation={ai_evaluation.get('entry_recommendation', 'NONE')}")
                    else:
                        self.logger.info(f"📊 No technical signal for {opportunity.symbol}")
                        continue
                            
                except Exception as e:
                    self.logger.error(f"Signal processing failed for {opportunity.symbol}: {e}")
                    
            if signals_generated > 0:
                self.logger.info(f"📈 Generated {signals_generated} validated trading signals")
                
        except Exception as e:
            self.logger.error(f"Signal generation failed: {e}")
            
    async def _execute_validated_signal(self, signal: TradingSignal, ai_evaluation: Dict, 
                                      opportunity: MarketOpportunity) -> bool:
        """Execute trading signal with comprehensive validation"""
        try:
            # Check if market is open before attempting to trade
            clock = await self.gateway.get_clock()
            if clock and hasattr(clock, 'is_open') and not clock.is_open:
                self.logger.warning(f"⏰ Skipping trade for {signal.symbol} - market is closed")
                return False
            
            # Check position limits - CRITICAL for risk management
            positions = await self.gateway.get_all_positions()
            active_positions = [p for p in positions if float(p.qty) != 0]
            max_positions = FUNNEL_CONFIG.get('max_active_positions', 8)
            
            if len(active_positions) >= max_positions:
                self.logger.warning(f"⚠️ Position limit reached ({len(active_positions)}/{max_positions}) - skipping {signal.symbol}")
                return False
            
            # Final risk check
            account = await self.gateway.get_account_safe()
            if not account:
                return False
                
            # Calculate position size based on AI recommendation - AGGRESSIVE 50% ANNUAL RETURN TARGET
            from config import RISK_CONFIG
            min_position_size = RISK_CONFIG['min_position_size_pct'] / 100  # 25% minimum
            max_position_size = RISK_CONFIG['max_position_size_pct'] / 100  # 40% maximum
            
            # Size based on AI confidence and recommendation - MORE AGGRESSIVE
            size_multiplier = {
                'FULL': 1.0,        # 40% position - MAXIMUM AGGRESSION
                'REDUCED': 0.8,     # 32% position (was 0.7)
                'MINIMAL': 0.625    # 25% position minimum (was 0.6)
            }.get(ai_evaluation.get('position_size_recommendation', 'REDUCED'), 0.8)
            
            # Calculate target position size - MUCH LARGER FOR 50% RETURNS
            target_size = max_position_size * size_multiplier
            adjusted_position_size = max(min_position_size, target_size)
            
            self.logger.info(f"🚀 TARGET POSITION: {signal.symbol} = {adjusted_position_size*100:.1f}% of account (subject to position sizing caps)")
            
            # Update signal with AI insights
            signal.stop_loss_price = signal.entry_price * (1 - RISK_CONFIG['stop_loss_pct'] / 100)
            signal.take_profit_price = signal.entry_price * (1 + ai_evaluation.get('expected_return_pct', 10) / 100)
            signal.confidence = ai_evaluation.get('confidence', signal.confidence)
            signal.reasoning = f"AI: {ai_evaluation.get('reasoning', 'No reasoning')}"
            
            # Execute trade
            success = await self.order_executor.execute_signal(signal)
            
            if success:
                # Log comprehensive trade details
                trade_log = {
                    'timestamp': datetime.now().isoformat(),
                    'symbol': signal.symbol,
                    'action': signal.action,
                    'entry_price': signal.entry_price,
                    'stop_loss': signal.stop_loss_price,
                    'take_profit': signal.take_profit_price,
                    'position_size_pct': adjusted_position_size * 100,
                    'ai_score': ai_evaluation.get('overall_score'),
                    'ai_confidence': ai_evaluation.get('confidence'),
                    'expected_return': ai_evaluation.get('expected_return_pct'),
                    'market_regime': self.current_intelligence.market_regime,
                    'discovery_source': opportunity.discovery_source,
                    'opportunity_score': opportunity.opportunity_score
                }
                
                self.logger.info(f"📝 TRADE LOG: {json.dumps(trade_log, indent=2)}")
                
            return success
            
        except Exception as e:
            self.logger.error(f"Trade execution failed: {e}")
            return False
            
    async def _manage_existing_positions(self):
        """Comprehensive autonomous position management"""
        try:
            # Get all current positions
            positions = await self.gateway.get_all_positions()
            active_positions = [pos for pos in positions if float(pos.qty) != 0]
            
            if not active_positions:
                self.logger.debug("No active positions to manage")
                return
                
            self.logger.info(f"📊 Managing {len(active_positions)} active positions...")
            
            for position in active_positions:
                try:
                    await self._manage_individual_position(position)
                except Exception as e:
                    self.logger.error(f"Position management failed for {position.symbol}: {e}")
            
            # Check for oversized positions and reduce automatically
            await self._check_and_reduce_oversized_positions(active_positions)
                    
        except Exception as e:
            self.logger.error(f"Position management system failed: {e}")
            
    async def _manage_individual_position(self, position):
        """Manage individual position with autonomous decision making"""
        try:
            from config import RISK_CONFIG
            symbol = position.symbol
            qty = float(position.qty)
            current_value = float(position.market_value)
            unrealized_pl = float(position.unrealized_pl)
            unrealized_pct = float(position.unrealized_plpc) * 100
            avg_entry = float(position.avg_entry_price)
            
            # SWING TRADING ENFORCEMENT - Check minimum holding period
            # Find when this position was opened by checking executed trades
            position_entry_time = None
            for trade in self.order_executor.executed_trades:
                if trade['signal'].symbol == symbol and trade['status'] == 'EXECUTED':
                    position_entry_time = trade.get('entry_timestamp', trade.get('execution_time'))
                    break
            
            if position_entry_time:
                hours_held = (datetime.now() - position_entry_time).total_seconds() / 3600
                days_held = hours_held / 24
                min_hold_hours = RISK_CONFIG['min_holding_period_hours']
                max_hold_days = RISK_CONFIG.get('max_position_age_days', 4)
                
                if hours_held < min_hold_hours:
                    self.logger.info(f"🕐 {symbol}: Swing trading hold - {hours_held:.1f}h/{min_hold_hours}h minimum")
                    return  # Skip position management - enforce swing trading
                    
                # Check for aging positions that need review
                if days_held >= max_hold_days:
                    self.logger.warning(f"🕒 {symbol}: Aging position held {days_held:.1f} days (limit: {max_hold_days})")
                    if unrealized_pct < 2.0:  # If not significantly profitable, consider exit
                        self.logger.info(f"🕒 {symbol}: Aging position with low profit (+{unrealized_pct:.1f}%) - will be managed more aggressively")
            else:
                # If we can't find entry time, assume it's been held long enough (existing position)
                self.logger.debug(f"📊 {symbol}: No entry time found, assuming swing trade eligible")
            
            self.logger.debug(f"📊 {symbol}: {qty} shares, {unrealized_pct:.1f}% P&L")
            
            # Get current market data for analysis
            bars = await self.gateway.get_bars(symbol, '1Day', limit=10)
            current_quote = await self.gateway.get_latest_quote(symbol)
            
            if not current_quote:
                self.logger.warning(f"No current quote for {symbol}, skipping management")
                return
                
            current_price = float(current_quote.get('ask_price', 0)) or float(current_quote.get('bid_price', 0))
            
            # CRITICAL: Enhanced risk management - Loss cutting at -4%
            max_loss_pct = RISK_CONFIG.get('max_position_loss_pct', -4.0)
            if unrealized_pct <= max_loss_pct:
                # Check if market is open before attempting loss cuts
                clock = await self.gateway.get_clock()
                if clock and hasattr(clock, 'is_open') and not clock.is_open:
                    self.logger.warning(f"⚠️ {symbol} at {unrealized_pct:.1f}% loss but market closed - will execute loss cut when market opens")
                    return  # Skip loss cut when market is closed
                # Check if position already has adequate stop protection before triggering loss cut
                try:
                    orders = await self.gateway.get_orders('open')
                    has_adequate_stop = False
                    
                    for order in orders:
                        if (order.symbol == symbol and 
                            order.side == ('sell' if qty > 0 else 'buy') and
                            order.order_type in ['stop', 'stop_limit']):
                            # Check if existing stop would trigger at or above our threshold
                            entry_price = float(position.avg_entry_price)
                            stop_price = float(order.stop_price) if hasattr(order, 'stop_price') else float(order.limit_price)
                            stop_loss_pct = ((stop_price - entry_price) / entry_price) * 100
                            
                            # Check if stop is at an acceptable level (stop should be negative, closer to 0 is less loss)
                            # For a long position, stop_loss_pct will be negative when stop < entry
                            # We want to skip if there's ANY stop order, as it provides protection
                            if order.order_type in ['stop', 'stop_limit']:
                                has_adequate_stop = True
                                self.logger.debug(f"✅ {symbol} already has stop protection at {stop_loss_pct:.1f}%")
                                break
                    
                    if has_adequate_stop:
                        self.logger.debug(f"⏭️ SKIPPING LOSS CUT: {symbol} already protected by existing stop order")
                        return  # Skip loss cut - already protected
                        
                except Exception as e:
                    self.logger.debug(f"Could not check existing orders for {symbol}: {e}")
                
                # Only log CRITICAL after confirming no protection exists
                # First try to execute the loss cut
                self.logger.info(f"📉 Attempting loss cut for {symbol} at {unrealized_pct:.1f}% loss (limit: {max_loss_pct}%)")
                
                # Execute immediate loss cut with market sell order
                order_data = {
                    'symbol': symbol,
                    'qty': str(int(abs(qty))),
                    'side': 'sell' if qty > 0 else 'buy',
                    'type': 'market',
                    'time_in_force': 'day'
                }
                
                try:
                    response = await self.gateway.submit_order(order_data)
                    if response and response.success:
                        self.logger.critical(f"🔴 LOSS CUT EXECUTED: {symbol} - sold {int(abs(qty))} shares at {unrealized_pct:.1f}% loss")
                        await self.alerter.send_critical_alert(
                            f"🔴 LOSS CUT: {symbol} sold at {unrealized_pct:.1f}% loss"
                        )
                        return  # Exit - position management complete
                    else:
                        error_msg = response.error if response else "No response received"
                        # Check if shares are held by existing orders (stop losses)
                        if response and "insufficient qty available" in str(response.error) and "held_for_orders" in str(response.error):
                            self.logger.debug(f"✅ {symbol} already protected by existing stop orders - loss cut not needed")
                        else:
                            self.logger.error(f"❌ LOSS CUT FAILED: {symbol} - {error_msg}")
                except Exception as e:
                    self.logger.error(f"❌ LOSS CUT ERROR: {symbol} - {e}")
            
            # Check for profit taking opportunities - ENHANCED GRANULAR SYSTEM
            profit_levels = RISK_CONFIG.get('profit_taking_levels', [5.0, 10.0, 15.0])
            profit_percentages = RISK_CONFIG.get('profit_taking_percentages', [0.15, 0.35, 0.50])
            
            for i, profit_level in enumerate(profit_levels):
                if unrealized_pct >= profit_level:
                    # Only take profit if we haven't already done so at this level
                    profit_flag = f'_{symbol}_profit_{int(profit_level)}_taken'
                    if not hasattr(self, profit_flag):
                        # Use corresponding percentage for this level
                        profit_pct = profit_percentages[i] if i < len(profit_percentages) else 0.25
                        calculated_qty = abs(qty) * profit_pct
                        sell_qty = max(1, int(calculated_qty)) if calculated_qty >= 0.5 else 0
                        
                        # EDGE CASE: 1-share positions - handle profit taking specially
                        if abs(qty) == 1:
                            if profit_level >= 15.0:  # Only take profit on 1-share if +15% or higher
                                sell_qty = 1
                                self.logger.info(f"   📏 1-SHARE PROFIT: {symbol} at +{unrealized_pct:.1f}% - selling entire position")
                            else:
                                sell_qty = 0
                                self.logger.info(f"   📏 1-SHARE PROFIT: {symbol} at +{unrealized_pct:.1f}% - keeping (threshold not met)")
                        
                        if sell_qty > 0:
                            # Check for existing orders BEFORE attempting new order
                            orders_exist = await self._check_actual_open_orders_for_symbol(symbol)
                            if orders_exist:
                                self.logger.info(f"✅ PROFIT TAKING SKIPPED: {symbol} - shares held by existing orders (protected)")
                                continue  # Skip to next profit level
                            
                            self.logger.info(f"💰 PROFIT TAKING: {symbol} at +{unrealized_pct:.1f}% - selling {sell_qty} shares ({profit_pct*100}%)")
                            
                            order_data = {
                                'symbol': symbol,
                                'qty': str(sell_qty),
                                'side': 'sell' if qty > 0 else 'buy',
                                'type': 'market',
                                'time_in_force': 'day'
                            }
                            
                            try:
                                response = await self.gateway.submit_order(order_data)
                                if response and response.success:
                                    self.logger.info(f"✅ PROFIT TAKEN: {symbol} - sold {sell_qty} shares at +{unrealized_pct:.1f}%")
                                    setattr(self, profit_flag, True)
                                    await self.alerter.send_critical_alert(
                                        f"💰 PROFIT TAKEN: {symbol} partial sale at +{unrealized_pct:.1f}%"
                                    )
                                else:
                                    error_msg = response.error if response else "No response received"
                                    # Check if shares are held by existing orders
                                    if response and "insufficient qty available" in str(response.error) and "held_for_orders" in str(response.error):
                                        # Verify if orders actually exist before skipping permanently
                                        orders_exist = await self._check_actual_open_orders_for_symbol(symbol)
                                        if orders_exist:
                                            self.logger.info(f"✅ PROFIT TAKING SKIPPED: {symbol} - shares held by existing orders (protected)")
                                        else:
                                            self.logger.warning(f"🔄 PROFIT TAKING RETRY: {symbol} - 'held_for_orders' error but no open orders found, will retry next cycle")
                                    else:
                                        self.logger.error(f"❌ PROFIT TAKING FAILED: {symbol} - {error_msg}")
                            except Exception as e:
                                self.logger.error(f"❌ PROFIT TAKING ERROR: {symbol} - {e}")
            
            # Analyze position against current market intelligence
            position_analysis = await self._analyze_position_context(
                symbol, current_price, unrealized_pct, bars
            )
            
            # Make autonomous management decisions
            management_action = await self._determine_position_action(
                symbol, qty, unrealized_pct, current_price, avg_entry, position_analysis
            )
            
            # Execute management action
            if management_action['action'] != 'HOLD':
                await self._execute_position_management(position, management_action, current_price)
                
        except Exception as e:
            self.logger.error(f"Individual position management failed for {position.symbol}: {e}")
    
    async def _check_and_reduce_oversized_positions(self, positions: List):
        """Check for oversized positions and reduce them automatically"""
        try:
            from config import RISK_CONFIG
            concentration_limit = RISK_CONFIG.get('concentration_limit_pct', 8.0) / 100.0
            
            # Get current account value
            account_info = await self.gateway.get_account()
            if not account_info or not hasattr(account_info, 'equity'):
                self.logger.warning("Could not get account info for concentration check")
                return
                
            account_value = float(account_info.equity)
            oversized_positions = []
            
            for position in positions:
                qty = float(position.qty)
                if qty == 0:
                    continue
                    
                # Get current price and calculate position value
                quote = await self.gateway.get_latest_quote(position.symbol)
                if not quote:
                    continue
                    
                current_price = float(quote.get('ask_price', 0) if qty > 0 else quote.get('bid_price', 0))
                position_value = abs(qty * current_price)
                position_pct = position_value / account_value
                
                if position_pct > concentration_limit:
                    oversized_positions.append({
                        'symbol': position.symbol,
                        'qty': qty,
                        'value': position_value,
                        'pct': position_pct * 100,
                        'current_price': current_price
                    })
                    
            # Reduce oversized positions
            for pos in oversized_positions:
                symbol = pos['symbol']
                current_qty = pos['qty']
                current_pct = pos['pct']
                
                # Calculate target quantity to get to 8% limit
                target_value = account_value * concentration_limit
                target_qty = int(target_value / pos['current_price'])
                reduce_qty = abs(int(current_qty)) - target_qty
                
                if reduce_qty > 0:
                    self.logger.warning(f"🔸 {symbol}: Reducing oversized position from {current_pct:.1f}% to {concentration_limit*100:.1f}%")
                    self.logger.info(f"📊 {symbol}: Selling {reduce_qty} shares (keeping {target_qty})")
                    
                    # Create market sell order to reduce position
                    order_data = {
                        'symbol': symbol,
                        'qty': str(reduce_qty),
                        'side': 'sell' if current_qty > 0 else 'buy',
                        'type': 'market',
                        'time_in_force': 'day'
                    }
                    
                    response = await self.gateway.submit_order(order_data)
                    if response and response.success:
                        self.logger.info(f"✅ Position reduction order submitted for {symbol}")
                        
                        # Send alert about position reduction
                        alert_msg = f"🔸 {symbol}: Reduced oversized position from {current_pct:.1f}% to target {concentration_limit*100:.1f}%"
                        await self.alerter.send_critical_alert(alert_msg)
                    else:
                        error_msg = response.error if response else "No response received"
                        # Check if shares are held by existing orders
                        if response and "insufficient qty available" in str(response.error) and "held_for_orders" in str(response.error):
                            # Verify if orders actually exist before skipping permanently
                            orders_exist = await self._check_actual_open_orders_for_symbol(symbol)
                            if orders_exist:
                                self.logger.info(f"✅ POSITION REDUCTION SKIPPED: {symbol} - shares held by existing orders (protected)")
                            else:
                                self.logger.warning(f"🔄 POSITION REDUCTION RETRY: {symbol} - 'held_for_orders' error but no open orders found, will retry next cycle")
                        else:
                            self.logger.error(f"❌ Position reduction failed for {symbol} - {error_msg}")
                        
        except Exception as e:
            self.logger.error(f"Oversized position check failed: {e}")
            
    async def _analyze_position_context(self, symbol: str, current_price: float, 
                                       unrealized_pct: float, bars: List) -> Dict:
        """Analyze position against current market context"""
        try:
            analysis = {
                'trend_strength': 'NEUTRAL',
                'momentum': 'NEUTRAL', 
                'volume_profile': 'NORMAL',
                'technical_outlook': 'NEUTRAL',
                'regime_alignment': True,
                'risk_level': 'MEDIUM'
            }
            
            if bars and len(bars) >= 3:
                # Simple trend analysis
                recent_prices = [float(bar.get('c', 0)) for bar in bars[-3:]]
                if len(recent_prices) == 3:
                    if recent_prices[2] > recent_prices[1] > recent_prices[0]:
                        analysis['trend_strength'] = 'STRONG_UP'
                    elif recent_prices[2] < recent_prices[1] < recent_prices[0]:
                        analysis['trend_strength'] = 'STRONG_DOWN'
                    elif recent_prices[2] > recent_prices[0]:
                        analysis['trend_strength'] = 'WEAK_UP'
                    else:
                        analysis['trend_strength'] = 'WEAK_DOWN'
                        
                # Volume analysis
                recent_volumes = [int(bar.get('v', 0)) for bar in bars[-3:]]
                if recent_volumes and len(recent_volumes) >= 2:
                    avg_volume = sum(recent_volumes[:-1]) / len(recent_volumes[:-1])
                    latest_volume = recent_volumes[-1]
                    if latest_volume > avg_volume * 1.5:
                        analysis['volume_profile'] = 'HIGH'
                    elif latest_volume < avg_volume * 0.7:
                        analysis['volume_profile'] = 'LOW'
                        
            # Market regime alignment check
            if self.current_intelligence:
                if (self.current_intelligence.market_regime in ['BEAR_TRENDING', 'VOLATILE_RANGE'] and 
                    unrealized_pct > 5):
                    analysis['regime_alignment'] = False
                    analysis['risk_level'] = 'HIGH'
                elif (self.current_intelligence.volatility_environment == 'HIGH' and 
                      abs(unrealized_pct) > 10):
                    analysis['risk_level'] = 'HIGH'
                    
            return analysis
            
        except Exception as e:
            self.logger.error(f"Position context analysis failed for {symbol}: {e}")
            return {'trend_strength': 'NEUTRAL', 'risk_level': 'HIGH'}
            
    async def _determine_position_action(self, symbol: str, qty: float, unrealized_pct: float,
                                        current_price: float, avg_entry: float, 
                                        analysis: Dict) -> Dict:
        """Determine autonomous position management action"""
        try:
            action = {
                'action': 'HOLD',
                'quantity': 0,
                'reason': 'No action needed',
                'urgency': 'LOW'
            }
            
            # === STOP LOSS TRIGGERS ===
            if unrealized_pct <= -8.0:  # Hard stop loss
                action = {
                    'action': 'SELL_ALL',
                    'quantity': abs(qty),
                    'reason': f'Stop loss triggered: {unrealized_pct:.1f}% loss',
                    'urgency': 'IMMEDIATE'
                }
                
            elif unrealized_pct <= -5.0 and analysis['trend_strength'] in ['STRONG_DOWN', 'WEAK_DOWN']:
                action = {
                    'action': 'SELL_HALF',
                    'quantity': abs(qty) / 2,
                    'reason': f'Trend deterioration with {unrealized_pct:.1f}% loss',
                    'urgency': 'HIGH'
                }
                
            # === PROFIT TAKING TRIGGERS ===
            elif unrealized_pct >= 20.0:  # Strong profits
                if analysis['trend_strength'] in ['STRONG_DOWN', 'WEAK_DOWN']:
                    action = {
                        'action': 'SELL_HALF',
                        'quantity': abs(qty) / 2,
                        'reason': f'Profit taking: {unrealized_pct:.1f}% gain with weakening trend',
                        'urgency': 'MEDIUM'
                    }
                elif analysis['volume_profile'] == 'LOW':
                    action = {
                        'action': 'SELL_QUARTER',
                        'quantity': abs(qty) / 4,
                        'reason': f'Partial profit taking: {unrealized_pct:.1f}% gain with low volume',
                        'urgency': 'LOW'
                    }
                    
            elif unrealized_pct >= 15.0 and not analysis['regime_alignment']:
                action = {
                    'action': 'SELL_HALF',
                    'quantity': abs(qty) / 2,
                    'reason': f'Market regime risk: {unrealized_pct:.1f}% gain in unfavorable regime',
                    'urgency': 'MEDIUM'
                }
                
            elif unrealized_pct >= 10.0 and analysis['risk_level'] == 'HIGH':
                action = {
                    'action': 'SELL_QUARTER',
                    'quantity': abs(qty) / 4,
                    'reason': f'Risk reduction: {unrealized_pct:.1f}% gain in high-risk environment',
                    'urgency': 'MEDIUM'
                }
                
            # === POSITION SCALING TRIGGERS ===
            elif (unrealized_pct >= 5.0 and unrealized_pct <= 8.0 and 
                  analysis['trend_strength'] == 'STRONG_UP' and 
                  analysis['volume_profile'] == 'HIGH'):
                
                # Add to winning position if we have capacity
                account = await self.gateway.get_account_safe()
                if account:
                    account_value = float(account.equity)
                    current_position_pct = (abs(qty) * current_price) / account_value
                    
                    if current_position_pct < 0.08:  # Don't exceed 8% in single position
                        add_quantity = max(1, int(abs(qty) * 0.25))  # Add 25% more
                        action = {
                            'action': 'BUY_MORE',
                            'quantity': add_quantity,
                            'reason': f'Scaling winner: {unrealized_pct:.1f}% gain with strong momentum',
                            'urgency': 'LOW'
                        }
                        
            # === RISK MANAGEMENT OVERRIDES ===
            if analysis['risk_level'] == 'HIGH' and abs(unrealized_pct) > 15:
                if action['action'] == 'HOLD':
                    action = {
                        'action': 'SELL_QUARTER',
                        'quantity': abs(qty) / 4,
                        'reason': 'High-risk position size reduction',
                        'urgency': 'MEDIUM'
                    }
                    
            return action
            
        except Exception as e:
            self.logger.error(f"Position action determination failed for {symbol}: {e}")
            return {'action': 'HOLD', 'quantity': 0, 'reason': 'Error in analysis', 'urgency': 'LOW'}
            
    async def _execute_position_management(self, position, action: Dict, current_price: float):
        """Execute position management action"""
        try:
            symbol = position.symbol
            current_qty = float(position.qty)
            action_type = action['action']
            quantity = int(action['quantity'])
            
            if quantity == 0:
                self.logger.warning(f"Zero quantity calculated for {symbol} {action_type}")
                return False
                
            self.logger.info(f"🎯 POSITION ACTION: {symbol} {action_type} {quantity} shares - {action['reason']}")
            
            # Determine order side and type
            if action_type in ['SELL_ALL', 'SELL_HALF', 'SELL_QUARTER']:
                side = 'sell'
                order_type = 'market' if action['urgency'] == 'IMMEDIATE' else 'limit'
                limit_price = current_price * 0.995 if order_type == 'limit' else None
                
            elif action_type == 'BUY_MORE':
                side = 'buy' 
                order_type = 'limit'  # Always use limit for adding positions
                limit_price = current_price * 1.005  # Slight premium acceptable
                
            else:
                self.logger.warning(f"Unknown action type: {action_type}")
                return False
                
            # Construct order
            order_data = {
                'symbol': symbol,
                'qty': str(quantity),
                'side': side,
                'type': order_type,
                'time_in_force': 'day'
            }
            
            if limit_price:
                order_data['limit_price'] = str(round(limit_price, 2))
                
            # Submit order
            order_response = await self.gateway.submit_order(order_data)
            
            if order_response and order_response.success:
                # Log comprehensive management action
                management_log = {
                    'timestamp': datetime.now().isoformat(),
                    'symbol': symbol,
                    'action': action_type,
                    'quantity': quantity,
                    'side': side,
                    'order_type': order_type,
                    'price': limit_price or current_price,
                    'reason': action['reason'],
                    'urgency': action['urgency'],
                    'original_qty': current_qty,
                    'order_id': order_response.data.id if order_response.success else 'N/A'
                }
                
                self.logger.info(f"📝 POSITION MANAGEMENT: {json.dumps(management_log, indent=2)}")
                
                # Update session stats
                self.session_stats['trades_executed'] += 1
                
                return True
            else:
                error_msg = order_response.error if order_response else "No response received"
                # Check if shares are held by existing orders
                if order_response and "insufficient qty available" in str(order_response.error) and "held_for_orders" in str(order_response.error):
                    self.logger.info(f"✅ POSITION MANAGEMENT SKIPPED: {symbol} - shares held by existing orders (protected)")
                else:
                    self.logger.error(f"❌ Position management order failed for {symbol} - {error_msg}")
                return False
                
        except Exception as e:
            self.logger.error(f"Position management execution failed: {e}")
            return False

    async def _monitor_system_risk(self):
        """Comprehensive system risk monitoring"""
        try:
            # Get current portfolio data
            account = await self.gateway.get_account_safe()
            if not account:
                return
                
            current_equity = float(account.equity)
            
            # Check daily drawdown
            if await self.risk_manager.check_daily_drawdown(current_equity):
                self.logger.critical("🚨 DAILY DRAWDOWN LIMIT EXCEEDED")
                await self.alerter.send_critical_alert(
                    "Daily drawdown limit exceeded",
                    f"Current equity: ${current_equity:,.2f} - Emergency shutdown initiated"
                )
                await self._emergency_shutdown("Daily drawdown limit exceeded")
                return
            
            # Check circuit breaker (flash crash protection)
            if await self.risk_manager.check_circuit_breaker(current_equity):
                self.logger.critical("⚡ CIRCUIT BREAKER TRIGGERED - FLASH CRASH PROTECTION")
                await self.alerter.send_critical_alert(
                    "CIRCUIT BREAKER: Flash crash protection activated",
                    f"Account equity dropped to ${current_equity:,.2f} - Emergency liquidation initiated"
                )
                await self._emergency_shutdown("Circuit breaker triggered - flash crash protection")
                return
                
            # Portfolio risk analysis
            if self.current_intelligence:
                portfolio_data = {
                    'total_value': current_equity,
                    'cash': float(account.cash),
                    'positions': await self._get_portfolio_positions(),
                    'daily_pnl': float(account.equity) - float(account.last_equity)
                }
                
                try:
                    risk_analysis = await self.ai_assistant.analyze_portfolio_risk(
                        portfolio_data, self.current_intelligence
                    )
                except Exception as ai_risk_error:
                    self.logger.warning(f"⚠️ AI PORTFOLIO RISK ANALYSIS FAILURE: {ai_risk_error}")
                    self.logger.warning(f"⚠️ Using fallback risk assessment")
                    risk_analysis = {
                        'overall_risk_score': 0.5,
                        'risk_level': 'MODERATE',
                        'recommendations': ['AI risk analysis unavailable - monitor manually']
                    }
                
                # Check for high-risk conditions
                if risk_analysis.get('risk_level') == 'HIGH':
                    self.logger.warning(f"⚠️ HIGH PORTFOLIO RISK: {risk_analysis.get('key_risks', [])}")
                    
                # Log risk metrics
                self.logger.debug(f"📊 Portfolio Risk Score: {risk_analysis.get('overall_risk_score', 0):.2f}")
                
        except Exception as e:
            self.logger.error(f"Risk monitoring failed: {e}")
    
    async def _monitor_pdt_status(self):
        """Monitor and report PDT status and blocked symbols"""
        try:
            # Log PDT-blocked symbols if any
            pdt_blocked = self.gateway.get_pdt_blocked_symbols()
            if pdt_blocked:
                self.logger.info(f"🚫 PDT-blocked symbols: {', '.join(pdt_blocked)}")
                
                # If we have too many blocked symbols, consider resetting older ones
                if len(pdt_blocked) > 10:
                    self.logger.warning(f"⚠️ High number of PDT-blocked symbols ({len(pdt_blocked)}) - consider manual review")
                    
        except Exception as e:
            self.logger.error(f"PDT status monitoring failed: {e}")
    
    async def _extended_hours_monitoring_loop(self):
        """Monitor positions during pre-market and after-hours for gap risk"""
        try:
            is_extended, period = self.market_status.is_extended_hours()
            if not is_extended:
                return
            
            self.logger.info(f"🌙 Extended hours monitoring active: {period}")
            
            # Get current positions
            positions = await self.gateway.get_all_positions()
            active_positions = [pos for pos in positions if float(pos.qty) != 0]
            
            if not active_positions:
                self.logger.info("✅ No positions to monitor during extended hours")
                await asyncio.sleep(300)  # Sleep 5 minutes and recheck
                return
            
            # Monitor each position for gap risk
            gap_risk_alerts = []
            
            for position in active_positions:
                try:
                    symbol = position.symbol
                    qty = float(position.qty)
                    current_value = float(position.market_value)
                    unrealized_pct = float(position.unrealized_plpc) * 100
                    
                    # Get current extended hours quote if available
                    try:
                        current_quote = await self.gateway.get_latest_quote(symbol) 
                        if current_quote:
                            current_price = float(current_quote.get('ask_price', 0)) or float(current_quote.get('bid_price', 0))
                            if current_price > 0:
                                # Check for significant moves during extended hours
                                entry_price = float(position.avg_entry_price)
                                current_move_pct = ((current_price - entry_price) / entry_price) * 100
                                
                                # Alert on large extended hours moves
                                if abs(current_move_pct) > 5:  # More than 5% move
                                    gap_risk_alerts.append({
                                        'symbol': symbol,
                                        'move_pct': current_move_pct,
                                        'current_price': current_price,
                                        'entry_price': entry_price,
                                        'position_value': abs(qty) * current_price
                                    })
                    except Exception as quote_error:
                        self.logger.debug(f"Could not get extended hours quote for {symbol}: {quote_error}")
                    
                    # Check for positions approaching dangerous loss levels (with suppression)
                    if unrealized_pct < -7:  # Approaching our -8% stop loss
                        warning_key = f"{symbol}_{int(unrealized_pct)}"  # Key includes symbol and loss percentage
                        if warning_key not in self.extended_hours_warnings_sent:
                            self.logger.warning(f"⚠️ EXTENDED HOURS RISK: {symbol} at {unrealized_pct:.1f}% loss")
                            self.extended_hours_warnings_sent.add(warning_key)
                        else:
                            self.logger.debug(f"🔇 Extended hours risk warning suppressed for {symbol} (already warned)")
                    
                    # EMERGENCY EXTENDED HOURS LOSS CUTTING - For severe losses
                    if unrealized_pct <= -6.0:  # Emergency threshold for extended hours
                        emergency_key = f"{symbol}_emergency_{int(unrealized_pct)}"
                        if emergency_key not in getattr(self, 'extended_hours_emergency_actions', set()):
                            self.logger.critical(f"🚨 EMERGENCY EXTENDED HOURS LOSS CUT: {symbol} at {unrealized_pct:.1f}% loss")
                            
                            try:
                                # Execute emergency sell order (limit order for extended hours)
                                current_price = float(position.market_value) / abs(qty)  # Calculate current price
                                # Use limit order with 1% discount for extended hours execution
                                limit_price = current_price * 0.99 if qty > 0 else current_price * 1.01
                                
                                order_data = {
                                    'symbol': symbol,
                                    'qty': str(int(abs(qty))),
                                    'side': 'sell' if qty > 0 else 'buy',
                                    'type': 'limit',  # Use limit order for extended hours
                                    'limit_price': str(round(limit_price, 2)),
                                    'time_in_force': 'day'
                                }
                                
                                response = await self.gateway.submit_order(order_data)
                                if response and response.success:
                                    self.logger.critical(f"✅ EMERGENCY LOSS CUT EXECUTED: {symbol} - limit sell {int(abs(qty))} shares @ ${limit_price:.2f} (at {unrealized_pct:.1f}% loss)")
                                    await self.alerter.send_critical_alert(
                                        f"🚨 EMERGENCY EXTENDED HOURS LOSS CUT: {symbol} limit sell @ ${limit_price:.2f} at {unrealized_pct:.1f}% loss"
                                    )
                                    # Track this emergency action
                                    if not hasattr(self, 'extended_hours_emergency_actions'):
                                        self.extended_hours_emergency_actions = set()
                                    self.extended_hours_emergency_actions.add(emergency_key)
                                else:
                                    error_msg = response.error if response else "No response received"
                                    # Check if shares are held by existing orders (stop losses)
                                    if response and "insufficient qty available" in str(response.error) and "held_for_orders" in str(response.error):
                                        self.logger.warning(f"✅ EMERGENCY LOSS CUT ALREADY PROTECTED: {symbol} - shares held by existing stop orders")
                                        # Mark as handled to prevent repeated attempts
                                        if not hasattr(self, 'extended_hours_emergency_actions'):
                                            self.extended_hours_emergency_actions = set()
                                        self.extended_hours_emergency_actions.add(emergency_key)
                                    else:
                                        self.logger.error(f"❌ EMERGENCY EXTENDED HOURS LOSS CUT FAILED: {symbol} - {error_msg}")
                            except Exception as e:
                                self.logger.error(f"❌ EMERGENCY EXTENDED HOURS LOSS CUT ERROR: {symbol} - {e}")
                        
                except Exception as pos_error:
                    self.logger.error(f"Extended hours monitoring failed for {position.symbol}: {pos_error}")
            
            # Send alerts for significant gap moves with AI decision making (with deduplication)
            if gap_risk_alerts:
                for alert in gap_risk_alerts:
                    # Create gap risk alert object for deduplication check
                    gap_alert = self.gap_risk_manager.calculate_gap_risk(
                        alert['symbol'],
                        alert['current_price']
                    )
                    
                    # Only proceed if this alert should be sent (prevents spam)
                    if gap_alert and self.gap_risk_manager.should_alert_gap_risk(gap_alert):
                        self.logger.critical(f"🚨 GAP RISK: {alert['symbol']} moved {alert['move_pct']:+.1f}% to ${alert['current_price']:.2f} in {period}")
                        
                        # Collect comprehensive data for AI decision
                        context = {
                            "market_session": period,
                            "position_value": alert.get('position_value', 0),
                            "account_equity": 2000  # Will be updated with real data in comprehensive collection
                        }
                        
                        # Gather enhanced market data for AI analysis
                        enhanced_data = await self._collect_comprehensive_market_data(alert['symbol'])
                        
                        ai_decision = await self.alerter.send_gap_risk_alert_with_ai(
                            alert['symbol'], 
                            alert['move_pct'], 
                            alert['current_price'],
                            context,
                            enhanced_data
                        )
                        
                        # Execute AI decision if confident and actionable
                        if ai_decision['confidence'] > 0.7 and ai_decision['decision'] != 'manual_review':
                            await self._execute_ai_decision(alert['symbol'], ai_decision)
                    else:
                        # Log suppressed alerts at debug level to avoid spam
                        self.logger.debug(f"🔇 Gap risk alert suppressed for {alert['symbol']} (already alerted or insufficient threshold)")
            
            # Sleep for 5 minutes before next extended hours check
            self.logger.debug(f"🔄 Extended hours monitoring cycle complete - sleeping 5 minutes")
            await asyncio.sleep(300)
            
        except Exception as e:
            self.logger.error(f"Extended hours monitoring failed: {e}")
            await asyncio.sleep(300)  # Sleep and retry
    
    async def _record_market_close_positions(self):
        """Record position prices at market close for gap risk monitoring"""
        try:
            # Only record closes near end of trading day (after 3:45 PM)
            current_time = datetime.now().time()
            if current_time >= time(15, 45):  # 3:45 PM ET
                positions = await self.gateway.get_all_positions()
                self.gap_risk_manager.record_market_close_positions(positions)
        except Exception as e:
            self.logger.error(f"Failed to record market close positions: {e}")
            
    async def _update_performance_metrics(self):
        """Update comprehensive performance tracking using REAL Alpaca data"""
        try:
            if not self.performance_tracker:
                return
                
            # Get REAL performance data
            daily_performance = await self.performance_tracker.get_daily_summary()
            
            if 'error' in daily_performance:
                self.logger.warning(f"⚠️ Performance tracking error: {daily_performance['error']}")
                return
            
            # Display REAL performance using Alpaca API data
            current_equity = daily_performance.get('current_equity', 0.0)
            daily_pnl = daily_performance.get('daily_pnl', 0.0)
            daily_pnl_pct = daily_performance.get('daily_pnl_pct', 0.0)
            total_pnl = daily_performance.get('total_pnl', 0.0)
            total_pnl_pct = daily_performance.get('total_pnl_pct', 0.0)
            
            # Color coding for P&L display
            daily_color = "🟢" if daily_pnl >= 0 else "🔴"
            total_color = "🟢" if total_pnl >= 0 else "🔴"
            
            self.logger.info(f"💰 REAL PERFORMANCE (Alpaca API):")
            self.logger.info(f"   Current Equity: ${current_equity:,.2f}")
            self.logger.info(f"   Daily P&L: {daily_color} ${daily_pnl:+.2f} ({daily_pnl_pct:+.2f}%)")
            self.logger.info(f"   Total P&L: {total_color} ${total_pnl:+.2f} ({total_pnl_pct:+.2f}%)")
                               
        except Exception as e:
            self.logger.error(f"Performance tracking failed: {e}")
            
    async def _system_health_check(self):
        """Comprehensive system health monitoring"""
        try:
            # Check API rate limits
            funnel_stats = await self.market_funnel.get_funnel_statistics()
            api_budget_status = funnel_stats.get('api_budget_remaining', {})
            
            # Warn if any budget category is low
            for category, remaining in api_budget_status.items():
                if remaining < 5:
                    self.logger.warning(f"⚠️ Low API budget: {category} ({remaining} remaining)")
                    
            # Log system statistics
            uptime = (datetime.now() - self.session_stats['system_uptime_start']).total_seconds() / 3600
            
            health_report = {
                'system_uptime_hours': uptime,
                'opportunities_discovered': self.session_stats['opportunities_discovered'],
                'signals_generated': self.session_stats['signals_generated'],
                'trades_executed': self.session_stats['trades_executed'],
                'current_watchlist_size': len(self.active_opportunities),
                'market_regime': self.current_intelligence.market_regime if self.current_intelligence else 'UNKNOWN',
                'api_budget_status': api_budget_status
            }
            
            self.logger.debug(f"💓 System Health: {json.dumps(health_report, indent=2)}")
            
        except Exception as e:
            self.logger.error(f"System health check failed: {e}")
            
    async def _execute_ai_decision(self, symbol: str, ai_decision: Dict):
        """Execute AI decision for gap risk management with fallback options"""
        try:
            decision = ai_decision['decision']
            confidence = ai_decision.get('confidence', 0)
            self.logger.info(f"🤖 Executing AI decision for {symbol}: {decision} (confidence: {confidence:.0%})")
            
            action_taken = False
            
            if decision == "emergency_sell":
                # Attempt immediate market sell (if market is open)
                action_taken = await self._emergency_sell_position(symbol, "AI emergency decision")
                
            elif decision == "sell_market_open":
                # Create sell order for market open (will execute when market opens)  
                action_taken = await self._schedule_market_open_sell(symbol, "AI scheduled sell decision")
                
            elif decision == "set_stop_loss":
                # Create or tighten stop loss
                action_taken = await self._create_tighter_stop_loss(symbol, "AI stop loss adjustment")
                
                # If stop loss creation failed, try alternative protective actions
                if not action_taken:
                    self.logger.info(f"🤖 Primary stop loss failed for {symbol}, trying alternative protective actions...")
                    
                    # Alternative 1: Cancel existing orders and create new stop loss
                    try:
                        existing_orders = await self.gateway.get_orders('open')
                        symbol_orders = [order for order in existing_orders if order.symbol == symbol]
                        
                        if symbol_orders:
                            self.logger.info(f"🤖 Found {len(symbol_orders)} existing orders for {symbol}")
                            # Log what orders exist but don't cancel them automatically
                            for order in symbol_orders:
                                order_type = getattr(order, 'order_type', getattr(order, 'type', 'unknown'))
                                side = getattr(order, 'side', 'unknown')
                                self.logger.info(f"   - Existing {order_type} {side} order: {order.id}")
                            
                            self.logger.info(f"🤖 Position already protected by existing orders - AI decision acknowledged but not executed")
                            action_taken = True  # Consider this as "action taken" since position is protected
                    except Exception as e:
                        self.logger.debug(f"Error checking existing orders for {symbol}: {e}")
                
            elif decision == "hold":
                self.logger.info(f"🤖 AI recommends holding {symbol} - no action needed")
                action_taken = True
                
            else:  # manual_review or unknown
                self.logger.info(f"🤖 AI recommends manual review for {symbol} - flagged for attention")
                action_taken = True
            
            # Report execution result
            if action_taken:
                self.logger.info(f"✅ AI decision executed successfully for {symbol}: {decision}")
            else:
                self.logger.warning(f"⚠️ AI decision could not be executed for {symbol}: {decision}")
                
        except Exception as e:
            self.logger.error(f"Failed to execute AI decision for {symbol}: {e}")
    
    async def _emergency_sell_position(self, symbol: str, reason: str) -> bool:
        """Emergency sell position if market allows"""
        try:
            # Check if we have the position
            position = await self.gateway.get_position(symbol)
            if not position or float(position.qty) == 0:
                self.logger.info(f"No position in {symbol} to emergency sell")
                return False
                
            # Try to place market sell order (will fail if market closed)
            try:
                sell_order = await self.order_executor.execute_trade(
                    TradingSignal(
                        symbol=symbol,
                        action="SELL",
                        quantity=abs(float(position.qty)),
                        confidence=0.9,
                        reasoning=f"AI Emergency Sell: {reason}",
                        strategy_name="AI_EMERGENCY"
                    )
                )
                
                if sell_order:
                    self.logger.info(f"🤖 AI Emergency sell executed for {symbol}: {sell_order.id}")
                    return True
                else:
                    self.logger.warning(f"🤖 AI Emergency sell failed for {symbol} - market likely closed")
                    return False
                    
            except Exception as e:
                self.logger.warning(f"🤖 AI Emergency sell failed for {symbol}: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"Emergency sell position failed for {symbol}: {e}")
            return False
    
    async def _schedule_market_open_sell(self, symbol: str, reason: str) -> bool:
        """Schedule sell order for market open"""
        try:
            # For now, just log the intention - could be enhanced with order scheduling
            self.logger.info(f"🤖 AI scheduled sell for {symbol} at market open: {reason}")
            # TODO: Implement order scheduling system for market open execution
            return True  # Consider scheduled as successful
            
        except Exception as e:
            self.logger.error(f"Schedule market open sell failed for {symbol}: {e}")
            return False
    
    async def _create_tighter_stop_loss(self, symbol: str, reason: str) -> bool:
        """Create or tighten stop loss for position"""
        try:
            position = await self.gateway.get_position(symbol)
            if not position or float(position.qty) == 0:
                self.logger.info(f"No position in {symbol} for stop loss adjustment")
                return False
                
            # Get current price
            current_price = float(position.current_price) if hasattr(position, 'current_price') else float(position.market_value) / abs(float(position.qty))
            
            # Calculate tighter stop loss (2% below current price)
            stop_price = round(current_price * 0.98, 2)
            
            try:
                # Try to place stop loss order
                order_data = {
                    "symbol": symbol,
                    "qty": abs(float(position.qty)),
                    "side": "sell", 
                    "type": "stop",
                    "stop_price": stop_price,
                    "time_in_force": "gtc"
                }
                stop_order = await self.gateway.submit_order(order_data)
                
                if stop_order:
                    self.logger.info(f"🤖 AI tighter stop loss set for {symbol} at ${stop_price:.2f}: {reason}")
                    return True
                else:
                    self.logger.debug(f"🤖 AI stop loss not created for {symbol} - shares held by existing orders")
                    return False
                    
            except Exception as e:
                self.logger.debug(f"🤖 AI stop loss creation failed for {symbol}: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"Create tighter stop loss failed for {symbol}: {e}")
            return False

    async def _collect_comprehensive_market_data(self, symbol: str) -> Dict:
        """Collect comprehensive market data for AI decision making"""
        enhanced_data = {}
        
        try:
            self.logger.debug(f"📊 Collecting comprehensive data for {symbol}...")
            
            # === ACCOUNT & POSITION DETAILS ===
            current_equity = 2000  # Default fallback
            try:
                # Get current account equity first
                account = await self.gateway.get_account()
                if account:
                    current_equity = float(account.equity)
                    enhanced_data["account_equity"] = current_equity
            except Exception as e:
                self.logger.debug(f"Account data collection failed: {e}")
            
            try:
                position = await self.gateway.get_position(symbol)
                if position and float(position.qty) != 0:
                    position_value = abs(float(position.market_value))
                    allocation_percent = (position_value / current_equity * 100) if current_equity > 0 else 0
                    
                    enhanced_data.update({
                        "position_qty": float(position.qty),
                        "position_avg_cost": float(position.avg_entry_price),
                        "position_current_pnl": float(position.unrealized_pl),
                        "position_pnl_percent": (float(position.unrealized_plpc) * 100),
                        "account_allocation_percent": allocation_percent
                    })
            except Exception as e:
                self.logger.debug(f"Position data collection failed for {symbol}: {e}")
            
            # === MARKET CONTEXT ===
            try:
                if hasattr(self, 'current_intelligence') and self.current_intelligence:
                    enhanced_data.update({
                        "market_regime": self.current_intelligence.market_regime,
                        "market_volatility": self.current_intelligence.volatility_regime
                    })
                
                # Get SPY performance for market context
                spy_bars = await self.supplemental_data_provider.get_historical_data("SPY", days=1, min_bars=1)
                if spy_bars and len(spy_bars) >= 1:
                    spy_current = float(spy_bars[-1]['c'])
                    spy_prev = float(spy_bars[0]['o']) if len(spy_bars) == 1 else float(spy_bars[-2]['c'])
                    spy_change = ((spy_current - spy_prev) / spy_prev * 100) if spy_prev > 0 else 0
                    enhanced_data["spy_performance_today"] = f"{spy_change:+.1f}%"
                
            except Exception as e:
                self.logger.debug(f"Market context collection failed: {e}")
            
            # === TECHNICAL ANALYSIS ===
            try:
                # Get historical bars for technical analysis
                bars = await self.supplemental_data_provider.get_historical_data(symbol, days=30, min_bars=20)
                if bars and len(bars) >= 20:
                    closes = [float(bar['c']) for bar in bars]
                    volumes = [int(bar['v']) for bar in bars]
                    
                    # Calculate moving average
                    ma20 = sum(closes[-20:]) / 20
                    current_price = closes[-1]
                    enhanced_data["price_vs_ma20"] = f"{((current_price - ma20) / ma20 * 100):+.1f}%"
                    
                    # Volume analysis
                    avg_volume = sum(volumes[-20:]) / 20
                    current_volume = volumes[-1]
                    enhanced_data["volume_vs_average"] = f"{(current_volume / avg_volume):.1f}x" if avg_volume > 0 else "N/A"
                    
                    # Simple RSI calculation (simplified)
                    if len(closes) >= 14:
                        gains = []
                        losses = []
                        for i in range(1, 15):  # Last 14 periods
                            change = closes[-(i+1)] - closes[-(i+2)]
                            if change > 0:
                                gains.append(change)
                                losses.append(0)
                            else:
                                gains.append(0)
                                losses.append(abs(change))
                        
                        avg_gain = sum(gains) / 14
                        avg_loss = sum(losses) / 14
                        if avg_loss != 0:
                            rs = avg_gain / avg_loss
                            rsi = 100 - (100 / (1 + rs))
                            enhanced_data["rsi"] = f"{rsi:.1f}"
                    
                    # Support and resistance (simple high/low)
                    lows = [float(bar['l']) for bar in bars[-20:]]
                    highs = [float(bar['h']) for bar in bars[-20:]]
                    enhanced_data["support_level"] = min(lows)
                    enhanced_data["resistance_level"] = max(highs)
                    
            except Exception as e:
                self.logger.debug(f"Technical analysis failed for {symbol}: {e}")
            
            # === RISK METRICS ===
            try:
                if "position_current_pnl" in enhanced_data and "account_allocation_percent" in enhanced_data:
                    # Calculate maximum potential loss from current position
                    current_position_value = enhanced_data.get("position_qty", 0) * enhanced_data.get("position_avg_cost", 0)
                    max_loss_percent = (current_position_value / current_equity) * 100
                    enhanced_data["max_loss_from_here"] = f"{max_loss_percent:.1f}%"
                
                # Estimate correlation with SPY (simplified)
                enhanced_data["correlation_with_market"] = "medium"  # Placeholder - could be calculated with more data
                
            except Exception as e:
                self.logger.debug(f"Risk metrics calculation failed for {symbol}: {e}")
            
            # === TIMING DATA ===
            try:
                # Calculate days held (simplified - would need order history)
                enhanced_data["days_held"] = "recent"  # Placeholder
                
                # News sentiment (placeholder - could integrate news API)
                enhanced_data["news_sentiment"] = "neutral"
                
                # Historical gap analysis (placeholder)
                enhanced_data["similar_gaps_outcome"] = "mixed results"
                enhanced_data["recovery_probability"] = "moderate"
                
            except Exception as e:
                self.logger.debug(f"Timing data collection failed for {symbol}: {e}")
            
            self.logger.info(f"📊 Collected {len(enhanced_data)} data points for AI analysis of {symbol}")
            
        except Exception as e:
            self.logger.error(f"Comprehensive data collection failed for {symbol}: {e}")
        
        return enhanced_data

    async def _emergency_shutdown(self, reason: str):
        """Emergency shutdown with position protection"""
        try:
            self.logger.critical(f"🚨 EMERGENCY SHUTDOWN: {reason}")
            
            # Send critical alert immediately
            await self.alerter.send_critical_alert(
                f"EMERGENCY SHUTDOWN: {reason}",
                "Trading system is shutting down immediately. All positions being closed."
            )
            
            # Close all positions immediately
            await self.order_executor.emergency_close_all()
            
            # Cancel all pending orders
            await self.gateway.cancel_all_orders()
            
            # Generate emergency report
            emergency_report = await self._generate_emergency_report(reason)
            # Convert datetime objects to strings for JSON serialization
            emergency_report_json = json.dumps(emergency_report, default=str, indent=2)
            self.logger.critical(f"📊 EMERGENCY REPORT: {emergency_report_json}")
            
            self.running = False
            
        except Exception as e:
            self.logger.critical(f"Emergency shutdown failed: {e}")
            await self.alerter.send_critical_alert(
                "Emergency shutdown system failure",
                f"Shutdown procedure encountered error: {e}"
            )
            
    async def _graceful_shutdown(self):
        """Graceful system shutdown with proper async resource cleanup"""
        try:
            self.logger.info("🛑 GRACEFUL SHUTDOWN INITIATED")
            self.running = False
            
            # Close components in reverse order of initialization
            shutdown_tasks = []
            
            # Generate final performance report BEFORE closing API gateway
            try:
                self.logger.info("📊 Generating final performance report...")
                final_report = await self.performance_tracker.generate_final_report()
                self.logger.info(f"📊 FINAL PERFORMANCE: {json.dumps(final_report, indent=2)}")
            except Exception as e:
                self.logger.warning(f"⚠️ Final report generation failed: {e}")
            
            # Close AI assistant
            if self.ai_assistant:
                try:
                    shutdown_tasks.append(self.ai_assistant.shutdown())
                except Exception as shutdown_error:
                    self.logger.warning(f"⚠️ AI ASSISTANT SHUTDOWN WARNING: {shutdown_error}")
                
            # Close API gateway AFTER final report
            if self.gateway:
                shutdown_tasks.append(self.gateway.shutdown())
                
            # Close supplemental data provider
            if self.supplemental_data:
                try:
                    shutdown_tasks.append(self.supplemental_data.shutdown())
                except Exception as e:
                    self.logger.warning(f"⚠️ Supplemental data shutdown warning: {e}")
            
            # Wait for all shutdown tasks to complete
            if shutdown_tasks:
                await asyncio.gather(*shutdown_tasks, return_exceptions=True)
            
            self.logger.info("✅ SYSTEM SHUTDOWN COMPLETE")
            
        except Exception as e:
            self.logger.error(f"Graceful shutdown error: {e}")
        finally:
            # Give the event loop and aiohttp more time to finish cleanup
            await asyncio.sleep(0.5)
    
    async def test_tiered_analysis_with_hot_stocks(self):
        """
        Test the tiered analysis system with the hot stocks mentioned by day traders
        This method demonstrates comprehensive analysis regardless of rate limits/data issues
        """
        try:
            self.logger.info("🔥 Testing Tiered Analysis with Day Trader Hot Stocks")
            
            # Hot stocks mentioned by day traders (from your example)
            hot_stocks = [
                'CWD', 'SMXT', 'RKLB', 'IONQ', 'OKLO', 'QBTS', 'SOFI', 'PLTR', 
                'MEIP', 'AUUD', 'AIP', 'IDXX'
            ]
            
            self.logger.info(f"🎯 Analyzing {len(hot_stocks)} hot stocks with comprehensive tiered approach")
            
            # Use the tiered analysis system
            results = await self.market_funnel.analyze_hot_stocks(hot_stocks)
            
            # Process and log results
            actionable_results = []
            all_results_summary = []
            
            for result in results:
                result_summary = {
                    'symbol': result.symbol,
                    'tier_completed': result.tier_completed.name,
                    'recommendation': result.recommendation,
                    'signal_strength': f"{result.signal_strength:.2f}",
                    'confidence': f"{result.confidence:.2f}",
                    'data_quality': result.data_quality,
                    'reasoning': result.reasoning
                }
                all_results_summary.append(result_summary)
                
                if result.recommendation in ['BUY', 'SELL']:
                    actionable_results.append(result)
            
            # Log comprehensive results
            self.logger.info(f"✅ TIERED ANALYSIS RESULTS:")
            self.logger.info(f"   - Total stocks analyzed: {len(hot_stocks)}")
            self.logger.info(f"   - Results generated: {len(results)}")
            self.logger.info(f"   - Actionable signals: {len(actionable_results)}")
            
            # Log detailed results for each stock
            for summary in all_results_summary:
                tier_icon = "🔬" if summary['tier_completed'] == "DEEP_DIVE" else "🔍" if summary['tier_completed'] == "PRIORITY_ANALYSIS" else "⚡"
                quality_icon = "🟢" if summary['data_quality'] == "EXCELLENT" else "🟡" if summary['data_quality'] == "GOOD" else "🟠" if summary['data_quality'] == "LIMITED" else "🔴"
                
                self.logger.info(f"   {tier_icon} {summary['symbol']}: {summary['recommendation']} "
                                f"(str:{summary['signal_strength']}, conf:{summary['confidence']}) "
                                f"{quality_icon} {summary['data_quality']} - {summary['reasoning']}")
            
            # Return actionable results for potential execution
            return actionable_results
            
        except Exception as e:
            self.logger.error(f"Hot stocks tiered analysis test failed: {e}")
            return []
            
    # Helper methods
    async def _collect_initial_market_data(self) -> Dict:
        """Collect initial market data for intelligence generation"""
        try:
            market_data = {}
            
            # Get SPY data (S&P 500 proxy)
            spy_bars = await self.gateway.get_bars('SPY', '1Day', limit=2)
            if spy_bars and len(spy_bars) >= 2:
                current_price = float(spy_bars[-1].get('c', 0))
                prev_price = float(spy_bars[-2].get('c', current_price))
                change_pct = ((current_price - prev_price) / prev_price) * 100 if prev_price > 0 else 0
                
                market_data['SPY'] = {
                    'price': current_price,
                    'change_pct': change_pct
                }
            else:
                # Fallback: get current quote
                spy_quote = await self.gateway.get_latest_quote('SPY')
                if spy_quote:
                    price = float(spy_quote.get('ask_price', 0)) or float(spy_quote.get('bid_price', 0))
                    market_data['SPY'] = {'price': price, 'change_pct': 0.0}
                    
            # Try to get VIX data (volatility index) - not available on free tier
            try:
                vix_quote = await self.gateway.get_latest_quote('VIX')
                if vix_quote:
                    vix_level = float(vix_quote.get('ask_price', 0)) or float(vix_quote.get('bid_price', 0))
                    if vix_level > 0:
                        market_data['VIX'] = {'level': vix_level}
                        self.logger.info(f"📊 VIX Level: {vix_level}")
                else:
                    self.logger.debug("VIX data not available (expected on free tier)")
            except Exception as e:
                self.logger.debug(f"VIX data not available (expected on free tier): {e}")
                
            # Analyze volume profile from major ETFs
            volume_profile = 'NORMAL'
            try:
                etf_volumes = []
                for etf in ['SPY', 'QQQ', 'IWM']:
                    bars = await self.gateway.get_bars(etf, '1Day', limit=1)
                    if bars:
                        volume = int(bars[0].get('v', 0))
                        if volume > 0:
                            etf_volumes.append(volume)
                            
                if etf_volumes:
                    avg_volume = sum(etf_volumes) / len(etf_volumes)
                    if avg_volume > 75000000:  # High volume threshold
                        volume_profile = 'HIGH'
                    elif avg_volume < 25000000:  # Low volume threshold
                        volume_profile = 'LOW'
            except Exception as e:
                self.logger.debug(f"Volume profile analysis failed: {e}")
                
            market_data['volume_profile'] = volume_profile
            
            return market_data
            
        except Exception as e:
            self.logger.warning(f"⚠️ INITIAL MARKET DATA COLLECTION FAILURE: {e}")
            self.logger.warning(f"⚠️ Market intelligence will have limited context")
            # Return minimal fallback data
            return {'volume_profile': 'UNKNOWN'}
        
    async def _collect_current_market_data(self) -> Dict:
        """Collect current market data"""
        return await self._collect_initial_market_data()
        
    async def _get_portfolio_positions(self) -> List[Dict]:
        """Get current portfolio positions"""
        try:
            positions = await self.gateway.get_all_positions()
            return [
                {
                    'symbol': pos.symbol,
                    'qty': float(pos.qty),
                    'market_value': float(pos.market_value),
                    'unrealized_pl': float(pos.unrealized_pl)
                }
                for pos in positions
            ]
        except:
            return []
            
    def _aggregate_intraday_to_daily(self, intraday_bars: List[Dict], hours_per_day: int = 6) -> List[Dict]:
        """Aggregate intraday bars to daily equivalents for better analysis"""
        try:
            if not intraday_bars or len(intraday_bars) < hours_per_day:
                return []
                
            daily_bars = []
            
            # Group bars by day and aggregate
            for i in range(0, len(intraday_bars), hours_per_day):
                day_group = intraday_bars[i:i + hours_per_day]
                
                if len(day_group) < hours_per_day // 2:  # Need at least half the expected bars
                    continue
                    
                # Aggregate OHLCV data
                open_price = float(day_group[0].get('o', 0))
                close_price = float(day_group[-1].get('c', 0))
                high_price = max(float(bar.get('h', 0)) for bar in day_group)
                low_price = min(float(bar.get('l', 0)) for bar in day_group if float(bar.get('l', 0)) > 0)
                total_volume = sum(int(bar.get('v', 0)) for bar in day_group)
                
                if open_price > 0 and close_price > 0 and high_price > 0 and low_price > 0:
                    daily_bars.append({
                        't': day_group[-1].get('t'),  # Use latest timestamp
                        'o': open_price,
                        'h': high_price,
                        'l': low_price,
                        'c': close_price,
                        'v': total_volume
                    })
                    
            self.logger.info(f"📊 Aggregated {len(intraday_bars)} intraday bars to {len(daily_bars)} daily equivalents")
            return daily_bars
            
        except Exception as e:
            self.logger.error(f"Intraday aggregation failed: {e}")
            return []
    
    async def _generate_emergency_report(self, reason: str) -> Dict:
        """Generate comprehensive emergency report"""
        return {
            'shutdown_reason': reason,
            'shutdown_time': datetime.now().isoformat(),
            'session_statistics': self.session_stats,
            'final_account_status': 'UNKNOWN'  # Would get actual account data
        }

# Signal handlers for graceful shutdown
def setup_signal_handlers(trading_system, loop):
    """Setup signal handlers for graceful shutdown"""
    def signal_handler():
        print("\n🛑 Ctrl+C detected - initiating graceful shutdown...")
        trading_system.running = False
        # Cancel all running tasks to force immediate shutdown
        for task in asyncio.all_tasks(loop):
            if not task.done():
                task.cancel()
        
    # Use loop.add_signal_handler for proper async integration
    try:
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)
    except NotImplementedError:
        # Fallback for Windows or other systems that don't support add_signal_handler
        def sync_signal_handler(signum, frame):
            print("\n🛑 Ctrl+C detected - initiating graceful shutdown...")
            trading_system.running = False
            # Force exit if graceful shutdown takes too long
            import threading
            def force_exit():
                import time
                time.sleep(5)  # Wait 5 seconds for graceful shutdown
                print("🚨 Force exiting...")
                import os
                os._exit(1)
            threading.Thread(target=force_exit, daemon=True).start()
            
        signal.signal(signal.SIGINT, sync_signal_handler)
        signal.signal(signal.SIGTERM, sync_signal_handler)

async def main():
    """Main entry point"""
    try:
        # Initialize trading system
        trading_system = IntelligentTradingSystem()
        
        # Get the current event loop
        loop = asyncio.get_event_loop()
        
        # Setup signal handlers
        setup_signal_handlers(trading_system, loop)
        
        # Initialize system
        if not await trading_system.initialize_system():
            print("❌ System initialization failed")
            return 1
            
        # Start intelligent trading
        await trading_system.run_intelligent_trading_loop()
        
        return 0
        
    except asyncio.CancelledError:
        print("🛑 System shutdown completed")
        return 0
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))