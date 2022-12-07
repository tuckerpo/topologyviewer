"""Module for parsing NBAPI metadata"""

def __token_is_device(token: str):
    return token == "Device"

def __should_skip_device_token(token: str, idx: int):
    return __token_is_device(token) and idx == 0

def parse_index_from_path_by_key(path: str, key: str) -> str:
    """Parse the NBAPI index of a keyword from a NBAPI path string.
    Example: `parse_index_from_path_by_key("Device.WiFi.DataElements.Device.1.Radio.3.BSS.4", "Radio") returns "3".

    Args:
        path (str): The NBAPI path string (i.e. "Device.WiFi.DataElements.Device.1.")
        key (str): The keyword to find the index for
    """
    split_path = path.split('.')
    for token_idx, token in enumerate(split_path):
        if token == key:
            # Special case: all NBAPI paths are prefixed by "Device", so ignore the first instance of this token.
            if __should_skip_device_token(token, token_idx):
                continue
            if len(split_path) > (token_idx + 1):
                return split_path[token_idx + 1]
    return ""
