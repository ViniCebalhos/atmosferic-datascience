"""Escrita da previsão em NetCDF."""

from datetime import datetime
from pathlib import Path

import netCDF4 as nc
from numpy.typing import NDArray

from src.parameters.nowcasting_parameters import NwcstParams


def write_forecast_netcdf(
    forecast: NDArray,
    latitude: NDArray,
    longitude: NDArray,
    start_time: datetime,
    params: NwcstParams,
    output_path: Path,
    timestep_minutes: int = 10,
) -> Path:
    """Escreve a previsão em um arquivo NetCDF.

    Parameters
    ----------
    forecast : NDArray
        Array 3D (tempo, lat, lon) em mm/h.
    latitude : NDArray
        Vetor 1D de latitudes.
    longitude : NDArray
        Vetor 1D de longitudes.
    start_time : datetime
        Data/hora de início da previsão.
    params : NwcstParams
        Parâmetros (formato do nome do arquivo, etc.).
    output_path : Path
        Diretório de saída.
    timestep_minutes : int
        Intervalo entre passos em minutos.

    Returns
    -------
    Path
        Caminho do arquivo NetCDF criado.
    """
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    n_times = forecast.shape[0]
    runtime = start_time
    seconds = [i * timestep_minutes * 60 for i in range(1, n_times + 1)]

    filename = params.output_format.format(runtime)
    filepath = output_path / filename

    with nc.Dataset(filepath, "w", format="NETCDF4") as fout:
        fout.set_fill_off()

        fout.createDimension("time", n_times)
        time_var = fout.createVariable("time", "f8", ("time",))
        time_var[:] = seconds
        time_var.units = "seconds since " + runtime.strftime("%Y-%m-%d %H:%M:00")
        time_var.long_name = "Time of grid"

        fout.createDimension("latitude", len(latitude))
        lat_var = fout.createVariable("latitude", "f4", ("latitude",))
        lat_var[:] = latitude
        lat_var.units = "degrees_north"
        lat_var.long_name = "Latitude points"

        fout.createDimension("longitude", len(longitude))
        lon_var = fout.createVariable("longitude", "f4", ("longitude",))
        lon_var[:] = longitude
        lon_var.units = "degrees_east"
        lon_var.long_name = "Longitude points"

        fout.source = params.source
        fout.Conventions = "CF-1.6"

        rain_var = fout.createVariable(
            "rain_rate",
            "f4",
            ("time", "latitude", "longitude"),
            fill_value=-9999.0,
            zlib=True,
            complevel=5,
        )
        rain_var[:] = forecast
        rain_var.units = "mm/h"
        rain_var.long_name = "Previsão de precipitação (nowcast GOES)"

    return filepath
