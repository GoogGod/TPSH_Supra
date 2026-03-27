import pandas as pd
from pathlib import Path
from typing import Union

def load_raw_dataset(file_path: Union[str, Path]) -> pd.DataFrame:
    """
    Загружает сырой датасет (CSV или Excel).
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path.absolute()}")
    
    if file_path.suffix.lower() == '.csv':
        df = pd.read_csv(file_path, encoding='utf-8-sig', low_memory=False)
    elif file_path.suffix.lower() == '.xlsx':
        df = pd.read_excel(file_path, header=1)
    else:
        raise ValueError(f"Неподдерживаемый формат: {file_path.suffix}")
    
    print(f"Загружено {len(df)} записей из {file_path.name}")
    print(f"Колонки: {list(df.columns)}")
    
    return df