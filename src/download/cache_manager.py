"""Gerenciador de cache temporário para arquivos baixados.

Gerencia um cache temporário que mantém arquivos por no máximo 24 horas
e limpa automaticamente arquivos antigos.
"""

import os
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


class CacheManager:
    """Gerencia cache temporário de arquivos baixados."""

    def __init__(
        self,
        cache_dir: Path,
        max_age_hours: int = 24,
        auto_clean: bool = True,
    ):
        """Inicializa o gerenciador de cache.

        Parameters
        ----------
        cache_dir : Path
            Diretório onde os arquivos serão armazenados em cache.
        max_age_hours : int, optional
            Idade máxima dos arquivos em horas (padrão: 24).
        auto_clean : bool, optional
            Se True, limpa automaticamente arquivos antigos (padrão: True).
        """
        self.cache_dir = Path(cache_dir)
        self.max_age_hours = max_age_hours
        self.auto_clean = auto_clean
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if auto_clean:
            self.clean_old_files()

    def get_cache_path(self, filename: str, subdir: Optional[str] = None) -> Path:
        """Retorna o caminho completo do arquivo no cache.

        Parameters
        ----------
        filename : str
            Nome do arquivo.
        subdir : str, optional
            Subdiretório dentro do cache (ex: 'goes19', 'goes16').

        Returns
        -------
        Path
            Caminho completo do arquivo no cache.
        """
        if subdir:
            cache_path = self.cache_dir / subdir / filename
        else:
            cache_path = self.cache_dir / filename

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        return cache_path

    def exists(self, filename: str, subdir: Optional[str] = None) -> bool:
        """Verifica se um arquivo no cache expirou.

        Parameters
        ----------
        filename : str
            Nome do arquivo.
        subdir : str, optional
            Subdiretório dentro do cache.

        Returns
        -------
        bool
            True se o arquivo existe e é válido, False caso contrário.
        """
        cache_path = self.get_cache_path(filename, subdir)

        if not cache_path.exists():
            return False

        # Verifica se o arquivo ainda é válido (não expirou)
        file_age = time.time() - cache_path.stat().st_mtime
        max_age_seconds = self.max_age_hours * 3600

        if file_age > max_age_seconds:
            # Arquivo expirado, remove
            cache_path.unlink()
            return False

        return True

    def get_file_path(
        self, filename: str, subdir: Optional[str] = None
    ) -> Optional[Path]:
        """Retorna o caminho do arquivo se existir e for válido.

        Parameters
        ----------
        filename : str
            Nome do arquivo.
        subdir : str, optional
            Subdiretório dentro do cache.

        Returns
        -------
        Path, optional
            Caminho do arquivo se existir e for válido, None caso contrário.
        """
        if self.exists(filename, subdir):
            return self.get_cache_path(filename, subdir)
        return None

    def find_files_by_pattern(
        self, pattern: str, subdir: Optional[str] = None
    ) -> list[Path]:
        """Encontra arquivos no cache que correspondem a um padrão.

        Parameters
        ----------
        pattern : str
            Padrão a procurar no nome do arquivo.
        subdir : str, optional
            Subdiretório dentro do cache.

        Returns
        -------
        list[Path]
            Lista de caminhos de arquivos válidos que correspondem ao padrão.
        """
        if not self.cache_dir.exists():
            return []

        search_dir = self.cache_dir / subdir if subdir else self.cache_dir
        if not search_dir.exists():
            return []

        max_age_seconds = self.max_age_hours * 3600
        current_time = time.time()
        matching_files = []

        for file_path in search_dir.glob("*"):
            if file_path.is_file() and pattern in file_path.name:
                # Verifica se o arquivo ainda é válido
                file_age = current_time - file_path.stat().st_mtime
                if file_age <= max_age_seconds:
                    matching_files.append(file_path)
                else:
                    # Arquivo expirado, remove
                    file_path.unlink()

        return matching_files

    def clean_old_files(self) -> int:
        """Remove arquivos antigos do cache.

        Returns
        -------
        int
            Número de arquivos removidos.
        """
        if not self.cache_dir.exists():
            return 0

        removed_count = 0
        max_age_seconds = self.max_age_hours * 3600
        current_time = time.time()

        for file_path in self.cache_dir.rglob("*"):
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    file_path.unlink()
                    removed_count += 1

        return removed_count

    def get_cache_size(self) -> int:
        """Retorna o tamanho total do cache em bytes.

        Returns
        -------
        int
            Tamanho total do cache em bytes.
        """
        total_size = 0
        if self.cache_dir.exists():
            for file_path in self.cache_dir.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        return total_size

    def clear_cache(self) -> int:
        """Remove todos os arquivos do cache.

        Returns
        -------
        int
            Número de arquivos removidos.
        """
        if not self.cache_dir.exists():
            return 0

        removed_count = 0
        for file_path in self.cache_dir.rglob("*"):
            if file_path.is_file():
                file_path.unlink()
                removed_count += 1

        # Remove diretórios vazios
        for dir_path in self.cache_dir.rglob("*"):
            if dir_path.is_dir() and not any(dir_path.iterdir()):
                dir_path.rmdir()

        return removed_count

