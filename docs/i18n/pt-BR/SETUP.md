Original Living Planet («Живая планета») was created by TPECKA180; original source: https://github.com/TPECKA180/living-planet.

# Instalação e primeiro uso

[Visão geral traduzida](README.md) · [GitHub](https://github.com/TPECKA180/living-planet) · [Original setup guide (Russian)](../../SETUP.md)

## Requisitos

Instale Python 3.12 e LM Studio e baixe um modelo de texto instruct/chat capaz de seguir instruções JSON estruturadas. Os scripts do Windows instalam pygame 2.6.1 em um ambiente virtual local.

## Instalação no Windows

1. Baixe o repositório em **Code → Download ZIP**, extraia para uma pasta gravável e não execute diretamente do ZIP.
2. Instale Python 3.12 a partir de [python.org](https://www.python.org/downloads/) e verifique o comando `py -3.12`.
3. Execute `install.bat` uma vez para criar `.venv` e instalar a dependência.
4. Inicie `run.bat` e abra as configurações de **LM Studio** no jogo, ou pressione `F2` no mundo.
5. No LM Studio, abra **Developer** e inicie o servidor; no jogo, use `http://localhost:1234/v1`.
6. Atualize a lista, selecione o modelo, salve as configurações, crie um mundo com 2–6 países e execute um dia antes da observação contínua.

## Execução manual / Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

## Modelos e servidores externos

Um servidor compatível precisa oferecer `/models` e `/chat/completions`. Se não tiver a API nativa do LM Studio, desative o isolamento estrito e o controle da janela de contexto do servidor. Um servidor remoto pode receber dados do jogo.

**Não há pesos de modelos, saves ou chaves de API incluídos. A versão pública v8.0.0 não carrega modelos diretamente de `models`. Para servidores com token Bearer, use o campo oculto de chave API e não publique `config.json`. Ajuste o contexto à memória e ao modelo disponíveis.**

## Mais ajuda

- [LM Studio server documentation](https://lmstudio.ai/docs/developer/core/server)
- [Full game guide (Russian)](../../GAME_GUIDE.md)
- [Troubleshooting (Russian)](../../TROUBLESHOOTING.md)
- [Official license](../../../LICENSE) · [Русский перевод](../../../LICENSE.ru.md)
