"""Dedicated school release: preflight restored database, backup, migrate, switch.

Requires the initialized school account/database/production.env and native nginx.
This intentionally refuses to infer or overwrite any other project's resources.
Run using root and the candidate release's Python; no credentials in arguments.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path('/opt/gestion-escolar')
ENV_FILE = Path('/etc/gestion-escolar/production.env')


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def configure(release, host):
    if release.resolve().parent != ROOT / 'releases' or not re.fullmatch(r'[a-zA-Z0-9.-]+', host):
        raise SystemExit('Invalid dedicated release path or hostname.')
    if not ENV_FILE.is_file():
        raise SystemExit('Dedicated school environment is not initialized; inspect VM before bootstrap.')
    values = dict(line.split('=', 1) for line in ENV_FILE.read_text().splitlines()
                  if line and not line.startswith('#'))
    if values.get('POSTGRES_DB') != 'gestion_escolar' or values.get('POSTGRES_USER') != 'gestion_escolar':
        raise SystemExit('Dedicated database identity changed; inspect before proceeding.')
    values.update({
        'DJANGO_ENV': 'production', 'DJANGO_SETTINGS_MODULE': 'project.settings_production',
        'DJANGO_ALLOWED_HOSTS': host, 'DJANGO_CSRF_TRUSTED_ORIGINS': f'https://{host}',
        'FRONTEND_PUBLIC_URL': f'https://{host}', 'DJANGO_HTTPS_ENABLED': 'true',
        'DJANGO_MEDIA_ROOT': '/var/lib/gestion-escolar/media',
        'REPORTES_PRIVATE_ROOT': '/var/lib/gestion-escolar/private/reportes',
        'RESPALDOS_ROOT': '/var/lib/gestion-escolar/private/respaldos',
        'TRUSTED_PROXY_IPS': '127.0.0.1',
    })
    return values


def backup():
    ROOT.joinpath('backups').mkdir(mode=0o700, exist_ok=True)
    target = Path(tempfile.mkdtemp(prefix=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-'), dir=ROOT / 'backups'))
    os.chmod(target, 0o700)
    with (target / 'database.dump').open('wb') as stream:
        run('runuser', '-u', 'postgres', '--', 'pg_dump', '--format=custom', 'gestion_escolar', stdout=stream)
    shutil.copy2(ENV_FILE, target / 'production.env')
    (target / 'release.txt').write_text(str((ROOT / 'current').resolve()) + '\n')
    if Path('/var/lib/gestion-escolar').is_dir():
        run('tar', '-czf', str(target / 'application-files.tar.gz'), '-C', '/var/lib/gestion-escolar', '.')
    own_site = Path('/etc/nginx/sites-available/gestion-escolar')
    if own_site.is_file():
        shutil.copy2(own_site, target / 'gestion-escolar.nginx')
    print(f'Private backup: {target}', flush=True)
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('release', type=Path)
    parser.add_argument('--host', required=True)
    parser.add_argument('--apply', action='store_true', help='Without this, preflight only.')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo.')
    release = args.release.resolve(strict=True)
    values = configure(release, args.host)
    python = release / '.venv/bin/python'
    if not python.is_file() or not (release / 'frontend/dist/manifest.webmanifest').is_file():
        raise SystemExit('Install Python dependencies and build the PWA first.')
    account = pwd.getpwnam('gestion-escolar')
    for folder in (release / 'staticfiles', Path('/var/lib/gestion-escolar/media'),
                   Path('/var/lib/gestion-escolar/private'),
                   Path(values['REPORTES_PRIVATE_ROOT']), Path(values['RESPALDOS_ROOT'])):
        folder.mkdir(parents=True, exist_ok=True)
        os.chown(folder, account.pw_uid, account.pw_gid)
    os.chmod('/var/lib/gestion-escolar/private', 0o700)
    env = {**os.environ, **values, 'PYTHONDONTWRITEBYTECODE': '1',
           'DJANGO_STATIC_ROOT': str(release / 'staticfiles')}

    def manage(*commands, database=None):
        configured = {**env, **({'POSTGRES_DB': database} if database else {})}
        run('runuser', '-u', 'gestion-escolar', '--', str(python), 'manage.py', *commands,
            cwd=release / 'backend', env=configured)

    snapshot = backup()
    clone = 'gestion_escolar_check_' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')
    run('runuser', '-u', 'postgres', '--', 'createdb', '-O', 'gestion_escolar', clone)
    with (snapshot / 'database.dump').open('rb') as stream:
        run('runuser', '-u', 'postgres', '--', 'pg_restore', '--exit-on-error', '--no-owner',
            '--role=gestion_escolar', '-d', clone, stdin=stream)
    manage('check', '--deploy', '--fail-level', 'WARNING', database=clone)
    manage('migrate', '--noinput', database=clone)
    manage('migrate', '--check', database=clone)
    manage('makemigrations', '--check', '--dry-run', database=clone)
    smoke_database = f'{clone}_smoke'
    run('runuser', '-u', 'postgres', '--', 'createdb', '-O', 'gestion_escolar', smoke_database)
    script = 'deploy/azure-native/smoke_portal.py'
    try:
        manage('migrate', '--noinput', database=smoke_database)
        manage('shell', '-c', f"exec(open({script!r}, encoding='utf-8').read())", database=smoke_database)
    finally:
        run('runuser', '-u', 'postgres', '--', 'dropdb', smoke_database)
    print(f'Preflight OK; restored test database retained: {clone}', flush=True)
    if not args.apply:
        return
    current = ROOT / 'current'
    if current.exists() and (not current.is_symlink() or current.resolve().parent != ROOT / 'releases'):
        raise SystemExit('Current school release is not an expected symlink.')
    previous = current.resolve() if current.is_symlink() else None
    # Stage only this application's own nginx virtual host.
    site = release / 'backend/deploy/azure-native/site.nginx.template'
    site_target = Path('/etc/nginx/sites-available/gestion-escolar')
    staged_site = ROOT / 'site-next.nginx'
    staged_site.write_text(site.read_text().replace('__HOST__', args.host))
    original_site = site_target.read_bytes()
    shutil.copy2(staged_site, site_target)
    try:
        run('nginx', '-t')
    except Exception:
        site_target.write_bytes(original_site)
        raise
    if previous:
        run('systemctl', 'stop', 'gestion-escolar')
        if Path('/etc/systemd/system/gestion-escolar-respaldos.service').is_file():
            run('systemctl', 'stop', 'gestion-escolar-respaldos')
    try:
        backup()  # Final consistent backup with incoming writes stopped.
        manage('migrate', '--noinput')
        manage('migrate', '--check')
        manage('collectstatic', '--noinput')
        script = 'deploy/azure-native/create_admin.py'
        manage('shell', '-c', f"exec(open({script!r}, encoding='utf-8').read())")
        env_candidate = ENV_FILE.with_suffix('.env.next')
        with os.fdopen(os.open(env_candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640), 'w') as stream:
            os.chown(env_candidate, 0, account.pw_gid)
            stream.write(''.join(f'{key}={value}\n' for key, value in values.items()))
        env_candidate.replace(ENV_FILE)
        link = ROOT / 'current-next'
        if link.exists() or link.is_symlink():
            raise RuntimeError('An unreviewed current-next path already exists.')
        link.symlink_to(release)
        link.replace(current)
        for service in ('gestion-escolar', 'gestion-escolar-respaldos'):
            unit = f'{service}.service'
            shutil.copy2(release / 'backend/deploy/azure-native' / unit, Path('/etc/systemd/system') / unit)
        run('systemctl', 'daemon-reload')
        run('systemctl', 'enable', '--now', 'gestion-escolar', 'gestion-escolar-respaldos')
        run('systemctl', 'reload', 'nginx')
    except Exception:
        print(f'Deploy failed; preserve database and inspect manually. Previous release: {previous}', flush=True)
        raise
    for attempt in range(15):
        try:
            with urllib.request.urlopen(f'https://{args.host}/healthz/', timeout=3) as response:
                if response.status != 200 or json.load(response) != {'status': 'ok'}:
                    raise RuntimeError('Health probe failed.')
            break
        except Exception:
            if attempt == 14:
                raise
            time.sleep(1)
    print(f'DEPLOYED https://{args.host}; previous={previous}; backup={snapshot}', flush=True)


if __name__ == '__main__':
    main()
