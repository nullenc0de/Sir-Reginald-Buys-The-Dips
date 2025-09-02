# AI-Driven Trading System - Complete Wiki

A comprehensive guide to understanding, deploying, and maintaining a production-grade AI-powered algorithmic trading system.

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Deep Dive](#architecture-deep-dive)
3. [Installation & Setup](#installation--setup)
4. [Configuration Guide](#configuration-guide)
5. [Trading Strategies](#trading-strategies)
6. [Safety Systems](#safety-systems)
7. [Monitoring & Alerting](#monitoring--alerting)
8. [API Integration](#api-integration)
9. [Troubleshooting](#troubleshooting)
10. [Advanced Topics](#advanced-topics)
11. [Performance Analysis](#performance-analysis)
12. [Security Considerations](#security-considerations)

---

## System Overview

### What is the AI-Driven Trading System?

This is a sophisticated algorithmic trading platform that combines artificial intelligence, comprehensive risk management, and professional-grade safety systems to automate stock trading through Alpaca Markets. The system is designed for both educational purposes and serious algorithmic trading with extensive safeguards.

### Key Capabilities

- **AI-Powered Decision Making**: Advanced market analysis using machine learning models
- **Multi-Strategy Approach**: Momentum, mean reversion, breakout, and defensive strategies
- **Production-Grade Safety**: Circuit breakers, PDT protection, position reconciliation
- **Real-Time Monitoring**: Comprehensive logging, alerting, and performance tracking
- **Extended Hours Protection**: Gap risk management for pre-market and after-hours positions
- **Advanced Emergency Stop System**: Intelligent order conflict resolution with automatic cancellation
- **Robust API Response Handling**: Comprehensive error detection and detailed failure reporting

### Target Users

- **Algorithmic Trading Enthusiasts**: Learn systematic trading approaches
- **Quantitative Developers**: Study production-grade trading system architecture
- **Individual Traders**: Automate trading strategies with institutional-level safety
- **Researchers**: Analyze AI applications in financial markets

---

## 🔥 Recent Major Improvements (v2.0)

### Emergency Stop System Overhaul
The trading system has undergone a comprehensive emergency stop system overhaul, fixing critical issues that were preventing proper risk management:

#### 🚨 Critical Fixes Implemented
- **✅ Emergency Stop Execution Fixed**: Emergency stops now actually execute when triggered (previously logging false success)
- **✅ API Response Validation**: Fixed all `if response:` patterns to `if response and response.success:` across the codebase  
- **✅ Order Conflict Resolution**: System automatically cancels existing orders before emergency execution to prevent "insufficient qty" errors
- **✅ HTTP Status Code Handling**: Fixed HTTP 204 (No Content) responses being treated as errors for order cancellations
- **✅ JSON Serialization**: Fixed datetime serialization errors in emergency shutdown reports

#### 🛡️ Enhanced Safety Features  
- **Protection Detection**: Intelligent detection of already-protected positions to prevent redundant orders
- **Detailed Error Reporting**: Emergency stops now provide specific failure reasons instead of generic errors
- **Order Lifecycle Management**: Comprehensive tracking from order submission through execution with proper error handling
- **Retry Logic**: Multi-attempt emergency liquidation with exponential backoff for broker state issues

#### 🔧 System Reliability Improvements
- **Market Status Detection**: Improved market hours and status checking with better error handling
- **Quote Object Consistency**: Standardized market data access patterns from `quote.ask_price` to `quote.get('ask_price', 0)`
- **Position Aging Management**: Proactive position turnover to prevent extended hours risks
- **Loss Cut Optimization**: Smart detection of existing protection before triggering redundant loss cuts

#### 📊 Before vs After
| Issue | Before v2.0 | After v2.0 |
|-------|-------------|-------------|
| Emergency Stops | False success logging, no execution | Actual execution with detailed error reporting |
| Order Conflicts | "Insufficient qty" errors | Automatic order cancellation before execution |
| HTTP 204 Responses | Treated as errors | Properly handled as success for DELETE operations |
| API Response Validation | Inconsistent checking | Uniform `response and response.success` pattern |
| Error Visibility | Generic failure messages | Specific error details and root cause analysis |

These improvements ensure the emergency stop system actually works when needed, providing real protection against significant losses during volatile market conditions or system anomalies.

---

## Architecture Deep Dive

### System Components Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Main System   │────│  Market Data &   │────│  AI Analysis    │
│   Orchestrator  │    │  API Gateway     │    │  Engine         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Risk Management │    │  Order Execution │    │  Strategy       │
│  & Safety       │    │  & Monitoring    │    │  Evaluation     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Alerting &     │    │  Performance     │    │  Extended Hours │
│  Notifications  │    │  Tracking        │    │  Monitoring     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Core Module Breakdown

#### 1. **main.py** - System Orchestrator
**Purpose**: Central control system that coordinates all components

**Key Responsibilities**:
- Initialize all subsystems and validate connections
- Perform startup position reconciliation and safety checks
- Manage the main trading loop with proper timing
- Handle emergency situations and system shutdown
- Coordinate between AI analysis, risk management, and execution

**Critical Features**:
- Startup position safety validation
- PDT compliance checking at system start
- Emergency liquidation for unprotected positions
- Extended hours monitoring with gap risk alerts

#### 2. **api_gateway.py** - Resilient API Gateway (v2.0 Enhanced)
**Purpose**: Resilient communication layer with comprehensive error handling

**Key Responsibilities**:
- Manage HTTP connections with retry logic and rate limiting
- Validate and parse market data from multiple endpoints
- Handle authentication and session management with enhanced security
- Detect stale data and SIP access limitations
- Track PDT violations and implement intelligent trading blocks

**Critical Features (v2.0)**:
- **Enhanced HTTP Status Handling**: Proper support for HTTP 201 (Created) and 204 (No Content) as success responses
- **Unified ApiResponse Objects**: All API operations return consistent ApiResponse objects for reliable error checking
- **Intelligent Error Classification**: Detailed error categorization with specific handling for PDT violations and order conflicts  
- **Rate Limiting with Safety Margins**: Configurable thresholds (200 req/min default) with 80% utilization cap
- **Stale Data Protection**: Automatic rejection of quotes older than 15 minutes to prevent bad trades
- **SIP Data Graceful Handling**: Smart fallback for free tier data limitations without spamming logs

#### 3. **ai_analyzer.py** - AI Decision Engine
**Purpose**: Intelligent market analysis and opportunity evaluation

**Key Responsibilities**:
- Analyze market conditions and identify trading opportunities
- Evaluate AI confidence levels for trade approval
- Process technical indicators and market sentiment
- Generate buy/sell recommendations with reasoning
- Adapt to different market regimes

**Critical Features**:
- AI confidence threshold validation (65% minimum)
- Market regime detection (momentum/mean reversion/breakout)
- Multi-factor analysis combining technical and sentiment data
- Dynamic strategy selection based on market conditions

#### 4. **risk_manager.py** - Risk Control System
**Purpose**: Multi-layered risk management and portfolio protection

**Key Responsibilities**:
- Position sizing validation and portfolio allocation limits
- Circuit breaker monitoring for flash crash protection
- Daily loss tracking and drawdown management
- Portfolio concentration risk assessment
- Emergency liquidation triggers

**Critical Features**:
- Circuit breaker at 5% total portfolio loss
- Maximum position size limits (10% of portfolio)
- Real-time loss tracking with emergency stops
- Position concentration monitoring

#### 5. **order_executor.py** - Enhanced Trade Execution System
**Purpose**: Intelligent order placement with advanced emergency stop capabilities

**Key Responsibilities**:
- Create and submit bracket orders (entry + stop + profit target)
- Execute emergency stops with automatic order conflict resolution  
- Monitor order status and handle partial fills
- Perform multi-attempt liquidation with detailed error reporting
- Track fill prices and slippage with comprehensive logging

**Critical Features (v2.0)**:
- **Emergency Stop System v2.0**: Automatic cancellation of existing orders before emergency execution
- **Order Conflict Resolution**: Intelligent handling of "insufficient qty available" scenarios  
- **Robust API Response Handling**: All order operations use proper ApiResponse validation
- **Enhanced Error Reporting**: Detailed error messages with specific failure analysis
- **Multi-Attempt Execution**: Retry logic with exponential backoff for broker state issues

### Safety System Components

#### 6. **pdt_manager.py** - PDT Compliance Manager
**Purpose**: Pattern Day Trading rule compliance and violation prevention

**Key Features**:
- Tracks day trades in rolling 5-day period
- Prevents trades that would cause PDT violations
- Monitors account equity requirements ($25,000 threshold)
- Maintains symbol-based blocking for violated tickers
- Daily reset functionality for new trading sessions

#### 7. **alerter.py** - Critical Alert System
**Purpose**: Real-time notification system for critical events

**Key Features**:
- Console and email alert capabilities
- Multiple alert levels (INFO, WARNING, CRITICAL)
- Position safety alerts for unprotected positions
- PDT violation warnings and blocking notifications
- System health and emergency alerts

#### 8. **gap_risk_manager.py** - Extended Hours Protection
**Purpose**: Monitor and protect positions during extended trading hours

**Key Features**:
- Record closing positions for overnight gap calculation
- Calculate gap risk percentages and dollar impact
- Generate alerts for significant overnight moves (>2%)
- Portfolio-wide gap exposure assessment
- Risk level categorization (LOW/MODERATE/HIGH/EXTREME)

#### 9. **market_status_manager.py** - Trading Hours Management
**Purpose**: Market session detection and extended hours monitoring

**Key Features**:
- Regular market hours detection (9:30 AM - 4:00 PM ET)
- Extended hours period identification
- Weekend and holiday handling
- Market open countdown and waiting functionality

### Trading Strategy Components

#### 10. **enhanced_momentum_strategy.py** - Primary Trading Strategy
**Purpose**: Multi-faceted momentum and technical analysis strategy

**Key Features**:
- Momentum detection using price and volume analysis
- Technical indicator integration (RSI, MACD, moving averages)
- Mean reversion and breakout pattern recognition
- Market regime-specific strategy adaptation
- AI confidence integration for final trade decisions

---

## Installation & Setup

### System Requirements

**Hardware Requirements**:
- CPU: Multi-core processor (4+ cores recommended)
- RAM: 8GB minimum, 16GB recommended
- Storage: 10GB free space
- Internet: Stable broadband connection

**Software Requirements**:
- Python 3.8 or higher
- Operating System: Linux, macOS, or Windows
- Alpaca Markets account (paper trading supported)

### Step-by-Step Installation

#### 1. Clone and Setup Repository
```bash
# Clone the repository
git clone https://github.com/yourusername/ai-trading-system.git
cd ai-trading-system

# Create virtual environment
python -m venv trading_env
source trading_env/bin/activate  # Linux/Mac
# OR
trading_env\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

#### 2. Alpaca Account Setup
1. Create account at [Alpaca Markets](https://alpaca.markets)
2. Enable paper trading in dashboard
3. Generate API credentials (Key ID and Secret Key)
4. Note your account number for reference

#### 3. Configure API Credentials
```bash
# Create environment file
cp .env.example .env

# Edit with your credentials
nano .env
```

Add your credentials:
```bash
APCA_API_KEY_ID=your_key_id_here
APCA_API_SECRET_KEY=your_secret_key_here
```

#### 4. Verify Installation
```bash
# Test API connection
python -c "
import asyncio
from api_gateway import ResilientAlpacaGateway

async def test():
    gateway = ResilientAlpacaGateway()
    success = await gateway.initialize()
    print(f'API Connection: {\"SUCCESS\" if success else \"FAILED\"}')
    await gateway.shutdown()

asyncio.run(test())
"
```

#### 5. Run Initial System Check
```bash
# Start the system for the first time
python main.py
```

Expected output:
```
[INFO] System initializing...
[INFO] ✅ Alpaca API Gateway initialized successfully
[INFO] 📊 Position reconciliation complete: 0 positions found
[INFO] 🎯 Trading system ready - monitoring market...
```

---

## Configuration Guide

### Core Configuration Files

#### config.py - Main Configuration
```python
# API Configuration
API_CONFIG = {
    'alpaca_key_id': os.getenv('APCA_API_KEY_ID'),
    'alpaca_secret_key': os.getenv('APCA_API_SECRET_KEY'),
    'paper_trading': True,  # ALWAYS start with paper trading
    'request_timeout': 30,
    'max_retries': 3,
    'retry_backoff_factor': 2
}

# Trading Configuration  
TRADING_CONFIG = {
    'max_position_size': 0.10,          # 10% max per position
    'stop_loss_percent': 0.03,          # 3% stop loss
    'take_profit_percent': 0.06,        # 6% take profit (2:1 reward/risk)
    'circuit_breaker_loss': 0.05,       # 5% total portfolio loss triggers halt
    'ai_confidence_threshold': 0.65,    # 65% minimum AI confidence
    'max_concurrent_positions': 5       # Maximum open positions
}

# Risk Management
RISK_CONFIG = {
    'max_portfolio_risk_percent': 0.12, # 12% max total portfolio risk
    'max_daily_drawdown_percent': 0.06, # 6% daily loss limit
    'position_size_method': 'fixed',    # 'fixed' or 'volatility_adjusted'
    'emergency_liquidation_threshold': 0.08  # 8% loss triggers emergency exit
}

# Market Scanning
MARKET_CONFIG = {
    'symbols_focus': ['SPY', 'QQQ', 'AAPL', 'MSFT', 'NVDA', 'TSLA'],
    'volume_threshold': 1000000,        # Minimum daily volume
    'price_range_min': 10.0,           # Minimum stock price
    'price_range_max': 500.0,          # Maximum stock price
    'price_change_threshold': 0.02,    # 2% minimum price movement
    'max_spread_percent': 0.01         # 1% max bid-ask spread
}

# Rate Limiting
RATE_LIMIT_CONFIG = {
    'max_requests_per_minute': 200,    # Alpaca's limit
    'rate_limit_buffer': 0.8,          # Use 80% of limit for safety
    'burst_allowance': 10,             # Emergency request reserve
    'cooldown_period': 60              # Seconds to wait on rate limit hit
}
```

### Trading Strategy Configuration

#### Strategy Selection Parameters
```python
STRATEGY_CONFIG = {
    'primary_strategy': 'enhanced_momentum',
    'strategy_rotation': True,          # Enable dynamic strategy selection
    'momentum_threshold': 0.05,         # 5% price movement for momentum
    'mean_reversion_threshold': 0.15,   # 15% pullback for mean reversion
    'breakout_volume_multiplier': 2.0,  # 2x average volume for breakout
    
    # Technical Indicators
    'rsi_oversold': 30,
    'rsi_overbought': 70,
    'macd_sensitivity': 0.02,
    'moving_average_periods': [10, 20, 50],
    
    # Market Regime Detection
    'bull_market_threshold': 0.03,      # 3% weekly gain
    'bear_market_threshold': -0.03,     # 3% weekly loss
    'volatile_market_vix_threshold': 25 # VIX above 25
}
```

### Risk Management Tuning

#### Conservative Profile
```python
TRADING_CONFIG.update({
    'max_position_size': 0.05,          # 5% max per position
    'stop_loss_percent': 0.02,          # 2% stop loss
    'take_profit_percent': 0.04,        # 4% take profit
    'circuit_breaker_loss': 0.03,       # 3% total loss limit
    'max_concurrent_positions': 3
})
```

#### Aggressive Profile
```python
TRADING_CONFIG.update({
    'max_position_size': 0.15,          # 15% max per position
    'stop_loss_percent': 0.05,          # 5% stop loss
    'take_profit_percent': 0.10,        # 10% take profit
    'circuit_breaker_loss': 0.08,       # 8% total loss limit
    'max_concurrent_positions': 8
})
```

### AI Configuration

#### AI Confidence and Model Settings
```python
AI_CONFIG = {
    'model_endpoint': 'your_ai_service_endpoint',
    'confidence_threshold': 0.65,       # Minimum confidence for trades
    'confidence_decay_hours': 4,        # Hours before confidence expires
    'market_context_weight': 0.3,       # Weight of market conditions
    'technical_analysis_weight': 0.4,   # Weight of technical indicators
    'sentiment_analysis_weight': 0.3,   # Weight of market sentiment
    
    # Analysis Parameters
    'lookback_days': 30,               # Days of historical data to analyze
    'analysis_refresh_minutes': 15,    # How often to refresh analysis
    'opportunity_timeout_minutes': 60  # How long opportunities remain valid
}
```

---

## Trading Strategies

### 1. Enhanced Momentum Strategy

#### Overview
The primary trading strategy that identifies stocks with strong momentum backed by volume and technical confirmation.

#### Key Components
- **Price Momentum Detection**: Identifies stocks with significant price movements
- **Volume Confirmation**: Ensures momentum is backed by institutional interest
- **Technical Validation**: Uses RSI, MACD, and moving averages for confirmation
- **Market Regime Adaptation**: Adjusts parameters based on overall market conditions

#### Implementation Details
```python
def evaluate_momentum_opportunity(self, symbol, market_data):
    # Price momentum calculation
    price_change = (current_price - previous_close) / previous_close
    
    # Volume analysis
    volume_ratio = current_volume / average_volume
    
    # Technical indicators
    rsi_score = self.calculate_rsi_score(market_data)
    macd_score = self.calculate_macd_score(market_data)
    
    # Combined confidence score
    confidence = (
        price_momentum_weight * price_score +
        volume_weight * volume_score +
        technical_weight * technical_score
    )
    
    return confidence, trade_direction, reasoning
```

#### Signal Generation Process
1. **Screening Phase**: Scan for stocks with >2% price movement and >1.5x average volume
2. **Technical Analysis**: Calculate RSI, MACD, and moving average positions
3. **Market Context**: Consider overall market regime (bull/bear/volatile)
4. **AI Validation**: Submit to AI for final confidence assessment
5. **Risk Assessment**: Validate position sizing and portfolio impact

### 2. Mean Reversion Strategy

#### When Activated
- Market regime: Range-bound or oversold conditions
- Individual stocks: Extended moves beyond normal ranges
- Technical setup: RSI < 30 or > 70 with divergence

#### Key Parameters
```python
MEAN_REVERSION_CONFIG = {
    'oversold_threshold': 0.15,     # 15% drop from recent high
    'overbought_threshold': 0.15,   # 15% gain from recent low
    'reversion_target': 0.05,       # 5% reversion expected
    'max_holding_days': 5,          # Maximum position hold time
    'volume_confirmation': 1.2      # 20% above average volume
}
```

### 3. Breakout Strategy

#### Identification Criteria
- Price breaks above/below key technical levels
- Volume surge (2x+ average) confirms breakout
- Market regime supports directional moves
- AI confidence validates breakout sustainability

#### Implementation
```python
def detect_breakout(self, symbol, market_data):
    # Identify key levels (support/resistance)
    resistance_level = self.find_resistance(market_data)
    support_level = self.find_support(market_data)
    
    # Check for breakout
    if current_price > resistance_level * 1.01:  # 1% buffer
        return 'bullish_breakout'
    elif current_price < support_level * 0.99:
        return 'bearish_breakout'
    
    return 'no_breakout'
```

### 4. Defensive Strategy

#### Activation Triggers
- Circuit breaker conditions
- High market volatility (VIX > 30)
- Significant portfolio drawdown
- Extended hours with gap risk

#### Defensive Actions
- Reduce position sizes by 50%
- Tighten stop losses to 2%
- Increase AI confidence threshold to 75%
- Focus on large-cap, liquid stocks only

---

## Safety Systems

### Multi-Layer Risk Protection

#### Layer 1: Position-Level Safety
```python
def validate_position_safety(self, symbol, quantity, price):
    # Position size validation
    position_value = quantity * price
    max_position_value = account_equity * TRADING_CONFIG['max_position_size']
    
    if position_value > max_position_value:
        return False, "Position size exceeds limit"
    
    # Risk per trade validation
    risk_per_trade = position_value * TRADING_CONFIG['stop_loss_percent']
    max_risk = account_equity * 0.02  # 2% max risk per trade
    
    if risk_per_trade > max_risk:
        return False, "Risk per trade exceeds limit"
    
    return True, "Position safety validated"
```

#### Layer 2: Portfolio-Level Safety
```python
def check_portfolio_risk(self):
    total_risk = 0
    for position in active_positions:
        position_risk = abs(position.qty) * position.current_price * stop_loss_percent
        total_risk += position_risk
    
    max_portfolio_risk = account_equity * RISK_CONFIG['max_portfolio_risk_percent']
    
    if total_risk > max_portfolio_risk:
        return False, "Portfolio risk exceeds maximum"
    
    return True, "Portfolio risk within limits"
```

#### Layer 3: Circuit Breaker System
```python
async def check_circuit_breaker(self, current_equity):
    if not hasattr(self, 'initial_account_value'):
        self.initial_account_value = current_equity
        return False
    
    loss_percent = (self.initial_account_value - current_equity) / self.initial_account_value
    
    if loss_percent >= TRADING_CONFIG['circuit_breaker_loss']:
        logger.critical(f"⚡ CIRCUIT BREAKER TRIGGERED: {loss_percent:.1%} loss")
        await self.emergency_liquidate_all()
        return True
    
    return False
```

### Pattern Day Trading (PDT) Protection

#### Day Trade Tracking
```python
class PDTManager:
    def __init__(self):
        self.day_trades = []  # Track recent day trades
        
    def would_be_day_trade(self, symbol, side):
        # Check if selling a position bought today
        today = datetime.now().date()
        bought_today = any(
            trade.symbol == symbol and 
            trade.side == 'buy' and 
            trade.date == today 
            for trade in self.recent_trades
        )
        return bought_today and side == 'sell'
    
    def check_pdt_compliance(self, symbol, side):
        if self.would_be_day_trade(symbol, side):
            recent_day_trades = self.get_recent_day_trades()
            if len(recent_day_trades) >= 3 and account_equity < 25000:
                return False, "PDT violation risk - blocking trade"
        return True, "PDT compliant"
```

### Emergency Procedures

#### Unprotected Position Response
```python
async def handle_unprotected_positions(self, positions):
    for position in positions:
        if not self.has_stop_loss(position.symbol):
            logger.critical(f"🚨 Naked position detected: {position.symbol}")
            
            # Create emergency stop loss
            stop_price = self.calculate_emergency_stop(position)
            emergency_order = {
                'symbol': position.symbol,
                'qty': abs(float(position.qty)),
                'side': 'sell' if float(position.qty) > 0 else 'buy',
                'type': 'stop',
                'stop_price': stop_price,
                'time_in_force': 'gtc'
            }
            
            await self.gateway.submit_order(emergency_order)
            logger.critical(f"✅ Emergency stop created: {position.symbol} @ ${stop_price}")
```

#### System Health Monitoring
```python
async def monitor_system_health(self):
    health_checks = {
        'api_connection': await self.check_api_health(),
        'account_access': await self.check_account_access(),
        'market_data': await self.check_market_data_quality(),
        'order_execution': await self.check_order_system(),
        'risk_systems': self.check_risk_system_status()
    }
    
    failed_checks = [check for check, status in health_checks.items() if not status]
    
    if failed_checks:
        logger.critical(f"🚨 SYSTEM HEALTH ALERT: Failed checks: {failed_checks}")
        await self.alerter.send_critical_alert(
            f"System health degraded: {', '.join(failed_checks)}"
        )
```

---

## Monitoring & Alerting

### Real-Time Monitoring Dashboard

#### Key Metrics Displayed
- **Account Equity**: Current account value and daily P&L
- **Active Positions**: Current holdings with real-time P&L
- **Open Orders**: Pending orders and their status
- **Risk Metrics**: Portfolio risk, drawdown, and circuit breaker status
- **System Health**: API connectivity, error rates, and performance

#### Implementation Example
```python
def generate_status_report():
    return {
        'timestamp': datetime.now().isoformat(),
        'account_equity': account.equity,
        'daily_pnl': account.equity - account.last_equity,
        'daily_pnl_percent': daily_pnl / account.last_equity * 100,
        'active_positions': len(positions),
        'portfolio_risk': calculate_portfolio_risk(),
        'circuit_breaker_level': account.equity * 0.95,
        'api_requests_today': self.gateway.request_count,
        'system_uptime': self.get_uptime(),
        'last_trade_time': self.last_trade_time
    }
```

### Alert System Architecture

#### Alert Levels and Triggers
```python
class AlertLevel:
    INFO = "INFO"           # General information
    WARNING = "WARNING"     # Attention needed
    CRITICAL = "CRITICAL"   # Immediate action required
    EMERGENCY = "EMERGENCY" # System emergency

ALERT_TRIGGERS = {
    AlertLevel.INFO: [
        'trade_executed',
        'position_opened',
        'market_status_change'
    ],
    AlertLevel.WARNING: [
        'position_loss_5_percent',
        'api_rate_limit_approaching',
        'stale_data_detected'
    ],
    AlertLevel.CRITICAL: [
        'position_loss_10_percent',
        'unprotected_position_found',
        'pdt_violation_risk'
    ],
    AlertLevel.EMERGENCY: [
        'circuit_breaker_triggered',
        'system_failure',
        'emergency_liquidation'
    ]
}
```

#### Alert Delivery Methods
```python
class AlertDelivery:
    async def send_console_alert(self, message, level):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color_code = self.get_color_for_level(level)
        print(f"{color_code}[{timestamp}] {level}: {message}{Colors.RESET}")
    
    async def send_email_alert(self, message, level, details=None):
        if level in ['CRITICAL', 'EMERGENCY']:
            subject = f"🚨 Trading System Alert - {level}"
            body = f"Alert: {message}\nTime: {datetime.now()}\n"
            if details:
                body += f"Details: {details}\n"
            await self.email_client.send_email(subject, body)
    
    async def send_sms_alert(self, message, level):
        if level == 'EMERGENCY':
            await self.sms_client.send_sms(
                f"TRADING EMERGENCY: {message[:100]}..."
            )
```

### Performance Tracking

#### Key Performance Indicators (KPIs)
```python
class PerformanceTracker:
    def __init__(self):
        self.trades = []
        self.daily_snapshots = []
    
    def calculate_performance_metrics(self):
        return {
            'total_trades': len(self.trades),
            'winning_trades': len([t for t in self.trades if t.pnl > 0]),
            'losing_trades': len([t for t in self.trades if t.pnl < 0]),
            'win_rate': self.calculate_win_rate(),
            'average_win': self.calculate_average_win(),
            'average_loss': self.calculate_average_loss(),
            'profit_factor': self.calculate_profit_factor(),
            'sharpe_ratio': self.calculate_sharpe_ratio(),
            'max_drawdown': self.calculate_max_drawdown(),
            'total_return': self.calculate_total_return(),
            'annual_return': self.calculate_annualized_return()
        }
```

#### Trade Analytics
```python
def analyze_trade_performance(self):
    trades_by_strategy = self.group_trades_by_strategy()
    trades_by_symbol = self.group_trades_by_symbol()
    trades_by_time = self.group_trades_by_time()
    
    return {
        'strategy_performance': {
            strategy: self.calculate_strategy_metrics(trades)
            for strategy, trades in trades_by_strategy.items()
        },
        'symbol_performance': {
            symbol: self.calculate_symbol_metrics(trades)
            for symbol, trades in trades_by_symbol.items()
        },
        'time_analysis': {
            'best_trading_hours': self.find_best_trading_hours(trades_by_time),
            'best_trading_days': self.find_best_trading_days(),
            'monthly_performance': self.calculate_monthly_returns()
        }
    }
```

---

## API Integration

### Alpaca Markets Integration

#### Authentication and Session Management
```python
class ResilientAlpacaGateway:
    def __init__(self):
        self.session = None
        self.base_url = "https://paper-api.alpaca.markets"  # Paper trading
        self.data_url = "https://data.alpaca.markets"
        
    async def initialize(self):
        headers = {
            'APCA-API-KEY-ID': API_CONFIG['alpaca_key_id'],
            'APCA-API-SECRET-KEY': API_CONFIG['alpaca_secret_key'],
            'Content-Type': 'application/json'
        }
        
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        
        # Test connection
        test_response = await self._make_request('GET', '/v2/account')
        return test_response.success
```

#### Rate Limiting Strategy
```python
async def _enforce_rate_limits(self):
    async with self.rate_limit_lock:
        now = datetime.now()
        
        # Clean old timestamps (older than 1 minute)
        cutoff_time = now - timedelta(minutes=1)
        self.request_timestamps = [
            ts for ts in self.request_timestamps if ts > cutoff_time
        ]
        
        # Check if approaching rate limit (200 requests/minute)
        requests_per_minute = len(self.request_timestamps)
        max_requests = int(200 * 0.8)  # Use 80% of limit for safety
        
        if requests_per_minute >= max_requests:
            sleep_time = 60 - (now - self.request_timestamps[0]).total_seconds()
            if sleep_time > 0:
                logger.debug(f"Rate limit approaching, sleeping {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)
```

#### Market Data Handling
```python
async def get_latest_quote(self, symbol):
    try:
        endpoint = f"/v2/stocks/{symbol}/quotes/latest"
        response = await self._make_data_request('GET', endpoint)
        
        if response.success:
            raw_quote = response.data.get('quote')
            if raw_quote:
                # Validate data freshness
                quote_time = raw_quote.get('t')
                if self._is_stale_data(quote_time):
                    logger.warning(f"⚠️ STALE DATA: {symbol} quote is too old")
                    return None
                
                return {
                    'bid_price': raw_quote.get('bp', 0),
                    'ask_price': raw_quote.get('ap', 0),
                    'bid_size': raw_quote.get('bs', 0),
                    'ask_size': raw_quote.get('as', 0),
                    'timestamp': quote_time
                }
        return None
    except Exception as e:
        logger.error(f"Quote request failed for {symbol}: {e}")
        return None
```

#### Order Management
```python
async def submit_order(self, order_data):
    try:
        # Pre-flight checks
        if self.is_symbol_pdt_blocked(order_data['symbol']):
            logger.warning(f"Order blocked - PDT violation risk: {order_data['symbol']}")
            return None
        
        response = await self._make_request('POST', '/v2/orders', data=order_data)
        
        if response.success:
            logger.info(f"Order submitted: {order_data['symbol']} {order_data['side']} {order_data['qty']}")
            return self._parse_order_data(response.data)
        else:
            # Handle PDT violations
            if response.status_code == 403 and '40310100' in str(response.error):
                logger.error(f"PDT VIOLATION: {order_data['symbol']}")
                self._add_pdt_blocked_symbol(order_data['symbol'])
            return None
            
    except Exception as e:
        logger.error(f"Order submission error: {e}")
        return None
```

### Data Quality Assurance

#### Stale Data Detection
```python
def _is_stale_data(self, timestamp_str, max_age_minutes=15):
    try:
        if isinstance(timestamp_str, str):
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            timestamp = datetime.fromtimestamp(timestamp_str)
        
        now = datetime.now(timestamp.tzinfo) if timestamp.tzinfo else datetime.now()
        age_minutes = (now - timestamp).total_seconds() / 60
        
        return age_minutes > max_age_minutes
    except:
        return True  # Assume stale if can't parse
```

#### SIP Data Limitations Handling
```python
async def get_bars_with_fallback(self, symbol, timeframe):
    try:
        # Try primary endpoint first
        bars = await self.get_bars(symbol, timeframe)
        if bars:
            return bars
        
        # Fall back to alternative data sources on free tier
        logger.debug(f"Primary data unavailable for {symbol}, using fallback")
        return await self._get_iex_bars(symbol, timeframe)
        
    except Exception as e:
        if 'SIP data' in str(e):
            logger.debug(f"SIP data unavailable for {symbol} (expected on free tier)")
            return []
        else:
            logger.error(f"Data request failed: {e}")
            return []
```

---

## Troubleshooting

### Common Issues and Solutions

#### 1. API Connection Problems

**Symptom**: `Gateway initialization failed` or `Request timeout`
```
ERROR - Gateway initialization failed: HTTP 401: Unauthorized
```

**Diagnosis Steps**:
```python
# Check API credentials
async def diagnose_api_connection():
    print("Testing API credentials...")
    
    # Test base connectivity
    try:
        response = requests.get("https://paper-api.alpaca.markets/v2/clock")
        print(f"Base connectivity: {'OK' if response.status_code == 401 else 'FAILED'}")
    except:
        print("Base connectivity: FAILED - Check internet connection")
    
    # Test authentication
    headers = {
        'APCA-API-KEY-ID': os.getenv('APCA_API_KEY_ID'),
        'APCA-API-SECRET-KEY': os.getenv('APCA_API_SECRET_KEY')
    }
    
    try:
        response = requests.get("https://paper-api.alpaca.markets/v2/account", headers=headers)
        if response.status_code == 200:
            print("Authentication: SUCCESS")
            account_data = response.json()
            print(f"Account equity: ${account_data['equity']}")
        else:
            print(f"Authentication: FAILED - {response.status_code}")
    except Exception as e:
        print(f"Authentication test failed: {e}")
```

**Solutions**:
- Verify API credentials in environment variables
- Ensure using paper trading endpoint for paper accounts
- Check account permissions and API key status
- Test network connectivity and firewall settings

#### 2. PDT Violations and Trading Blocks

**Symptom**: `PDT VIOLATION: Order blocked` messages
```
ERROR - PDT VIOLATION: Order blocked for AAPL - Pattern Day Trading rules exceeded
```

**Understanding PDT Rules**:
```python
def explain_pdt_status(account):
    equity = float(account.equity)
    day_trade_count = account.day_trade_count
    
    print(f"Account Equity: ${equity:,.2f}")
    print(f"Day Trades (5-day period): {day_trade_count}/3")
    print(f"PDT Status: {'Exempt' if equity >= 25000 else 'Subject to PDT rules'}")
    
    if equity < 25000 and day_trade_count >= 3:
        print("⚠️  WARNING: Additional day trades will trigger PDT violation")
        print("   Solution: Wait for day trades to age out or increase equity to $25K")
    
    return {
        'can_day_trade': equity >= 25000 or day_trade_count < 3,
        'trades_remaining': max(0, 3 - day_trade_count) if equity < 25000 else float('inf')
    }
```

**Solutions**:
- Increase account equity to $25,000+ for unlimited day trading
- Wait for day trades to age out of 5-day rolling period
- Use swing trading strategies (hold positions overnight)
- Monitor day trade count before placing orders

#### 3. Stale Data Warnings

**Symptom**: `STALE DATA WARNING: Quote is X minutes old`
```
WARNING - ⚠️ STALE DATA WARNING: AAPL quote is 18.3 minutes old
```

**Root Causes**:
- Free tier limitations on real-time data access
- SIP data subscription restrictions
- Market hours vs. extended hours data availability
- Network connectivity issues

**Solutions**:
```python
def handle_stale_data(symbol, age_minutes):
    if age_minutes < 5:
        return "DATA_OK"
    elif age_minutes < 15:
        logger.warning(f"Data slightly stale for {symbol}: {age_minutes:.1f}min")
        return "DATA_CAUTION"
    else:
        logger.error(f"Data too stale for {symbol}: {age_minutes:.1f}min")
        return "DATA_REJECT"

# Implementation
data_quality = handle_stale_data(symbol, age_minutes)
if data_quality == "DATA_REJECT":
    logger.info(f"Skipping trade for {symbol} due to stale data")
    return None
```

#### 4. Position Reconciliation Issues

**Symptom**: `STARTUP ALERT: X positions without stop protection found`
```
CRITICAL - 🚨 STARTUP ALERT: 3 positions without stop protection found
CRITICAL -    AMD: 1.0 shares, -7.0% P&L, $163.25 value
```

**This is Actually Good News**: The system is working correctly by detecting unprotected positions and automatically creating emergency stops.

**Verification Steps**:
```python
async def verify_position_protection():
    positions = await gateway.get_all_positions()
    orders = await gateway.get_orders('open')
    
    for position in positions:
        if float(position.qty) == 0:
            continue
            
        symbol = position.symbol
        position_side = 'long' if float(position.qty) > 0 else 'short'
        
        # Check for protective stops
        protective_orders = [
            order for order in orders
            if order.symbol == symbol and 
            order.order_type in ['stop', 'stop_limit'] and
            ((position_side == 'long' and order.side == 'sell') or
             (position_side == 'short' and order.side == 'buy'))
        ]
        
        if not protective_orders:
            print(f"⚠️  {symbol}: No stop loss protection found")
            # System will automatically create emergency stop
        else:
            print(f"✅ {symbol}: Protected by {len(protective_orders)} stop order(s)")
```

#### 5. Circuit Breaker Activations

**Symptom**: `CIRCUIT BREAKER TRIGGERED` - Trading halts automatically
```
CRITICAL - ⚡ CIRCUIT BREAKER TRIGGERED: 5.2% total loss - Emergency liquidation initiated
```

**This is a Safety Feature**: The circuit breaker prevents catastrophic losses during market crashes or system malfunctions.

**Response Protocol**:
1. **Immediate**: All trading halted automatically
2. **Assessment**: Review what caused the losses
3. **Analysis**: Check if losses were due to market conditions or system issues
4. **Decision**: Manual intervention required to resume trading

```python
async def circuit_breaker_recovery_protocol():
    # Step 1: Assess current situation
    account = await gateway.get_account_safe()
    positions = await gateway.get_all_positions()
    
    print("=== CIRCUIT BREAKER RECOVERY ASSESSMENT ===")
    print(f"Current Equity: ${float(account.equity):,.2f}")
    print(f"Day's P&L: ${float(account.equity) - float(account.last_equity):,.2f}")
    print(f"Total Positions: {len([p for p in positions if float(p.qty) != 0])}")
    
    # Step 2: Review recent trades
    recent_orders = await gateway.get_orders('filled')
    print(f"Recent Orders: {len(recent_orders)}")
    
    # Step 3: Manual decision point
    print("\n⚠️  MANUAL INTERVENTION REQUIRED")
    print("Review the situation and decide:")
    print("1. Resume trading with current settings")
    print("2. Resume with reduced risk parameters") 
    print("3. Stop trading for the day")
    
    # Reset circuit breaker only after manual review
    response = input("Enter choice (1-3): ")
    return response
```

### System Diagnostics

#### Comprehensive Health Check
```python
async def run_full_system_diagnostic():
    diagnostics = {
        'timestamp': datetime.now().isoformat(),
        'system_status': 'CHECKING',
        'checks': {}
    }
    
    # API Connectivity
    try:
        account = await gateway.get_account_safe()
        diagnostics['checks']['api_connection'] = {
            'status': 'PASS' if account else 'FAIL',
            'details': f"Account equity: ${account.equity}" if account else "Connection failed"
        }
    except Exception as e:
        diagnostics['checks']['api_connection'] = {
            'status': 'FAIL',
            'details': str(e)
        }
    
    # Market Data Quality
    try:
        quote = await gateway.get_latest_quote('SPY')
        age = calculate_data_age(quote['timestamp']) if quote else None
        diagnostics['checks']['market_data'] = {
            'status': 'PASS' if quote and age < 10 else 'WARN' if quote else 'FAIL',
            'details': f"SPY quote age: {age:.1f} minutes" if age else "No data received"
        }
    except Exception as e:
        diagnostics['checks']['market_data'] = {
            'status': 'FAIL',
            'details': str(e)
        }
    
    # Risk System Status
    diagnostics['checks']['risk_systems'] = {
        'status': 'PASS',
        'details': {
            'circuit_breaker': 'Armed',
            'pdt_protection': 'Active',
            'position_monitoring': 'Running'
        }
    }
    
    # Overall system status
    all_checks = [check['status'] for check in diagnostics['checks'].values()]
    if any(status == 'FAIL' for status in all_checks):
        diagnostics['system_status'] = 'DEGRADED'
    elif any(status == 'WARN' for status in all_checks):
        diagnostics['system_status'] = 'WARNING'
    else:
        diagnostics['system_status'] = 'HEALTHY'
    
    return diagnostics
```

---

## Advanced Topics

### Custom Strategy Development

#### Creating a New Strategy
```python
from base_strategy import BaseStrategy

class CustomMACDStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        self.name = "Custom MACD Strategy"
        self.min_confidence = 0.70
    
    async def evaluate_opportunity(self, symbol, market_data):
        # Calculate MACD
        macd_line, signal_line, histogram = self.calculate_macd(market_data['bars'])
        
        # Generate signals
        if macd_line[-1] > signal_line[-1] and macd_line[-2] <= signal_line[-2]:
            # Bullish crossover
            confidence = self.calculate_confidence(market_data, 'buy')
            return {
                'action': 'buy',
                'confidence': confidence,
                'reasoning': f"MACD bullish crossover detected for {symbol}"
            }
        elif macd_line[-1] < signal_line[-1] and macd_line[-2] >= signal_line[-2]:
            # Bearish crossover
            confidence = self.calculate_confidence(market_data, 'sell')
            return {
                'action': 'sell',
                'confidence': confidence,
                'reasoning': f"MACD bearish crossover detected for {symbol}"
            }
        
        return {
            'action': 'hold',
            'confidence': 0.0,
            'reasoning': f"No clear MACD signal for {symbol}"
        }
    
    def calculate_macd(self, bars, fast=12, slow=26, signal=9):
        # Implementation of MACD calculation
        closes = [bar['c'] for bar in bars]
        
        # Calculate EMAs
        fast_ema = self.calculate_ema(closes, fast)
        slow_ema = self.calculate_ema(closes, slow)
        
        # MACD line = fast EMA - slow EMA
        macd_line = [fast - slow for fast, slow in zip(fast_ema, slow_ema)]
        
        # Signal line = EMA of MACD line
        signal_line = self.calculate_ema(macd_line, signal)
        
        # Histogram = MACD - Signal
        histogram = [macd - sig for macd, sig in zip(macd_line, signal_line)]
        
        return macd_line, signal_line, histogram
```

#### Strategy Registration and Selection
```python
# In main.py
AVAILABLE_STRATEGIES = {
    'enhanced_momentum': EnhancedMomentumStrategy,
    'mean_reversion': MeanReversionStrategy,
    'breakout': BreakoutStrategy,
    'custom_macd': CustomMACDStrategy
}

async def initialize_strategies():
    strategies = {}
    enabled_strategies = TRADING_CONFIG.get('enabled_strategies', ['enhanced_momentum'])
    
    for strategy_name in enabled_strategies:
        if strategy_name in AVAILABLE_STRATEGIES:
            strategy_class = AVAILABLE_STRATEGIES[strategy_name]
            strategies[strategy_name] = strategy_class(TRADING_CONFIG)
            logger.info(f"✅ Initialized strategy: {strategy_name}")
    
    return strategies
```

### Multi-Timeframe Analysis

#### Implementation Framework
```python
class MultiTimeframeAnalyzer:
    def __init__(self):
        self.timeframes = ['1Min', '5Min', '15Min', '1Hour', '1Day']
        self.weights = {'1Min': 0.1, '5Min': 0.2, '15Min': 0.3, '1Hour': 0.3, '1Day': 0.1}
    
    async def analyze_symbol(self, symbol):
        timeframe_signals = {}
        
        for timeframe in self.timeframes:
            try:
                bars = await self.gateway.get_bars(symbol, timeframe, limit=50)
                if bars:
                    signal = await self.analyze_timeframe(symbol, bars, timeframe)
                    timeframe_signals[timeframe] = signal
            except Exception as e:
                logger.warning(f"Failed to analyze {symbol} on {timeframe}: {e}")
        
        # Combine signals with weighted average
        return self.combine_timeframe_signals(timeframe_signals)
    
    def combine_timeframe_signals(self, signals):
        if not signals:
            return {'action': 'hold', 'confidence': 0.0}
        
        total_weighted_confidence = 0
        total_weights = 0
        action_votes = {'buy': 0, 'sell': 0, 'hold': 0}
        
        for timeframe, signal in signals.items():
            weight = self.weights.get(timeframe, 0.2)
            confidence = signal.get('confidence', 0.0)
            action = signal.get('action', 'hold')
            
            total_weighted_confidence += confidence * weight
            total_weights += weight
            action_votes[action] += weight
        
        # Determine consensus action
        consensus_action = max(action_votes.items(), key=lambda x: x[1])[0]
        
        # Calculate final confidence
        final_confidence = total_weighted_confidence / total_weights if total_weights > 0 else 0.0
        
        return {
            'action': consensus_action,
            'confidence': final_confidence,
            'timeframe_breakdown': signals
        }
```

### Portfolio Optimization

#### Dynamic Position Sizing
```python
class PortfolioOptimizer:
    def __init__(self, risk_config):
        self.risk_config = risk_config
        self.volatility_lookback_days = 20
    
    async def calculate_optimal_position_size(self, symbol, confidence, account_equity):
        # Get volatility data
        volatility = await self.calculate_symbol_volatility(symbol)
        
        # Base position size from configuration
        base_size_pct = self.risk_config['max_position_size']
        
        # Adjust based on confidence
        confidence_multiplier = confidence / 0.65  # Normalize to minimum threshold
        
        # Adjust based on volatility (higher volatility = smaller position)
        volatility_multiplier = 1.0 / (1.0 + volatility)
        
        # Calculate final position size
        adjusted_size_pct = base_size_pct * confidence_multiplier * volatility_multiplier
        
        # Apply hard limits
        max_position_value = account_equity * min(adjusted_size_pct, base_size_pct)
        
        return max_position_value
    
    async def calculate_symbol_volatility(self, symbol):
        try:
            # Get historical data
            bars = await self.gateway.get_bars(symbol, '1Day', limit=self.volatility_lookback_days)
            
            if len(bars) < 10:
                return 0.02  # Default volatility assumption
            
            # Calculate daily returns
            closes = [float(bar['c']) for bar in bars]
            returns = [(closes[i] / closes[i-1] - 1) for i in range(1, len(closes))]
            
            # Calculate standard deviation (volatility)
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
            volatility = variance ** 0.5
            
            return volatility
            
        except Exception as e:
            logger.warning(f"Volatility calculation failed for {symbol}: {e}")
            return 0.02  # Default volatility
```

### Machine Learning Integration

#### Feature Engineering for AI
```python
class FeatureEngineer:
    def __init__(self):
        self.feature_names = [
            'price_momentum_1d', 'price_momentum_5d', 'price_momentum_10d',
            'volume_ratio_5d', 'volume_ratio_20d',
            'rsi_14', 'macd_signal', 'bb_position',
            'market_beta', 'sector_relative_strength'
        ]
    
    def create_features(self, symbol, bars, market_data):
        features = {}
        closes = [float(bar['c']) for bar in bars]
        volumes = [float(bar['v']) for bar in bars]
        
        # Price momentum features
        if len(closes) >= 10:
            features['price_momentum_1d'] = (closes[-1] / closes[-2] - 1)
            features['price_momentum_5d'] = (closes[-1] / closes[-6] - 1) if len(closes) >= 6 else 0
            features['price_momentum_10d'] = (closes[-1] / closes[-11] - 1) if len(closes) >= 11 else 0
        
        # Volume features
        if len(volumes) >= 20:
            avg_volume_5d = sum(volumes[-5:]) / 5
            avg_volume_20d = sum(volumes[-20:]) / 20
            features['volume_ratio_5d'] = avg_volume_5d / avg_volume_20d if avg_volume_20d > 0 else 1
            features['volume_ratio_20d'] = volumes[-1] / avg_volume_20d if avg_volume_20d > 0 else 1
        
        # Technical indicators
        features['rsi_14'] = self.calculate_rsi(closes, 14) if len(closes) >= 14 else 50
        features['macd_signal'] = self.calculate_macd_signal(closes) if len(closes) >= 26 else 0
        features['bb_position'] = self.calculate_bollinger_position(closes) if len(closes) >= 20 else 0.5
        
        # Market relative features
        features['market_beta'] = self.calculate_beta(symbol, closes, market_data)
        features['sector_relative_strength'] = self.calculate_sector_strength(symbol)
        
        return features
    
    def prepare_ml_input(self, features):
        # Normalize features for ML model
        normalized_features = []
        for feature_name in self.feature_names:
            value = features.get(feature_name, 0)
            # Apply feature-specific normalization
            normalized_value = self.normalize_feature(feature_name, value)
            normalized_features.append(normalized_value)
        
        return normalized_features
```

---

## Performance Analysis

### Trade Analysis Framework

#### Trade Performance Metrics
```python
class TradeAnalyzer:
    def __init__(self):
        self.trades = []
        
    def add_trade(self, trade):
        trade_record = {
            'symbol': trade.symbol,
            'side': trade.side,
            'quantity': float(trade.qty),
            'entry_price': float(trade.filled_avg_price),
            'entry_time': trade.created_at,
            'exit_price': None,
            'exit_time': None,
            'pnl': None,
            'pnl_percent': None,
            'strategy': trade.strategy,
            'confidence': trade.ai_confidence,
            'max_favorable': 0,
            'max_adverse': 0
        }
        self.trades.append(trade_record)
    
    def analyze_performance(self):
        completed_trades = [t for t in self.trades if t['exit_price'] is not None]
        
        if not completed_trades:
            return {'error': 'No completed trades to analyze'}
        
        # Basic metrics
        total_trades = len(completed_trades)
        winning_trades = [t for t in completed_trades if t['pnl'] > 0]
        losing_trades = [t for t in completed_trades if t['pnl'] < 0]
        
        win_rate = len(winning_trades) / total_trades
        
        total_pnl = sum(t['pnl'] for t in completed_trades)
        total_gross_profit = sum(t['pnl'] for t in winning_trades)
        total_gross_loss = sum(abs(t['pnl']) for t in losing_trades)
        
        avg_win = total_gross_profit / len(winning_trades) if winning_trades else 0
        avg_loss = total_gross_loss / len(losing_trades) if losing_trades else 0
        
        profit_factor = total_gross_profit / total_gross_loss if total_gross_loss > 0 else float('inf')
        
        return {
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'average_win': avg_win,
            'average_loss': avg_loss,
            'profit_factor': profit_factor,
            'largest_win': max((t['pnl'] for t in winning_trades), default=0),
            'largest_loss': min((t['pnl'] for t in completed_trades), default=0),
            'expectancy': (win_rate * avg_win) - ((1 - win_rate) * avg_loss)
        }
```

#### Drawdown Analysis
```python
def calculate_drawdown_metrics(self, equity_curve):
    """Calculate maximum drawdown and related metrics"""
    if len(equity_curve) < 2:
        return {}
    
    peak = equity_curve[0]
    max_drawdown = 0
    max_drawdown_duration = 0
    current_drawdown_duration = 0
    drawdown_periods = []
    
    for i, equity in enumerate(equity_curve):
        if equity > peak:
            # New peak
            if current_drawdown_duration > 0:
                drawdown_periods.append(current_drawdown_duration)
            peak = equity
            current_drawdown_duration = 0
        else:
            # In drawdown
            current_drawdown_duration += 1
            drawdown = (peak - equity) / peak
            max_drawdown = max(max_drawdown, drawdown)
            max_drawdown_duration = max(max_drawdown_duration, current_drawdown_duration)
    
    # Handle ongoing drawdown
    if current_drawdown_duration > 0:
        drawdown_periods.append(current_drawdown_duration)
    
    avg_drawdown_duration = sum(drawdown_periods) / len(drawdown_periods) if drawdown_periods else 0
    
    return {
        'max_drawdown_percent': max_drawdown * 100,
        'max_drawdown_duration_periods': max_drawdown_duration,
        'average_drawdown_duration': avg_drawdown_duration,
        'current_drawdown': (peak - equity_curve[-1]) / peak * 100,
        'recovery_factor': abs(equity_curve[-1] - equity_curve[0]) / (max_drawdown * peak) if max_drawdown > 0 else float('inf')
    }
```

### Risk Metrics

#### Value at Risk (VaR) Calculation
```python
def calculate_var(self, returns, confidence_level=0.95):
    """Calculate Value at Risk at given confidence level"""
    if len(returns) < 30:
        return None  # Insufficient data
    
    sorted_returns = sorted(returns)
    var_index = int((1 - confidence_level) * len(sorted_returns))
    var = sorted_returns[var_index] if var_index < len(sorted_returns) else sorted_returns[0]
    
    # Expected Shortfall (Conditional VaR)
    shortfall_returns = sorted_returns[:var_index+1]
    expected_shortfall = sum(shortfall_returns) / len(shortfall_returns) if shortfall_returns else var
    
    return {
        'var_95': var,
        'expected_shortfall': expected_shortfall,
        'var_observations': len(returns),
        'worst_return': min(returns),
        'best_return': max(returns)
    }
```

#### Sharpe and Sortino Ratios
```python
def calculate_risk_adjusted_returns(self, returns, risk_free_rate=0.02):
    """Calculate Sharpe and Sortino ratios"""
    if len(returns) < 10:
        return {}
    
    mean_return = sum(returns) / len(returns)
    annual_return = (1 + mean_return) ** 252 - 1  # Annualize assuming daily returns
    
    # Sharpe Ratio
    std_dev = (sum((r - mean_return) ** 2 for r in returns) / len(returns)) ** 0.5
    annual_volatility = std_dev * (252 ** 0.5)
    sharpe_ratio = (annual_return - risk_free_rate) / annual_volatility if annual_volatility > 0 else 0
    
    # Sortino Ratio (only downside deviation)
    negative_returns = [r for r in returns if r < 0]
    if negative_returns:
        downside_dev = (sum(r ** 2 for r in negative_returns) / len(negative_returns)) ** 0.5
        annual_downside_dev = downside_dev * (252 ** 0.5)
        sortino_ratio = (annual_return - risk_free_rate) / annual_downside_dev if annual_downside_dev > 0 else 0
    else:
        sortino_ratio = float('inf')  # No downside
    
    return {
        'annual_return': annual_return,
        'annual_volatility': annual_volatility,
        'sharpe_ratio': sharpe_ratio,
        'sortino_ratio': sortino_ratio,
        'calmar_ratio': annual_return / max_drawdown if max_drawdown > 0 else float('inf')
    }
```

### Strategy Performance Comparison

#### Multi-Strategy Analysis
```python
def compare_strategy_performance(self):
    """Compare performance across different strategies"""
    strategy_stats = {}
    
    for strategy_name in self.get_active_strategies():
        strategy_trades = [t for t in self.trades if t.get('strategy') == strategy_name]
        
        if not strategy_trades:
            continue
        
        # Calculate strategy-specific metrics
        strategy_returns = [t['pnl_percent'] for t in strategy_trades if t['pnl_percent'] is not None]
        
        if strategy_returns:
            strategy_stats[strategy_name] = {
                'total_trades': len(strategy_trades),
                'win_rate': len([t for t in strategy_trades if t['pnl'] > 0]) / len(strategy_trades),
                'avg_return': sum(strategy_returns) / len(strategy_returns),
                'total_pnl': sum(t['pnl'] for t in strategy_trades),
                'best_trade': max(t['pnl'] for t in strategy_trades),
                'worst_trade': min(t['pnl'] for t in strategy_trades),
                'sharpe_ratio': self.calculate_sharpe_ratio(strategy_returns),
                'max_consecutive_losses': self.calculate_max_consecutive_losses(strategy_trades)
            }
    
    return strategy_stats
```

---

## Security Considerations

### API Security Best Practices

#### Credential Management
```python
import os
from cryptography.fernet import Fernet

class SecureCredentialManager:
    def __init__(self):
        self.encryption_key = self._get_or_create_key()
        self.cipher_suite = Fernet(self.encryption_key)
    
    def _get_or_create_key(self):
        key_file = '.encryption_key'
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            os.chmod(key_file, 0o600)  # Read-only for owner
            return key
    
    def encrypt_credential(self, credential):
        return self.cipher_suite.encrypt(credential.encode()).decode()
    
    def decrypt_credential(self, encrypted_credential):
        return self.cipher_suite.decrypt(encrypted_credential.encode()).decode()
    
    def get_secure_config(self):
        return {
            'alpaca_key_id': os.getenv('APCA_API_KEY_ID'),
            'alpaca_secret_key': os.getenv('APCA_API_SECRET_KEY'),
            # Never store credentials in code
        }
```

#### Secure Logging
```python
class SecureLogger:
    SENSITIVE_PATTERNS = [
        r'APCA-API-KEY-ID.*',
        r'APCA-API-SECRET-KEY.*',
        r'Authorization: Bearer .*',
        r'password.*',
        r'secret.*',
        r'token.*'
    ]
    
    def sanitize_log_message(self, message):
        """Remove sensitive information from log messages"""
        sanitized = message
        for pattern in self.SENSITIVE_PATTERNS:
            sanitized = re.sub(pattern, '[REDACTED]', sanitized, flags=re.IGNORECASE)
        return sanitized
    
    def safe_log(self, level, message):
        sanitized_message = self.sanitize_log_message(message)
        getattr(logger, level.lower())(sanitized_message)
```

### Network Security

#### HTTPS Enforcement
```python
class SecureAPIGateway(ResilientAlpacaGateway):
    def __init__(self):
        super().__init__()
        self.enforce_https = True
        self.verify_ssl = True
        self.timeout_seconds = 30
    
    async def _make_secure_request(self, method, endpoint, data=None):
        if self.enforce_https and not endpoint.startswith('https://'):
            raise SecurityError("HTTPS required for all API requests")
        
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        
        connector = aiohttp.TCPConnector(
            ssl=ssl_context,
            limit=10,
            limit_per_host=5,
            enable_cleanup_closed=True
        )
        
        async with aiohttp.ClientSession(connector=connector) as session:
            return await self._make_request_with_session(session, method, endpoint, data)
```

#### Request Validation
```python
def validate_api_request(self, request_data):
    """Validate API request for potential security issues"""
    
    # Check for injection attempts
    dangerous_patterns = [
        r'<script.*?>.*?</script>',
        r'javascript:',
        r'on\w+\s*=',
        r'eval\s*\(',
        r'document\.',
        r'window\.',
        r'\bunion\b.*\bselect\b',
        r'\bdrop\b.*\btable\b'
    ]
    
    request_str = str(request_data).lower()
    for pattern in dangerous_patterns:
        if re.search(pattern, request_str, re.IGNORECASE):
            logger.critical(f"🚨 SECURITY ALERT: Potential injection attempt detected")
            return False
    
    return True
```

### Access Control

#### Rate Limiting Security
```python
class SecurityAwareRateLimiter:
    def __init__(self):
        self.request_history = {}
        self.blocked_ips = set()
        self.max_requests_per_minute = 200
        self.suspicious_threshold = 50  # Requests per minute that trigger review
    
    async def check_rate_limit_security(self, client_identifier):
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        # Clean old requests
        if client_identifier in self.request_history:
            self.request_history[client_identifier] = [
                req_time for req_time in self.request_history[client_identifier]
                if req_time > minute_ago
            ]
        else:
            self.request_history[client_identifier] = []
        
        # Count recent requests
        recent_requests = len(self.request_history[client_identifier])
        
        # Security checks
        if recent_requests > self.max_requests_per_minute:
            logger.critical(f"🚨 SECURITY: Rate limit exceeded by {client_identifier}")
            self.blocked_ips.add(client_identifier)
            return False
        
        if recent_requests > self.suspicious_threshold:
            logger.warning(f"⚠️ SECURITY: Suspicious request rate from {client_identifier}")
        
        # Record this request
        self.request_history[client_identifier].append(now)
        return True
```

### Data Protection

#### Secure Data Storage
```python
class SecureDataStore:
    def __init__(self, encryption_key):
        self.cipher = Fernet(encryption_key)
        self.data_dir = os.path.join(os.path.expanduser('~'), '.trading_system_secure')
        self._ensure_secure_directory()
    
    def _ensure_secure_directory(self):
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            os.chmod(self.data_dir, 0o700)  # Owner only
    
    def store_encrypted_data(self, filename, data):
        file_path = os.path.join(self.data_dir, filename)
        encrypted_data = self.cipher.encrypt(json.dumps(data).encode())
        
        with open(file_path, 'wb') as f:
            f.write(encrypted_data)
        
        os.chmod(file_path, 0o600)  # Owner read/write only
    
    def load_encrypted_data(self, filename):
        file_path = os.path.join(self.data_dir, filename)
        
        if not os.path.exists(file_path):
            return None
        
        with open(file_path, 'rb') as f:
            encrypted_data = f.read()
        
        try:
            decrypted_data = self.cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            logger.error(f"Failed to decrypt data from {filename}: {e}")
            return None
```

---

## Conclusion

This comprehensive wiki provides everything needed to understand, deploy, and maintain the AI-Driven Trading System. The system represents a sophisticated approach to algorithmic trading with institutional-grade safety features and professional risk management.

### Key Takeaways

1. **Safety First**: The system prioritizes capital preservation through multiple layers of risk protection
2. **AI Integration**: Artificial intelligence enhances decision-making while maintaining human oversight
3. **Professional Grade**: Production-ready architecture with comprehensive error handling and monitoring
4. **Educational Value**: Transparent design allows learning from real trading system implementation
5. **Continuous Improvement**: Modular architecture enables easy enhancement and customization

### Next Steps for Users

1. **Start with Paper Trading**: Always begin with paper trading to validate performance
2. **Understand the Risks**: Read all disclaimers and risk warnings thoroughly
3. **Monitor Performance**: Use the built-in analytics to track and improve results
4. **Stay Updated**: Keep the system updated with latest security patches and improvements
5. **Community Engagement**: Contribute improvements and share experiences

### Support and Resources

- **GitHub Repository**: Source code, issues, and community discussions
- **Documentation**: Comprehensive guides and API references  
- **Best Practices**: Proven configurations and strategies
- **Security Updates**: Regular patches and security improvements

---

**⚠️ Final Disclaimer**: This system is for educational and informational purposes only. All trading involves substantial risk of loss. Past performance does not guarantee future results. Users are responsible for all trading decisions and outcomes. Always comply with applicable laws and regulations.

**🔒 Security Notice**: Keep API credentials secure, use strong passwords, enable two-factor authentication where available, and regularly review security logs.

**📊 Performance Notice**: Results may vary based on market conditions, configuration settings, and user modifications. Regular monitoring and adjustment may be required for optimal performance.

---

*This wiki is maintained by the AI-Trading-System community. Contributions and improvements are welcome.*

**Last Updated: August 12, 2025 | Version: 2.0 - Emergency Stop System Overhaul**