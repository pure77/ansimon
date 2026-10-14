from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
WEATHER_OUTPUT = PROCESSED_DIR / "heat_data.csv"
HEAT_ILLNESS_INPUT = RAW_DIR / "질병관리청_온열질환 감시 데이터_20250925.CSV"
HEAT_ILLNESS_OUTPUT = PROCESSED_DIR / "heat_illness.csv"
HEAT_ILLNESS_COLUMNS = ["발생일자", "나이", "발생시도", "발생시군구"]
STATION_REPLACEMENTS = {
    "가평조종": "가평",
    "경기광주": "광주",
    "연천청산": "연천",
    "북강릉": "강릉",
    "북춘천": "춘천",
    "정": "정읍",
}
REGION_REPLACEMENTS = {
    "울릉": "울릉도",
    "서귀포": "제주",
}


def read_csv(file_path: Path) -> pd.DataFrame:
    """UTF-8 또는 CP949로 저장된 CSV 파일을 읽는다."""
    try:
        return pd.read_csv(file_path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(file_path, encoding="cp949")


def require_columns(dataframe: pd.DataFrame, columns: list[str]) -> None:
    missing_columns = [column for column in columns if column not in dataframe.columns]
    if missing_columns:
        raise KeyError(f"필요한 컬럼이 없습니다: {missing_columns}")


def drop_fully_empty_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """모든 값이 결측치이거나 공백인 컬럼을 제거한다."""
    normalized = dataframe.apply(
        lambda column: column.astype("string").str.strip().replace("", pd.NA)
    )
    empty_columns = normalized.columns[normalized.isna().all()]
    return dataframe.drop(columns=empty_columns)


def normalize_station_column(dataframe: pd.DataFrame) -> pd.DataFrame:
    """지점에서 번호를 제거하고 지점명을 지역명 형식으로 통일한다."""
    require_columns(dataframe, ["지점"])

    result = dataframe.copy()
    station = result["지점"].astype("string").str.strip()
    extracted = station.str.extract(r"^(.*)\((\d+)\)$")
    station_name = extracted[0].str.replace(r"[^가-힣]", "", regex=True)
    invalid = station.notna() & (extracted[1].isna() | station_name.eq(""))
    if invalid.any():
        invalid_values = station[invalid].drop_duplicates().tolist()
        raise ValueError(f"지점 형식이 올바르지 않습니다: {invalid_values[:5]}")

    station_name = station_name.str.replace(r"[군시읍]$", "", regex=True)
    station_name = station_name.replace(STATION_REPLACEMENTS)
    result["지점"] = station_name
    return result


def normalize_weather_date_column(dataframe: pd.DataFrame) -> pd.DataFrame:
    """날씨 데이터의 일시를 YYYY-MM-DD 형식으로 통일한다."""
    require_columns(dataframe, ["일시"])

    result = dataframe.copy()
    result["일시"] = pd.to_datetime(
        result["일시"].astype("string").str.strip(),
        format="%m/%d/%Y",
        errors="raise",
    ).dt.strftime("%Y-%m-%d")
    return result


def prepare_weather_data() -> tuple[pd.DataFrame, int, int]:
    """월별 날씨 CSV를 병합하고 일시 및 지점 컬럼을 정제한다."""
    csv_files = sorted(RAW_DIR.glob("????-??.csv"))
    if not csv_files:
        raise FileNotFoundError(f"날씨 CSV 파일이 없습니다: {RAW_DIR}")

    merged = pd.concat(
        [read_csv(file_path) for file_path in csv_files], ignore_index=True
    )
    row_count_before = len(merged)
    merged = merged.drop_duplicates().reset_index(drop=True)
    duplicate_count = row_count_before - len(merged)
    require_columns(merged, ["평균기온(°C)"])
    mean_temperature = merged["평균기온(°C)"].astype("string").str.strip()
    merged = merged.loc[mean_temperature.notna() & mean_temperature.ne("")].reset_index(
        drop=True
    )
    merged = normalize_weather_date_column(merged)
    return normalize_station_column(merged), len(csv_files), duplicate_count


def prepare_heat_illness_data() -> pd.DataFrame:
    """온열질환 데이터를 지역별 65세 이상 발생 데이터로 정제한다."""
    dataframe = drop_fully_empty_columns(read_csv(HEAT_ILLNESS_INPUT))
    require_columns(dataframe, HEAT_ILLNESS_COLUMNS)
    selected = dataframe.loc[:, HEAT_ILLNESS_COLUMNS].copy()

    district = selected["발생시군구"].astype("string").str.strip()
    selected = selected.loc[district.notna() & district.ne("")].copy()
    selected["발생시도"] = selected["발생시도"].astype("string").str.strip()
    selected["발생시군구"] = district.loc[selected.index]

    city_mask = selected["발생시도"].str.endswith("시", na=False)
    non_city = selected.loc[~city_mask, ["발생일자", "나이"]].copy()
    non_city["발생지역"] = (
        selected.loc[~city_mask, "발생시군구"]
        .str.split()
        .str[0]
        .str.replace(r"[시군]$", "", regex=True)
    )
    city = selected.loc[city_mask, ["발생일자", "나이"]].copy()
    city["발생지역"] = selected.loc[city_mask, "발생시도"].str[:2]

    result = pd.concat([non_city, city], ignore_index=True)
    age = pd.to_numeric(result["나이"], errors="raise")
    if (age % 1 != 0).any():
        raise ValueError("나이 컬럼에 정수가 아닌 값이 있습니다.")

    result = result.loc[age.ge(65)].copy()
    result["나이"] = age.loc[result.index].astype("int64")
    result["발생지역"] = result["발생지역"].replace(REGION_REPLACEMENTS)
    result["발생일자"] = pd.to_datetime(result["발생일자"], errors="raise")
    result = result.sort_values("발생일자", kind="stable").reset_index(drop=True)
    result["발생일자"] = result["발생일자"].dt.strftime("%Y-%m-%d")
    return result


def keep_common_regions(
    weather: pd.DataFrame, heat_illness: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """두 데이터에 모두 존재하는 지역의 행만 남긴다."""
    stations = weather["지점"].astype("string").str.strip()
    regions = heat_illness["발생지역"].astype("string").str.strip()
    common_regions = set(stations.dropna()) & set(regions.dropna())

    weather_result = weather.loc[stations.isin(common_regions)].reset_index(drop=True)
    illness_result = heat_illness.loc[regions.isin(common_regions)].reset_index(
        drop=True
    )
    return weather_result, illness_result


def add_heat_illness_occurrence(
    weather: pd.DataFrame, heat_illness: pd.DataFrame
) -> pd.DataFrame:
    """날짜와 지역이 모두 일치하는 날씨 행에 온열질환자 발생 여부를 표시한다."""
    require_columns(weather, ["일시", "지점"])
    require_columns(heat_illness, ["발생일자", "발생지역"])

    result = weather.copy()
    illness_keys = pd.MultiIndex.from_frame(
        heat_illness[["발생일자", "발생지역"]].drop_duplicates()
    )
    weather_keys = pd.MultiIndex.from_frame(result[["일시", "지점"]])
    result["온열질환자발생여부"] = pd.Series(
        weather_keys.isin(illness_keys), index=result.index
    ).map({True: "O", False: "X"})
    return result


def preprocess() -> tuple[pd.DataFrame, pd.DataFrame]:
    """날씨와 온열질환 데이터를 정제해 최종 CSV 파일로 저장한다."""
    weather, weather_file_count, duplicate_count = prepare_weather_data()
    heat_illness = prepare_heat_illness_data()
    weather, heat_illness = keep_common_regions(weather, heat_illness)
    weather = add_heat_illness_occurrence(weather, heat_illness)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    weather.to_csv(WEATHER_OUTPUT, index=False, encoding="utf-8-sig")
    heat_illness.to_csv(HEAT_ILLNESS_OUTPUT, index=False, encoding="utf-8-sig")

    common_region_count = weather["지점"].nunique()
    print(f"날씨 CSV {weather_file_count}개 병합 완료")
    print(f"중복 행 제거: {duplicate_count:,}개")
    print(f"공통 지역: {common_region_count:,}개")
    print(f"날씨 데이터: {len(weather):,}행 -> {WEATHER_OUTPUT}")
    print(f"온열질환 데이터: {len(heat_illness):,}행 -> {HEAT_ILLNESS_OUTPUT}")
    return weather, heat_illness


if __name__ == "__main__":
    preprocess()
