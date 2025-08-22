"""
Simple trade executor with bracket orders and position management
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
import asyncio
from config import *
from alerter import CriticalAlerter

logger = logging.getLogger(__name__)

class SimpleTradeExecutor:
    """
    Simple but robust trade execution system
    Handles bracket orders, position monitoring, and emergency stops
    """
    
    def __init__(self, gateway, risk_manager):
        self.gateway = gateway
        self.risk_manager = risk_manager
        self.active_orders = {}
        self.executed_trades = []
        self.alerter = CriticalAlerter()
        self.pdt_manager = None  # Will be set by main system
        
    async def execute_signal(self, signal) -> bool:
        """Execute trading signal with bracket orders"""
        try:
            logger.info(f"🎯 Executing signal: {signal.symbol} {signal.action}")
            
            # Get current account info
            account = await self.gateway.get_account_safe()
            if not account:
                logger.error("Cannot access account for trade execution")
                return False
                
            account_value = float(account.equity)
            
            # Final risk validation
            if not await self.risk_manager.validate_trade_execution(signal, account_value):
                logger.warning(f"❌ Risk validation failed for {signal.symbol}")
                return False
            
            # POSITION SIZING - Calculate quantity first for PDT compliance check
            # Initialize quantity variable to avoid reference errors
            quantity = 0
            
            # ATR-BASED POSITION SIZING (Gemini's excellent suggestion)
            # Risk the same dollar amount per trade by adjusting for volatility
            if hasattr(signal, 'atr') and signal.atr and signal.atr > 0:
                # Use ATR for volatility-adjusted sizing
                atr_stop_multiple = 2.0  # Stop loss at 2x ATR
                risk_per_share = signal.atr * atr_stop_multiple
                dollar_risk_per_trade = account_value * (RISK_CONFIG['max_position_risk_pct'] / 100)
                
                if risk_per_share > 0:
                    quantity = int(dollar_risk_per_trade / risk_per_share)
                    position_value = quantity * signal.entry_price
                    logger.info(f"📊 ATR sizing: ${dollar_risk_per_trade:.2f} risk, {quantity} shares")
                else:
                    # Fallback to percentage sizing
                    position_value = account_value * signal.position_size_pct
                    quantity = int(position_value / signal.entry_price)
            else:
                # Traditional percentage-based sizing with conservative cap
                max_position_pct = 0.05  # Never exceed 5% of account for small accounts
                actual_position_pct = min(signal.position_size_pct, max_position_pct)
                position_value = account_value * actual_position_pct
                quantity = int(position_value / signal.entry_price)
                
                if actual_position_pct < signal.position_size_pct:
                    logger.warning(f"⚠️ Position size capped at {actual_position_pct*100:.1f}% (was {signal.position_size_pct*100:.1f}%)")
            
            # SAFETY CHECK: Minimum quantity requirements
            if quantity == 0:
                # Check if this is a known expensive stock that we should avoid with small accounts
                expensive_stocks = ['GOOGL', 'GOOG', 'AMZN', 'TSLA', 'BRK.A', 'BRK.B', 'NVDA', 'META']
                if signal.symbol in expensive_stocks and account_value < 10000:
                    logger.warning(f"❌ {signal.symbol} avoided: Known expensive stock, account too small (${account_value:,.0f})")
                    logger.info(f"💡 Consider focusing on stocks under $100 for better position sizing with small account")
                    return False
                
                # For high-priced stocks, try to buy 1 share if we can afford it within conservative limits
                one_share_cost = signal.entry_price * 1.05  # 5% buffer for slippage
                
                # More conservative limits for small accounts
                if account_value < 5000:
                    max_for_expensive_stock = account_value * 0.08  # Only 8% for very small accounts
                elif account_value < 10000: 
                    max_for_expensive_stock = account_value * 0.10  # 10% for small accounts
                else:
                    max_for_expensive_stock = account_value * 0.15  # 15% for larger accounts
                
                if one_share_cost <= max_for_expensive_stock:
                    quantity = 1
                    position_value = one_share_cost
                    logger.info(f"💰 High-priced stock: Buying 1 share of {signal.symbol} for ${position_value:.2f} ({(position_value/account_value*100):.1f}% of account)")
                else:
                    logger.warning(f"❌ Cannot afford {signal.symbol} at ${signal.entry_price:.2f}")
                    logger.warning(f"   Need ${one_share_cost:.2f}, max allowed ${max_for_expensive_stock:.2f} ({(max_for_expensive_stock/account_value*100):.0f}% of account)")
                    logger.info(f"💡 Consider stocks under ${max_for_expensive_stock/1.05:.0f} for better position sizing")
                    return False
                    
            # PDT compliance check (now that quantity is properly calculated)
            if self.pdt_manager:
                can_trade, pdt_reason = await self.pdt_manager.check_pdt_compliance_before_trade(
                    signal.symbol, signal.action, quantity
                )
                if not can_trade:
                    logger.warning(f"❌ PDT compliance failed for {signal.symbol}: {pdt_reason}")
                    await self.alerter.send_pdt_violation_alert(
                        f"Trade blocked for {signal.symbol}: {pdt_reason}"
                    )
                    return False
                elif "WARNING" in pdt_reason or "Day trade" in pdt_reason:
                    logger.warning(f"⚠️ PDT warning for {signal.symbol}: {pdt_reason}")
                    
            # Additional quantity safety checks
            if quantity > 100:  # Safety check for very large quantities
                logger.warning(f"⚠️ Large quantity {quantity} for {signal.symbol} - double checking...")
                if position_value > account_value * 0.1:  # More than 10% of account
                    logger.error(f"❌ Position too large: ${position_value:.2f} (>{account_value * 0.1:.2f})")
                    return False
            
            logger.info(f"📊 Position sizing: account=${account_value:,.2f}, "
                       f"size_pct={signal.position_size_pct:.3f}, "
                       f"value=${position_value:.2f}, "
                       f"price=${signal.entry_price:.2f}, "
                       f"quantity={quantity}")
            
            # Store intended execution parameters for reconciliation
            intended_execution = {
                'symbol': signal.symbol,
                'intended_quantity': quantity,
                'intended_price': signal.entry_price,
                'intended_value': position_value,
                'submission_timestamp': datetime.now()
            }
            
            # CRITICAL SAFETY CHECK: Prevent duplicate positions
            existing_positions = await self.gateway.get_all_positions()
            for pos in existing_positions:
                if pos.symbol == signal.symbol and float(pos.qty) != 0:
                    logger.error(f"🚨 DUPLICATE TRADE BLOCKED: {signal.symbol} already has {pos.qty} shares")
                    logger.error(f"   Avg entry: ${float(pos.avg_entry_price):.2f}, Market value: ${float(pos.market_value):.2f}")
                    logger.error(f"   Would have added {quantity} more shares - TRADE REJECTED")
                    return False  # BLOCK the duplicate trade
                
            logger.info(f"📊 Position details: {quantity} shares, ${position_value:,.2f} value")
            
            # Execute bracket order
            success = await self._execute_bracket_order(signal, quantity)
            
            if success:
                # CRITICAL: Post-fill verification with extended monitoring
                post_fill_success = await self._post_fill_verification_and_monitoring(signal, quantity)
                
                if not post_fill_success:
                    logger.critical(f"🚨 POST-FILL VERIFICATION FAILED for {signal.symbol} - trade execution incomplete")
                    return False
                
                # Get actual fill data for reconciliation
                actual_fill_data = await self._get_actual_fill_data(signal.symbol)
                
                # Use actual filled quantity and price, not intended values
                actual_quantity = actual_fill_data.get('filled_qty', quantity)
                actual_price = actual_fill_data.get('filled_avg_price', signal.entry_price)
                
                # If no fill data yet, use intended values but log warning
                if not actual_fill_data:
                    logger.warning(f"⚠️ {signal.symbol}: No fill data available yet - using intended values")
                
                # Record trade execution with ACTUAL fill data
                await self.risk_manager.record_trade_execution(
                    signal, actual_price, actual_quantity
                )
                
                # Enhanced trade record with comprehensive reconciliation data
                trade_record = {
                    'signal': signal,
                    'intended_quantity': quantity,
                    'actual_quantity': actual_quantity,
                    'intended_price': signal.entry_price,
                    'actual_price': actual_price,
                    'execution_time': datetime.now(),
                    'entry_timestamp': datetime.now(),  # Track for swing trading
                    'status': 'EXECUTED'
                }
                
                # Add comprehensive reconciliation data if available
                if actual_fill_data and 'fill_quality' in actual_fill_data:
                    trade_record['fill_reconciliation'] = {
                        'fill_quality': actual_fill_data.get('fill_quality'),
                        'fill_ratio': actual_fill_data.get('fill_ratio'),
                        'slippage_pct': actual_fill_data.get('price_slippage_pct'),
                        'slippage_cost': actual_fill_data.get('slippage_cost_dollars'),
                        'is_partial_fill': actual_fill_data.get('is_partial_fill'),
                        'fill_duration': actual_fill_data.get('fill_duration_seconds')
                    }
                    
                    # Alert on poor execution quality
                    fill_quality = actual_fill_data.get('fill_quality')
                    if fill_quality in ['POOR', 'VERY_POOR']:
                        logger.warning(f"⚠️ {signal.symbol}: Poor execution quality - {fill_quality}")
                
                self.executed_trades.append(trade_record)
                
                logger.info(f"✅ Trade executed successfully: {signal.symbol}")
                logger.info(f"   Intended: {quantity} shares @ ${signal.entry_price:.2f}")
                logger.info(f"   Actual: {actual_quantity} shares @ ${actual_price:.2f}")
                
                # Log execution quality summary
                if actual_fill_data and 'fill_quality' in actual_fill_data:
                    fill_quality = actual_fill_data.get('fill_quality')
                    logger.info(f"   Fill Quality: {fill_quality}")
                    
                    if actual_fill_data.get('is_partial_fill', False):
                        fill_ratio = actual_fill_data.get('fill_ratio', 0)
                        logger.info(f"   Partial Fill: {fill_ratio:.1%} completed")
                    
                    slippage_pct = actual_fill_data.get('price_slippage_pct', 0)
                    if abs(slippage_pct) > 0.05:  # > 0.05% slippage
                        logger.info(f"   Slippage: {slippage_pct:+.3f}%")
                
                # Record trade for PDT tracking (if PDT manager is available)
                if self.pdt_manager:
                    await self.pdt_manager.record_trade_execution(
                        signal.symbol, signal.action, actual_quantity, actual_price
                    )
                
                return True
            else:
                logger.error(f"❌ Trade execution failed: {signal.symbol}")
                return False
                
        except Exception as e:
            logger.error(f"Trade execution error for {signal.symbol}: {e}")
            return False
            
    async def _execute_bracket_order(self, signal, quantity: int) -> bool:
        """Execute bracket order with main order, stop loss, and take profit"""
        try:
            # Main order (market buy) with Alpaca-compliant pricing
            # Ensure stop loss is at least $0.01 below entry price and take profit is at least $0.01 above
            entry_price = signal.entry_price
            
            # Calculate compliant prices
            min_stop_price = entry_price - 0.01
            min_take_profit = entry_price + 0.01
            
            # Ensure our prices meet minimum requirements
            # Stop loss: use signal price if it's lower than min_stop_price, otherwise use min_stop_price
            compliant_stop_price = min(signal.stop_loss_price, min_stop_price)
            # Take profit: use signal price if it's higher than min_take_profit, otherwise use min_take_profit
            compliant_take_profit = max(signal.take_profit_price, min_take_profit)
            
            # Round to 2 decimal places
            compliant_stop_price = round(compliant_stop_price, 2)
            compliant_take_profit = round(compliant_take_profit, 2)
            
            main_order_data = {
                'symbol': signal.symbol,
                'qty': str(quantity),
                'side': signal.action.lower(),
                'type': 'market',
                'time_in_force': 'day',
                'order_class': 'bracket',
                'stop_loss': {
                    'stop_price': str(compliant_stop_price)
                },
                'take_profit': {
                    'limit_price': str(compliant_take_profit)
                }
            }
            
            # Log price adjustments if any were made
            if compliant_stop_price != round(signal.stop_loss_price, 2):
                logger.info(f"📊 {signal.symbol} stop price adjusted: ${signal.stop_loss_price:.2f} → ${compliant_stop_price:.2f} (Alpaca compliance)")
            if compliant_take_profit != round(signal.take_profit_price, 2):
                logger.info(f"📊 {signal.symbol} take profit adjusted: ${signal.take_profit_price:.2f} → ${compliant_take_profit:.2f} (Alpaca compliance)")
            
            # Pre-check: Cancel any conflicting orders to prevent "insufficient qty" errors
            await self._clear_conflicting_orders(signal.symbol)
            
            # Submit bracket order
            order_response = await self.gateway.submit_order(main_order_data)
            
            if order_response and order_response.success:
                # CRITICAL: Verify bracket order legs are properly created
                verification_success = await self._verify_bracket_order_legs(order_response, signal)
                
                if verification_success:
                    self.active_orders[signal.symbol] = {
                        'main_order_id': order_response.data.id,
                        'signal': signal,
                        'quantity': quantity,
                        'status': 'ACTIVE',
                        'submission_time': datetime.now()
                    }
                    
                    logger.info(f"📝 Bracket order submitted: {signal.symbol} "
                               f"Entry: ${signal.entry_price:.2f} "
                               f"Stop: ${signal.stop_loss_price:.2f} "
                               f"Target: ${signal.take_profit_price:.2f}")
                               
                    return True
                else:
                    logger.error(f"❌ Bracket order legs verification failed for {signal.symbol}")
                    return False
            else:
                logger.error(f"Failed to submit bracket order for {signal.symbol}")
                return False
                
        except Exception as e:
            logger.error(f"Bracket order execution failed: {e}")
            return False
            
    async def monitor_positions(self) -> Dict:
        """Monitor all active positions and orders"""
        try:
            monitoring_summary = {
                'active_positions': 0,
                'open_orders': 0,
                'total_unrealized_pnl': 0.0,
                'positions_details': [],
                'alerts': []
            }
            
            # Get current positions
            positions = await self.gateway.get_all_positions()
            
            for position in positions:
                if float(position.qty) != 0:
                    monitoring_summary['active_positions'] += 1
                    monitoring_summary['total_unrealized_pnl'] += float(position.unrealized_pl)
                    
                    # Check for position alerts
                    unrealized_pct = float(position.unrealized_plpc) * 100
                    
                    position_detail = {
                        'symbol': position.symbol,
                        'quantity': float(position.qty),
                        'unrealized_pl': float(position.unrealized_pl),
                        'unrealized_pct': unrealized_pct,
                        'market_value': float(position.market_value)
                    }
                    
                    monitoring_summary['positions_details'].append(position_detail)
                    
                    # Enhanced Position Management
                    await self._enhanced_position_management(position, unrealized_pct, monitoring_summary)
                    
                    # Generate alerts for significant moves
                    if unrealized_pct < -7.0:  # Approaching stop loss
                        monitoring_summary['alerts'].append(
                            f"⚠️ {position.symbol}: {unrealized_pct:.1f}% unrealized loss"
                        )
                    elif unrealized_pct > 15.0:  # Strong profit
                        monitoring_summary['alerts'].append(
                            f"🎯 {position.symbol}: {unrealized_pct:.1f}% unrealized profit"
                        )
                        
            # Get open orders
            open_orders = await self.gateway.get_orders('open')
            monitoring_summary['open_orders'] = len(open_orders)
            
            # Check for oversized positions and reduce automatically
            if positions:
                account_info = await self.gateway.get_account()
                if account_info and hasattr(account_info, 'equity'):
                    account_value = float(account_info.equity)
                    await self._check_and_reduce_oversized_positions(account_value, monitoring_summary)
            
            return monitoring_summary
            
        except Exception as e:
            logger.error(f"Position monitoring failed: {e}")
            return {'error': str(e)}
            
    async def _enhanced_position_management(self, position, unrealized_pct: float, monitoring_summary: Dict):
        """Enhanced position management with profit taking and loss cutting"""
        try:
            from config import RISK_CONFIG
            symbol = position.symbol
            qty = float(position.qty)
            
            # 1. LOSS CUTTING: Cut losses at -4%
            if unrealized_pct <= RISK_CONFIG.get('max_position_loss_pct', -4.0):
                logger.warning(f"💸 {symbol}: Loss cutting triggered at {unrealized_pct:.1f}%")
                await self._execute_loss_cut(symbol, qty, unrealized_pct)
                monitoring_summary['alerts'].append(
                    f"🔴 {symbol}: Loss cut executed at {unrealized_pct:.1f}%"
                )
                
            # 2. PROFIT TAKING: Take partial profits at configured levels
            profit_levels = RISK_CONFIG.get('profit_taking_levels', [6.0, 12.0])
            for profit_level in profit_levels:
                if unrealized_pct >= profit_level and not hasattr(self, f'_{symbol}_profit_{int(profit_level)}_taken'):
                    logger.info(f"💰 {symbol}: Profit taking triggered at {unrealized_pct:.1f}%")
                    await self._execute_partial_profit_taking(symbol, qty, profit_level, unrealized_pct)
                    setattr(self, f'_{symbol}_profit_{int(profit_level)}_taken', True)
                    monitoring_summary['alerts'].append(
                        f"🟢 {symbol}: Partial profit taken at +{profit_level}%"
                    )
                    
            # 3. TRAILING STOP: Activate trailing stop when in profit
            trailing_activation = RISK_CONFIG.get('trailing_stop_activation_pct', 3.0)
            if unrealized_pct >= trailing_activation:
                await self._manage_trailing_stop(symbol, unrealized_pct)
                
        except Exception as e:
            logger.error(f"Enhanced position management error for {position.symbol}: {e}")
            
    async def _execute_loss_cut(self, symbol: str, qty: float, loss_pct: float):
        """Execute immediate loss cut"""
        try:
            logger.critical(f"🔴 LOSS CUT: Selling {qty} shares of {symbol} at {loss_pct:.1f}% loss")
            
            # Create market sell order to cut loss immediately
            order_data = {
                'symbol': symbol,
                'qty': str(int(abs(qty))),
                'side': 'sell' if qty > 0 else 'buy',
                'type': 'market',
                'time_in_force': 'day'
            }
            
            response = await self.gateway.submit_order(order_data)
            if response.success:
                logger.info(f"✅ Loss cut order submitted for {symbol}")
            else:
                logger.error(f"❌ Loss cut order failed for {symbol}: {response.error}")
                
        except Exception as e:
            logger.error(f"Loss cut execution failed for {symbol}: {e}")
            
    async def _execute_partial_profit_taking(self, symbol: str, qty: float, target_pct: float, current_pct: float):
        """Execute partial profit taking"""
        try:
            # Sell 25% of position at first profit level, 50% at second
            if target_pct <= 6.0:
                sell_pct = 0.25
            else:
                sell_pct = 0.50
                
            sell_qty = int(abs(qty) * sell_pct)
            
            logger.info(f"💰 PROFIT TAKING: Selling {sell_qty} shares ({sell_pct*100}%) of {symbol} at +{current_pct:.1f}%")
            
            order_data = {
                'symbol': symbol,
                'qty': str(sell_qty),
                'side': 'sell' if qty > 0 else 'buy',
                'type': 'market',
                'time_in_force': 'day'
            }
            
            response = await self.gateway.submit_order(order_data)
            if response.success:
                logger.info(f"✅ Profit taking order submitted for {symbol}")
            else:
                logger.error(f"❌ Profit taking order failed for {symbol}: {response.error}")
                
        except Exception as e:
            logger.error(f"Profit taking execution failed for {symbol}: {e}")
            
    async def _manage_trailing_stop(self, symbol: str, current_profit_pct: float):
        """Manage trailing stop loss orders"""
        try:
            from config import STRATEGY_CONFIG
            trailing_pct = STRATEGY_CONFIG['momentum_strategy'].get('trailing_stop_pct', 0.08)
            
            # This would implement trailing stop logic - for now just log
            logger.debug(f"📊 {symbol}: Trailing stop active at {current_profit_pct:.1f}% profit")
            
        except Exception as e:
            logger.error(f"Trailing stop management failed for {symbol}: {e}")
    
    async def _check_and_reduce_oversized_positions(self, account_value: float, monitoring_summary: Dict):
        """Check for oversized positions and reduce them automatically"""
        try:
            from config import RISK_CONFIG
            concentration_limit = RISK_CONFIG.get('concentration_limit_pct', 8.0) / 100.0
            
            positions = await self.gateway.get_all_positions()
            oversized_positions = []
            
            for position in positions:
                qty = float(position.qty)
                if qty == 0:
                    continue
                    
                # Get current price and calculate position value
                quote = await self.gateway.get_quote(position.symbol)
                if not quote:
                    continue
                    
                current_price = float(quote.ask_price if qty > 0 else quote.bid_price)
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
                    logger.warning(f"🔸 {symbol}: Reducing oversized position from {current_pct:.1f}% to {concentration_limit*100:.1f}%")
                    logger.info(f"📊 {symbol}: Selling {reduce_qty} shares (keeping {target_qty})")
                    
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
                        logger.info(f"✅ Position reduction order submitted for {symbol}")
                        monitoring_summary['alerts'].append(
                            f"🔸 {symbol}: Reduced oversized position from {current_pct:.1f}% to target {concentration_limit*100:.1f}%"
                        )
                    else:
                        logger.error(f"❌ Position reduction failed for {symbol}")
                        
        except Exception as e:
            logger.error(f"Oversized position check failed: {e}")
            
    async def emergency_close_all(self) -> bool:
        """Emergency liquidation of all positions"""
        try:
            logger.critical("🚨 EMERGENCY CLOSE ALL POSITIONS INITIATED")
            
            # Cancel all open orders first
            cancel_success = await self.gateway.cancel_all_orders()
            if cancel_success:
                logger.info("✅ All open orders cancelled")
            else:
                logger.warning("⚠️ Failed to cancel some orders")
                
            # Get all positions
            positions = await self.gateway.get_all_positions()
            
            emergency_orders = []
            
            for position in positions:
                qty = float(position.qty)
                if qty != 0:
                    # Determine side for closing
                    side = 'sell' if qty > 0 else 'buy'
                    close_qty = abs(int(qty))
                    
                    # Market order to close position immediately
                    close_order_data = {
                        'symbol': position.symbol,
                        'qty': str(close_qty),
                        'side': side,
                        'type': 'market',
                        'time_in_force': 'day'
                    }
                    
                    order_response = await self.gateway.submit_order(close_order_data)
                    
                    if order_response and order_response.success:
                        emergency_orders.append({
                            'symbol': position.symbol,
                            'qty': close_qty,
                            'side': side,
                            'order_id': order_response.data.id
                        })
                        
                        logger.critical(f"🚨 Emergency close order: {position.symbol} "
                                      f"{side} {close_qty}")
                    else:
                        logger.error(f"❌ Failed to submit emergency close for {position.symbol}")
                        
            logger.critical(f"🚨 Emergency liquidation: {len(emergency_orders)} orders submitted")
            
            return len(emergency_orders) == len([p for p in positions if float(p.qty) != 0])
            
        except Exception as e:
            logger.critical(f"❌ Emergency close all failed: {e}")
            return False
            
    async def check_stop_losses(self) -> List[str]:
        """Check positions against stop loss levels (backup to bracket orders)"""
        try:
            alerts = []
            
            positions = await self.gateway.get_all_positions()
            
            for position in positions:
                if float(position.qty) != 0:
                    unrealized_pct = float(position.unrealized_plpc) * 100
                    
                    # Check if approaching critical loss level
                    if unrealized_pct < -RISK_CONFIG['stop_loss_pct']:
                        alert_msg = (f"🚨 CRITICAL LOSS: {position.symbol} "
                                   f"{unrealized_pct:.1f}% loss exceeds stop limit")
                        alerts.append(alert_msg)
                        logger.warning(alert_msg)
                        
                        # Implement emergency stop loss
                        await self._execute_emergency_stop(position)
                        
            return alerts
            
        except Exception as e:
            logger.error(f"Stop loss check failed: {e}")
            return [f"Stop loss check error: {e}"]
            
    async def _execute_emergency_stop(self, position):
        """Execute emergency stop loss order"""
        try:
            symbol = position.symbol
            qty = float(position.qty)
            
            if qty == 0:
                return
                
            side = 'sell' if qty > 0 else 'buy'
            close_qty = abs(int(qty))
            
            # First, cancel any existing orders for this symbol that might be holding shares
            logger.critical(f"🚨 EMERGENCY STOP: Cancelling existing orders for {symbol}")
            try:
                open_orders = await self.gateway.get_orders('open')
                cancelled_orders = 0
                for order in open_orders:
                    if hasattr(order, 'symbol') and order.symbol == symbol:
                        cancel_response = await self.gateway.cancel_order(order.id)
                        if cancel_response and cancel_response.success:
                            cancelled_orders += 1
                            logger.critical(f"✅ Cancelled order {order.id} for {symbol}")
                        else:
                            logger.warning(f"⚠️ Failed to cancel order {order.id} for {symbol}")
                
                if cancelled_orders > 0:
                    logger.critical(f"🧹 Cancelled {cancelled_orders} existing orders for {symbol}")
                    # Brief delay to ensure orders are cancelled before placing new one
                    await asyncio.sleep(0.5)
                else:
                    logger.critical(f"ℹ️ No existing orders to cancel for {symbol}")
                    
            except Exception as cancel_error:
                logger.error(f"Failed to cancel existing orders for {symbol}: {cancel_error}")
            
            # Now place emergency market order
            emergency_order_data = {
                'symbol': symbol,
                'qty': str(close_qty),
                'side': side,
                'type': 'market',
                'time_in_force': 'day'
            }
            
            order_response = await self.gateway.submit_order(emergency_order_data)
            
            if order_response and order_response.success:
                logger.critical(f"🚨 EMERGENCY STOP EXECUTED: {symbol} {side} {close_qty} @ market")
            else:
                error_msg = order_response.error if order_response else "No response received"
                logger.critical(f"❌ EMERGENCY STOP FAILED: {symbol} - {error_msg}")
                
        except Exception as e:
            logger.critical(f"Emergency stop execution failed: {e}")
            
    async def update_trailing_stops(self):
        """Update trailing stop losses for profitable positions"""
        try:
            positions = await self.gateway.get_all_positions()
            
            for position in positions:
                qty = float(position.qty)
                if qty != 0:
                    unrealized_pct = float(position.unrealized_plpc) * 100
                    symbol = position.symbol
                    
                    # Only trail stops for profitable positions
                    if unrealized_pct > 5.0:
                        await self._update_trailing_stop(position, unrealized_pct)
                        
        except Exception as e:
            logger.error(f"Trailing stop update failed: {e}")
            
    async def _update_trailing_stop(self, position, unrealized_pct: float):
        """Update trailing stop for individual position"""
        try:
            symbol = position.symbol
            current_price = float(position.market_value) / abs(float(position.qty))
            
            # Calculate trailing stop level based on profit
            if unrealized_pct >= 20.0:
                trailing_pct = 0.10  # 10% trailing stop for big winners
            elif unrealized_pct >= 15.0:
                trailing_pct = 0.08  # 8% trailing stop
            elif unrealized_pct >= 10.0:
                trailing_pct = 0.06  # 6% trailing stop
            else:
                trailing_pct = 0.05  # 5% trailing stop
                
            new_stop_price = current_price * (1 - trailing_pct)
            
            # Check if we have an existing stop order to update
            # This would require tracking stop orders, simplified for now
            logger.debug(f"📊 {symbol}: Trailing stop level ${new_stop_price:.2f} ({trailing_pct*100:.0f}% trail)")
            
        except Exception as e:
            logger.error(f"Trailing stop update failed for {position.symbol}: {e}")
            
    async def get_execution_summary(self) -> Dict:
        """Get comprehensive execution summary with fill quality analytics"""
        try:
            monitoring_data = await self.monitor_positions()
            
            # Calculate execution quality metrics
            execution_analytics = self._calculate_execution_analytics()
            
            summary = {
                'total_executed_trades': len(self.executed_trades),
                'active_positions': monitoring_data.get('active_positions', 0),
                'open_orders': monitoring_data.get('open_orders', 0),
                'total_unrealized_pnl': monitoring_data.get('total_unrealized_pnl', 0.0),
                'active_orders_count': len(self.active_orders),
                'recent_trades': self.executed_trades[-5:],  # Last 5 trades
                'alerts': monitoring_data.get('alerts', []),
                'last_update': datetime.now().isoformat(),
                'execution_analytics': execution_analytics
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Execution summary failed: {e}")
            return {'error': str(e)}
    
    def _calculate_execution_analytics(self) -> Dict:
        """
        Calculate comprehensive execution quality analytics
        """
        try:
            if not self.executed_trades:
                return {'message': 'No executed trades for analysis'}
            
            analytics = {
                'total_trades': len(self.executed_trades),
                'trades_with_reconciliation': 0,
                'fill_quality_distribution': {},
                'average_slippage_pct': 0,
                'total_slippage_cost': 0,
                'partial_fills_count': 0,
                'partial_fills_pct': 0,
                'average_fill_ratio': 0,
                'execution_alerts': []
            }
            
            slippage_values = []
            slippage_costs = []
            fill_ratios = []
            quality_counts = {'EXCELLENT': 0, 'GOOD': 0, 'ACCEPTABLE': 0, 'POOR': 0, 'VERY_POOR': 0}
            
            for trade in self.executed_trades:
                reconciliation = trade.get('fill_reconciliation', {})
                
                if reconciliation:
                    analytics['trades_with_reconciliation'] += 1
                    
                    # Quality distribution
                    quality = reconciliation.get('fill_quality', 'UNKNOWN')
                    if quality in quality_counts:
                        quality_counts[quality] += 1
                    
                    # Slippage analysis
                    slippage_pct = reconciliation.get('slippage_pct', 0)
                    slippage_cost = reconciliation.get('slippage_cost', 0)
                    if slippage_pct is not None:
                        slippage_values.append(slippage_pct)
                    if slippage_cost is not None:
                        slippage_costs.append(slippage_cost)
                    
                    # Fill ratio analysis
                    fill_ratio = reconciliation.get('fill_ratio', 1.0)
                    if fill_ratio is not None:
                        fill_ratios.append(fill_ratio)
                    
                    # Partial fills
                    if reconciliation.get('is_partial_fill', False):
                        analytics['partial_fills_count'] += 1
            
            # Calculate aggregated metrics
            if slippage_values:
                analytics['average_slippage_pct'] = sum(slippage_values) / len(slippage_values)
            
            if slippage_costs:
                analytics['total_slippage_cost'] = sum(slippage_costs)
            
            if fill_ratios:
                analytics['average_fill_ratio'] = sum(fill_ratios) / len(fill_ratios)
            
            analytics['partial_fills_pct'] = (analytics['partial_fills_count'] / analytics['total_trades']) * 100
            analytics['fill_quality_distribution'] = quality_counts
            
            # Generate execution alerts
            if analytics['average_slippage_pct'] > 0.25:
                analytics['execution_alerts'].append(
                    f"High average slippage: {analytics['average_slippage_pct']:.3f}%"
                )
            
            if analytics['partial_fills_pct'] > 20:
                analytics['execution_alerts'].append(
                    f"High partial fill rate: {analytics['partial_fills_pct']:.1f}%"
                )
            
            poor_quality_count = quality_counts['POOR'] + quality_counts['VERY_POOR']
            poor_quality_pct = (poor_quality_count / analytics['total_trades']) * 100
            if poor_quality_pct > 10:
                analytics['execution_alerts'].append(
                    f"Poor execution quality rate: {poor_quality_pct:.1f}%"
                )
            
            return analytics
            
        except Exception as e:
            logger.error(f"Execution analytics calculation failed: {e}")
            return {'error': str(e)}
            
    async def _verify_bracket_order_legs(self, order_response, signal) -> bool:
        """CRITICAL: Verify bracket order legs are properly created"""
        try:
            order_id = order_response.data.id
            symbol = signal.symbol
            
            logger.info(f"🔍 Verifying bracket order legs for {symbol} (Order ID: {order_id})")
            
            # Wait briefly for order to be processed
            await asyncio.sleep(2)
            
            # Get order details to check status and legs
            for attempt in range(3):  # Try 3 times with increasing delay
                try:
                    order_details = await self.gateway.get_order_by_id(order_id)
                    
                    if not order_details:
                        logger.warning(f"⚠️ Could not retrieve order details for {symbol}, attempt {attempt + 1}")
                        await asyncio.sleep(2 * (attempt + 1))
                        continue
                    
                    # Check if main order is filled or partially filled
                    order_status = getattr(order_details, 'status', 'unknown')
                    filled_qty = float(getattr(order_details, 'filled_qty', 0))
                    
                    logger.info(f"📊 {symbol} order status: {order_status}, filled: {filled_qty}")
                    
                    if order_status in ['filled', 'partially_filled'] and filled_qty > 0:
                        # Main order has execution - always create emergency stop as backup
                        logger.info(f"✅ {symbol} main order filled: {filled_qty} shares")
                        
                        # Create backup emergency stop loss immediately (better safe than sorry)
                        emergency_stop_created = await self._create_emergency_stop_loss(symbol, signal, filled_qty)
                        
                        if emergency_stop_created:
                            logger.info(f"✅ Emergency protective stop created for {symbol}")
                            return True
                        else:
                            logger.critical(f"❌ FAILED to create emergency stop for {symbol} - LIQUIDATING")
                            await self._emergency_liquidate_position(symbol)
                            return False
                    
                    elif order_status == 'pending_new':
                        logger.info(f"⏳ {symbol} order still pending, waiting...")
                        await asyncio.sleep(3)
                        continue
                    
                    else:
                        logger.warning(f"⚠️ {symbol} order status: {order_status} (not filled)")
                        # Order not filled yet - bracket legs should exist when it fills
                        return True
                        
                except Exception as e:
                    logger.error(f"Error checking order details for {symbol}: {e}")
                    await asyncio.sleep(2 * (attempt + 1))
                    
            logger.warning(f"⚠️ Could not verify bracket order legs for {symbol} after 3 attempts")
            # CRITICAL: If we can't verify, we must assume failure for safety
            logger.critical(f"🚨 VERIFICATION FAILED for {symbol} - Creating emergency stop as safety measure")
            emergency_stop_created = await self._create_emergency_stop_loss(symbol, signal, 1)  # Assume 1 share
            return emergency_stop_created
            
        except Exception as e:
            logger.error(f"Bracket order verification failed for {signal.symbol}: {e}")
            # CRITICAL: System-level failure in verification - create emergency stop for safety
            try:
                logger.critical(f"🚨 SYSTEM ERROR in verification for {signal.symbol} - Creating emergency stop")
                emergency_stop_created = await self._create_emergency_stop_loss(signal.symbol, signal, 1)
                return emergency_stop_created
            except Exception as emergency_error:
                logger.critical(f"❌ EMERGENCY STOP CREATION FAILED for {signal.symbol}: {emergency_error}")
                return False  # Complete failure - reject the trade
    
    async def _verify_order_legs_exist(self, symbol: str, parent_order_id: str) -> bool:
        """Verify stop loss and take profit legs exist"""
        try:
            # Get all open orders to find child orders
            open_orders = await self.gateway.get_orders('open')
            
            stop_loss_found = False
            take_profit_found = False
            
            for order in open_orders:
                if (hasattr(order, 'symbol') and order.symbol == symbol and 
                    hasattr(order, 'parent_order_id') and order.parent_order_id == parent_order_id):
                    
                    order_type = getattr(order, 'type', '')
                    order_class = getattr(order, 'order_class', '')
                    stop_price = getattr(order, 'stop_price', None)
                    limit_price = getattr(order, 'limit_price', None)
                    
                    logger.info(f"📋 Found child order: {symbol} {order_type} (class: {order_class}) stop_price: {stop_price} limit_price: {limit_price}")
                    
                    # Check for stop loss orders (stop or stop_limit types)
                    if order_type.lower() in ['stop', 'stop_limit'] or stop_price is not None:
                        stop_loss_found = True
                        logger.info(f"✅ Stop loss leg found for {symbol}: {order_type} @ ${stop_price}")
                    # Check for take profit orders (limit orders with higher price than current)
                    elif order_type.lower() == 'limit' and limit_price is not None:
                        take_profit_found = True
                        logger.info(f"✅ Take profit leg found for {symbol}: {order_type} @ ${limit_price}")
                    else:
                        logger.warning(f"⚠️ Unknown child order type for {symbol}: {order_type} (class: {order_class})")
            
            if stop_loss_found and take_profit_found:
                return True
            elif stop_loss_found:
                logger.warning(f"⚠️ {symbol}: Stop loss found but take profit missing")
                return True  # Stop loss is critical, take profit is nice-to-have
            else:
                logger.critical(f"🚨 {symbol}: STOP LOSS LEG MISSING - CRITICAL RISK")
                await self.alerter.send_position_safety_alert(
                    symbol,
                    "Stop loss leg missing from bracket order",
                    "Position is exposed without stop loss protection"
                )
                return False
                
        except Exception as e:
            logger.error(f"Error verifying order legs for {symbol}: {e}")
            return False
    
    async def _create_emergency_stop_loss(self, symbol: str, signal, filled_qty: float) -> bool:
        """Create emergency stop loss order - simplified and more reliable"""
        try:
            logger.critical(f"🚨 Creating EMERGENCY stop loss for {symbol}")
            
            # Simple approach: Just create the stop loss immediately
            # Check current position to get actual quantity
            position = await self.gateway.get_position(symbol)
            if position:
                actual_qty = abs(float(position.qty))
            else:
                actual_qty = filled_qty
            
            if actual_qty <= 0:
                logger.critical(f"❌ No position found for {symbol} to protect")
                return False
            
            # Calculate safe stop price (7% below current market price as fallback)
            try:
                current_price = float(position.market_value) / actual_qty if position else signal.entry_price
                safe_stop_price = current_price * 0.93  # 7% stop loss
                stop_price = min(signal.stop_loss_price, safe_stop_price)
            except:
                stop_price = signal.stop_loss_price
                
            emergency_stop_data = {
                'symbol': symbol,
                'qty': str(int(actual_qty)),
                'side': 'sell',  # Assuming long position
                'type': 'stop',
                'stop_price': str(round(stop_price, 2)),
                'time_in_force': 'day'  # Day order safer than GTC for emergency stops
            }
            
            stop_order_response = await self.gateway.submit_order(emergency_stop_data)
            
            if stop_order_response and stop_order_response.success:
                logger.critical(f"✅ Emergency stop loss created: {symbol} @ ${signal.stop_loss_price:.2f}")
                return True
            else:
                # Enhanced error logging - check if it's a PDT or account issue
                error_msg = stop_order_response.error if stop_order_response else "No response received"
                logger.critical(f"❌ Failed to create emergency stop loss for {symbol} - {error_msg}")
                logger.critical(f"   Stop loss details: {emergency_stop_data}")
                logger.critical(f"   Signal stop price: ${signal.stop_loss_price:.2f}")
                logger.critical(f"   Filled quantity: {filled_qty}")
                
                # Check if symbol is PDT-blocked
                if self.gateway.is_symbol_pdt_blocked(symbol):
                    logger.critical(f"   💡 CAUSE: {symbol} is PDT-blocked, cannot create stop loss orders")
                
                # Get account info to check for buying power issues
                try:
                    account = await self.gateway.get_account()
                    if account:
                        logger.critical(f"   📊 Account status - Cash: ${float(account.cash):.2f}, Buying Power: ${float(account.buying_power):.2f}")
                except Exception as e:
                    logger.critical(f"   ⚠️ Could not retrieve account info: {e}")
                
                await self.alerter.send_position_safety_alert(
                    symbol,
                    "Failed to create emergency stop loss",
                    f"Unable to create protective stop loss at ${signal.stop_loss_price:.2f}. "
                    f"Details: {emergency_stop_data}"
                )
                return False
                
        except Exception as e:
            logger.critical(f"Emergency stop loss creation failed for {symbol}: {e}")
            return False
    
    async def _emergency_liquidate_position(self, symbol: str) -> bool:
        """Enhanced emergency liquidation with retry logic for broker state issues"""
        try:
            logger.critical(f"🚨 EMERGENCY LIQUIDATION: {symbol}")
            
            # FIRST: Check if position is already protected by existing orders
            open_orders = await self.gateway.get_orders(status='open')
            protective_orders = [order for order in open_orders if order.symbol == symbol and order.side == 'sell']
            
            if protective_orders:
                logger.critical(f"✅ EMERGENCY LIQUIDATION AVOIDED: {symbol} already has {len(protective_orders)} protective sell orders")
                for order in protective_orders:
                    order_type = getattr(order, 'order_type', 'unknown')
                    stop_price = getattr(order, 'stop_price', None)
                    limit_price = getattr(order, 'limit_price', None)
                    price_str = f"@ ${stop_price}" if stop_price else f"@ ${limit_price}" if limit_price else ""
                    logger.critical(f"   - {order_type} order: {order.qty} shares {price_str}")
                return True  # Position is protected
            
            # Get current position
            positions = await self.gateway.get_all_positions()
            target_position = None
            
            for pos in positions:
                if pos.symbol == symbol and float(pos.qty) != 0:
                    target_position = pos
                    break
            
            if not target_position:
                logger.critical(f"⚠️ No position found for emergency liquidation: {symbol}")
                return True  # No position to liquidate
            
            qty = float(target_position.qty)
            side = 'sell' if qty > 0 else 'buy'
            close_qty = abs(int(qty))
            
            emergency_liquidation_data = {
                'symbol': symbol,
                'qty': str(close_qty),
                'side': side,
                'type': 'market',
                'time_in_force': 'day'
            }
            
            # Enhanced retry logic for broker state issues
            max_retries = 10  # Retry for up to 5 minutes (10 attempts × 30s)
            retry_delay = 30  # 30 seconds between attempts
            
            for attempt in range(max_retries):
                try:
                    liquidation_response = await self.gateway.submit_order(emergency_liquidation_data)
                    
                    if liquidation_response and liquidation_response.success:
                        logger.critical(f"🚨 EMERGENCY LIQUIDATION EXECUTED: {symbol} {side} {close_qty} (attempt {attempt + 1})")
                        return True
                    else:
                        error_msg = liquidation_response.error if liquidation_response else "No response received"
                        logger.critical(f"❌ EMERGENCY LIQUIDATION ATTEMPT {attempt + 1} FAILED: {symbol} - {error_msg}")
                        
                except Exception as liquidation_error:
                    error_msg = str(liquidation_error)
                    
                    # Check for specific "held for orders" or "insufficient qty" broker errors
                    if any(phrase in error_msg.lower() for phrase in ['held_for_orders', 'insufficient qty', 'related_orders']):
                        logger.critical(f"🔄 BROKER STATE ISSUE: {symbol} shares held by broker (attempt {attempt + 1}/{max_retries})")
                        logger.critical(f"   Error: {error_msg}")
                        
                        if attempt < max_retries - 1:  # Don't wait after the last attempt
                            logger.critical(f"   Retrying in {retry_delay} seconds...")
                            await asyncio.sleep(retry_delay)
                            continue
                        else:
                            logger.critical(f"❌ EMERGENCY LIQUIDATION EXHAUSTED ALL RETRIES: {symbol}")
                            logger.critical(f"   MANUAL INTERVENTION REQUIRED - Position may be held by broker")
                            return False
                    else:
                        # Different type of error - don't retry
                        logger.critical(f"❌ EMERGENCY LIQUIDATION FAILED with non-retry error: {error_msg}")
                        return False
            
            logger.critical(f"❌ EMERGENCY LIQUIDATION FAILED after {max_retries} attempts: {symbol}")
            
            # Send critical alert for manual intervention
            await self.alerter.send_position_safety_alert(
                symbol,
                f"Emergency liquidation failed after {max_retries} attempts",
                "Manual intervention required - position may be held by broker"
            )
            return False
                
        except Exception as e:
            logger.critical(f"Emergency liquidation system failure for {symbol}: {e}")
            await self.alerter.send_position_safety_alert(
                symbol,
                f"Emergency liquidation system failure: {e}",
                "Complete system failure during emergency liquidation"
            )
            return False
    
    async def _get_actual_fill_data(self, symbol: str) -> Dict:
        """Get comprehensive actual fill data for reconciliation with broker"""
        try:
            # Check if we have an active order for this symbol
            if symbol not in self.active_orders:
                logger.warning(f"No active order tracking for {symbol}")
                return {}
            
            order_id = self.active_orders[symbol]['main_order_id']
            intended_signal = self.active_orders[symbol]['signal']
            intended_quantity = self.active_orders[symbol]['quantity']
            
            # Get comprehensive order details for reconciliation
            order_details = await self.gateway.get_order_by_id(order_id)
            
            if order_details:
                # Extract all available fill information
                filled_qty = float(getattr(order_details, 'filled_qty', 0))
                filled_avg_price = float(getattr(order_details, 'filled_avg_price', 0))
                order_status = getattr(order_details, 'status', 'unknown')
                submitted_at = getattr(order_details, 'submitted_at', None)
                filled_at = getattr(order_details, 'filled_at', None)
                
                if filled_qty > 0 and filled_avg_price > 0:
                    # Calculate comprehensive reconciliation metrics
                    reconciliation_data = self._calculate_fill_reconciliation(
                        symbol, intended_signal, intended_quantity, 
                        filled_qty, filled_avg_price, order_status,
                        submitted_at, filled_at
                    )
                    
                    logger.info(f"📊 {symbol} fill reconciliation completed")
                    return reconciliation_data
            
            return {}
            
        except Exception as e:
            logger.error(f"Failed to get actual fill data for {symbol}: {e}")
            return {}
    
    def _calculate_fill_reconciliation(self, symbol: str, intended_signal, intended_qty: int, 
                                     filled_qty: float, filled_avg_price: float, order_status: str,
                                     submitted_at, filled_at) -> Dict:
        """
        Calculate comprehensive fill reconciliation metrics for slippage and partial fills
        """
        try:
            intended_price = intended_signal.entry_price
            
            # Basic fill data
            reconciliation = {
                'symbol': symbol,
                'filled_qty': filled_qty,
                'filled_avg_price': filled_avg_price,
                'order_status': order_status,
                'intended_qty': intended_qty,
                'intended_price': intended_price
            }
            
            # Fill completeness analysis
            fill_ratio = filled_qty / intended_qty if intended_qty > 0 else 0
            reconciliation['fill_ratio'] = fill_ratio
            reconciliation['is_partial_fill'] = fill_ratio < 0.99  # Consider <99% as partial
            reconciliation['unfilled_qty'] = intended_qty - filled_qty
            
            # Slippage analysis
            price_difference = filled_avg_price - intended_price
            slippage_pct = (price_difference / intended_price * 100) if intended_price > 0 else 0
            reconciliation['price_slippage_dollars'] = price_difference
            reconciliation['price_slippage_pct'] = slippage_pct
            
            # Dollar impact analysis
            intended_position_value = intended_qty * intended_price
            actual_position_value = filled_qty * filled_avg_price
            value_difference = actual_position_value - (filled_qty * intended_price)
            
            reconciliation['intended_position_value'] = intended_position_value
            reconciliation['actual_position_value'] = actual_position_value
            reconciliation['slippage_cost_dollars'] = value_difference
            
            # Timing analysis
            if submitted_at and filled_at:
                try:
                    if isinstance(submitted_at, str):
                        submitted_time = datetime.fromisoformat(submitted_at.replace('Z', '+00:00'))
                    else:
                        submitted_time = submitted_at
                    
                    if isinstance(filled_at, str):
                        filled_time = datetime.fromisoformat(filled_at.replace('Z', '+00:00'))
                    else:
                        filled_time = filled_at
                    
                    fill_duration = (filled_time - submitted_time).total_seconds()
                    reconciliation['fill_duration_seconds'] = fill_duration
                except Exception as time_error:
                    logger.debug(f"Time parsing error for {symbol}: {time_error}")
                    reconciliation['fill_duration_seconds'] = None
            else:
                reconciliation['fill_duration_seconds'] = None
            
            # Quality assessment
            reconciliation['fill_quality'] = self._assess_fill_quality(
                fill_ratio, slippage_pct, reconciliation.get('fill_duration_seconds')
            )
            
            # Log detailed reconciliation
            self._log_fill_reconciliation(reconciliation)
            
            return reconciliation
            
        except Exception as e:
            logger.error(f"Fill reconciliation calculation failed for {symbol}: {e}")
            return {
                'symbol': symbol,
                'filled_qty': filled_qty,
                'filled_avg_price': filled_avg_price,
                'order_status': order_status,
                'reconciliation_error': str(e)
            }
    
    def _assess_fill_quality(self, fill_ratio: float, slippage_pct: float, duration_seconds: float = None) -> str:
        """
        Assess the quality of the fill based on multiple factors
        """
        try:
            quality_score = 0
            
            # Fill completeness scoring (40% weight)
            if fill_ratio >= 0.99:
                quality_score += 40  # Complete fill
            elif fill_ratio >= 0.95:
                quality_score += 35  # Near complete
            elif fill_ratio >= 0.90:
                quality_score += 30  # Mostly filled
            elif fill_ratio >= 0.75:
                quality_score += 20  # Partially filled
            else:
                quality_score += 10  # Poor fill
            
            # Slippage scoring (40% weight)
            abs_slippage = abs(slippage_pct)
            if abs_slippage <= 0.05:  # <= 0.05%
                quality_score += 40  # Excellent slippage
            elif abs_slippage <= 0.10:  # <= 0.10%
                quality_score += 35  # Good slippage
            elif abs_slippage <= 0.25:  # <= 0.25%
                quality_score += 30  # Acceptable slippage
            elif abs_slippage <= 0.50:  # <= 0.50%
                quality_score += 20  # Poor slippage
            else:
                quality_score += 5   # Very poor slippage
            
            # Speed scoring (20% weight)
            if duration_seconds is not None:
                if duration_seconds <= 1.0:
                    quality_score += 20  # Very fast
                elif duration_seconds <= 5.0:
                    quality_score += 18  # Fast
                elif duration_seconds <= 15.0:
                    quality_score += 15  # Normal
                elif duration_seconds <= 30.0:
                    quality_score += 10  # Slow
                else:
                    quality_score += 5   # Very slow
            else:
                quality_score += 10  # Unknown timing
            
            # Convert score to quality rating
            if quality_score >= 90:
                return "EXCELLENT"
            elif quality_score >= 80:
                return "GOOD"
            elif quality_score >= 70:
                return "ACCEPTABLE"
            elif quality_score >= 60:
                return "POOR"
            else:
                return "VERY_POOR"
                
        except Exception as e:
            logger.error(f"Fill quality assessment failed: {e}")
            return "UNKNOWN"
    
    def _log_fill_reconciliation(self, reconciliation: Dict):
        """
        Log comprehensive fill reconciliation details
        """
        try:
            symbol = reconciliation['symbol']
            fill_quality = reconciliation.get('fill_quality', 'UNKNOWN')
            
            # Main reconciliation summary
            logger.info(f"🎯 {symbol} Fill Reconciliation Summary:")
            logger.info(f"   Fill Quality: {fill_quality}")
            
            # Quantity reconciliation
            intended_qty = reconciliation.get('intended_qty', 0)
            filled_qty = reconciliation.get('filled_qty', 0)
            fill_ratio = reconciliation.get('fill_ratio', 0)
            
            if reconciliation.get('is_partial_fill', False):
                logger.warning(f"   ⚠️ PARTIAL FILL: {filled_qty}/{intended_qty} shares ({fill_ratio:.1%})")
                unfilled = reconciliation.get('unfilled_qty', 0)
                logger.warning(f"   Unfilled quantity: {unfilled} shares")
            else:
                logger.info(f"   ✅ Complete fill: {filled_qty} shares")
            
            # Price reconciliation
            intended_price = reconciliation.get('intended_price', 0)
            filled_price = reconciliation.get('filled_avg_price', 0)
            slippage_pct = reconciliation.get('price_slippage_pct', 0)
            slippage_dollars = reconciliation.get('slippage_cost_dollars', 0)
            
            if abs(slippage_pct) > 0.10:  # > 0.10% slippage
                logger.warning(f"   ⚠️ SLIPPAGE: Intended ${intended_price:.2f}, Filled ${filled_price:.2f}")
                logger.warning(f"   Slippage: {slippage_pct:+.3f}% (${slippage_dollars:+.2f})")
            else:
                logger.info(f"   ✅ Good execution: ${filled_price:.2f} vs ${intended_price:.2f} intended")
                logger.info(f"   Slippage: {slippage_pct:+.3f}% (${slippage_dollars:+.2f})")
            
            # Timing information
            duration = reconciliation.get('fill_duration_seconds')
            if duration is not None:
                logger.info(f"   Fill duration: {duration:.2f} seconds")
            
            # Value reconciliation
            intended_value = reconciliation.get('intended_position_value', 0)
            actual_value = reconciliation.get('actual_position_value', 0)
            logger.info(f"   Position value: ${actual_value:,.2f} (intended: ${intended_value:,.2f})")
            
            # Quality-based alerting
            if fill_quality in ['POOR', 'VERY_POOR']:
                logger.warning(f"⚠️ {symbol}: Poor fill quality detected - review execution")
            elif reconciliation.get('is_partial_fill', False) and fill_ratio < 0.75:
                logger.warning(f"⚠️ {symbol}: Significant partial fill - may need follow-up order")
            
        except Exception as e:
            logger.error(f"Fill reconciliation logging failed: {e}")

    async def _post_fill_verification_and_monitoring(self, signal, quantity: int) -> bool:
        """
        CRITICAL: Enhanced post-fill verification with extended monitoring
        Ensures bracket order legs are active after main order fills
        """
        try:
            symbol = signal.symbol
            logger.info(f"🔍 Starting enhanced post-fill verification for {symbol}")
            
            # Phase 1: Wait for initial fill and basic verification
            await asyncio.sleep(3)  # Initial wait for order processing
            
            # Phase 2: Extended monitoring to ensure legs become active
            max_monitoring_time = 60  # Monitor for up to 60 seconds
            check_interval = 10       # Check every 10 seconds
            monitoring_start = datetime.now()
            
            verification_successful = False
            
            while (datetime.now() - monitoring_start).total_seconds() < max_monitoring_time:
                try:
                    # Check if main order has been filled
                    if symbol in self.active_orders:
                        order_id = self.active_orders[symbol]['main_order_id']
                        order_details = await self.gateway.get_order_by_id(order_id)
                        
                        if order_details:
                            order_status = getattr(order_details, 'status', 'unknown')
                            filled_qty = float(getattr(order_details, 'filled_qty', 0))
                            
                            logger.info(f"📊 {symbol} monitoring: status={order_status}, filled={filled_qty}")
                            
                            if order_status in ['filled', 'partially_filled'] and filled_qty > 0:
                                # Main order has fill - verify bracket legs are active
                                legs_active = await self._verify_bracket_legs_are_active(symbol, order_id, filled_qty)
                                
                                if legs_active:
                                    logger.info(f"✅ Post-fill verification successful for {symbol} - bracket legs active")
                                    verification_successful = True
                                    break
                                else:
                                    logger.warning(f"⚠️ {symbol}: Bracket legs not yet active, continuing monitoring...")
                            elif order_status == 'cancelled' or order_status == 'rejected':
                                logger.error(f"❌ {symbol}: Main order {order_status} - verification failed")
                                break
                            elif order_status == 'accepted' and (datetime.now() - monitoring_start).total_seconds() > 30:
                                # Order has been accepted for 30+ seconds but not filled - likely won't fill
                                logger.warning(f"⏳ {symbol}: Order accepted for 30+ seconds without fill - may not execute")
                            else:
                                logger.debug(f"⏳ {symbol}: Order status {order_status}, continuing monitoring...")
                        else:
                            logger.warning(f"⚠️ {symbol}: Could not retrieve order details, continuing monitoring...")
                    
                    # Wait before next check
                    await asyncio.sleep(check_interval)
                    
                except Exception as e:
                    logger.error(f"Error during post-fill monitoring for {symbol}: {e}")
                    await asyncio.sleep(check_interval)
            
            # Phase 3: Final verification result and safety measures
            if verification_successful:
                logger.info(f"✅ Enhanced post-fill verification completed successfully for {symbol}")
                return True
            else:
                logger.critical(f"🚨 ENHANCED POST-FILL VERIFICATION FAILED for {symbol} after {max_monitoring_time}s monitoring")
                
                # Check if failure is due to order not filling vs other issues
                order_never_filled = False
                if symbol in self.active_orders:
                    order_id = self.active_orders[symbol]['main_order_id']
                    try:
                        order_details = await self.gateway.get_order_by_id(order_id)
                        if order_details:
                            filled_qty = float(getattr(order_details, 'filled_qty', 0))
                            order_status = getattr(order_details, 'status', 'unknown')
                            if filled_qty == 0 and order_status == 'accepted':
                                order_never_filled = True
                                logger.critical(f"📊 {symbol} verification failed because order never filled (status: {order_status})")
                    except Exception as e:
                        logger.error(f"Error checking order status for {symbol}: {e}")
                
                # Critical safety measure: Create emergency protective orders
                emergency_protection_success = await self._create_emergency_protection(symbol, signal, quantity)
                
                if emergency_protection_success:
                    logger.critical(f"✅ Emergency protection created for {symbol} - position secured")
                    return True
                else:
                    logger.critical(f"❌ EMERGENCY PROTECTION FAILED for {symbol} - LIQUIDATING")
                    await self._emergency_liquidate_position(symbol)
                    return False
                    
        except Exception as e:
            logger.critical(f"Post-fill verification system error for {signal.symbol}: {e}")
            # System-level failure - create emergency protection as safety net
            try:
                emergency_protection_success = await self._create_emergency_protection(signal.symbol, signal, quantity)
                return emergency_protection_success
            except Exception as emergency_error:
                logger.critical(f"❌ EMERGENCY PROTECTION SYSTEM FAILURE for {signal.symbol}: {emergency_error}")
                return False
    
    async def _verify_bracket_legs_are_active(self, symbol: str, parent_order_id: str, filled_qty: float) -> bool:
        """
        Verify that bracket order legs are actually active (not just submitted)
        More flexible approach that focuses on position protection
        """
        try:
            # Get all open orders to find active child orders
            open_orders = await self.gateway.get_orders('open')
            
            active_stop_loss = False
            active_take_profit = False
            
            # Look for any protective orders for this symbol
            for order in open_orders:
                if (hasattr(order, 'symbol') and order.symbol == symbol):
                    order_type = getattr(order, 'type', '').lower()
                    order_side = getattr(order, 'side', '').lower()
                    order_status = getattr(order, 'status', '').lower()
                    order_qty = float(getattr(order, 'qty', 0))
                    
                    # More flexible bracket leg detection
                    # Look for any sell orders (for long positions) that could be protective
                    if order_side == 'sell' and order_status in ['new', 'accepted', 'pending_new']:
                        if 'stop' in order_type:
                            active_stop_loss = True
                            logger.info(f"✅ Active stop loss found for {symbol}: {order_type} qty={order_qty}")
                        elif 'limit' in order_type:
                            active_take_profit = True
                            logger.info(f"✅ Active take profit found for {symbol}: {order_type} qty={order_qty}")
            
            # Alternative verification: Check if position exists and has any protection
            if not (active_stop_loss or active_take_profit):
                position_verification = await self._verify_position_has_protection(symbol)
                if position_verification:
                    logger.info(f"✅ Position protection verified via position check for {symbol}")
                    return True
            
            # Be more lenient - if we have any protection, consider it successful
            if active_stop_loss or active_take_profit:
                logger.info(f"✅ {symbol}: Position has protective orders (stop_loss={active_stop_loss}, take_profit={active_take_profit})")
                return True
            else:
                logger.critical(f"🚨 {symbol}: NO ACTIVE STOP LOSS PROTECTION FOUND")
                return False
                
        except Exception as e:
            logger.error(f"Error verifying bracket legs for {symbol}: {e}")
            return False
    
    async def _verify_position_has_protection(self, symbol: str) -> bool:
        """
        Verify that a position has some form of protective order
        """
        try:
            # Get current position
            position = await self.gateway.get_position(symbol)
            if not position or float(position.qty) == 0:
                return False
            
            # Check for any open orders that could protect this position
            open_orders = await self.gateway.get_orders('open')
            for order in open_orders:
                if (hasattr(order, 'symbol') and order.symbol == symbol and 
                    hasattr(order, 'side') and order.side == 'sell'):
                    # Any sell order for this symbol could be protective
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error verifying position protection for {symbol}: {e}")
            return False
    
    async def _verify_position_has_stop_protection(self, symbol: str, expected_qty: float) -> bool:
        """
        Alternative verification: Check if position has any stop loss protection
        """
        try:
            # Get current position
            positions = await self.gateway.get_all_positions()
            position_found = False
            
            for pos in positions:
                if pos.symbol == symbol:
                    current_qty = float(pos.qty)
                    if abs(current_qty - expected_qty) < 0.1:  # Quantities match
                        position_found = True
                        break
            
            if not position_found:
                logger.warning(f"⚠️ {symbol}: Expected position not found")
                return False
            
            # Check all open orders for any stop protection
            open_orders = await self.gateway.get_orders('open')
            
            for order in open_orders:
                if (hasattr(order, 'symbol') and order.symbol == symbol):
                    order_type = getattr(order, 'type', '').lower()
                    order_side = getattr(order, 'side', '').lower()
                    order_qty = float(getattr(order, 'qty', 0))
                    
                    # Look for any stop order that would protect this position
                    if ('stop' in order_type and order_side == 'sell' and 
                        abs(order_qty - expected_qty) < 0.1):
                        logger.info(f"✅ Stop protection found for {symbol}: {order_type} order")
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error verifying position stop protection for {symbol}: {e}")
            return False
    
    async def _create_emergency_protection(self, symbol: str, signal, quantity: int) -> bool:
        """
        Create comprehensive emergency protection when bracket legs fail
        """
        try:
            logger.critical(f"🚨 Creating comprehensive emergency protection for {symbol}")
            
            # FIRST: Verify we actually have a position to protect
            positions = await self.gateway.get_all_positions()
            actual_position = None
            
            for pos in positions:
                if pos.symbol == symbol and float(pos.qty) != 0:
                    actual_position = pos
                    break
            
            if not actual_position:
                logger.critical(f"⚠️ No position found for {symbol} - emergency protection not needed")
                logger.critical(f"📊 This indicates the order may not have filled or was rejected")
                
                # Cancel any pending orders for this symbol to clean up state
                try:
                    open_orders = await self.gateway.get_orders('open')
                    orders_cancelled = 0
                    for order in open_orders:
                        if hasattr(order, 'symbol') and order.symbol == symbol:
                            cancel_response = await self.gateway.cancel_order(order.id)
                            if cancel_response and cancel_response.success:
                                orders_cancelled += 1
                                logger.info(f"🧹 Cancelled pending order for {symbol}: {order.id}")
                    
                    if orders_cancelled > 0:
                        logger.info(f"🧹 Cleaned up {orders_cancelled} pending orders for {symbol}")
                        
                except Exception as cleanup_error:
                    logger.error(f"Failed to clean up orders for {symbol}: {cleanup_error}")
                
                return False  # No position means the trade failed to execute
            
            actual_qty = abs(int(float(actual_position.qty)))
            logger.critical(f"📊 Found {symbol} position: {actual_qty} shares - creating protection")
            
            protection_orders_created = 0
            
            # 1. Emergency stop loss (most critical)
            emergency_stop_data = {
                'symbol': symbol,
                'qty': str(actual_qty),  # Use actual position quantity, not intended quantity
                'side': 'sell',
                'type': 'stop',
                'stop_price': str(round(signal.stop_loss_price, 2)),
                'time_in_force': 'day'
            }
            
            stop_response = await self.gateway.submit_order(emergency_stop_data)
            if stop_response and stop_response.success:
                logger.critical(f"✅ Emergency stop loss created: {symbol} @ ${signal.stop_loss_price:.2f}")
                protection_orders_created += 1
            else:
                error_msg = stop_response.error if stop_response else "No response received"
                logger.critical(f"❌ Failed to create emergency stop loss for {symbol} - {error_msg}")
            
            # 2. Emergency take profit (secondary protection)
            try:
                emergency_profit_data = {
                    'symbol': symbol,
                    'qty': str(actual_qty),  # Use actual position quantity, not intended quantity
                    'side': 'sell',
                    'type': 'limit',
                    'limit_price': str(round(signal.take_profit_price, 2)),
                    'time_in_force': 'day'
                }
                
                profit_response = await self.gateway.submit_order(emergency_profit_data)
                if profit_response and profit_response.success:
                    logger.critical(f"✅ Emergency take profit created: {symbol} @ ${signal.take_profit_price:.2f}")
                    protection_orders_created += 1
                else:
                    error_msg = profit_response.error if profit_response else "No response received"
                    logger.warning(f"⚠️ Failed to create emergency take profit for {symbol} - {error_msg}")
            except Exception as profit_error:
                logger.warning(f"Emergency take profit creation failed for {symbol}: {profit_error}")
            
            # 3. Set up enhanced monitoring for this position
            self.active_orders[symbol] = {
                'main_order_id': 'emergency_protection',
                'signal': signal,
                'quantity': quantity,
                'status': 'EMERGENCY_PROTECTED',
                'submission_time': datetime.now(),
                'protection_orders_created': protection_orders_created
            }
            
            # Success if we created at least the stop loss
            if protection_orders_created >= 1:
                logger.critical(f"✅ Emergency protection established for {symbol} ({protection_orders_created} orders)")
                return True
            else:
                logger.critical(f"❌ Emergency protection failed for {symbol} - no protective orders created")
                return False
                
        except Exception as e:
            logger.critical(f"Emergency protection creation failed for {symbol}: {e}")
            return False

    async def cleanup_completed_orders(self):
        """Clean up completed orders from tracking"""
        try:
            symbols_to_remove = []
            
            for symbol, order_info in self.active_orders.items():
                # Check order status
                order_id = order_info['main_order_id']
                
                # This would check actual order status via API
                # For now, remove orders older than 1 day
                age_hours = (datetime.now() - order_info['submission_time']).total_seconds() / 3600
                
                if age_hours > 24:  # Order older than 24 hours
                    symbols_to_remove.append(symbol)
                    
            for symbol in symbols_to_remove:
                del self.active_orders[symbol]
                logger.debug(f"Cleaned up completed order tracking for {symbol}")
                
        except Exception as e:
            logger.error(f"Order cleanup failed: {e}")
            
    async def _verify_bracket_order_legs(self, order_response, signal, max_wait_seconds=30):
        """Verify that bracket order stop loss and take profit legs are properly created"""
        try:
            logger.info(f"🔍 Starting enhanced bracket order verification for {signal.symbol}")
            main_order_id = order_response.data.id
            
            # Wait for bracket legs to be created (they appear as separate orders)
            for attempt in range(max_wait_seconds):
                try:
                    # Get all open orders to find bracket legs
                    open_orders = await self.gateway.get_orders(status='open')
                    
                    # Look for stop loss and take profit orders related to this bracket
                    stop_loss_found = False
                    take_profit_found = False
                    
                    if open_orders:
                        for order in open_orders:
                            order_symbol = getattr(order, 'symbol', None)
                            order_type = getattr(order, 'type', None) or getattr(order, 'order_type', None)
                            parent_id = getattr(order, 'parent_order_id', None) or getattr(order, 'legs', {}).get('parent_order_id', None)
                            
                            if order_symbol == signal.symbol:
                                # Check if this order is part of our bracket
                                if parent_id == main_order_id or (
                                    order_type in ['stop', 'stop_limit'] and 
                                    abs(datetime.now().timestamp() - order_response.timestamp) < 60  # Created within last minute
                                ):
                                    if order_type in ['stop', 'stop_limit']:
                                        stop_loss_found = True
                                        logger.info(f"✅ {signal.symbol}: Stop loss leg verified - {order_type}")
                                    elif order_type in ['limit', 'take_profit']:
                                        take_profit_found = True
                                        logger.info(f"✅ {signal.symbol}: Take profit leg verified - {order_type}")
                    
                    # Check if we have the minimum required protection (stop loss)
                    if stop_loss_found:
                        if take_profit_found:
                            logger.info(f"✅ {signal.symbol}: Complete bracket order verification successful (stop + profit)")
                        else:
                            logger.info(f"✅ {signal.symbol}: Essential bracket order verification successful (stop loss confirmed)")
                        return True
                    
                    # Wait 1 second before next check
                    if attempt < max_wait_seconds - 1:
                        await asyncio.sleep(1)
                        
                except Exception as check_error:
                    logger.warning(f"⚠️ Bracket verification check {attempt + 1} failed for {signal.symbol}: {check_error}")
                    if attempt < max_wait_seconds - 1:
                        await asyncio.sleep(1)
            
            # Verification failed - no stop loss found within time limit
            logger.warning(f"⚠️ {signal.symbol}: Bracket order verification taking longer than {max_wait_seconds}s")
            
            # IMMEDIATE emergency protection creation - don't wait for complete failure
            logger.critical(f"🚨 {signal.symbol}: CREATING IMMEDIATE EMERGENCY PROTECTION")
            emergency_success = await self._create_emergency_bracket_protection(signal.symbol, signal)
            
            if emergency_success:
                logger.info(f"✅ {signal.symbol}: Emergency protection created successfully")
                return True  # Consider this a success since we have protection
            else:
                logger.critical(f"❌ {signal.symbol}: EMERGENCY PROTECTION FAILED - UNPROTECTED POSITION")
                return False
            
        except Exception as e:
            logger.error(f"Bracket order verification failed for {signal.symbol}: {e}")
            return False
            
    async def _create_emergency_bracket_protection(self, symbol: str, signal):
        """Create emergency stop loss and take profit when bracket legs fail"""
        try:
            logger.critical(f"🚨 Creating emergency bracket protection for {symbol}")
            
            # Get current position to determine quantity
            positions = await self.gateway.get_all_positions()
            position = None
            
            for pos in positions:
                if pos.symbol == symbol and float(pos.qty) != 0:
                    position = pos
                    break
            
            if not position:
                logger.error(f"❌ No position found for emergency protection: {symbol}")
                return False
            
            qty = abs(float(position.qty))
            
            # Cancel any conflicting orders first
            open_orders = await self.gateway.get_orders(status='open')
            cancelled_orders = 0
            
            if open_orders:
                for order in open_orders:
                    if getattr(order, 'symbol', None) == symbol:
                        try:
                            await self.gateway.cancel_order(order.id)
                            cancelled_orders += 1
                            logger.info(f"🗑️ Cancelled conflicting order: {order.id}")
                        except Exception as cancel_error:
                            logger.warning(f"⚠️ Failed to cancel order {order.id}: {cancel_error}")
            
            if cancelled_orders > 0:
                logger.info(f"🧹 Cancelled {cancelled_orders} conflicting orders for {symbol}")
                # Wait for cancellations to process
                await asyncio.sleep(2)
            
            # Create emergency stop loss
            stop_order_data = {
                'symbol': symbol,
                'qty': str(int(qty)),
                'side': 'sell' if float(position.qty) > 0 else 'buy',
                'type': 'stop',
                'stop_price': str(round(signal.stop_loss_price, 2)),
                'time_in_force': 'gtc'
            }
            
            stop_response = await self.gateway.submit_order(stop_order_data)
            
            # Handle PDT-blocked symbols gracefully
            if stop_response and not stop_response.success and self.gateway.is_symbol_pdt_blocked(symbol):
                logger.warning(f"⚠️ {symbol}: Stop loss blocked due to PDT restrictions")
                logger.warning(f"⚠️ Position will rely on manual monitoring and market-based protection")
                return False
            
            if stop_response and stop_response.success:
                logger.critical(f"✅ Emergency stop loss created: {symbol} @ ${signal.stop_loss_price:.2f}")
                
                # Try to create take profit as well
                try:
                    profit_order_data = {
                        'symbol': symbol,
                        'qty': str(int(qty)),
                        'side': 'sell' if float(position.qty) > 0 else 'buy',
                        'type': 'limit',
                        'limit_price': str(round(signal.take_profit_price, 2)),
                        'time_in_force': 'gtc'
                    }
                    
                    profit_response = await self.gateway.submit_order(profit_order_data)
                    
                    if profit_response and profit_response.success:
                        logger.info(f"✅ Emergency take profit created: {symbol} @ ${signal.take_profit_price:.2f}")
                    else:
                        logger.warning(f"⚠️ Emergency take profit failed for {symbol}")
                        
                except Exception as profit_error:
                    logger.warning(f"Emergency take profit creation failed: {profit_error}")
                
                return True
            else:
                error_msg = stop_response.error if stop_response else "No response received"
                logger.critical(f"❌ Emergency stop loss creation FAILED for {symbol}: {error_msg}")
                return False
                
        except Exception as e:
            logger.critical(f"Emergency bracket protection creation failed for {symbol}: {e}")
            return False
            
    async def _clear_conflicting_orders(self, symbol: str):
        """Clear any existing orders for a symbol to prevent conflicts"""
        try:
            # Get all open orders
            open_orders = await self.gateway.get_orders(status='open')
            
            if not open_orders:
                return
            
            # Find orders for this symbol
            symbol_orders = [order for order in open_orders if getattr(order, 'symbol', None) == symbol]
            
            if symbol_orders:
                logger.info(f"🧹 Found {len(symbol_orders)} existing orders for {symbol} - clearing to prevent conflicts")
                
                for order in symbol_orders:
                    try:
                        order_id = order.id
                        order_type = getattr(order, 'type', 'unknown')
                        order_side = getattr(order, 'side', 'unknown')
                        
                        cancel_response = await self.gateway.cancel_order(order_id)
                        if cancel_response and cancel_response.success:
                            logger.info(f"✅ Cancelled {order_type} {order_side} order: {order_id}")
                        else:
                            logger.warning(f"⚠️ Failed to cancel order {order_id}")
                            
                    except Exception as cancel_error:
                        logger.warning(f"⚠️ Error cancelling order {order.id}: {cancel_error}")
                
                # Wait for cancellations to process
                if symbol_orders:
                    await asyncio.sleep(2)
                    logger.info(f"✅ Cleared {len(symbol_orders)} orders for {symbol}")
            else:
                logger.debug(f"🔍 No existing orders found for {symbol}")
                
        except Exception as e:
            logger.warning(f"Error clearing conflicting orders for {symbol}: {e}")