"""Initialize only this school's dedicated resources on an inspected Ubuntu VM.

Requires PostgreSQL, nginx, certbot and Python venv packages already installed.
Does not modify existing virtual hosts or create demo academic data.
"""
import argparse
import os
from pathlib import Path
import pwd
import re
import secrets
import subprocess


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', required=True)
    args = parser.parse_args()
    if os.geteuid() != 0 or not re.fullmatch(r'gestion-escolar\.[0-9-]+\.sslip\.io', args.host):
        raise SystemExit('Run as root with the dedicated school hostname.')
    root = Path('/opt/gestion-escolar')
    env_path = Path('/etc/gestion-escolar/production.env')
    try:
        account = pwd.getpwnam('gestion-escolar')
    except KeyError:
        run('useradd', '--system', '--home-dir', str(root), '--shell', '/usr/sbin/nologin', 'gestion-escolar')
        account = pwd.getpwnam('gestion-escolar')
    root.mkdir(mode=0o755, exist_ok=True)
    releases = root / 'releases'
    releases.mkdir(exist_ok=True)
    owner = pwd.getpwnam('azureuser')
    os.chown(releases, owner.pw_uid, owner.pw_gid)
    env_path.parent.mkdir(mode=0o750, exist_ok=True)
    os.chown(env_path.parent, 0, account.pw_gid)
    if not env_path.exists():
        query = "SELECT (EXISTS(SELECT 1 FROM pg_roles WHERE rolname='gestion_escolar') OR EXISTS(SELECT 1 FROM pg_database WHERE datname='gestion_escolar'))::int;"
        exists = run('runuser', '-u', 'postgres', '--', 'psql', '-XAt', '-c', query, capture_output=True, text=True).stdout.strip()
        if exists != '0':
            raise SystemExit('School database/role exists without configuration; refusing replacement.')
        password = secrets.token_hex(32)
        values = {
            'DJANGO_ENV': 'production', 'DJANGO_SETTINGS_MODULE': 'project.settings_production',
            'DJANGO_SECRET_KEY': secrets.token_hex(32), 'DJANGO_ALLOWED_HOSTS': args.host,
            'DJANGO_CSRF_TRUSTED_ORIGINS': 'https://' + args.host,
            'DJANGO_HTTPS_ENABLED': 'true', 'POSTGRES_DB': 'gestion_escolar',
            'POSTGRES_USER': 'gestion_escolar', 'POSTGRES_PASSWORD': password,
            'POSTGRES_HOST': '127.0.0.1', 'POSTGRES_PORT': '5432',
            'DJANGO_MEDIA_ROOT': '/var/lib/gestion-escolar/media',
            'DJANGO_STATIC_ROOT': '/opt/gestion-escolar/current/staticfiles',
            'REPORTES_PRIVATE_ROOT': '/var/lib/gestion-escolar/private/reportes',
            'RESPALDOS_ROOT': '/var/lib/gestion-escolar/private/respaldos',
            'FRONTEND_PUBLIC_URL': 'https://' + args.host,
            'TRUSTED_PROXY_IPS': '127.0.0.1', 'WEB_CONCURRENCY': '2',
        }
        with env_path.open('x') as output:
            os.chmod(env_path, 0o640)
            os.chown(env_path, 0, account.pw_gid)
            output.write(''.join(f'{key}={value}\n' for key, value in values.items()))
        run('runuser', '-u', 'postgres', '--', 'psql', '-X', '-v', 'ON_ERROR_STOP=1',
            input=f"CREATE ROLE gestion_escolar LOGIN PASSWORD '{password}' NOSUPERUSER NOCREATEDB NOCREATEROLE;\nCREATE DATABASE gestion_escolar OWNER gestion_escolar;\n", text=True)
    for name in ('media', 'private/reportes', 'private/respaldos'):
        folder = Path('/var/lib/gestion-escolar') / name
        folder.mkdir(parents=True, exist_ok=True, mode=0o750)
        os.chown(folder, account.pw_uid, account.pw_gid)
    # Shared certificate challenge directory already used by the existing nginx.
    Path('/var/lib/letsencrypt/.well-known/acme-challenge').mkdir(parents=True, exist_ok=True)
    site = Path('/etc/nginx/sites-available/gestion-escolar')
    enabled = Path('/etc/nginx/sites-enabled/gestion-escolar')
    # The inspected nginx default is 64; the additional long Azure hostname
    # needs a larger hash bucket. A separate file keeps existing sites intact.
    hash_config = Path('/etc/nginx/conf.d/gestion-escolar-hash.conf')
    if not hash_config.exists():
        hash_config.write_text('server_names_hash_bucket_size 128;\n')
    if not site.exists():
        site.write_text('server {\n listen 80;\n server_name ' + args.host + ';\n'
                        ' location /.well-known/acme-challenge/ { root /var/lib/letsencrypt; }\n'
                        ' location / { return 503; }\n}\n')
        if not enabled.exists():
            enabled.symlink_to(site)
    run('nginx', '-t')
    run('systemctl', 'reload', 'nginx')
    certificate = Path('/etc/letsencrypt/live') / args.host / 'fullchain.pem'
    if not certificate.is_file():
        run('certbot', 'certonly', '--webroot', '-w', '/var/lib/letsencrypt', '-d', args.host,
            '--non-interactive', '--agree-tos', '--register-unsafely-without-email')
    print('School environment and TLS ready; no secrets printed.')


if __name__ == '__main__':
    main()
