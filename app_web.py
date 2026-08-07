"""Interface web temporária para geração dos relatórios de pendências."""

from pathlib import Path
from typing import List, Optional
from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
import shutil
import tempfile
import os
import secrets

from analisar_pendencias import executar_analise


app = FastAPI(title='Pendências Simplificada', docs_url=None, redoc_url=None)

APP_BASE_URL = os.getenv('APP_BASE_URL', '').rstrip('/')
SESSION_SECRET = os.getenv('SESSION_SECRET', secrets.token_urlsafe(32))
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie='pendencias_session',
    max_age=8 * 60 * 60,
    same_site='lax',
    https_only=APP_BASE_URL.startswith('https://')
)

oauth = OAuth()
if os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET'):
    oauth.register(
        name='google',
        client_id=os.environ['GOOGLE_CLIENT_ID'],
        client_secret=os.environ['GOOGLE_CLIENT_SECRET'],
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email'}
    )

LIMITE_ARQUIVO_BYTES = 20 * 1024 * 1024
LIMITE_TOTAL_BYTES = 100 * 1024 * 1024


PAGINA_INICIAL = """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pendências Simplificada</title>
  <style>
    body { background:#f4f7fb; color:#172033; font:16px system-ui,sans-serif; margin:0; }
    main { max-width:680px; margin:48px auto; background:#fff; padding:32px; border-radius:12px; box-shadow:0 4px 20px #17203318; }
    h1 { margin-top:0; } label { display:block; font-weight:600; margin:22px 0 8px; }
    input { box-sizing:border-box; width:100%; padding:10px; } button { background:#1859a9; border:0; border-radius:6px; color:#fff; cursor:pointer; font-size:16px; margin-top:24px; padding:12px 18px; }
    .aviso { background:#edf5ff; border-left:4px solid #1859a9; padding:12px; } small { color:#536078; }
  </style>
</head>
<body><main>
  <h1>Pendências Simplificada</h1>
  <p>Envie os relatórios CSV da plataforma para gerar os arquivos Excel.</p>
  <p class="aviso">Os arquivos são processados temporariamente para gerar o download e são apagados após o envio do ZIP.</p>
  {mensagem}
  {conteudo}
</main></body></html>"""

FORMULARIO = """
  <form action="/gerar-relatorios" method="post" enctype="multipart/form-data">
    <label for="arquivos">Arquivos CSV</label>
    <input id="arquivos" name="arquivos" type="file" accept=".csv,text/csv" multiple required>
    <small>Use o padrão <code>TURMA_DISCIPLINA_BIMESTRE.csv</code>.</small>
    <label for="ate_semana">Considerar atividades até a semana (opcional)</label>
    <input id="ate_semana" name="ate_semana" type="number" min="1" placeholder="Ex.: 8">
    <button type="submit">Gerar relatórios</button>
  </form>
  <form action="/sair" method="post"><button type="submit">Sair</button></form>
"""


def configuracao_google_disponivel() -> bool:
    return bool(
        APP_BASE_URL
        and os.getenv('SESSION_SECRET')
        and oauth.create_client('google')
    )


def esta_autenticado(request: Request) -> bool:
    return request.session.get('autenticado') is True


def url_callback(request: Request) -> str:
    return f'{APP_BASE_URL}/auth/callback' if APP_BASE_URL else str(request.url_for('auth_callback'))


@app.get('/', response_class=HTMLResponse)
def pagina_inicial(request: Request):
    erro = request.query_params.get('erro')
    mensagem = '<p class="aviso">Não foi possível concluir o login. Tente novamente.</p>' if erro else ''
    if esta_autenticado(request):
        conteudo = FORMULARIO
    elif configuracao_google_disponivel():
        conteudo = '<p><a href="/entrar"><button type="button">Entrar com Google</button></a></p>'
    else:
        conteudo = '<p class="aviso">O login Google ainda não foi configurado neste ambiente.</p>'
    return PAGINA_INICIAL.replace('{mensagem}', mensagem).replace('{conteudo}', conteudo)


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/entrar')
async def entrar_com_google(request: Request):
    if not configuracao_google_disponivel():
        raise HTTPException(status_code=503, detail='Login Google não configurado.')
    cliente_google = oauth.create_client('google')
    return await cliente_google.authorize_redirect(request, url_callback(request))


@app.get('/auth/callback', name='auth_callback')
async def auth_callback(request: Request):
    if not configuracao_google_disponivel():
        raise HTTPException(status_code=503, detail='Login Google não configurado.')
    try:
        token = await oauth.create_client('google').authorize_access_token(request)
        usuario = token.get('userinfo', {})
        if not usuario.get('email_verified'):
            request.session.clear()
            return RedirectResponse('/?erro=conta-nao-verificada', status_code=303)
    except OAuthError:
        request.session.clear()
        return RedirectResponse('/?erro=oauth', status_code=303)

    request.session.clear()
    request.session['autenticado'] = True
    return RedirectResponse('/', status_code=303)


@app.post('/sair')
def sair(request: Request):
    request.session.clear()
    return RedirectResponse('/', status_code=303)


def salvar_uploads(arquivos: List[UploadFile], pasta_entrada: Path):
    nomes_recebidos = set()
    total_bytes = 0

    for arquivo in arquivos:
        nome = Path(arquivo.filename or '').name
        partes = Path(nome).stem.split('_')
        if not nome.lower().endswith('.csv') or len(partes) != 3 or not all(partes):
            raise ValueError('Use apenas CSVs no padrão TURMA_DISCIPLINA_BIMESTRE.csv.')
        if nome.lower() in nomes_recebidos:
            raise ValueError('Há arquivos com o mesmo nome.')
        nomes_recebidos.add(nome.lower())

        destino = pasta_entrada / nome
        tamanho_arquivo = 0
        with destino.open('wb') as destino_aberto:
            while True:
                conteudo = arquivo.file.read(1024 * 1024)
                if not conteudo:
                    break
                tamanho_arquivo += len(conteudo)
                total_bytes += len(conteudo)
                if tamanho_arquivo > LIMITE_ARQUIVO_BYTES or total_bytes > LIMITE_TOTAL_BYTES:
                    raise ValueError('O limite é de 20 MB por arquivo e 100 MB no total.')
                destino_aberto.write(conteudo)


@app.post('/gerar-relatorios')
def gerar_relatorios(
    request: Request,
    background_tasks: BackgroundTasks,
    arquivos: List[UploadFile] = File(...),
    ate_semana: Optional[int] = Form(None)
):
    if not esta_autenticado(request):
        return RedirectResponse('/entrar', status_code=303)
    if not arquivos:
        raise HTTPException(status_code=400, detail='Envie ao menos um arquivo CSV.')

    pasta_temporaria = Path(tempfile.mkdtemp(prefix='pendencias-'))
    pasta_entrada = pasta_temporaria / 'entrada'
    pasta_saida = pasta_temporaria / 'saida'
    pasta_entrada.mkdir()

    try:
        salvar_uploads(arquivos, pasta_entrada)
        executar_analise(pasta_entrada, pasta_saida, ate_semana)
        caminho_zip = Path(shutil.make_archive(str(pasta_temporaria / 'relatorios'), 'zip', pasta_saida))
    except ValueError as erro:
        shutil.rmtree(pasta_temporaria, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    except Exception as erro:
        shutil.rmtree(pasta_temporaria, ignore_errors=True)
        raise HTTPException(status_code=422, detail='Não foi possível processar os arquivos enviados.') from erro
    finally:
        for arquivo in arquivos:
            arquivo.file.close()

    background_tasks.add_task(shutil.rmtree, pasta_temporaria, ignore_errors=True)
    return FileResponse(
        caminho_zip,
        media_type='application/zip',
        filename='relatorios_pendencias.zip',
        background=background_tasks
    )
