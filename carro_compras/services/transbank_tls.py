import ssl
from urllib.parse import urlsplit

import requests
import truststore
from requests.adapters import HTTPAdapter
from transbank.common import request_service as sdk_request_service


TRANSBANK_API_HOSTS = {
    'webpay3g.transbank.cl',
    'webpay3gint.transbank.cl',
}


class _TruststoreAdapter(HTTPAdapter):
    """Usa el almacén nativo solo dentro del cliente HTTP de Transbank."""

    def __init__(self, *args, **kwargs):
        self.ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        pool_kwargs['ssl_context'] = self.ssl_context
        return super().init_poolmanager(connections, maxsize, block, **pool_kwargs)

    def build_connection_pool_key_attributes(self, request, verify, cert=None):
        host_params, pool_kwargs = super().build_connection_pool_key_attributes(
            request,
            verify,
            cert,
        )
        if verify is not True:
            raise ValueError('El cliente de Transbank exige verificación TLS.')
        pool_kwargs['ssl_context'] = self.ssl_context
        pool_kwargs.pop('ca_certs', None)
        pool_kwargs.pop('ca_cert_dir', None)
        pool_kwargs.pop('cert_reqs', None)
        return host_params, pool_kwargs


class ClienteHttpTransbank:
    def __init__(self):
        self.session = requests.Session()
        adapter = _TruststoreAdapter()
        for host in TRANSBANK_API_HOSTS:
            self.session.mount(f'https://{host}/', adapter)

    @staticmethod
    def _validar_url(url):
        destino = urlsplit(url)
        if destino.scheme != 'https' or destino.hostname not in TRANSBANK_API_HOSTS:
            raise ValueError('El cliente de Transbank solo admite sus endpoints oficiales.')

    def request(self, method, url, **kwargs):
        self._validar_url(url)
        kwargs['verify'] = True
        return self.session.request(method, url, **kwargs)

    def get(self, url, **kwargs):
        return self.request('GET', url, **kwargs)

    def post(self, url, **kwargs):
        return self.request('POST', url, **kwargs)

    def put(self, url, **kwargs):
        return self.request('PUT', url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request('DELETE', url, **kwargs)


cliente_http_transbank = ClienteHttpTransbank()


def configurar_transbank_tls():
    """Conecta únicamente el SDK de Transbank a su sesión TLS dedicada."""
    sdk_request_service.requests = cliente_http_transbank
