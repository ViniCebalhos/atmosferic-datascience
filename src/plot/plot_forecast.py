"""Geração de plots a partir do NetCDF de previsão.

Usa configuração de referência do plot_goes (cartopy, paleta pysteps, costa, estados).
"""

from pathlib import Path

import cartopy.feature as cfeature
import cartopy.crs as ccrs
from cartopy.feature import NaturalEarthFeature
import matplotlib.pyplot as plt
import netCDF4 as nc
import numpy as np

try:
    from pysteps.visualization import get_colormap
    PYSTEPS_CMAP = True
except ImportError:
    PYSTEPS_CMAP = False


def _get_domain(lons: np.ndarray, lats: np.ndarray) -> list[float]:
    """Domínio [lon_min, lon_max, lat_min, lat_max] para set_extent."""
    return [float(lons.min()), float(lons.max()), float(lats.min()), float(lats.max())]


def plot_forecast_netcdf(
    netcdf_path: Path | str,
    output_dir: Path | str,
    save_plots: bool = True,
    dpi: int = 300,
) -> list[Path]:
    """Gera um PNG por timestep do NetCDF de previsão.

    Usa projeção PlateCarree, paleta pysteps (intensidade mm/h), costa,
    divisas de estados e grade, em linha com plot_goes.ipynb.

    Parameters
    ----------
    netcdf_path : Path | str
        Caminho do arquivo NetCDF de saída do nowcast.
    output_dir : Path | str
        Diretório onde salvar os PNGs.
    save_plots : bool
        Se True, salva os arquivos em disco.
    dpi : int
        Resolução das imagens.

    Returns
    -------
    list[Path]
        Lista de caminhos dos PNGs gerados.
    """
    netcdf_path = Path(netcdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Paleta pysteps (intensidade em mm/h), como no plot_goes
    if PYSTEPS_CMAP:
        cmap, norm, levels, _ = get_colormap(
            ptype="intensity", units="mm/h", colorscale="pysteps"
        )
    else:
        cmap = None
        norm = None
        levels = None

    saved = []
    with nc.Dataset(netcdf_path) as ds:
        rain = ds.variables["rain_rate"][:]
        lats = np.asarray(ds.variables["latitude"][:])
        lons = np.asarray(ds.variables["longitude"][:])
        n_times = rain.shape[0]
        source = getattr(ds, "source", "goes")

        domain = _get_domain(lons, lats)
        lon_2d, lat_2d = np.meshgrid(lons, lats)

        base_name = netcdf_path.stem
        for i in range(n_times):
            fig = plt.figure(figsize=(12, 10))
            ax = plt.axes(projection=ccrs.PlateCarree())

            precip = np.ma.masked_less_equal(rain[i], 0)

            if PYSTEPS_CMAP and levels is not None:
                cs = ax.contourf(
                    lon_2d,
                    lat_2d,
                    precip,
                    transform=ccrs.PlateCarree(),
                    cmap=cmap,
                    levels=levels,
                    norm=norm,
                    zorder=10,
                )
            else:
                vmax = max(float(np.nanmax(rain[i])), 0.1)
                cs = ax.contourf(
                    lon_2d,
                    lat_2d,
                    precip,
                    transform=ccrs.PlateCarree(),
                    levels=np.linspace(0, vmax, 17),
                    cmap="YlGnBu",
                    zorder=10,
                )

            ax.set_extent(domain, crs=ccrs.PlateCarree())

            # Features geográficas (como no plot_goes)
            ax.coastlines(resolution="50m", linewidth=0.8)
            ax.add_feature(cfeature.OCEAN, color="lightblue", alpha=0.3)
            ax.add_feature(
                cfeature.LAND,
                color="lightgray",
                alpha=0.3,
                edgecolor="black",
                linewidth=0.5,
            )
            ax.add_feature(
                cfeature.LAKES, color="lightblue", alpha=0.5, edgecolor="black"
            )
            ax.add_feature(
                cfeature.RIVERS, color="blue", alpha=0.5, linewidth=0.5
            )

            # Divisas dos estados
            states = NaturalEarthFeature(
                category="cultural",
                name="admin_1_states_provinces_lines",
                scale="10m",
                edgecolor="black",
                facecolor="none",
            )
            ax.add_feature(states, linestyle="-", linewidth=1.0)

            # Grade
            gl = ax.gridlines(
                draw_labels=True,
                crs=ccrs.PlateCarree(),
                linewidth=1,
                color="gray",
                alpha=0.5,
                linestyle="--",
            )
            gl.top_labels = False
            gl.right_labels = False
            gl.xlabel_style = {"size": 10, "color": "black"}
            gl.ylabel_style = {"size": 10, "color": "black"}

            cbar = fig.colorbar(
                cs, ax=ax, orientation="horizontal", pad=0.05, shrink=0.8, aspect=30
            )
            cbar.set_label("Taxa de Precipitação (mm/h)", fontsize=12)

            ax.set_title(
                f"Nowcast — {source} — lead time {i + 1}/{n_times}",
                fontsize=14,
                pad=20,
            )

            if save_plots:
                out_name = f"{base_name}_{i + 1:02d}.png"
                out_path = output_dir / out_name
                fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
                saved.append(out_path)
            plt.close(fig)

    return saved
