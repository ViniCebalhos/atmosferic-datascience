"""Cálculo de campo de movimento para nowcasting."""

from numpy.typing import NDArray

from pysteps import motion


def calculate_motion_field(
    precip_data: NDArray,
    method: str = "LK",
) -> NDArray:
    """Calcula o campo de movimento (advecção) a partir da precipitação.

    Parameters
    ----------
    precip_data : NDArray
        Array 3D (tempo, lat, lon) de precipitação em mm/h.
    method : str
        Método do pysteps (ex.: "LK" para Lucas-Kanade).

    Returns
    -------
    NDArray
        Campo de velocidade (2 componentes por pixel).
    """
    oflow = motion.get_method(method)
    motion_field = oflow(precip_data)
    return motion_field
