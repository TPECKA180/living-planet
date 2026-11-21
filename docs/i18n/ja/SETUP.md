Original Living Planet («Живая планета») was created by TPECKA180; original source: https://github.com/TPECKA180/living-planet.

# インストールと初回起動

[翻訳版プロジェクト概要](README.md) · [GitHub](https://github.com/TPECKA180/living-planet) · [Original setup guide (Russian)](../../SETUP.md)

## 必要な環境

Python 3.12 と LM Studio をインストールし、構造化 JSON の指示に従える instruct/chat テキストモデルをダウンロードします。Windows 用スクリプトはローカル仮想環境に pygame 2.6.1 をインストールします。

## Windows での設定

1. **Code → Download ZIP** でリポジトリを取得し、書き込み可能なフォルダーに展開します。ZIP 内から直接実行しないでください。
2. [python.org](https://www.python.org/downloads/) から Python 3.12 をインストールし、`py -3.12` が動作することを確認します。
3. `install.bat` を一度実行し、`.venv` の作成と依存関係のインストールを行います。
4. `run.bat` を起動し、ゲーム内の **LM Studio** 設定を開きます（ワールド内では `F2`）。
5. LM Studio の **Developer** 画面でサーバーを開始し、ゲーム内で `http://localhost:1234/v1` を入力します。
6. モデル一覧を更新してモデルを選択・保存します。2〜6か国の世界を作成し、連続観察の前に1日だけ実行して動作を確認します。

## 手動起動 / Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

## モデルと外部サーバー

互換サーバーには `/models` と `/chat/completions` が必要です。LM Studio 固有の API がないサーバーでは、厳密な分離とサーバー側コンテキスト管理を無効にしてください。外部サーバーにゲームデータが送信される場合があります。

**モデルの重み、セーブデータ、APIキーは同梱されません。公開版 v8.0.0 は `models` フォルダーから直接モデルを起動できません。Bearer トークンが必要な場合はゲームの非表示 API キー欄に入力し、`config.json` を公開しないでください。モデルとメモリに適したコンテキスト長を設定してください。**

## 追加ヘルプ

- [LM Studio server documentation](https://lmstudio.ai/docs/developer/core/server)
- [Full game guide (Russian)](../../GAME_GUIDE.md)
- [Troubleshooting (Russian)](../../TROUBLESHOOTING.md)
- [Official license](../../../LICENSE) · [Русский перевод](../../../LICENSE.ru.md)
