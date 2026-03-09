"""Extrapolação de precipitação (nowcasting)."""

from numpy.typing import NDArray

from pysteps import nowcasts


def extrapolate_precipitation(
    precip_data: NDArray,
    motion_field: NDArray,
    timesteps: int,
    method: str = "sprog",
    R_thr: float = 0.5,
) -> NDArray:
    """Gera previsão por extrapolação (SPROG ou ANVIL).

    Parameters
    ----------
    precip_data : NDArray
        Array 3D (tempo, lat, lon) de precipitação em mm/h.
    motion_field : NDArray
        Campo de movimento (saída de calculate_motion_field).
    timesteps : int
        Número de passos de tempo da previsão.
    method : str
        "sprog" ou "anvil".
    R_thr : float
        Limiar de precipitação para SPROG (mm/h).

    Returns
    -------
    NDArray
        Previsão 3D (tempo, lat, lon).
    """
    if method == "sprog":
        nowcast_fn = nowcasts.get_method("sprog")
        # pysteps pode usar R_thr (versões antigas) ou precip_thr (novas)
        result = nowcast_fn(
            precip_data[-3:, :, :],
            motion_field,
            timesteps=timesteps,
            precip_thr=R_thr,
        )
    elif method == "anvil":
        nowcast_fn = nowcasts.get_method("anvil")
        result = nowcast_fn(
            precip_data,
            motion_field,
            timesteps=timesteps,
        )
    else:
        raise ValueError(f"Método desconhecido: {method}. Use 'sprog' ou 'anvil'.")
    # pysteps pode retornar (precip, metadata) ou só precip
    forecast = result[0] if isinstance(result, tuple) else result
    return forecast
