from django.contrib.auth.models import User
from django.contrib.auth.decorators import user_passes_test, login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from prometheus_client import Counter, Gauge
import threading
from django.db import close_old_connections
import requests
import time
import re
from urllib.parse import urlparse, urljoin
import socket
import ssl
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib import messages
from .models import Domain, DomainCheck
from django.core.paginator import Paginator

def is_admin(user):
    return user.is_superuser

def login_view(request):
    if request.user.is_authenticated:
        return redirect('list_domains')
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('list_domains')
        else:
            messages.error(request, 'Credenciais inválidas.')
    return render(request, 'login.html', {'form': form})

@user_passes_test(is_admin)
def list_users(request):
    users = User.objects.order_by('username')
    return render(request, 'list_users.html', {'users': users})

@user_passes_test(is_admin)
def add_user(request):
    form = UserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Usuário criado com sucesso.')
        return redirect('list_users')
    return render(request, 'add_user.html', {'form': form})

@login_required
def list_domains(request):
    notificacao = None
    intervalo_selecionado = 'agora'
    domains = Domain.objects.all().order_by('-date_added')
    if request.method == 'POST':
        intervalo = request.POST.get('intervalo')
        intervalo_selecionado = intervalo
        if intervalo == 'agora':
            # Executa a verificação em background para não bloquear a página
            def run_checks(domains_list):
                close_old_connections()
                MAX_LINKS_TO_CHECK = 20
                session = requests.Session()
                session.headers.update({'User-Agent': 'Monitor/1.0'})
                for d in domains_list:
                    dns_lookup_time_ms = None
                    tls_handshake_time_ms = None
                    content_size_bytes = None
                    broken_links_count = None
                    response_time_ms = None
                    status = False
                    response_time = None
                    http_status = None
                    try:
                        parsed = urlparse(d.domain)
                        hostname = parsed.hostname
                        if hostname:
                            start_dns = time.time()
                            socket.gethostbyname(str(hostname))
                            end_dns = time.time()
                            dns_lookup_time_ms = (end_dns - start_dns) * 1000
                            if parsed.scheme == 'https':
                                start_tls = time.time()
                                ctx = ssl.create_default_context()
                                with ctx.wrap_socket(socket.socket(), server_hostname=hostname) as ssock:
                                    ssock.settimeout(5)
                                    ssock.connect((hostname, 443))
                                end_tls = time.time()
                                tls_handshake_time_ms = (end_tls - start_tls) * 1000
                        start_req = time.time()
                        resp = session.get(d.domain, timeout=(3, 4))
                        end_req = time.time()
                        status = resp.ok
                        response_time = resp.elapsed.total_seconds() * 1000
                        response_time_ms = (end_req - start_req) * 1000
                        http_status = resp.status_code
                        content_size_bytes = len(resp.content)
                        html = resp.text
                        links = re.findall(r'<a [^>]*href=[\"\'](.*?)[\"\']', html, re.IGNORECASE)
                        seen = set()
                        to_check = []
                        for link in links:
                            abs_url = urljoin(d.domain, link)
                            p = urlparse(abs_url)
                            if p.scheme in ('http', 'https') and abs_url not in seen:
                                seen.add(abs_url)
                                to_check.append(abs_url)
                                if len(to_check) >= MAX_LINKS_TO_CHECK:
                                    break
                        broken = 0
                        for url in to_check:
                            try:
                                r = session.head(url, timeout=(1, 2), allow_redirects=True)
                                if r.status_code >= 400:
                                    broken += 1
                            except Exception:
                                broken += 1
                        broken_links_count = broken
                    except Exception:
                        pass
                    DomainCheck.objects.create(
                        domain=d,
                        status=status,
                        response_time=response_time,
                        http_status=http_status,
                        response_time_ms=response_time_ms,
                        dns_lookup_time_ms=dns_lookup_time_ms,
                        tls_handshake_time_ms=tls_handshake_time_ms,
                        content_size_bytes=content_size_bytes,
                        broken_links_count=broken_links_count
                    )
                    d.status = status
                    d.response_time = response_time
                    d.save()

            threading.Thread(target=run_checks, args=(list(domains),), daemon=True).start()
            notificacao = 'Verificação iniciada em background. Recarregue a página em alguns segundos para ver resultados.'
        else:
            notificacao = f'Agendamento salvo: verificação a cada {intervalo} minutos.' if intervalo != '60' else 'Agendamento salvo: verificação a cada 1 hora.'
        domains = Domain.objects.all().order_by('-date_added')
    return render(request, 'list_domains.html', {'domains': domains, 'notificacao': notificacao, 'intervalo_selecionado': intervalo_selecionado})

# Métricas Prometheus
SITES_ADDED = Counter('sites_added_total', 'Total de sites cadastrados')
SITE_STATUS = Gauge('site_up', 'Status do site (1=UP, 0=DOWN)', ['domain'])
SITE_RESPONSE_TIME = Gauge('site_response_ms', 'Tempo de resposta (ms)', ['domain'])

@login_required
def add_site(request):
    error = None
    if request.method == 'POST':
        domain = request.POST.get('domain', '').strip()
        try:
            if not domain.startswith(('http://', 'https://')):
                domain = f'https://{domain}'
            validador = URLValidator()
            validador(domain)
            # Verifica o domínio ao cadastrar
            try:
                response = requests.get(domain, timeout=5)
                status = 1 if response.ok else 0
                response_time = response.elapsed.total_seconds() * 1000
            except Exception:
                status = 0
                response_time = None
            Domain.objects.create(domain=domain, status=status, response_time=response_time)
            # Métricas Prometheus (opcional)
            try:
                SITES_ADDED.inc()
                SITE_STATUS.labels(domain=domain).set(status)
                SITE_RESPONSE_TIME.labels(domain=domain).set(response_time if response_time else 0)
            except Exception:
                pass
            return redirect('list_domains')
        except ValidationError:
            error = 'Domínio inválido.'
        except requests.RequestException:
            error = 'Site inacessível.'
        except Exception as e:
            error = f'Erro: {str(e)}'
    return render(request, 'add_site.html', {'error': error})

@login_required
def domain_detail(request, domain_id):
    domain = get_object_or_404(Domain, id=domain_id)
    checks_qs = DomainCheck.objects.filter(domain=domain).order_by('-checked_at')
    paginator = Paginator(checks_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        'domain': domain,
        'checks': page_obj.object_list,
        'page_obj': page_obj,
    }
    return render(request, 'domain_detail.html', context)

def home(request):
    return render(request, 'home.html')
