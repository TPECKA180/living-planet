Original Living Planet («Живая планета») was created by TPECKA180; original source: https://github.com/TPECKA180/living-planet.

# 🌍 Living Planet — 自主 AI 文明模拟

**本地语言模型、独立国家，以及由真实决策推动的历史。**

**Languages / Языки:** [English](../en/README.md) · [Русский](../../../README.md) · [Español](../es/README.md) · [简体中文](../zh-CN/README.md) · [Português (Brasil)](../pt-BR/README.md) · [Deutsch](../de/README.md) · [Français](../fr/README.md) · [日本語](../ja/README.md) · [한국어](../ko/README.md) · [Italiano](../it/README.md)

![Living Planet interface](../../assets/interface.png)

Living Planet（《Живая планета》，意为“活的星球”）是一款大战略模拟游戏。2–6 个国家分别由本地运行的语言模型作出决策。每个国家都有自己的资源、领土、规划、外交关系和记忆。你可以创建世界，观察它们如何发展、谈判、贸易、交战并承担后果。

## 模拟如何运行

Python 游戏引擎会根据领土归属、资源、科技、路线和条约验证 AI 提交的结构化指令。AI 说“建造工厂”并不会凭空生成工厂；必须满足建造和支付条件。

55 类行动 · 31 种资源 · 2 个时代 · 25 + 33 项科技 · 45 种工业时代建筑 · 8 类现代部队。经济系统涉及劳动力、生产链、能源、维护、补给和危机。地图支持固定种子复现、像素风近景与群岛模式。

## 快速开始

1. 安装 Python 3.12 和 LM Studio；下载能够输出结构化 JSON 的 instruct/chat 模型，并在 **Developer** 页面启动服务器。
2. 通过 GitHub 的 ZIP 下载仓库，将其解压到可写目录；Windows 用户运行 `install.bat`。
3. 运行 `run.bat`，在游戏中打开 **LM Studio**（或按 `F2`），输入 `http://localhost:1234/v1`，刷新模型列表并选择模型。
4. 创建拥有 2–6 个国家的世界，然后点击游戏中的“单日推进”或“观察”功能（当前界面按钮为俄语）。

```bash
python -m pip install -r requirements.txt
python main.py
```

**下载包**不包含**语言模型、模型权重、存档或 API 密钥。公开的 v8.0.0 需要兼容的模型服务器，不能直接从 `models` 文件夹启动模型。记忆和奖励会影响后续提示，但**不会微调模型权重**。**

![Archipelago mode](../../assets/archipelago.png)

## 文档与许可

- [安装与首次运行](SETUP.md)
- [完整玩家手册（俄语）](../../GAME_GUIDE.md)
- [游戏截图](../../SCREENSHOTS.md)
- [许可证：免费分发并保留原作者署名](../../../LICENSE) · [Русский перевод лицензии](../../../LICENSE.ru.md)
- [GitHub / Source](https://github.com/TPECKA180/living-planet)

完整玩家手册和技术文档目前仍以俄语为准。本页与安装指南仅为本地化入门说明，**不代表游戏界面已汉化**。

分发或修改本项目时，必须保留原始作者信息与原仓库链接。
