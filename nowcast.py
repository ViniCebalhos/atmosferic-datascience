"""Script principal — Nowcasting de precipitação com dados GOES.

Pipeline:
1. Download de dados de satélite (GOES-19 ou GOES-16 conforme a data)
2. Leitura e regrid para o domínio configurado
3. Previsão por nowcasting (motion field + extrapolação)
4. Escrita dos resultados em NetCDF
5. (Opcional) Geração de plots
"""

import argparse
from datetime import datetime
from pathlib import Path

import pytz

from src.download.download_satellite import download_satellite_data
from src.forecast.extrapolation import extrapolate_precipitation
from src.forecast.motion_fields import calculate_motion_field
from src.parameters.nowcasting_parameters import NwcstParams
from src.plot.plot_forecast import plot_forecast_netcdf
from src.read.read_satellite import read_satellite_data
from src.write.write_netcdf import write_forecast_netcdf


def main():
    """Ponto de entrada do pipeline de nowcast."""
    parser = argparse.ArgumentParser(
        description="Nowcasting de precipitação com dados GOES (GOES-19/GOES-16)"
    )
    parser.add_argument(
        "-source",
        type=str,
        default="goes",
        help="Fonte de dados (goes, satellite)",
    )
    parser.add_argument(
        "-time",
        type=str,
        help="Data e hora no formato YYYYMMDDTHHMM",
    )
    parser.add_argument(
        "-output_path",
        type=str,
        default=None,
        help="Diretório de saída (padrão: ./outputs)",
    )
    parser.add_argument(
        "-plot",
        action="store_true",
        help="Gera plots dos resultados e salva em ./tests",
    )

    args = parser.parse_args()

    params = NwcstParams(source=args.source)

    if args.time:
        dtime = datetime.strptime(args.time, "%Y%m%dT%H%M")
    else:
        dtime = datetime.now()

    if args.output_path:
        output_path = Path(args.output_path)
    else:
        output_path = params.output_path_default

    utc = pytz.UTC
    if dtime.tzinfo is None:
        dtime = utc.localize(dtime)
    else:
        dtime = dtime.astimezone(utc)

    print("Nowcast — Processando dados de", params.source)
    print(f"Data/Hora: {dtime.strftime('%Y-%m-%d %H:%M')} UTC")
    print("Domínio:", params.domain)
    print("Frequência:", params.frequency)
    print("Diretório de saída:", output_path)
    print(f"Cache: {params.cache_dir} (max {params.cache_max_age_hours}h)")

    print("\n" + "=" * 60)
    print("FASE 1: Download de dados de satélite")
    print("=" * 60)
    downloaded_files = download_satellite_data(
        dtime=dtime,
        params=params,
        num_times=params.num_times_needed,
        verbose=True,
    )
    print(f"\n✓ Fase 1 concluída: {len(downloaded_files)} arquivos disponíveis")

    print("\n" + "=" * 60)
    print("FASE 2: Leitura e regrid dos dados de satélite")
    print("=" * 60)
    rainrate, latitude, longitude = read_satellite_data(
        file_paths=downloaded_files,
        params=params,
        new_res=0.03,
    )
    print("\n✓ Fase 2 concluída: Dados carregados e regridados")
    print(f"  Shape: {rainrate.shape} (tempo, lat, lon)")
    print(f"  Domínio: {latitude.min():.2f}° a {latitude.max():.2f}° (lat)")
    print(f"          {longitude.min():.2f}° a {longitude.max():.2f}° (lon)")

    print("\n" + "=" * 60)
    print("FASE 3: Previsão de nowcasting")
    print("=" * 60)
    print("\nSubfase 3.1: Geração de motion fields")
    print("  Método:", params.motion_method)
    motion_field = calculate_motion_field(
        precip_data=rainrate,
        method=params.motion_method,
    )
    print("  ✓ Motion field calculado: shape", motion_field.shape)

    print("\nSubfase 3.2: Extrapolação")
    print("  Método:", params.extrapolation_method)
    print(
        f"  Timesteps: {params.forecast_timesteps} "
        f"({params.forecast_timesteps * params.time_range_minutes / 60:.1f} horas)"
    )
    forecast = extrapolate_precipitation(
        precip_data=rainrate,
        motion_field=motion_field,
        timesteps=params.forecast_timesteps,
        method=params.extrapolation_method,
        R_thr=params.sprog_R_thr,
    )
    print("  ✓ Previsão gerada: shape", forecast.shape)
    print(f"\n✓ Fase 3 concluída: {params.forecast_timesteps} timesteps")

    print("\n" + "=" * 60)
    print("FASE 4: Escrita dos resultados em NetCDF")
    print("=" * 60)
    output_file = write_forecast_netcdf(
        forecast=forecast,
        latitude=latitude,
        longitude=longitude,
        start_time=dtime,
        params=params,
        output_path=output_path,
        timestep_minutes=params.time_range_minutes,
    )
    print("\n✓ Fase 4 concluída: Arquivo NetCDF salvo")
    print("  Arquivo:", output_file)

    if args.plot:
        print("\n" + "=" * 60)
        print("GERANDO PLOTS DOS RESULTADOS")
        print("=" * 60)
        plot_files = plot_forecast_netcdf(
            netcdf_path=output_file,
            output_dir=Path("tests"),
            save_plots=True,
            dpi=300,
        )
        print(f"\n✓ {len(plot_files)} plots gerados em: tests/")


if __name__ == "__main__":
    main()
