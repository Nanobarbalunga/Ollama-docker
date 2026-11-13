#!/usr/bin/env python3
"""Backup OpenWebUI Docker: spazio, preallocazione, progress, ZIP/7z.

Dalla root della repository Ollama-docker:
  python3 script/openwebui-backup.py /mnt/backup/openwebui -e
  python3 script/openwebui-backup.py /mnt/backup/openwebui -t -a zip -p balanced
  python3 script/openwebui-backup.py /mnt/backup/openwebui -t -a 7z -p max

Python >= 3.9 su Linux; Docker Compose e accesso al daemon senza sudo.
Default: docker-compose-ollama-nvidia.yaml + docker-compose.ssl.override.yaml.
Per CPU/AMD usare -f con i propri Compose, in ordine.
Salva /app/backend/data (SQLite, chat, utenti, upload, indice vettoriale locale
ed eventuali cache). NON salva modelli Ollama, ComfyUI o Automatic1111.
Rifiuta DB/storage remoti e directory dati fuori da /app/backend/data.
Non modifica immagini, router o impostazioni HTTPS. Ferma SOLO ollama-webui.
Prealloca il TAR prima dello stop; tenta sempre il riavvio dopo errori gestibili.
ZIP è preallocato; 7z (7zz/7z richiesto) controlla lo spazio prima e durante.
Compressione e test integrità dopo il riavvio; originale sempre conservato.
Le percentuali del backup sono riferite alla stima. Nessuna cifratura.
Destinazione esistente/scrivibile, esterna ai mount, con supporto fallocate.
Non eseguire aggiornamenti o altri writer sul volume durante il backup.
SIGINT/SIGTERM recuperano il servizio; SIGKILL o perdita di alimentazione no.
.partial indica backup incompleto. SUCCESS indica completamento, non una
prova di ripristino. Conservare anche credenziali/secret esterni al volume.
-t/--timestamp aggiunge _DATA_ORA_DI_AVVIO; default cartella openwebui.
Nessun backup esistente viene sovrascritto. -h/--help mostra questa guida.
"""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile

MIB = 1024 ** 2
GIB = 1024 ** 3


def human(n):
    for u in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if n < 1024 or u == 'TiB':
            return f'{n:.1f} {u}'
        n /= 1024


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode:
        # Non stampare argomenti/env: potrebbero contenere dati sensibili.
        raise RuntimeError(f'Comando {cmd[0]} fallito ({p.returncode}): {p.stderr.strip()[-3000:]}')
    return p.stdout.strip()


def space(path, needed, reserve):
    free = shutil.disk_usage(path).free
    if free < needed + reserve:
        raise RuntimeError(f'Spazio insufficiente: liberi {human(free)}, da allocare {human(needed)}, riserva {human(reserve)}.')
    return free


class Output:
    """Preallocazione fisica; niente file sparse creati con truncate."""
    def __init__(self, path, capacity, reserve):
        self.path, self.capacity, self.reserve = path, capacity, reserve
        self.written, self.digest = 0, hashlib.sha256()
        self.file = open(path, 'xb', buffering=0)
        try:
            os.posix_fallocate(self.file.fileno(), 0, capacity)
        except BaseException:
            self.file.close()
            path.unlink(missing_ok=True)
            raise

    def write(self, data):
        required = self.written + len(data)
        if required > self.capacity:
            growth = max(required - self.capacity, 64 * MIB)
            space(self.path.parent, growth, self.reserve)
            print(f'\nStima superata per {self.path.name}: alloco altri {human(growth)}.', flush=True)
            os.posix_fallocate(self.file.fileno(), self.capacity, growth)
            self.capacity += growth
        view = memoryview(data)
        while view:
            n = self.file.write(view)
            if not n:
                raise OSError('Scrittura incompleta')
            view = view[n:]
        self.written += len(data)
        self.digest.update(data)

    def close(self):
        if not self.file.closed:
            try:
                os.ftruncate(self.file.fileno(), self.written)
                os.fsync(self.file.fileno())
            finally:
                self.file.close()


def stream(cmd, output, label):
    print(f'{label}...', flush=True)
    start = last = time.monotonic()
    # stderr su file per non bloccare il processo durante un flusso molto grande.
    with tempfile.TemporaryFile() as errors:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errors, start_new_session=True)
        try:
            while True:
                chunk = p.stdout.read(MIB)
                if not chunk:
                    break
                output.write(chunk)
                now = time.monotonic()
                if now - last >= 0.5:
                    elapsed = max(now - start, 0.001)
                    pct = min(99.9, output.written * 100 / output.capacity)
                    print(f'\r{label}: {pct:5.1f}% della stima | {human(output.written)} | {human(output.written / elapsed)}/s', end='', flush=True)
                    last = now
            rc = p.wait()
            if rc:
                errors.seek(0)
                raise RuntimeError(f'{label} fallito ({rc}): {errors.read().decode(errors="replace")[-3000:]}')
            if not output.written:
                raise RuntimeError(f'{label}: nessun dato ricevuto')
            print(f'\r{label}: completato | {human(output.written)} | {time.monotonic() - start:.1f}s' + ' ' * 15, flush=True)
        finally:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait()
            p.stdout.close()
            output.close()



def interrupt_signal(*_):
    raise KeyboardInterrupt()


def archive_backup(folder, kind, preset, reserve):
    """Comprimi solo un backup completato, dopo il recupero di Nextcloud.

    ZIP viene scritto in un file fisicamente preallocato. Per 7z il file viene
    gestito dal programma esterno: controlliamo lo spazio, senza dichiarare
    una preallocazione del file 7z che l'archiver non garantisce di conservare.
    Il backup originale non viene mai rimosso.
    """
    items = sorted(p for p in folder.rglob('*') if p.is_file())
    total = sum(p.stat().st_size for p in items)
    capacity = math.ceil(total * 1.10) + len(items) * 4096 + 16 * MIB
    space(folder.parent, capacity, reserve)
    target = folder.with_name(folder.name + '.' + kind)
    partial = folder.with_name(folder.name + '.' + kind + '.partial')
    if target.exists() or partial.exists():
        raise RuntimeError('Archivio esistente: non viene sovrascritto')
    levels = {'fast': 1, 'balanced': 5, 'max': 9}
    level = levels[preset]
    print(f'Compressione {kind}, preset {preset} (livello {level}); spazio prudenziale {human(capacity)}.', flush=True)
    if kind == 'zip':
        print('Prealloco il file ZIP...', flush=True)
        with open(partial, 'x+b') as handle:
            os.posix_fallocate(handle.fileno(), 0, capacity)
            written = done = 0
            start = last = time.monotonic()
            try:
                with zipfile.ZipFile(handle, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=level, allowZip64=True) as archive:
                    for item in items:
                        name = str(Path(folder.name) / item.relative_to(folder))
                        with item.open('rb') as source, archive.open(name, 'w', force_zip64=True) as dest:
                            while True:
                                chunk = source.read(MIB)
                                if not chunk:
                                    break
                                # Margine extra ZIP; fermarsi prima di consumare la riserva.
                                if handle.tell() + 4 * MIB > capacity:
                                    growth = 64 * MIB
                                    space(folder.parent, growth, reserve)
                                    os.posix_fallocate(handle.fileno(), capacity, growth)
                                    capacity += growth
                                dest.write(chunk)
                                done += len(chunk)
                                now = time.monotonic()
                                if now - last >= .5:
                                    print(f'\rZIP: {done / max(1,total) * 100:5.1f}% | {human(done)} letti | {human(done / max(.001,now-start))}/s', end='', flush=True)
                                    last = now
                written = handle.tell()
            finally:
                # In caso di errore resta un archivio parziale esplicitamente nominato.
                if not written:
                    written = handle.tell()
                handle.truncate(written)
                handle.flush()
                os.fsync(handle.fileno())
        print('\nVerifico integrità ZIP (CRC)...', flush=True)
        with zipfile.ZipFile(partial, 'r') as archive:
            bad = archive.testzip()
            if bad:
                raise RuntimeError(f'CRC ZIP non valido: {bad}')
    else:
        binary = shutil.which('7zz') or shutil.which('7z')
        if not binary:
            raise RuntimeError('7z richiede il programma 7zz oppure 7z installato sul Docker host')
        # LZMA2 esplicito; -mx e -bsp1 sono gestiti dal programma 7-Zip.
        command = [binary, 'a', '-t7z', '-m0=lzma2', f'-mx={level}', '-bsp1', '-y', str(partial), folder.name]
        proc = subprocess.Popen(command, cwd=folder.parent, start_new_session=True)
        try:
            while proc.poll() is None:
                if shutil.disk_usage(folder.parent).free < reserve:
                    raise RuntimeError('Compressione interrotta: raggiunta la riserva di spazio libero')
                time.sleep(.2)
            if proc.returncode:
                raise RuntimeError(f'7-Zip è terminato con codice {proc.returncode}; backup originale conservato')
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
        print('Verifico integrità 7z...', flush=True)
        run([binary, 't', '-t7z', str(partial)])
    # Hash esterno dell'archivio, oltre ai checksum dei file contenuti.
    digest = hashlib.sha256()
    with partial.open('rb') as handle:
        while True:
            chunk = handle.read(MIB)
            if not chunk:
                break
            digest.update(chunk)
    partial.rename(target)
    target.with_name(target.name + '.sha256').write_text(f'{digest.hexdigest()}  {target.name}\n')
    print(f'Archivio verificato: {target} ({human(target.stat().st_size)})\nBackup originale conservato: {folder}', flush=True)
    return target


# Eseguito nel container senza importare l'applicazione o scrivere sul DB.
PREFLIGHT = r'''
import json, os
from pathlib import Path
from urllib.parse import urlsplit, unquote
root = Path('/app/backend/data').resolve()
data = Path(os.environ.get('DATA_DIR') or '/app/backend/data').resolve()
if data != root:
    raise SystemExit('DATA_DIR personalizzata: supportato solo /app/backend/data')
url = os.environ.get('DATABASE_URL', '').strip()
if url:
    parsed = urlsplit(url)
    if parsed.scheme not in ('sqlite', 'sqlite+pysqlite') or parsed.netloc or parsed.query or parsed.fragment:
        raise SystemExit('DATABASE_URL remota o personalizzata non supportata: serve un backup dedicato')
    prefix = parsed.scheme + ':///'
    if not url.startswith(prefix):
        raise SystemExit('DATABASE_URL SQLite non supportata')
    db = Path(unquote(url[len(prefix):])).resolve()
else:
    db = root / 'webui.db'
if root not in db.parents or not db.is_file():
    raise SystemExit('Database SQLite locale non trovato sotto /app/backend/data')
vector = os.environ.get('VECTOR_DB', 'chroma').strip().lower()
if vector not in ('chroma',):
    raise SystemExit('VECTOR_DB esterno/non supportato: il backup locale non sarebbe completo')
if os.environ.get('CHROMA_HTTP_HOST') or os.environ.get('CHROMA_HTTP_PORT'):
    raise SystemExit('Chroma remoto rilevato: serve un backup dedicato')
if os.environ.get('STORAGE_PROVIDER', 'local').lower() not in ('', 'local'):
    raise SystemExit('Storage non locale rilevato: serve un backup dedicato')
# Rifiuta link verso file fuori dal volume: docker cp non li dereferenzia.
total, count = 0, 0
def fail(error): raise error
for parent, dirs, files in os.walk(root, followlinks=False, onerror=fail):
    count += 1
    for name in dirs + files:
        p = Path(parent) / name
        if p.is_symlink() and (p.resolve() != root and root not in p.resolve().parents):
            raise SystemExit('Link simbolico esterno alla directory dati: backup locale non completo')
    for name in files:
        total += (Path(parent) / name).lstat().st_size
        count += 1
try:
    from importlib.metadata import version
    app_version = version('open-webui')
except Exception:
    app_version = 'unknown'
print(json.dumps({'bytes': total, 'entries': count, 'sqlite_relative': str(db.relative_to(root)), 'version': app_version}))
'''


def main():
    started_at = dt.datetime.now().astimezone()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, add_help=False)
    ap.add_argument('-h', '--help', action='help', help='Mostra guida e parametri')
    ap.add_argument('destination', type=Path, help='Cartella di backup già esistente e scrivibile')
    ap.add_argument('-P', '--project-dir', type=Path, default=Path.cwd(), help='Root del progetto; default directory corrente')
    ap.add_argument('-f', '--file', action='append', dest='files', help='Compose in ordine; ripetibile, sostituisce i default')
    ap.add_argument('-s', '--service', default='ollama-webui', help='Nome servizio OpenWebUI')
    ap.add_argument('-m', '--margin-percent', type=float, default=20, help='Margine di stima TAR, default 20%%')
    ap.add_argument('-M', '--min-free-gib', type=float, default=1, help='Spazio libero da preservare, default 1 GiB')
    ap.add_argument('-a', '--archive', choices=['none', 'zip', '7z'], default='none', help='Archivio aggiuntivo, default none')
    ap.add_argument('-p', '--preset', choices=['fast', 'balanced', 'max'], default='balanced', help='Livelli 1/5/9; default balanced')
    ap.add_argument('-e', '--estimate', action='store_true', help='Solo stima; non prealloca e non ferma il servizio')
    ap.add_argument('-t', '--timestamp', action='store_true', help='Aggiunge _DATA_ORA_DI_AVVIO al nome')
    if len(sys.argv) == 1:
        ap.print_usage(sys.stderr)
        ap.exit(2, 'Nessun parametro specificato. Consulta -h oppure --help.\n')
    args = ap.parse_args()
    if any(not math.isfinite(n) or n < 0 for n in (args.margin_percent, args.min_free_gib)):
        ap.error('Margini e riserva devono essere numeri finiti non negativi')
    if not hasattr(os, 'posix_fallocate') or not shutil.which('docker'):
        ap.error('Servono Linux con posix_fallocate e il comando docker')
    if args.archive == '7z' and not (shutil.which('7zz') or shutil.which('7z')):
        ap.error('Installa 7zz oppure 7z per --archive 7z')
    os.umask(0o077)
    project = args.project_dir.expanduser().resolve(strict=True)
    dest = args.destination.expanduser().resolve(strict=True)
    if not dest.is_dir():
        ap.error('La destinazione deve essere una directory esistente: crea/monta prima il disco')
    files = [(project / name).resolve(strict=True) for name in (args.files or ['docker-compose-ollama-nvidia.yaml', 'docker-compose.ssl.override.yaml'])]
    compose = ['docker', 'compose', '--project-directory', str(project)]
    for f in files:
        compose += ['-f', str(f)]
    with open(project / '.openwebui-backup.lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Un backup dello stesso progetto è già in esecuzione')
        cid = run(compose + ['ps', '-q', args.service])
        if not cid or '\n' in cid:
            raise RuntimeError('È richiesta una sola istanza OpenWebUI avviata')
        info = json.loads(run(['docker', 'inspect', cid]))[0]
        if not info['State']['Running']:
            raise RuntimeError('Il servizio deve essere avviato per le verifiche iniziali')
        mounts = info.get('Mounts', [])
        data_mounts = [m for m in mounts if m.get('Destination') == '/app/backend/data']
        if len(data_mounts) != 1:
            raise RuntimeError('È richiesto un mount persistente dedicato su /app/backend/data')
        for mount in mounts:
            source = Path(mount['Source']).resolve()
            if dest == source or source in dest.parents:
                raise RuntimeError('Destinazione dentro un mount OpenWebUI: scegliere una cartella esterna')
        print('Verifico SQLite/storage locale e calcolo dimensioni (può richiedere tempo)...', flush=True)
        stats = json.loads(run(compose + ['exec', '-T', '--user', 'root', args.service, 'python', '-c', PREFLIGHT]))
        size, count = int(stats['bytes']), int(stats['entries'])
        tar_est = math.ceil((size + count * 2048 + 2 * MIB) * (1 + args.margin_percent / 100))
        # Incluse le definizioni extends locali senza copiare dataset/modelli.
        config_sources = list(dict.fromkeys(files + sorted(project.glob('docker-compose*.yaml')) + sorted(project.glob('docker-compose*.yml')) + sorted(project.glob('compose*.yaml')) + sorted(project.glob('compose*.yml')) + ([project / '.env'] if (project / '.env').is_file() else [])))
        config_sources = [f for f in config_sources if f.is_file()]
        configsize = sum(f.stat().st_size for f in config_sources)
        reserve = math.ceil(args.min_free_gib * GIB)
        needed = tar_est + configsize + MIB
        archive_est = math.ceil(needed * 1.10) + 16 * MIB if args.archive != 'none' else 0
        free = shutil.disk_usage(dest).free
        print(f'Dati OpenWebUI: {human(size)} ({count} elementi)\nPreallocazione TAR: {human(tar_est)}\nSpazio aggiuntivo archivio: {human(archive_est)}\nSpazio libero: {human(free)}\nRichiesto con riserva: {human(needed + archive_est + reserve)}', flush=True)
        print('Dimensioni finali stimate; non si presume che i dati siano comprimibili.', flush=True)
        space(dest, needed + archive_est, reserve)
        if args.estimate:
            print('Stima completata. Nessuna preallocazione e nessuno stop del servizio.')
            return
        name = 'openwebui'
        if args.timestamp:
            name += '_' + started_at.strftime('%Y%m%d_%H%M%S_%f')
        if (dest / name).exists():
            raise RuntimeError('Backup già esistente: usare -t o una destinazione diversa; nessuna sovrascrittura')
        folder = dest / (name + '.partial')
        folder.mkdir(mode=0o700)
        output = None
        stop_attempted = False
        manifest = {'format': 1, 'status': 'incomplete', 'created_at': started_at.isoformat(), 'service': args.service, 'data_path': '/app/backend/data', 'sqlite_relative': stats['sqlite_relative'], 'version': stats['version'], 'image': info['Config']['Image'], 'image_id': info['Image'], 'estimated_tar_bytes': tar_est, 'files': {}}
        try:
            print(f'Prealloco TAR: {human(tar_est)}...', flush=True)
            space(folder, tar_est + configsize + MIB, reserve)
            output = Output(folder / 'openwebui-data.tar', tar_est, reserve)
            configs = folder / 'configuration'
            configs.mkdir()
            for i, source in enumerate(config_sources):
                target = configs / f'{i:02d}-{source.name}'
                shutil.copyfile(source, target)
                manifest['files'][str(target.relative_to(folder))] = {'source': str(source), 'bytes': target.stat().st_size, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
            print('Fermo solo OpenWebUI per rendere coerente la copia SQLite...', flush=True)
            stop_attempted = True
            run(compose + ['stop', args.service])
            stopped = json.loads(run(['docker', 'inspect', cid]))[0]
            if stopped['State']['Running']:
                raise RuntimeError('Container ancora attivo dopo lo stop; backup annullato')
            stream(['docker', 'cp', cid + ':/app/backend/data/.', '-'], output, 'Dati OpenWebUI')
            print('Verifico TAR e presenza del database SQLite...', flush=True)
            expected_db = Path(stats['sqlite_relative']).parts
            found = False
            with tarfile.open(output.path, 'r:') as archive:
                for member in archive:
                    # Docker cp può includere il nome della directory radice.
                    parts = Path(member.name).parts
                    if member.isfile() and parts in (expected_db, ('data',) + expected_db):
                        if found:
                            raise RuntimeError('Più database con lo stesso percorso relativo: archivio ambiguo')
                        header = archive.extractfile(member).read(16)
                        if header != b'SQLite format 3\x00':
                            raise RuntimeError('Header SQLite non valido')
                        found = True
                if not found:
                    raise RuntimeError('Database SQLite non trovato nel TAR')
            manifest['files'][output.path.name] = {'bytes': output.written, 'sha256': output.digest.hexdigest()}
        finally:
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            problems = []
            if output is not None:
                try:
                    output.close()
                except OSError as exc:
                    problems.append(str(exc))
            if stop_attempted:
                try:
                    print('Riavvio OpenWebUI...', flush=True)
                    run(compose + ['start', args.service])
                    for attempt in range(10):
                        state = json.loads(run(['docker', 'inspect', cid]))[0]['State']
                        if state['Running'] and not state.get('Restarting', False):
                            break
                        if attempt == 9:
                            raise RuntimeError('OpenWebUI non risulta avviato: controllare i log Docker')
                        time.sleep(1)
                except Exception as exc:
                    problems.append(str(exc))
            if problems:
                raise RuntimeError('Recupero incompleto: ' + '; '.join(problems))
        signal.signal(signal.SIGINT, signal.default_int_handler)
        signal.signal(signal.SIGTERM, interrupt_signal)
        manifest['status'] = 'complete'
        (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
        (folder / 'SHA256SUMS').write_text(''.join(f'{entry["sha256"]}  {name}\n' for name, entry in manifest['files'].items()))
        (folder / 'SUCCESS').write_text('Backup completato; eseguire anche una prova di ripristino separata.\n')
        final = folder.with_name(name)
        folder.rename(final)
        print(f'\nBackup completato: {final}\nDati scritti: {human(sum(x["bytes"] for x in manifest["files"].values()))}\nVerifica: sha256sum -c SHA256SUMS dalla cartella del backup.', flush=True)
        if args.archive != 'none':
            try:
                archive_backup(final, args.archive, args.preset, reserve)
            except BaseException:
                print(f'Compressione non completata. Backup originale conservato: {final}', file=sys.stderr)
                raise


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, interrupt_signal)
    try:
        main()
    except (Exception, KeyboardInterrupt) as exc:
        print(f'\nERRORE: {exc or "interrotto"}. File/cartelle .partial non sono backup completati.', file=sys.stderr)
        sys.exit(1)
