# Checkpoint 1 - RPA - Spotify

Automação em Flask que recebe a escolha de uma playlist e inicia a reprodução no Spotify através da Web API.

## 1. Pré-requisitos

- Python 3.11+;
- conta Spotify Premium;
- Spotify aberto em um notebook, celular ou dispositivo Spotify Connect;
- app criado em https://developer.spotify.com/dashboard.

## 2. Configuração no Spotify Developer Dashboard

1. Crie um app e habilite **Web API**.
2. Em **Redirect URIs**, adicione exatamente: `http://127.0.0.1:5000/callback`.
3. Copie Client ID e Client Secret.
4. Em Development Mode, use a conta dona do app ou adicione os usuários necessários em Users Management.

## 3. Preparar as playlists

Para evitar qualquer risco de conteúdo explícito, crie três playlists próprias e revise manualmente as faixas. Sugestão:

- Focus Instrumental;
- Lo-fi Clean;
- Acoustic Clean.

No Spotify, copie a URI da playlist e coloque-a no `.env`.

## 4. Executar

No Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edite o `.env` e depois:

```powershell
python app.py
```

Abra: `http://127.0.0.1:5000`

Na primeira vez, clique em **Conectar Spotify** e aceite as permissões.

Após a primeira vez, executar:

```powershell
.venv\Scripts\Activate.ps1
python app.py
```

## 5. Demonstração em aula

Antes da validação:

1. execute `python app.py`;
2. abra o Spotify Desktop ou celular com a mesma conta;
3. toque uma música por alguns segundos para garantir que o dispositivo esteja disponível;
4. abra o formulário no navegador;
5. escolha uma playlist;
6. clique em **Reproduzir playlist**.

O backend identifica a opção, transfere o playback para o dispositivo escolhido/ativo e chama o endpoint de reprodução com a URI da playlist.

## 6. Scopes utilizados

- `user-read-playback-state`: localizar dispositivos Spotify Connect;
- `user-modify-playback-state`: transferir e iniciar a reprodução.

## 7. Diagnóstico rápido

- **401**: token inválido/expirado; exclua `.spotify_token.json` e autentique de novo.
- **403**: confirme Spotify Premium, usuário permitido no app e scopes.
- **404 / nenhum dispositivo**: abra o Spotify e reproduza uma faixa manualmente antes do teste.
- **429**: limite temporário de chamadas; aguarde o período indicado pelo Spotify.