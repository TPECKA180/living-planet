Original Living Planet («Живая планета») was created by TPECKA180; original source: https://github.com/TPECKA180/living-planet.

# 🌍 Living Planet — AIが動かす自律文明

**ローカル言語モデル。独立した国家。実際の意思決定が紡ぐ歴史。**

**Languages / Языки:** [English](../en/README.md) · [Русский](../../../README.md) · [Español](../es/README.md) · [简体中文](../zh-CN/README.md) · [Português (Brasil)](../pt-BR/README.md) · [Deutsch](../de/README.md) · [Français](../fr/README.md) · [日本語](../ja/README.md) · [한국어](../ko/README.md) · [Italiano](../it/README.md)

![Living Planet interface](../../assets/interface.png)

Living Planet は、ローカルで動く言語モデルが 2〜6 か国の意思決定を行うグランドストラテジー・シミュレーションです。各国には独自の資源、領土、計画、外交関係、記憶があります。世界を作成し、国家が建設・交渉・貿易・戦争を行い、その結果を受け止める様子を観察できます。

## シミュレーションの仕組み

Python製のゲームエンジンは、AIが出力した構造化命令を領土の所有権、資源、技術、経路、条約に照らして検証します。「工場を建てる」と宣言するだけでは、条件と費用が満たされない限り工場は建ちません。

55種類の行動 · 31種類の資源 · 2つの時代 · 25 + 33種類の技術 · 工業時代の建物45種類 · 近代兵種8種類。経済には労働力、生産工程、エネルギー、維持費、補給、危機が含まれます。シードで再現できるマップと群島モードがあります。

## クイックスタート

1. Python 3.12 と LM Studio をインストールします。構造化 JSON を出力できる instruct/chat モデルを用意し、**Developer** からサーバーを起動します。
2. リポジトリを ZIP でダウンロードし、書き込み可能なフォルダーに展開して Windows で `install.bat` を実行します。
3. `run.bat` を起動し、**LM Studio**（または `F2`）から `http://localhost:1234/v1` を設定し、モデル一覧を更新してモデルを選びます。
4. 2〜6か国の世界を作成し、1日進めるか観察モードを開始します（現行のゲーム画面はロシア語です）。

```bash
python -m pip install -r requirements.txt
python main.py
```

**配布物には**言語モデル、モデルの重み、セーブデータ、APIキーは含まれません**。公開版 v8.0.0 では互換モデルサーバーが必要で、`models` フォルダーから直接モデルを起動できません。記憶や報酬はフィードバックになりますが、**モデルの重みをファインチューニングしません**。**

![Archipelago mode](../../assets/archipelago.png)

## ドキュメントとライセンス

- [セットアップ手順](SETUP.md)
- [完全版ガイド（ロシア語）](../../GAME_GUIDE.md)
- [スクリーンショット](../../SCREENSHOTS.md)
- [ライセンス：無料配布と原作者表記が必須](../../../LICENSE) · [Русский перевод лицензии](../../../LICENSE.ru.md)
- [GitHub / Source](https://github.com/TPECKA180/living-planet)

完全なゲームガイドと技術資料は現在ロシア語です。本ページと翻訳版セットアップガイドは入門用の翻訳であり、**ゲーム内UIの日本語化を意味しません**。

再配布や改変を行う場合、原作者の表示と元のリポジトリへのリンクを必ず残してください。
