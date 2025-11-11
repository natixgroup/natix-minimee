"""
Utility tools for Minimee agents
Calendar, date/time, weather, and other utility functions
"""
from langchain.tools import tool
from typing import Optional
from datetime import datetime, timezone
import json


@tool
def get_current_date() -> str:
    """
    Get the current date and time. 
    CRITICAL: ALWAYS use this tool when the user asks about the current date, today's date, what day it is, 
    or the current time. Do NOT guess or invent dates - use this tool to get the real current date.
    Examples: "quelle est la date", "what is today", "what date is it", "quelle date sommes-nous"
    
    Returns:
        Current date and time in a readable format
    """
    now = datetime.now(timezone.utc)
    return f"Current date and time (UTC): {now.strftime('%Y-%m-%d %H:%M:%S UTC')}. Today is {now.strftime('%A, %B %d, %Y')}."


@tool
def get_current_time(timezone_name: Optional[str] = None) -> str:
    """
    Get the current time, optionally in a specific timezone.
    
    Args:
        timezone_name: Optional timezone name (e.g., 'Europe/Paris', 'America/New_York')
                      If not provided, returns UTC time.
    
    Returns:
        Current time in the specified timezone
    """
    from datetime import datetime
    import pytz
    
    if timezone_name:
        try:
            tz = pytz.timezone(timezone_name)
            now = datetime.now(tz)
            return f"Current time in {timezone_name}: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}"
        except Exception as e:
            return f"Error: Invalid timezone '{timezone_name}'. {str(e)}"
    else:
        now = datetime.now(timezone.utc)
        return f"Current time (UTC): {now.strftime('%Y-%m-%d %H:%M:%S UTC')}"


@tool
def calculate_date_difference(date1: str, date2: str) -> str:
    """
    Calculate the difference between two dates.
    
    Args:
        date1: First date in format YYYY-MM-DD
        date2: Second date in format YYYY-MM-DD
    
    Returns:
        Difference in days between the two dates
    """
    try:
        from datetime import datetime
        d1 = datetime.strptime(date1, '%Y-%m-%d')
        d2 = datetime.strptime(date2, '%Y-%m-%d')
        diff = abs((d2 - d1).days)
        return f"Difference between {date1} and {date2}: {diff} days"
    except Exception as e:
        return f"Error calculating date difference: {str(e)}. Please use format YYYY-MM-DD."


@tool
def get_weather(location: str) -> str:
    """
    Get current weather information for a location.
    Note: This is a placeholder. For production, integrate with a weather API (OpenWeatherMap, etc.)
    
    Args:
        location: City name or location (e.g., "Paris", "New York")
    
    Returns:
        Weather information for the location
    """
    # TODO: Integrate with a real weather API (OpenWeatherMap, WeatherAPI, etc.)
    return f"Weather information for {location} is not available yet. Weather API integration pending."


@tool
def search_web(query: str) -> str:
    """
    Search the web for information.
    Note: This is a placeholder. For production, integrate with a search API (Google Search, DuckDuckGo, etc.)
    
    Args:
        query: Search query
    
    Returns:
        Search results
    """
    # TODO: Integrate with a real search API (Google Search API, DuckDuckGo, Tavily, etc.)
    return f"Web search for '{query}' is not available yet. Search API integration pending."


@tool
def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """
    Convert currency from one to another.
    Note: This is a placeholder. For production, integrate with a currency API.
    
    Args:
        amount: Amount to convert
        from_currency: Source currency code (e.g., "USD", "EUR")
        to_currency: Target currency code (e.g., "USD", "EUR")
    
    Returns:
        Converted amount
    """
    # TODO: Integrate with a real currency API (ExchangeRate-API, Fixer.io, etc.)
    return f"Currency conversion from {amount} {from_currency} to {to_currency} is not available yet. Currency API integration pending."


@tool
def get_timezone_info(timezone_name: str) -> str:
    """
    Get information about a timezone.
    
    Args:
        timezone_name: Timezone name (e.g., 'Europe/Paris', 'America/New_York')
    
    Returns:
        Timezone information including current time and UTC offset
    """
    try:
        import pytz
        from datetime import datetime
        
        tz = pytz.timezone(timezone_name)
        now = datetime.now(tz)
        utc_offset = now.strftime('%z')
        
        return f"Timezone: {timezone_name}\nCurrent time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}\nUTC offset: {utc_offset}"
    except Exception as e:
        return f"Error: Invalid timezone '{timezone_name}'. {str(e)}"

