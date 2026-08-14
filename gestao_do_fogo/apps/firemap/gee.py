"""
Acesso ao Google Earth Engine.

A inicialização é feita uma vez por processo e sob demanda: autenticar custa uma
chamada de rede, então nada disso acontece no import do módulo (senão `manage.py`,
migrações e testes ficariam dependendo do GEE estar no ar).
"""

import json
import logging
import threading

import ee
from django.conf import settings

logger = logging.getLogger("gestao_do_fogo.firemap")

_lock = threading.Lock()
_initialized = False


class GEEUnavailable(RuntimeError):
    """O Earth Engine não pôde ser inicializado (credencial ausente ou inválida)."""


def _load_credentials() -> ee.ServiceAccountCredentials:
    """
    Monta as credenciais a partir do arquivo JSON ou das variáveis de ambiente.

    O arquivo tem precedência por ser o formato usado em desenvolvimento; as variáveis
    soltas existem para deploys onde não dá para montar um arquivo (Cloud Run, etc.).
    """
    path = settings.GEE_CREDENTIALS_PATH
    if path:
        with open(path, encoding="utf-8") as fh:
            info = json.load(fh)
        return ee.ServiceAccountCredentials(info["client_email"], path)

    if settings.GEE_CLIENT_EMAIL and settings.GEE_PRIVATE_KEY:
        key_data = json.dumps(
            {
                "type": "service_account",
                "client_email": settings.GEE_CLIENT_EMAIL,
                "private_key": settings.GEE_PRIVATE_KEY.replace("\\n", "\n"),
            }
        )
        return ee.ServiceAccountCredentials(settings.GEE_CLIENT_EMAIL, key_data=key_data)

    raise GEEUnavailable(
        "Credencial do Earth Engine não configurada. Defina GEE_CREDENTIALS_PATH "
        "ou GEE_CLIENT_EMAIL + GEE_PRIVATE_KEY no .env."
    )


def initialize() -> None:
    """
    Garante que o `ee` está inicializado. Idempotente e seguro entre threads.

    Note que `ee.Initialize` é chamado SEM `project=`: a conta de serviço não tem a
    permissão `serviceusage.services.use` no projeto, e passar o projeto explicitamente
    faz a chamada falhar. Sem o argumento, o GEE usa o projeto da própria credencial.
    """
    global _initialized
    if _initialized:
        return
    with _lock:
        if _initialized:
            return
        try:
            ee.Initialize(_load_credentials())
        except GEEUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - a lib levanta tipos variados
            logger.exception("Falha ao inicializar o Earth Engine")
            raise GEEUnavailable(str(exc)) from exc
        _initialized = True
        logger.info("Earth Engine inicializado")


def is_available() -> bool:
    """Usado pelas views para degradar a interface em vez de estourar erro 500."""
    try:
        initialize()
    except GEEUnavailable:
        return False
    return True


def tile_url(ee_object, vis_params: dict) -> str:
    """
    Gera a URL de tiles ({z}/{x}/{y}) de uma imagem do GEE.

    É a chamada cara do fluxo - por isso as views guardam o resultado em cache.
    """
    initialize()
    return ee_object.getMapId(vis_params)["tile_fetcher"].url_format
