import pandas as pd
from functools import lru_cache
from modules.utils.paths import ITEM_IDS_FILE

@lru_cache(maxsize=1)
def _id_to_name_map() -> dict[int, str]:
    df = pd.read_csv(ITEM_IDS_FILE)
    df.columns = ["typeID", "groupID", "typeName", "_"]  # drop duplicate
    return pd.Series(df.typeName.values, index=df.typeID).to_dict()

@lru_cache(maxsize=1)
def _name_to_id_map() -> dict[str, int]:
    df = pd.read_csv(ITEM_IDS_FILE)
    df.columns = ["typeID", "groupID", "typeName", "_"]
    return pd.Series(df.typeID.values, index=df.typeName).to_dict()

async def map_id_to_name(type_id: int) -> str | None:
    return _id_to_name_map().get(type_id)

async def map_name_to_id(type_name: str) -> int | None:
    return _name_to_id_map().get(type_name.strip())