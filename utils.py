#!/usr/bin/env python3
"""
Trading System Utilities
========================

Consolidated utility functions to eliminate code duplication across the trading system.
All shared datetime, order management, and configuration logic centralized here.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
import asyncio

logger = logging.getLogger(__name__)


class DateTimeUtils:
    """Centralized datetime handling utilities"""

    @staticmethod
    def parse_datetime(dt_input: Any) -> Optional[datetime]:
        """
        Robust datetime parsing that handles both strings and datetime objects

        Args:
            dt_input: String timestamp or datetime object

        Returns:
            datetime object or None if parsing fails
        """
        if dt_input is None:
            return None

        if isinstance(dt_input, datetime):
            return dt_input

        if isinstance(dt_input, str):
            try:
                import dateutil.parser
                return dateutil.parser.parse(dt_input)
            except Exception as e:
                logger.warning(f"Failed to parse datetime string '{dt_input}': {e}")
                return None

        return None

    @staticmethod
    def calculate_age_seconds(created_at: Any) -> Optional[float]:
        """
        Calculate age of an object in seconds from creation time

        Args:
            created_at: Creation timestamp (string or datetime)

        Returns:
            Age in seconds or None if calculation fails
        """
        parsed_dt = DateTimeUtils.parse_datetime(created_at)
        if parsed_dt is None:
            return None

        try:
            return (datetime.now(timezone.utc) - parsed_dt).total_seconds()
        except Exception as e:
            logger.warning(f"Failed to calculate age for {created_at}: {e}")
            return None

    @staticmethod
    def format_age(age_seconds: float) -> str:
        """Format age in seconds to human readable string"""
        if age_seconds < 60:
            return f"{age_seconds:.1f}s"
        elif age_seconds < 3600:
            return f"{age_seconds/60:.1f}m"
        else:
            return f"{age_seconds/3600:.1f}h"


class OrderUtils:
    """Centralized order management utilities"""

    @staticmethod
    def is_order_stale(order: Any, threshold_seconds: float = 120) -> Tuple[bool, str]:
        """
        Check if an order is stale based on age and status

        Args:
            order: Order object with created_at and status attributes
            threshold_seconds: Age threshold in seconds (default 2 minutes)

        Returns:
            Tuple of (is_stale: bool, reason: str)
        """
        status = getattr(order, 'status', None)
        created_at = getattr(order, 'created_at', None)

        if status != 'new':
            return False, f"status is '{status}', not 'new'"

        if not created_at:
            return False, "no creation time available"

        age_seconds = DateTimeUtils.calculate_age_seconds(created_at)
        if age_seconds is None:
            return False, "could not calculate age"

        if age_seconds > threshold_seconds:
            age_str = DateTimeUtils.format_age(age_seconds)
            return True, f"age {age_str} exceeds {threshold_seconds/60:.1f}m threshold"

        return False, f"age {DateTimeUtils.format_age(age_seconds)} under threshold"

    @staticmethod
    async def cleanup_stale_orders(gateway, symbol: Optional[str] = None,
                                 threshold_seconds: float = 120) -> int:
        """
        Clean up stale orders for a specific symbol or all symbols

        Args:
            gateway: API gateway instance
            symbol: Specific symbol to clean (None for all symbols)
            threshold_seconds: Age threshold for stale orders

        Returns:
            Number of orders cancelled
        """
        try:
            open_orders = await gateway.get_orders(status='open')
            if not open_orders:
                return 0

            # Filter by symbol if specified
            target_orders = open_orders
            if symbol:
                target_orders = [order for order in open_orders
                               if getattr(order, 'symbol', None) == symbol]

            cancelled_count = 0

            for order in target_orders:
                order_id = getattr(order, 'id', None)
                order_symbol = getattr(order, 'symbol', 'unknown')
                order_type = getattr(order, 'type', 'unknown')
                side = getattr(order, 'side', 'unknown')

                is_stale, reason = OrderUtils.is_order_stale(order, threshold_seconds)

                if is_stale and order_id:
                    logger.warning(f"🧹 STALE ORDER: {order_symbol} - {order_type} {side}, {reason}")

                    try:
                        cancel_response = await gateway.cancel_order(order_id)
                        if cancel_response and cancel_response.success:
                            logger.info(f"   ✅ Cancelled stale order {order_id}")
                            cancelled_count += 1
                        else:
                            logger.warning(f"   ⚠️ Failed to cancel stale order {order_id}")
                    except Exception as e:
                        logger.error(f"   ❌ Error cancelling order {order_id}: {e}")

            if cancelled_count > 0:
                logger.info(f"🧹 Cleanup complete: {cancelled_count} stale orders cancelled")
                await asyncio.sleep(0.5)  # Brief pause for API processing

            return cancelled_count

        except Exception as e:
            logger.error(f"Error during stale order cleanup: {e}")
            return 0


class ConfigurationValidator:
    """Validate and resolve configuration inconsistencies"""

    @staticmethod
    def get_consistent_position_limit(config_dict: Dict[str, Any]) -> int:
        """Get consistent position limit from configuration"""
        # Priority: config.py > fallback value of 30
        return config_dict.get('max_active_positions', 30)

    @staticmethod
    def get_profit_taking_config() -> Tuple[List[float], List[float]]:
        """Get consistent profit-taking configuration"""
        # Standardized aggressive profit-taking
        profit_levels = [5.0, 8.0, 12.0, 20.0]
        profit_percentages = [0.20, 0.30, 0.50, 0.75]
        return profit_levels, profit_percentages

    @staticmethod
    def validate_configuration(config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and fix common configuration issues"""
        validated = config_dict.copy()

        # Ensure consistent position limits
        if 'max_active_positions' in validated:
            if validated['max_active_positions'] < 10:
                logger.warning(f"Position limit {validated['max_active_positions']} seems low, using 30")
                validated['max_active_positions'] = 30

        # Ensure profit-taking levels are consistent
        profit_levels, profit_percentages = ConfigurationValidator.get_profit_taking_config()
        validated['profit_taking_levels'] = profit_levels
        validated['profit_taking_percentages'] = profit_percentages

        return validated


class PerformanceUtils:
    """Performance monitoring and optimization utilities"""

    @staticmethod
    def log_function_performance(func_name: str, duration_seconds: float):
        """Log function performance for monitoring"""
        if duration_seconds > 5.0:
            logger.warning(f"⏱️ SLOW: {func_name} took {duration_seconds:.2f}s")
        elif duration_seconds > 2.0:
            logger.info(f"⏱️ {func_name} took {duration_seconds:.2f}s")

    @staticmethod
    def format_percentage(value: float, precision: int = 1) -> str:
        """Consistently format percentage values"""
        return f"{value:.{precision}f}%"

    @staticmethod
    def format_currency(value: float, precision: int = 2) -> str:
        """Consistently format currency values"""
        return f"${value:,.{precision}f}"


# Convenience functions for backward compatibility
def parse_datetime_safe(dt_input: Any) -> Optional[datetime]:
    """Backward compatible datetime parsing"""
    return DateTimeUtils.parse_datetime(dt_input)


def calculate_order_age(created_at: Any) -> Optional[float]:
    """Backward compatible order age calculation"""
    return DateTimeUtils.calculate_age_seconds(created_at)


# Export main utilities
__all__ = [
    'DateTimeUtils',
    'OrderUtils',
    'ConfigurationValidator',
    'PerformanceUtils',
    'parse_datetime_safe',
    'calculate_order_age'
]