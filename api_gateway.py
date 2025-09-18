"""
Resilient Alpaca API Gateway with comprehensive error handling and rate limiting
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import aiohttp
from dataclasses import dataclass
from config import *

logger = logging.getLogger(__name__)

@dataclass
class ApiResponse:
    """Standardized API response wrapper"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    status_code: Optional[int] = None
    rate_limit_remaining: Optional[int] = None

class ResilientAlpacaGateway:
    """
    Resilient API gateway for Alpaca with comprehensive error handling,
    rate limiting, and connection management
    """
    
    def __init__(self):
        self.session = None
        self.trading_client = None
        self.data_client = None
        self.base_url = "https://paper-api.alpaca.markets" if API_CONFIG['paper_trading'] else "https://api.alpaca.markets"
        self.data_url = "https://data.alpaca.markets"
        
        # Rate limiting
        self.request_timestamps = []
        self.rate_limit_lock = asyncio.Lock()
        
        # Connection health
        self.last_successful_request = None
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        
    async def initialize(self) -> bool:
        """Initialize the API gateway with authentication"""
        try:
            # Validate credentials
            if not API_CONFIG['alpaca_key_id'] or not API_CONFIG['alpaca_secret_key']:
                logger.error("Missing Alpaca API credentials")
                return False
                
            # Create HTTP session
            headers = {
                'APCA-API-KEY-ID': API_CONFIG['alpaca_key_id'],
                'APCA-API-SECRET-KEY': API_CONFIG['alpaca_secret_key'],
                'Content-Type': 'application/json'
            }
            
            timeout = aiohttp.ClientTimeout(total=API_CONFIG['request_timeout'])
            self.session = aiohttp.ClientSession(headers=headers, timeout=timeout)
            
            # Test connection
            test_response = await self._make_request('GET', '/v2/account')
            if not test_response.success:
                logger.error(f"API connection test failed: {test_response.error}")
                return False
                
            logger.info("✅ Alpaca API Gateway initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Gateway initialization failed: {e}")
            return False
            
    async def shutdown(self):
        """Clean shutdown of the gateway with proper connection handling"""
        try:
            if self.session and not self.session.closed:
                # Give pending requests time to complete
                await asyncio.sleep(0.1)
                await self.session.close()
                # Wait for the underlying connections to close
                await asyncio.sleep(0.1)
                self.session = None
                logger.info("✅ API Gateway session closed cleanly")
        except Exception as e:
            logger.warning(f"⚠️ Gateway shutdown warning: {e}")
        finally:
            # Ensure session is set to None even if close failed
            self.session = None
            
    async def _make_request(self, method: str, endpoint: str, data: Dict = None,
                          params: Dict = None, retry_count: int = 0) -> ApiResponse:
        """Make HTTP request with comprehensive error handling and retries"""

        # CRITICAL: Check and recover session if None
        if self.session is None:
            logger.warning("⚠️ API session is None - attempting recovery...")
            if not await self.initialize():
                return ApiResponse(success=False, error="Failed to recover API session")

        # Rate limiting check
        await self._enforce_rate_limits()
        
        try:
            url = f"{self.base_url}{endpoint}"
            
            async with self.session.request(
                method=method,
                url=url,
                json=data,
                params=params
            ) as response:
                
                # Track request for rate limiting
                self.request_timestamps.append(datetime.now())
                
                # Parse response
                try:
                    response_data = await response.json()
                except:
                    response_data = await response.text()
                    
                # Handle rate limiting
                rate_limit_remaining = response.headers.get('X-RateLimit-Remaining')
                
                if response.status in [200, 201, 204]:  # Include 201 (Created) and 204 (No Content) as success
                    self.last_successful_request = datetime.now()
                    self.consecutive_failures = 0
                    
                    return ApiResponse(
                        success=True,
                        data=response_data,
                        status_code=response.status,
                        rate_limit_remaining=int(rate_limit_remaining) if rate_limit_remaining else None
                    )
                    
                elif response.status == 429:  # Rate limited
                    self.consecutive_failures += 1
                    backoff_time = min(60, API_CONFIG['retry_backoff_factor'] ** retry_count * (1 + self.consecutive_failures))
                    logger.warning(f"Rate limit exceeded (failure #{self.consecutive_failures}), backing off for {backoff_time:.1f}s...")
                    
                    if retry_count < API_CONFIG['max_retries']:
                        await asyncio.sleep(backoff_time)
                        return await self._make_request(method, endpoint, data, params, retry_count + 1)
                    
                else:
                    error_msg = f"HTTP {response.status}: {response_data}"
                    self.consecutive_failures += 1
                    
                    return ApiResponse(
                        success=False,
                        error=error_msg,
                        status_code=response.status,
                        rate_limit_remaining=int(rate_limit_remaining) if rate_limit_remaining else None
                    )
                    
        except asyncio.TimeoutError:
            logger.warning(f"Request timeout for {endpoint}")
            self.consecutive_failures += 1
            
            if retry_count < API_CONFIG['max_retries']:
                await asyncio.sleep(API_CONFIG['retry_backoff_factor'] ** retry_count)
                return await self._make_request(method, endpoint, data, params, retry_count + 1)
                
            return ApiResponse(success=False, error="Request timeout")
            
        except Exception as e:
            logger.error(f"Request failed for {endpoint}: {e}")
            self.consecutive_failures += 1
            
            if retry_count < API_CONFIG['max_retries']:
                await asyncio.sleep(API_CONFIG['retry_backoff_factor'] ** retry_count)
                return await self._make_request(method, endpoint, data, params, retry_count + 1)
                
            return ApiResponse(success=False, error=str(e))
            
    async def _enforce_rate_limits(self):
        """Enforce API rate limits"""
        async with self.rate_limit_lock:
            now = datetime.now()
            
            # Clean old timestamps (older than 1 minute)
            cutoff_time = now - timedelta(minutes=1)
            self.request_timestamps = [
                ts for ts in self.request_timestamps if ts > cutoff_time
            ]
            
            # Check if we're approaching rate limit
            requests_per_minute = len(self.request_timestamps)
            max_requests = int(RATE_LIMIT_CONFIG['max_requests_per_minute'] * 
                             RATE_LIMIT_CONFIG['rate_limit_buffer'])
                             
            if requests_per_minute >= max_requests:
                sleep_time = 60 - (now - self.request_timestamps[0]).total_seconds()
                if sleep_time > 0:
                    logger.debug(f"Rate limit approaching, sleeping {sleep_time:.2f}s")
                    await asyncio.sleep(sleep_time)
                    
    # Account and Portfolio Methods
    async def get_account_safe(self):
        """Safely get account information with error handling"""
        try:
            response = await self._make_request('GET', '/v2/account')
            if response.success:
                return self._parse_account_data(response.data)
            else:
                logger.error(f"Failed to get account: {response.error}")
                return None
        except Exception as e:
            logger.error(f"Account request failed: {e}")
            return None
    
    async def get_account(self):
        """Get account information (alias for get_account_safe for compatibility)"""
        return await self.get_account_safe()
    
    async def get_clock(self):
        """Get market clock information"""
        try:
            response = await self._make_request('GET', '/v2/clock')
            if response.success:
                # Return parsed clock data with proper attributes
                class Clock:
                    def __init__(self, data):
                        self.timestamp = data.get('timestamp')
                        self.is_open = data.get('is_open', False)
                        self.next_open = data.get('next_open')
                        self.next_close = data.get('next_close')
                
                return Clock(response.data)
            else:
                logger.error(f"Failed to get clock: {response.error}")
                return None
        except Exception as e:
            logger.error(f"Clock request failed: {e}")
            return None
            
    async def get_all_positions(self):
        """Get all current positions"""
        try:
            response = await self._make_request('GET', '/v2/positions')
            if response.success:
                return [self._parse_position_data(pos) for pos in response.data]
            else:
                logger.error(f"Failed to get positions: {response.error}")
                return []
        except Exception as e:
            logger.error(f"Positions request failed: {e}")
            return []
            
    async def get_position(self, symbol: str):
        """Get position for specific symbol"""
        try:
            response = await self._make_request('GET', f'/v2/positions/{symbol}')
            if response.success:
                return self._parse_position_data(response.data)
            else:
                return None
        except Exception as e:
            logger.error(f"Position request failed for {symbol}: {e}")
            return None
            
    # Order Management Methods
    async def submit_order(self, order_data: Dict):
        """Submit a new order with enhanced PDT checking"""
        try:
            # Pre-check if this symbol is known to be PDT-blocked
            if hasattr(self, '_pdt_blocked_symbols') and order_data['symbol'] in self._pdt_blocked_symbols:
                logger.warning(f"Skipping order for {order_data['symbol']} - known PDT violation risk")
                return ApiResponse(success=False, error="Symbol is PDT-blocked")
            
            response = await self._make_request('POST', '/v2/orders', data=order_data)
            if response.success:
                logger.info(f"Order submitted: {order_data['symbol']} {order_data['side']} {order_data['qty']}")
                order_result = self._parse_order_data(response.data)
                return ApiResponse(success=True, data=order_result)
            else:
                # Enhanced error handling for common scenarios
                if response.status_code == 403 and '40310100' in str(response.error):
                    # PDT violation - log with clear explanation
                    logger.error(f"PDT VIOLATION: Order blocked for {order_data['symbol']} - Pattern Day Trading rules exceeded")
                    logger.error(f"Account equity below $25,000 and day trade limit reached")
                    # Mark this symbol as PDT-blocked to prevent repeated attempts
                    if not hasattr(self, '_pdt_blocked_symbols'):
                        self._pdt_blocked_symbols = set()
                    self._pdt_blocked_symbols.add(order_data['symbol'])
                elif response.status_code == 403 and '40310000' in str(response.error) and 'insufficient qty available' in str(response.error):
                    # Shares held by existing orders - this is expected for stop loss scenarios
                    logger.debug(f"Order not submitted for {order_data['symbol']} - shares held by existing orders (expected for protected positions)")
                else:
                    logger.error(f"Order submission failed: {response.error}")
                return response  # Return the failed ApiResponse instead of None
        except Exception as e:
            logger.error(f"Order submission error: {e}")
            return ApiResponse(success=False, error=str(e))
    
    def is_symbol_pdt_blocked(self, symbol: str) -> bool:
        """Check if symbol is currently PDT-blocked"""
        return hasattr(self, '_pdt_blocked_symbols') and symbol in self._pdt_blocked_symbols
    
    def reset_pdt_blocks(self):
        """Reset PDT blocked symbols (call at start of new trading day)"""
        if hasattr(self, '_pdt_blocked_symbols'):
            blocked_count = len(self._pdt_blocked_symbols)
            self._pdt_blocked_symbols.clear()
            logger.info(f"Reset {blocked_count} PDT-blocked symbols for new trading day")
    
    def get_pdt_blocked_symbols(self) -> set:
        """Get currently PDT-blocked symbols"""
        return getattr(self, '_pdt_blocked_symbols', set())
            
    async def cancel_order(self, order_id: str):
        """Cancel an existing order"""
        try:
            response = await self._make_request('DELETE', f'/v2/orders/{order_id}')
            if response.success:
                logger.info(f"Order {order_id} cancelled")
                return response
            else:
                logger.error(f"Order cancellation failed: {response.error}")
                return response
        except Exception as e:
            logger.error(f"Order cancellation error: {e}")
            return ApiResponse(success=False, error=str(e))
            
    async def cancel_all_orders(self):
        """Cancel all pending orders"""
        try:
            response = await self._make_request('DELETE', '/v2/orders')
            if response.success:
                logger.info("All orders cancelled")
                return True
            else:
                logger.error(f"Bulk order cancellation failed: {response.error}")
                return False
        except Exception as e:
            logger.error(f"Bulk order cancellation error: {e}")
            return False
            
    async def get_orders(self, status: str = 'open'):
        """Get orders by status"""
        try:
            params = {'status': status}
            response = await self._make_request('GET', '/v2/orders', params=params)
            if response.success:
                return [self._parse_order_data(order) for order in response.data]
            else:
                logger.error(f"Orders request failed: {response.error}")
                return []
        except Exception as e:
            logger.error(f"Orders request error: {e}")
            return []
    
    async def get_order_by_id(self, order_id: str):
        """Get specific order by ID"""
        try:
            response = await self._make_request('GET', f'/v2/orders/{order_id}')
            if response.success:
                return self._parse_order_data(response.data)
            else:
                logger.error(f"Order {order_id} request failed: {response.error}")
                return None
        except Exception as e:
            logger.error(f"Order {order_id} request error: {e}")
            return None
            
    # Market Data Methods
    async def get_bars(self, symbol: str, timeframe: str, limit: int = 100, 
                      start: datetime = None, end: datetime = None):
        """Get historical bars for symbol"""
        try:
            # Handle different timeframe formats for Alpaca API
            timeframe_mapping = {
                '1Day': '1Day',
                '4Hour': '4Hour', 
                '1Hour': '1Hour',
                '30Min': '30Min',
                '15Min': '15Min',
                '5Min': '5Min',
                '1Min': '1Min'
            }
            
            alpaca_timeframe = timeframe_mapping.get(timeframe, timeframe)
            
            params = {
                'timeframe': alpaca_timeframe,
                'limit': limit,
                'asof': None,
                'feed': None,
                'adjustment': 'raw'
            }
            
            # Remove None values
            params = {k: v for k, v in params.items() if v is not None}
            
            if start:
                params['start'] = start.strftime('%Y-%m-%d')
            if end:
                params['end'] = end.strftime('%Y-%m-%d')
                
            # Use correct data API endpoint format
            endpoint = f"/v2/stocks/{symbol}/bars"
            response = await self._make_data_request('GET', endpoint, params=params)
            
            if response.success:
                # Debug: Log the response structure
                logger.debug(f"Bars response structure for {symbol}: {list(response.data.keys())}")
                
                # Alpaca returns data in nested format - try multiple extraction methods
                bars_data = []
                
                # Method 1: Direct bars key
                if 'bars' in response.data:
                    bars_data = response.data['bars']
                    
                # Method 2: Symbol-keyed data
                elif symbol in response.data:
                    bars_data = response.data[symbol]
                    
                # Method 3: Sometimes it's nested under symbol -> bars
                elif symbol in response.data and isinstance(response.data[symbol], dict):
                    symbol_data = response.data[symbol]
                    if 'bars' in symbol_data:
                        bars_data = symbol_data['bars']
                        
                # Method 4: Check if the whole response is the bars array
                elif isinstance(response.data, list):
                    bars_data = response.data
                    
                logger.debug(f"Extracted {len(bars_data) if bars_data else 0} bars for {symbol}")
                
                # Validate bar data freshness for the most recent bar
                if bars_data and len(bars_data) > 0:
                    try:
                        latest_bar = bars_data[-1]
                        bar_time = latest_bar.get('t')
                        if bar_time:
                            if isinstance(bar_time, str):
                                bar_timestamp = datetime.fromisoformat(bar_time.replace('Z', '+00:00'))
                            else:
                                bar_timestamp = datetime.fromtimestamp(bar_time)
                            
                            # For daily bars, allow up to 24 hours staleness
                            # For intraday bars, allow up to 1 hour staleness
                            max_age_hours = 24 if timeframe == '1Day' else 1
                            now = datetime.now(bar_timestamp.tzinfo) if bar_timestamp.tzinfo else datetime.now()
                            age_hours = (now - bar_timestamp).total_seconds() / 3600
                            
                            if age_hours > max_age_hours:
                                logger.warning(f"⚠️ STALE BARS: {symbol} latest bar is {age_hours:.1f} hours old")
                    except Exception as bar_timestamp_error:
                        logger.debug(f"Could not validate bar timestamps for {symbol}: {bar_timestamp_error}")
                
                return bars_data if bars_data else []
            else:
                # Enhanced error handling for common subscription issues
                if (response.status_code == 403 and 
                    ('subscription does not permit querying recent SIP data' in str(response.error) or
                     'SIP data' in str(response.error) or
                     'querying recent' in str(response.error))):
                    # This is expected on free tier - log once per symbol, not repeatedly
                    if not hasattr(self, '_sip_warnings_logged'):
                        self._sip_warnings_logged = set()
                    
                    if symbol not in self._sip_warnings_logged:
                        logger.warning(f"⚠️ SIP data unavailable for {symbol} (free tier limitation)")
                        self._sip_warnings_logged.add(symbol)
                    # Don't spam logs with repeated SIP errors
                    logger.debug(f"SIP data request failed for {symbol} (expected on free tier)")
                else:
                    logger.error(f"Bars request failed for {symbol}: {response.error}")
                    logger.error(f"Status code: {response.status_code}")
                    # Try to provide helpful debug info
                    if response.status_code == 400:
                        logger.error(f"Bad request - check parameters: timeframe={timeframe}, limit={limit}")
                    elif response.status_code == 404:
                        logger.error(f"Symbol not found or endpoint incorrect: {symbol}")
                    elif response.status_code == 422:
                        logger.error(f"Unprocessable entity - data format issue")
                return []
        except Exception as e:
            logger.error(f"Bars request error for {symbol}: {e}")
            return []
            
    async def get_latest_quote(self, symbol: str):
        """Get latest quote for symbol"""
        try:
            endpoint = f"/v2/stocks/{symbol}/quotes/latest"
            response = await self._make_data_request('GET', endpoint)
            
            if response.success:
                raw_quote = response.data.get('quote')
                if raw_quote:
                    # Validate data freshness (stale data protection)
                    quote_time = raw_quote.get('t')  # Alpaca uses 't' for timestamp
                    if quote_time:
                        try:
                            # Parse timestamp (Alpaca format)
                            if isinstance(quote_time, str):
                                quote_timestamp = datetime.fromisoformat(quote_time.replace('Z', '+00:00'))
                            else:
                                quote_timestamp = datetime.fromtimestamp(quote_time)
                            
                            # Check if data is stale (older than 5 minutes)
                            now = datetime.now(quote_timestamp.tzinfo) if quote_timestamp.tzinfo else datetime.now()
                            age_minutes = (now - quote_timestamp).total_seconds() / 60
                            
                            if age_minutes > 5:
                                logger.warning(f"⚠️ STALE DATA WARNING: {symbol} quote is {age_minutes:.1f} minutes old")
                                if age_minutes > 15:
                                    logger.error(f"🚨 CRITICAL: {symbol} quote is {age_minutes:.1f} minutes old - rejecting")
                                    return None
                        except Exception as timestamp_error:
                            logger.debug(f"Could not validate timestamp for {symbol}: {timestamp_error}")
                    
                    # Map Alpaca field names to our expected field names
                    mapped_quote = {
                        'bid_price': raw_quote.get('bp', 0),  # bp = bid price
                        'bid_size': raw_quote.get('bs', 0),   # bs = bid size  
                        'ask_price': raw_quote.get('ap', 0),  # ap = ask price
                        'ask_size': raw_quote.get('as', 0),   # as = ask size
                        'timestamp': raw_quote.get('t', ''),  # t = timestamp
                        'condition': raw_quote.get('c', ''),  # c = condition
                        'exchange': raw_quote.get('ax', ''),  # ax = ask exchange, bx = bid exchange
                        'tape': raw_quote.get('z', '')        # z = tape
                    }
                    return mapped_quote
                return None
            else:
                # Handle expected failures more gracefully
                error_msg = str(response.error).lower()
                if 'no quote found' in error_msg or 'not found' in error_msg:
                    # These are common for invalid symbols or free tier limitations
                    if symbol in ['VIX', 'NDTAF'] or response.status_code == 404:
                        logger.debug(f"Quote not available for {symbol} (symbol not found or free tier limitation)")
                    else:
                        logger.warning(f"Quote not found for {symbol}: {response.error}")
                elif 'subscription does not permit' in error_msg or 'sip data unavailable' in error_msg:
                    logger.debug(f"Quote unavailable for {symbol} (subscription limitation)")
                else:
                    logger.error(f"Quote request failed for {symbol}: {response.error}")
                return None
        except Exception as e:
            logger.error(f"Quote request error for {symbol}: {e}")
            return None
            
    async def _make_data_request(self, method: str, endpoint: str, params: Dict = None) -> ApiResponse:
        """Make request to data API"""
        # Similar to _make_request but for data endpoints
        url = f"{self.data_url}{endpoint}"
        
        try:
            async with self.session.request(
                method=method,
                url=url,
                params=params
            ) as response:
                
                response_data = await response.json()
                
                if response.status == 200:
                    return ApiResponse(success=True, data=response_data, status_code=response.status)
                else:
                    return ApiResponse(
                        success=False,
                        error=f"HTTP {response.status}: {response_data}",
                        status_code=response.status
                    )
                    
        except Exception as e:
            return ApiResponse(success=False, error=str(e))
            
    # Data parsing helpers
    def _parse_account_data(self, data: Dict):
        """Parse account data into standardized format"""
        class Account:
            def __init__(self, data):
                self.equity = data.get('equity', '0')
                self.cash = data.get('cash', '0')
                self.buying_power = data.get('buying_power', '0')
                self.last_equity = data.get('last_equity', '0')
                self.day_trade_count = data.get('day_trade_count', 0)
                self.pattern_day_trader = data.get('pattern_day_trader', False)
                self.status = data.get('status', 'ACTIVE')  # Default to ACTIVE if not specified
                
        return Account(data)
        
    def _parse_position_data(self, data: Dict):
        """Parse position data into standardized format"""
        class Position:
            def __init__(self, data):
                self.symbol = data.get('symbol')
                self.qty = data.get('qty', '0')
                self.market_value = data.get('market_value', '0')
                self.cost_basis = data.get('cost_basis', '0')
                self.unrealized_pl = data.get('unrealized_pl', '0')
                self.unrealized_plpc = data.get('unrealized_plpc', '0')
                self.avg_entry_price = data.get('avg_entry_price', '0')
                
        return Position(data)
        
    def _parse_order_data(self, data: Dict):
        """Parse order data into standardized format"""
        class Order:
            def __init__(self, data):
                self.id = data.get('id')
                self.symbol = data.get('symbol')
                self.qty = data.get('qty', '0')
                self.side = data.get('side')
                self.order_type = data.get('order_type')
                self.status = data.get('status')
                self.limit_price = data.get('limit_price')
                self.stop_price = data.get('stop_price')
                self.filled_qty = data.get('filled_qty', '0')
                self.filled_avg_price = data.get('filled_avg_price')
                # CRITICAL FIX: Parse created_at string to datetime object
                created_at_str = data.get('created_at')
                if created_at_str:
                    try:
                        from datetime import datetime
                        import dateutil.parser
                        self.created_at = dateutil.parser.parse(created_at_str)
                    except Exception as e:
                        # Fallback: keep as string but log warning
                        logger.warning(f"Failed to parse created_at: {created_at_str} - {e}")
                        self.created_at = created_at_str
                else:
                    self.created_at = None

                # Add missing attributes for compatibility
                self.type = data.get('type', self.order_type)
                
        return Order(data)
    
    async def get_all_assets(self, status='active', asset_class='us_equity'):
        """Get all available assets from Alpaca"""
        try:
            params = {
                'status': status,
                'asset_class': asset_class
            }
            
            response = await self._make_request('GET', '/v2/assets', params=params)
            
            if response.success:
                assets = response.data
                # Filter for tradeable stocks
                tradeable_assets = []
                for asset in assets:
                    if (asset.get('tradable', False) and 
                        asset.get('status') == 'active' and
                        asset.get('exchange') in ['NASDAQ', 'NYSE', 'NYSEARCA', 'BATS']):
                        tradeable_assets.append({
                            'symbol': asset.get('symbol'),
                            'name': asset.get('name', ''),
                            'exchange': asset.get('exchange'),
                            'asset_class': asset.get('class')
                        })
                
                logger.info(f"Retrieved {len(tradeable_assets)} tradeable assets")
                return tradeable_assets
            else:
                logger.error(f"Assets request failed: {response.error}")
                return []
        except Exception as e:
            logger.error(f"Assets request error: {e}")
            return []
        
    # Market Screener Methods
    async def get_market_movers(self, direction: str = 'gainers', limit: int = 50):
        """Get market movers (gainers/losers)"""
        try:
            # Use correct Alpaca screener API endpoint
            endpoint = "/v1beta1/screener/stocks/movers"
            params = {
                'top': limit
            }
            
            response = await self._make_data_request('GET', endpoint, params=params)
            
            if response.success:
                # Extract movers data based on direction
                if direction == 'gainers':
                    movers = response.data.get('gainers', [])
                else:
                    movers = response.data.get('losers', [])
                    
                # Map field names to match our expected format
                mapped_movers = []
                for mover in movers[:limit]:
                    mapped_mover = {
                        'symbol': mover.get('symbol', ''),
                        'price': mover.get('price', 0),
                        'change_percent': mover.get('percent_change', 0),
                        'change': mover.get('change', 0),
                        'volume': mover.get('volume', 0)  # May not be present
                    }
                    mapped_movers.append(mapped_mover)
                    
                return mapped_movers
            else:
                logger.error(f"Market movers request failed: {response.error}")
                return []
        except Exception as e:
            logger.error(f"Market movers error: {e}")
            return []
            
    async def get_most_active_stocks(self, limit: int = 50):
        """Get most active stocks by volume"""
        try:
            params = {
                'top': limit
            }
            
            endpoint = "/v1beta1/screener/stocks/most-actives"
            response = await self._make_data_request('GET', endpoint, params=params)
            
            if response.success:
                actives = response.data.get('most_actives', [])
                
                # Map field names to match our expected format
                mapped_actives = []
                for active in actives[:limit]:
                    mapped_active = {
                        'symbol': active.get('symbol', ''),
                        'volume': active.get('volume', 0),
                        'trade_count': active.get('trade_count', 0),
                        'price': active.get('price', 0),  # May need to get from quote
                        'change_percent': active.get('change_percent', 0)  # May need to calculate
                    }
                    mapped_actives.append(mapped_active)
                    
                return mapped_actives
            else:
                logger.error(f"Most active stocks request failed: {response.error}")
                return []
        except Exception as e:
            logger.error(f"Most active stocks error: {e}")
            return []
            
    async def get_market_calendar(self, start_date=None, end_date=None):
        """Get market calendar"""
        try:
            params = {}
            if start_date:
                params['start'] = start_date.strftime('%Y-%m-%d')
            if end_date:
                params['end'] = end_date.strftime('%Y-%m-%d')
                
            endpoint = "/v2/calendar"
            response = await self._make_request('GET', endpoint, params=params)
            
            if response.success:
                return response.data
            else:
                logger.error(f"Market calendar request failed: {response.error}")
                return []
        except Exception as e:
            logger.error(f"Market calendar error: {e}")
            return []
            
    async def get_news(self, symbols=None, limit=50):
        """Get market news"""
        try:
            params = {
                'sort': 'desc',
                'include_content': 'true',
                'exclude_contentless': 'true',
                'limit': limit
            }
            
            if symbols:
                if isinstance(symbols, list):
                    params['symbols'] = ','.join(symbols)
                else:
                    params['symbols'] = symbols
                    
            endpoint = "/v1beta1/news"
            response = await self._make_data_request('GET', endpoint, params=params)
            
            if response.success:
                return response.data.get('news', []) or response.data.get('articles', [])
            else:
                logger.error(f"News request failed: {response.error}")
                return []
        except Exception as e:
            logger.error(f"News request error: {e}")
            return []

    async def get_connection_health(self) -> Dict:
        """Get connection health metrics"""
        return {
            'last_successful_request': self.last_successful_request,
            'consecutive_failures': self.consecutive_failures,
            'is_healthy': self.consecutive_failures < self.max_consecutive_failures,
            'requests_in_last_minute': len(self.request_timestamps)
        }