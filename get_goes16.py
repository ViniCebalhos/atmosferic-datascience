#!/usr/bin/env python3
"""
Script para download dos dados RRQPE do satélite GOES-16 com suporte a paralelização
Suporta execução via linha de comando e como módulo Python
"""

import s3fs
import time
import argparse
from datetime import datetime, timedelta
import pytz
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import threading

# Lock para impressão thread-safe
print_lock = Lock()

def thread_safe_print(*args, **kwargs):
    """Imprime de forma thread-safe"""
    with print_lock:
        print(*args, **kwargs)

def get_time(dt=None):
    """
    Obtém a data e hora em UTC, arredondada para o múltiplo de 10 minutos mais próximo.
    Se uma data e hora forem fornecidas, usa essa data e hora.

    Parameters
    ----------
    dt : datetime, optional
        Data e hora para arredondar e converter (default é None, usa a data e hora atuais).

    Returns
    -------
    tuple
        Uma tupla contendo o ano, mês, dia, hora, minuto arredondado e o dia do ano no fuso horário UTC.
    """
    # Definindo o fuso horário como UTC
    utc_timezone = pytz.timezone('UTC')

    # Se dt for None, use a data e hora atuais
    if dt is None:
        dt = datetime.now(utc_timezone)
    else:
        # Garantir que dt está em UTC
        if dt.tzinfo is None:
            dt = utc_timezone.localize(dt)
        else:
            dt = dt.astimezone(utc_timezone)

    # Arredondando os minutos para o múltiplo mais próximo de 10
    minuto_arredondado = dt.minute - (dt.minute % 10)
    dt = dt.replace(minute=minuto_arredondado, second=0, microsecond=0)

    # Extraindo dia, mês, ano, hora e minutos do horário atual no fuso horário UTC
    day = str(dt.day).zfill(2)
    month = str(dt.month).zfill(2)
    year = dt.year
    hour = str(dt.hour).zfill(2)
    minute = str(dt.minute).zfill(2)

    # Obtendo o dia do ano e formatando com três dígitos
    day_year = str(dt.timetuple().tm_yday).zfill(3)

    return year, month, day, hour, minute, day_year

def get_goes_single(dt, output_path='/mnt/ssd/vinicius/db/noaa-goes16', max_retries=10, wait_time=60, verbose=True, skip_existing=True, dry_run=False, organize_folders=True, thread_id=None):
    """
    Realiza o download de um único arquivo GOES (versão thread-safe).
    
    Parameters
    ----------
    dt : datetime
        Data e hora para baixar os dados
    output_path : str
        Diretório onde salvar os arquivos
    max_retries : int
        Número máximo de tentativas para verificar a existência do diretório
    wait_time : int
        Tempo em segundos para esperar entre tentativas
    verbose : bool
        Se True, imprime mensagens de status
    skip_existing : bool
        Se True, pula arquivos que já existem
    dry_run : bool
        Se True, simula a execução sem baixar arquivos
    organize_folders : bool
        Se True, organiza arquivos em pastas por ano/dia_do_ano
    thread_id : int
        ID da thread para logs
        
    Returns
    -------
    dict
        Dicionário com informações sobre o download
    """
    result = {
        'datetime': dt,
        'success': False,
        'file_path': None,
        'error': None,
        'skipped': False,
        'thread_id': thread_id
    }
    
    try:
        # Obtém a data e hora arredondadas
        year, month, day, hour, minute, day_year = get_time(dt)

        # Cada thread deve ter sua própria instância do S3FileSystem
        fs = s3fs.S3FileSystem(anon=True)

        # Constrói o caminho S3
        s3_path = f'noaa-goes16/ABI-L2-RRQPEF/{year}/{day_year}/{hour}'

        if verbose:
            thread_safe_print(f"[Thread {thread_id}] Procurando dados para: {year}-{month}-{day} {hour}:{minute} UTC")

        # Verifica se a pasta existe, com tentativas múltiplas
        retries = 0
        files = []
        
        while retries < max_retries:
            try:
                files = fs.ls(s3_path)
                if files:
                    break
            except FileNotFoundError:
                pass
            except Exception as e:
                if verbose:
                    thread_safe_print(f"[Thread {thread_id}] Erro ao acessar S3: {e}")
            
            retries += 1
            if verbose and retries < max_retries:
                thread_safe_print(f"[Thread {thread_id}] Tentativa {retries} falhou. Esperando {wait_time} segundos...")
            time.sleep(wait_time)
        
        # Verifica se o limite de tentativas foi atingido
        if not files:
            result['error'] = f"Nenhum arquivo encontrado no caminho {s3_path} após {max_retries} tentativas."
            if verbose:
                thread_safe_print(f"[Thread {thread_id}] ERRO: {result['error']}")
            return result

        # Filtrar arquivos que correspondam ao minuto arredondado
        target_timestamp = f"_s{year}{day_year}{hour}{minute}"
        desired_file = None
        
        for file in files:
            if target_timestamp in file:
                desired_file = file
                break
        
        # Se não encontrar o arquivo exato, pegar o mais recente da hora
        if desired_file is None:
            # Filtrar arquivos da mesma hora
            hour_files = [f for f in files if f"_s{year}{day_year}{hour}" in f]
            if hour_files:
                desired_file = sorted(hour_files)[-1]  # Pega o mais recente
                if verbose:
                    thread_safe_print(f"[Thread {thread_id}] Arquivo exato não encontrado, usando o mais recente da hora")
            else:
                desired_file = sorted(files)[-1]  # Pega o mais recente do dia
                if verbose:
                    thread_safe_print(f"[Thread {thread_id}] Nenhum arquivo da hora encontrado, usando o mais recente do dia")
        
        # Define o nome do arquivo local
        filename = desired_file.split("/")[-1]
        
        # Organiza em pastas por ano/dia_do_ano se solicitado
        if organize_folders:
            final_output_path = os.path.join(output_path, str(year), day_year)
        else:
            final_output_path = output_path
            
        local_file_path = os.path.join(final_output_path, filename)

        # Cria o diretório de saída se não existir
        if not dry_run:
            os.makedirs(final_output_path, exist_ok=True)

        # Só baixa se não existir (ou se skip_existing for False)
        if os.path.exists(local_file_path) and skip_existing:
            if verbose:
                thread_safe_print(f"[Thread {thread_id}] Arquivo já existe (pulando): {filename}")
            result['success'] = True
            result['file_path'] = local_file_path
            result['skipped'] = True
            return result
        
        if dry_run:
            if verbose:
                thread_safe_print(f"[Thread {thread_id}] [DRY RUN] Baixaria arquivo: {filename}")
            result['success'] = True
            result['file_path'] = local_file_path
            return result

        # Baixar o arquivo
        if verbose:
            thread_safe_print(f"[Thread {thread_id}] Baixando arquivo: {filename}")
        
        fs.get(desired_file, local_file_path)
        
        if verbose:
            thread_safe_print(f"[Thread {thread_id}] ✓ Arquivo baixado: {filename}")
        
        result['success'] = True
        result['file_path'] = local_file_path
        
    except Exception as e:
        result['error'] = str(e)
        if verbose:
            thread_safe_print(f"[Thread {thread_id}] ERRO ao baixar arquivo: {e}")
    
    return result

def get_goes(dt=None, output_path='/mnt/ssd/vinicius/db/noaa-goes16', max_retries=10, wait_time=60, verbose=True, skip_existing=True, dry_run=False, organize_folders=True):
    """
    Versão de compatibilidade da função original (single-thread).
    """
    result = get_goes_single(dt, output_path, max_retries, wait_time, verbose, skip_existing, dry_run, organize_folders, thread_id=1)
    return result['file_path'] if result['success'] else None

def download_time_range_parallel(start_dt, end_dt, output_path='/mnt/ssd/vinicius/db/noaa-goes16', 
                                interval_minutes=10, max_retries=10, wait_time=60, verbose=True, 
                                skip_existing=True, dry_run=False, organize_folders=True, 
                                max_workers=10, progress_interval=100):
    """
    Baixa dados GOES para um intervalo de tempo usando paralelização.
    
    Parameters
    ----------
    start_dt : datetime
        Data/hora de início
    end_dt : datetime  
        Data/hora de fim
    output_path : str
        Diretório de saída
    interval_minutes : int
        Intervalo em minutos entre downloads
    max_retries : int
        Número máximo de tentativas por arquivo
    wait_time : int
        Tempo de espera entre tentativas
    verbose : bool
        Se True, imprime mensagens de status
    skip_existing : bool
        Se True, pula arquivos que já existem
    dry_run : bool
        Se True, simula a execução sem baixar arquivos
    organize_folders : bool
        Se True, organiza arquivos em pastas por ano/dia_do_ano
    max_workers : int
        Número máximo de threads paralelas
    progress_interval : int
        Intervalo para mostrar progresso (a cada N arquivos)
        
    Returns
    -------
    dict
        Dicionário com estatísticas do download
    """
    # Gerar lista de timestamps
    timestamps = []
    current_dt = start_dt
    while current_dt <= end_dt:
        timestamps.append(current_dt)
        current_dt += timedelta(minutes=interval_minutes)
    
    total_files = len(timestamps)
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"DOWNLOAD PARALELO INICIADO")
        print(f"Período: {start_dt.strftime('%Y-%m-%d %H:%M')} até {end_dt.strftime('%Y-%m-%d %H:%M')} UTC")
        print(f"Total de arquivos: {total_files:,}")
        print(f"Threads paralelas: {max_workers}")
        print(f"Intervalo: {interval_minutes} minutos")
        print(f"{'='*60}\n")
    
    # Estatísticas
    stats = {
        'total': total_files,
        'success': 0,
        'errors': 0,
        'skipped': 0,
        'downloaded_files': [],
        'failed_times': [],
        'start_time': time.time()
    }
    
    # Executar downloads em paralelo
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submeter todas as tarefas
        future_to_dt = {
            executor.submit(
                get_goes_single,
                dt=dt,
                output_path=output_path,
                max_retries=max_retries,
                wait_time=wait_time,
                verbose=verbose,
                skip_existing=skip_existing,
                dry_run=dry_run,
                organize_folders=organize_folders,
                thread_id=i % max_workers + 1
            ): dt for i, dt in enumerate(timestamps)
        }
        
        # Processar resultados conforme completam
        completed = 0
        for future in as_completed(future_to_dt):
            dt = future_to_dt[future]
            result = future.result()
            completed += 1
            
            if result['success']:
                stats['success'] += 1
                if result['skipped']:
                    stats['skipped'] += 1
                else:
                    stats['downloaded_files'].append(result['file_path'])
            else:
                stats['errors'] += 1
                stats['failed_times'].append((dt, result['error']))
            
            # Mostrar progresso
            if verbose and (completed % progress_interval == 0 or completed == total_files):
                elapsed = time.time() - stats['start_time']
                rate = completed / elapsed if elapsed > 0 else 0
                eta = (total_files - completed) / rate if rate > 0 else 0
                
                thread_safe_print(f"Progresso: {completed}/{total_files} ({completed/total_files*100:.1f}%) | "
                                f"Sucesso: {stats['success']} | Erros: {stats['errors']} | "
                                f"Taxa: {rate:.1f} arq/s | ETA: {eta/60:.1f}min")
    
    stats['total_time'] = time.time() - stats['start_time']
    
    return stats

def download_time_range(start_dt, end_dt, output_path='/mnt/ssd/vinicius/db/noaa-goes16', interval_minutes=10, max_retries=10, wait_time=60, verbose=True, skip_existing=True, dry_run=False, organize_folders=True, max_workers=1):
    """
    Versão de compatibilidade que suporta tanto serial quanto paralelo.
    """
    if max_workers > 1:
        stats = download_time_range_parallel(
            start_dt, end_dt, output_path, interval_minutes, max_retries, 
            wait_time, verbose, skip_existing, dry_run, organize_folders, max_workers
        )
        return stats['downloaded_files']
    else:
        # Versão serial original
        downloaded_files = []
        current_dt = start_dt
        
        while current_dt <= end_dt:
            if verbose:
                print(f"\n--- Processando: {current_dt.strftime('%Y-%m-%d %H:%M')} UTC ---")
            
            file_path = get_goes(
                dt=current_dt,
                output_path=output_path,
                max_retries=max_retries,
                wait_time=wait_time,
                verbose=verbose,
                skip_existing=skip_existing,
                dry_run=dry_run,
                organize_folders=organize_folders
            )
            
            if file_path:
                downloaded_files.append(file_path)
            
            current_dt += timedelta(minutes=interval_minutes)
        
        return downloaded_files

def download_latest(output_path='/mnt/ssd/vinicius/db/noaa-goes16', num_times=6, max_retries=10, wait_time=60, verbose=True, organize_folders=True, max_workers=4):
    """
    Baixa os últimos N tempos disponíveis (com suporte a paralelização).
    """
    timestamps = []
    current_dt = datetime.now(pytz.UTC)
    
    for i in range(num_times):
        dt = current_dt - timedelta(minutes=i * 10)
        timestamps.append(dt)
    
    if max_workers > 1:
        # Usar versão paralela
        end_dt = timestamps[-1]
        start_dt = timestamps[0]
        stats = download_time_range_parallel(
            start_dt, end_dt, output_path, 10, max_retries, 
            wait_time, verbose, True, False, organize_folders, max_workers
        )
        return stats['downloaded_files']
    else:
        # Versão serial original
        downloaded_files = []
        for i, dt in enumerate(timestamps):
            if verbose:
                print(f"\n--- Baixando tempo {i+1}/{num_times}: {dt.strftime('%Y-%m-%d %H:%M')} UTC ---")
            
            file_path = get_goes(
                dt=dt,
                output_path=output_path,
                max_retries=max_retries,
                wait_time=wait_time,
                verbose=verbose,
                organize_folders=organize_folders
            )
            
            if file_path:
                downloaded_files.append(file_path)
        
        return downloaded_files

def parse_datetime(date_str):
    """
    Converte string de data/hora para objeto datetime.
    Formatos suportados: YYYY-MM-DDTHH:MM, YYYY-MM-DD HH:MM, YYYYMMDDHHMM
    """
    formats = [
        '%Y-%m-%dT%H:%M',
        '%Y-%m-%d %H:%M', 
        '%Y%m%d%H%M',
        '%Y-%m-%d',
        '%Y%m%d'
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return pytz.UTC.localize(dt)
        except ValueError:
            continue
    
    raise ValueError(f"Formato de data inválido: {date_str}")

def main():
    """Função principal para execução via linha de comando."""
    parser = argparse.ArgumentParser(
        description='Download de dados RRQPE do satélite GOES-16 (com suporte a paralelização)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python goes_download.py --latest 6 --workers 4
  python goes_download.py --start 2024-01-15T12:00 --end 2024-01-15T18:00 --workers 8
  python goes_download.py --year 2024 --workers 10 --output ./dados_2024
  python goes_download.py --month 2024-01 --workers 6 --output ./dados_jan
  python goes_download.py --single 2024-01-15T15:30
        """
    )
    
    # Grupo para diferentes modos de operação
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('--latest', type=int, metavar='N',
                           help='Baixa os últimos N tempos (padrão: 6)')
    mode_group.add_argument('--start', type=str, metavar='DATETIME',
                           help='Data/hora de início (formato: YYYY-MM-DDTHH:MM)')
    mode_group.add_argument('--single', type=str, metavar='DATETIME',
                           help='Baixa um único tempo específico')
    mode_group.add_argument('--year', type=int, metavar='YYYY',
                           help='Baixa todo um ano (ex: 2024)')
    mode_group.add_argument('--month', type=str, metavar='YYYY-MM',
                           help='Baixa todo um mês (ex: 2024-01)')
    
    parser.add_argument('--end', type=str, metavar='DATETIME',
                       help='Data/hora de fim (necessário com --start)')
    parser.add_argument('--output', '-o', type=str, default='/mnt/ssd/vinicius/db/noaa-goes16',
                       help='Diretório de saída (padrão: /mnt/ssd/vinicius/db/noaa-goes16)')
    parser.add_argument('--interval', type=int, default=10,
                       help='Intervalo em minutos entre downloads (padrão: 10)')
    parser.add_argument('--workers', '-w', type=int, default=1,
                       help='Número de threads paralelas (padrão: 1, recomendado: 4-10)')
    parser.add_argument('--max-retries', type=int, default=10,
                       help='Número máximo de tentativas por arquivo (padrão: 10)')
    parser.add_argument('--wait-time', type=int, default=60,
                       help='Tempo de espera entre tentativas em segundos (padrão: 60)')
    parser.add_argument('--skip-existing', action='store_true', default=True,
                       help='Pular arquivos que já existem (acelera re-execuções)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Simular execução sem baixar arquivos')
    parser.add_argument('--no-organize', action='store_true',
                       help='Não organizar arquivos em pastas por ano/dia')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Executar em modo silencioso')
    parser.add_argument('--progress-interval', type=int, default=100,
                       help='Intervalo para mostrar progresso (padrão: a cada 100 arquivos)')
    
    args = parser.parse_args()
    
    verbose = not args.quiet
    organize_folders = not args.no_organize
    downloaded_files = []
    
    # Validar número de workers
    if args.workers < 1:
        parser.error("Número de workers deve ser pelo menos 1")
    if args.workers > 20:
        print("AVISO: Usar mais de 20 workers pode causar throttling do servidor S3")
    
    try:
        if args.latest:
            # Modo: baixar últimos N tempos
            num_times = args.latest if args.latest > 0 else 6
            downloaded_files = download_latest(
                output_path=args.output,
                num_times=num_times,
                max_retries=args.max_retries,
                wait_time=args.wait_time,
                verbose=verbose,
                organize_folders=organize_folders,
                max_workers=args.workers
            )
            
        elif args.year:
            # Modo: baixar ano completo
            start_dt = datetime(args.year, 1, 1, 0, 0)
            end_dt = datetime(args.year, 12, 31, 23, 59)
            start_dt = pytz.UTC.localize(start_dt)
            end_dt = pytz.UTC.localize(end_dt)
            
            if verbose:
                print(f"Baixando dados para todo o ano {args.year}")
                print(f"Período: {start_dt.strftime('%Y-%m-%d %H:%M')} até {end_dt.strftime('%Y-%m-%d %H:%M')} UTC")
                total_times = int((end_dt - start_dt).total_seconds() / (args.interval * 60)) + 1
                print(f"Estimativa de {total_times:,} arquivos para baixar")
                if args.workers > 1:
                    print(f"Usando {args.workers} threads paralelas")
            
            if args.workers > 1:
                stats = download_time_range_parallel(
                    start_dt=start_dt,
                    end_dt=end_dt,
                    output_path=args.output,
                    interval_minutes=args.interval,
                    max_retries=args.max_retries,
                    wait_time=args.wait_time,
                    verbose=verbose,
                    skip_existing=args.skip_existing,
                    dry_run=args.dry_run,
                    organize_folders=organize_folders,
                    max_workers=args.workers,
                    progress_interval=args.progress_interval
                )
                downloaded_files = stats['downloaded_files']
                
                # Mostrar estatísticas finais
                if verbose:
                    print(f"\n{'='*60}")
                    print(f"ESTATÍSTICAS FINAIS")
                    print(f"Total de arquivos: {stats['total']:,}")
                    print(f"Sucessos: {stats['success']:,}")
                    print(f"Erros: {stats['errors']:,}")
                    print(f"Pulados: {stats['skipped']:,}")
                    print(f"Tempo total: {stats['total_time']/60:.1f} minutos")
                    print(f"Taxa média: {stats['success']/stats['total_time']:.1f} arquivos/segundo")
                    if stats['failed_times']:
                        print(f"\nPrimeiros 10 erros:")
                        for dt, error in stats['failed_times'][:10]:
                            print(f"  {dt.strftime('%Y-%m-%d %H:%M')}: {error}")
                    print(f"{'='*60}")
            else:
                downloaded_files = download_time_range(
                    start_dt=start_dt,
                    end_dt=end_dt,
                    output_path=args.output,
                    interval_minutes=args.interval,
                    max_retries=args.max_retries,
                    wait_time=args.wait_time,
                    verbose=verbose,
                    skip_existing=args.skip_existing,
                    dry_run=args.dry_run,
                    organize_folders=organize_folders,
                    max_workers=1
                )
            
        elif args.month:
            # Modo: baixar mês completo
            year, month = map(int, args.month.split('-'))
            start_dt = datetime(year, month, 1, 0, 0)
            
            # Último dia do mês
            if month == 12:
                next_month = datetime(year + 1, 1, 1)
            else:
                next_month = datetime(year, month + 1, 1)
            end_dt = next_month - timedelta(seconds=1)
            
            start_dt = pytz.UTC.localize(start_dt)
            end_dt = pytz.UTC.localize(end_dt)
            
            if verbose:
                print(f"Baixando dados para {args.month}")
                print(f"Período: {start_dt.strftime('%Y-%m-%d %H:%M')} até {end_dt.strftime('%Y-%m-%d %H:%M')} UTC")
                if args.workers > 1:
                    print(f"Usando {args.workers} threads paralelas")
            
            downloaded_files = download_time_range(
                start_dt=start_dt,
                end_dt=end_dt,
                output_path=args.output,
                interval_minutes=args.interval,
                max_retries=args.max_retries,
                wait_time=args.wait_time,
                verbose=verbose,
                skip_existing=args.skip_existing,
                dry_run=args.dry_run,
                organize_folders=organize_folders,
                max_workers=args.workers
            )
            
        elif args.single:
            # Modo: baixar um único tempo
            dt = parse_datetime(args.single)
            file_path = get_goes(
                dt=dt,
                output_path=args.output,
                max_retries=args.max_retries,
                wait_time=args.wait_time,
                verbose=verbose,
                skip_existing=args.skip_existing,
                dry_run=args.dry_run,
                organize_folders=organize_folders
            )
            if file_path:
                downloaded_files.append(file_path)
                
        elif args.start:
            # Modo: intervalo de tempo
            if not args.end:
                parser.error("--end é obrigatório quando --start é usado")
            
            start_dt = parse_datetime(args.start)
            end_dt = parse_datetime(args.end)
            
            if start_dt > end_dt:
                parser.error("Data de início deve ser anterior à data de fim")
            
            if verbose and args.workers > 1:
                print(f"Usando {args.workers} threads paralelas")
            
            downloaded_files = download_time_range(
                start_dt=start_dt,
                end_dt=end_dt,
                output_path=args.output,
                interval_minutes=args.interval,
                max_retries=args.max_retries,
                wait_time=args.wait_time,
                verbose=verbose,
                skip_existing=args.skip_existing,
                dry_run=args.dry_run,
                organize_folders=organize_folders,
                max_workers=args.workers
            )
    
    except KeyboardInterrupt:
        print("\nDownload interrompido pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"ERRO: {e}")
        sys.exit(1)
    
    # Resumo final
    if verbose and args.workers == 1:
        print(f"\n{'='*50}")
        print(f"Download concluído!")
        print(f"Arquivos baixados: {len(downloaded_files)}")
    
    return downloaded_files

if __name__ == "__main__":
    main()