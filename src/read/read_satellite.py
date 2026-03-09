"""Leitura e regrid de dados GOES para o domínio configurado."""

from pathlib import Path

import GOES
import numpy as np
from numpy.typing import NDArray
from scipy.interpolate import griddata

from src.parameters.nowcasting_parameters import NwcstParams


def _goes_regular_grid(
    latitude: NDArray,
    longitude: NDArray,
    rain_rate: NDArray,
    domain: list[float],
    new_res: float,
) -> tuple[NDArray, NDArray, NDArray]:
    """Regrid GOES para grade regular no domínio."""
    lon_min, lon_max, lat_min, lat_max = domain
    lat_flat = latitude.flatten()
    lon_flat = longitude.flatten()
    rain_flat = rain_rate.flatten()

    i = int((lon_max - lon_min) / new_res)
    j = int((lat_max - lat_min) / new_res)
    lat_grid_1d = np.linspace(lat_min, lat_max, num=j)
    lon_grid_1d = np.linspace(lon_min, lon_max, num=i)
    lon_grid, lat_grid = np.meshgrid(lon_grid_1d, lat_grid_1d)

    rain_regrid = griddata(
        (lon_flat, lat_flat),
        rain_flat,
        (lon_grid, lat_grid),
        method="nearest",
    )
    return rain_regrid, lon_grid_1d, lat_grid_1d


def read_satellite_data(
    file_paths: list[Path],
    params: NwcstParams,
    new_res: float = 0.03,
) -> tuple[NDArray, NDArray, NDArray]:
    """Lê arquivos GOES e regrida para grade regular no domínio.

    Parameters
    ----------
    file_paths : list[Path]
        Lista de caminhos dos arquivos NetCDF GOES (RRQPE).
    params : NwcstParams
        Parâmetros (domínio, etc.).
    new_res : float
        Resolução espacial em graus (ex.: 0.03 ~ 3.3 km).

    Returns
    -------
    rainrate : NDArray
        Array 3D (tempo, lat, lon) em mm/h.
    latitude : NDArray
        Vetor 1D de latitudes.
    longitude : NDArray
        Vetor 1D de longitudes.
    """
    domain = params.domain
    data_list = []
    latitude: NDArray | None = None
    longitude: NDArray | None = None

    for path in file_paths:
        path_str = str(path) if isinstance(path, Path) else path
        ds = GOES.open_dataset(path_str)
        RR, LonGOES, LatGOES = ds.image(
            "RRQPE", lonlat="center", domain=domain
        )
        rain_2d, lon_1d, lat_1d = _goes_regular_grid(
            LatGOES.data,
            LonGOES.data,
            RR.data,
            domain=domain,
            new_res=new_res,
        )
        data_list.append(rain_2d)
        if latitude is None:
            latitude = lat_1d
            longitude = lon_1d

    rainrate = np.array(data_list)
    return rainrate, latitude, longitude
