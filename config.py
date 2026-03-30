import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "naver_config.json")


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return None
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(data):
    required_keys = {
        "searchad": ["customer_id", "api_key", "secret_key"],
        "search": ["client_id", "client_secret"],
    }
    for section, keys in required_keys.items():
        if section not in data:
            raise ValueError(f"'{section}' 섹션이 필요합니다.")
        for key in keys:
            if not data[section].get(key, "").strip():
                raise ValueError(f"'{section}.{key}' 값을 입력해주세요.")

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def has_config():
    return os.path.exists(CONFIG_PATH)
