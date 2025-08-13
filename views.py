from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from prometheus_client import Counter, Gauge
import requests

# Métricas Prometheus
SITES_ADDED = Counter('sites_added_total', 'Total de sites cadastrados')
SITE_STATUS = Gauge('site_up', 'Status do site (1=UP, 0=DOWN)', ['domain'])
SITE_RESPONSE_TIME = Gauge('site_response_ms', 'Tempo de resposta (ms)', ['domain'])

@login_required
def add_site(request):
    if request.method == 'POST':
        domain = request.POST.get('domain').strip()
        
        # Validação do domínio
        try:
            if not domain.startswith(('http://', 'https://')):
                domain = f'https://{domain}'
            
            validador = URLValidator()
            validador(domain)  # Levanta ValidationError se inválido
            
            # Verifica se o site está UP
            response = requests.get(domain, timeout=5)
            status = 1 if response.ok else 0
            response_time = response.elapsed.total_seconds() * 1000
            
            # Envia métricas para o Prometheus
            SITES_ADDED.inc()
            SITE_STATUS.labels(domain=domain).set(status)
            SITE_RESPONSE_TIME.labels(domain=domain).set(response_time)
            
            return JsonResponse({
                'status': 'success',
                'domain': domain,
                'http_status': response.status_code,
                'response_time_ms': round(response_time, 2)
            })
            
        except ValidationError:
            return JsonResponse({'error': 'Domínio inválido'}, status=400)
        except requests.RequestException:
            SITE_STATUS.labels(domain=domain).set(0)
            return JsonResponse({'error': 'Site inacessível'}, status=400)
    
    return render(request, 'add_site.html')