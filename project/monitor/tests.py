from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.test import Client
from .models import Domain


class BasicFlowTests(TestCase):
	def setUp(self):
		self.client = Client()
		self.user = User.objects.create_user(username='tester', password='pass12345')

	def test_root_redirects_to_login(self):
		resp = self.client.get('/')
		self.assertEqual(resp.status_code, 302)
		self.assertIn('/login/', resp.headers.get('Location', ''))

	def test_login_page_ok(self):
		url = reverse('login')
		resp = self.client.get(url)
		self.assertEqual(resp.status_code, 200)

	def test_domains_requires_auth(self):
		url = reverse('list_domains')
		resp = self.client.get(url)
		self.assertEqual(resp.status_code, 302)
		self.assertIn('/login/', resp.headers.get('Location', ''))

	def test_login_and_access_domains(self):
		login_url = reverse('login')
		list_url = reverse('list_domains')
		resp = self.client.post(login_url, {'username': 'tester', 'password': 'pass12345'})
		self.assertEqual(resp.status_code, 302)
		self.assertEqual(resp.headers.get('Location'), list_url)
		resp2 = self.client.get(list_url)
		self.assertEqual(resp2.status_code, 200)

	def test_add_site_creates_domain(self):
		# autentica
		self.client.login(username='tester', password='pass12345')
		url = reverse('add_site')
		# Evitar chamadas externas: usar um domínio simples que passe validação, mas
		# como a view tenta requests.get, tolera exceção e trata status=0.
		resp = self.client.post(url, {'domain': 'example.com'})
		self.assertEqual(resp.status_code, 302)
		self.assertEqual(Domain.objects.count(), 1)

	def test_domain_detail_page_renders(self):
		self.client.login(username='tester', password='pass12345')
		d = Domain.objects.create(domain='https://example.com', status=1, response_time=123.456)
		resp = self.client.get(reverse('domain_detail', args=[d.id]))
		self.assertEqual(resp.status_code, 200)
		self.assertContains(resp, 'Histórico de Verificações')
		# deve renderizar 123,46 (floatformat:2)
		self.assertContains(resp, '123,46')

	def test_domain_detail_null_fields_render_dash(self):
		self.client.login(username='tester', password='pass12345')
		d = Domain.objects.create(domain='https://example.com', status=1)
		# criar um check com campos técnicos nulos
		from .models import DomainCheck
		DomainCheck.objects.create(domain=d, status=True, http_status=200)
		resp = self.client.get(reverse('domain_detail', args=[d.id]))
		self.assertEqual(resp.status_code, 200)
		# Espera ver '-' para DNS/TLS/tamanho/links
		self.assertContains(resp, '<td class="px-4 py-2">-</td>', html=True)
