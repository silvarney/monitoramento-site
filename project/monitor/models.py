from django.db import models

class Domain(models.Model):
    domain = models.CharField(max_length=255, unique=True)
    date_added = models.DateTimeField(auto_now_add=True)
    status = models.BooleanField(default=False)
    response_time = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.domain

class DomainCheck(models.Model):
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name='checks')
    checked_at = models.DateTimeField(auto_now_add=True)
    status = models.BooleanField()
    response_time = models.FloatField(null=True, blank=True)
    http_status = models.IntegerField(null=True, blank=True)
    # Novos campos técnicos
    response_time_ms = models.FloatField(null=True, blank=True)
    dns_lookup_time_ms = models.FloatField(null=True, blank=True)
    tls_handshake_time_ms = models.FloatField(null=True, blank=True)
    content_size_bytes = models.IntegerField(null=True, blank=True)
    broken_links_count = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.domain.domain} - {self.checked_at:%d/%m/%Y %H:%M:%S}"
