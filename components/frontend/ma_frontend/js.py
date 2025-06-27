"""JavaScript functions for TOS handling in Gradio callbacks.

Note: These functions are for side effects only. Gradio ignores JavaScript return values.
Python functions handle the actual return values for event chains.
"""


def TOS_SET_COOKIE(checksum, expiry_hours):
    """JavaScript to set TOS acceptance cookie"""
    return f"""() => {{
        document.cookie = 'tos_accepted_{checksum}={checksum}; max-age={expiry_hours * 3600}; path=/';
        console.log('TOS cookie set for checksum:', '{checksum}');
    }}"""


def TOS_CLEAR_COOKIE(checksum):
    """JavaScript to clear TOS acceptance cookie"""
    return f"""() => {{
        document.cookie = 'tos_accepted_{checksum}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/';
        console.log('TOS cookie cleared for checksum:', '{checksum}');
    }}"""
