"""Parâmetros de nowcasting (configuração via TOML)."""

import tomllib
from datetime import datetime
from pathlib import Path

basepath = Path(__file__).parent.resolve()


class NwcstParams:
    """Classe responsável por carregar os parâmetros de nowcasting."""

    def __init__(
        self,
        source: str,
        path_params: Path = basepath / "./nowcasting_params.toml",
    ):
        """Inicializa os parâmetros de nowcasting.

        Parameters
        ----------
        source : str
            Fonte de dados (ex: 'goes', 'satellite').
        path_params : Path, optional
            Caminho para o arquivo TOML de parâmetros.
            Por padrão usa nowcasting_params.toml na pasta parameters.
        """
        self.source = source.lower()
        self.verifica_source()
        self.load_parameters(path_params)

    def verifica_source(self) -> None:
        """Verifica se o tipo de entrada é válido."""
        fontes_validas = ["goes", "satellite"]
        if self.source not in fontes_validas:
            raise ValueError(
                f"Tipo de entrada inválido: {self.source}. "
                f"Fontes válidas: {fontes_validas}"
            )

    def load_parameters(self, path_params: Path) -> None:
        """Carrega os parâmetros do arquivo TOML.

        Parameters
        ----------
        path_params : Path
            Caminho para o arquivo TOML contendo os parâmetros a serem carregados.
        """
        with open(path_params, "rb") as f:
            self.params = tomllib.load(f)

    def input_dir(self, dtime: datetime) -> Path:
        """Diretório de entrada dos arquivos.

        Parameters
        ----------
        dtime : datetime
            Data e hora que serão utilizadas para formatar o caminho do diretório.

        Returns
        -------
        Path
            Caminho completo do diretório de entrada onde os arquivos estão
            armazenados, baseado no valor de `db_path` e no padrão de
            diretório configurado para o `source`.
        """
        base = Path(self.params["geral"]["db_path"])

        dirpath = base / Path(
            self.params[self.source]["dir_path"].format(date=dtime)
        )
        return dirpath

    def input_pattern(self, dtime: datetime) -> str:
        """Padrão de busca dos arquivos.

        Parameters
        ----------
        dtime : datetime
            Data e hora que serão utilizadas para formatar o padrão de nome dos arquivos.

        Returns
        -------
        str
            O padrão de busca dos arquivos, formatado com a data fornecida.
        """
        return self.params[self.source]["input_format"].format(date=dtime)

    @property
    def frequency(self) -> str:
        """Frequência de amostragem dos dados."""
        return str(self.params[self.source]["freq"]) + "min"

    @property
    def time_range_minutes(self) -> int:
        """Tempo de intervalo para a busca dos arquivos."""
        return self.params[self.source]["freq"]

    @property
    def domain(self) -> list[float]:
        """Domínio de corte dos dados."""
        return self.params["geral"]["domain_BR"]

    @property
    def look_behind_minutes(self) -> int:
        """Tempo de atraso para a busca dos arquivos."""
        return self.params["geral"]["look_behind_minutes"]

    @property
    def output_format(self) -> str:
        """Formato de saída dos arquivos, baseado no source."""
        return self.params[self.source]["output_format"]

    @property
    def output_path_default(self) -> Path:
        """Diretório padrão de saída."""
        return Path(self.params["geral"]["output_path_default"])

    @property
    def cache_dir(self) -> Path:
        """Diretório do cache temporário."""
        return Path(self.params["geral"]["cache_dir"])

    @property
    def cache_max_age_hours(self) -> int:
        """Idade máxima dos arquivos no cache (em horas)."""
        return self.params["geral"]["cache_max_age_hours"]

    @property
    def num_times_needed(self) -> int:
        """Número de tempos necessários para previsão."""
        return self.params[self.source].get("num_times_needed", 4)

    @property
    def prefer_goes19(self) -> bool:
        """Se True, prioriza GOES-19 sobre GOES-16."""
        return self.params[self.source].get("prefer_goes19", True)

    @property
    def max_workers(self) -> int:
        """Número máximo de workers para download paralelo."""
        return self.params[self.source].get("max_workers", 4)

    @property
    def motion_method(self) -> str:
        """Método para cálculo de motion field."""
        return self.params[self.source].get("motion_method", "LK")

    @property
    def extrapolation_method(self) -> str:
        """Método de extrapolação."""
        return self.params[self.source].get("extrapolation_method", "sprog")

    @property
    def sprog_R_thr(self) -> float:
        """Threshold de precipitação para SPROG (mm/h)."""
        return self.params[self.source].get("sprog_R_thr", 0.5)

    @property
    def forecast_timesteps(self) -> int:
        """Número de timesteps para previsão."""
        return self.params[self.source].get("forecast_timesteps", 18)

