import ssl
from urllib.parse import urlsplit

import requests
import truststore
from requests.adapters import HTTPAdapter


GEMINI_API_HOST = 'generativelanguage.googleapis.com'


class _TruststoreAdapter(HTTPAdapter):
    """Usa el almacén nativo del sistema sin alterar otras sesiones HTTP."""

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
            raise ValueError('El cliente de Gemini exige verificación TLS.')
        pool_kwargs['ssl_context'] = self.ssl_context
        pool_kwargs.pop('ca_certs', None)
        pool_kwargs.pop('ca_cert_dir', None)
        pool_kwargs.pop('cert_reqs', None)
        return host_params, pool_kwargs


class ClienteGemini:
    def __init__(self):
        self.session = requests.Session()
        self.session.mount(
            f'https://{GEMINI_API_HOST}/',
            _TruststoreAdapter(),
        )

    def post(self, url, **kwargs):
        destino = urlsplit(url)
        if destino.scheme != 'https' or destino.hostname != GEMINI_API_HOST:
            raise ValueError('El cliente de Gemini solo admite el endpoint oficial de Google.')
        kwargs['verify'] = True
        return self.session.post(url, **kwargs)


cliente_gemini = ClienteGemini()
