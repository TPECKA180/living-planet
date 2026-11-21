Original Living Planet («Живая планета») was created by TPECKA180; original source: https://github.com/TPECKA180/living-planet.

# 安装与首次运行

[本地化项目介绍](README.md) · [GitHub](https://github.com/TPECKA180/living-planet) · [Original setup guide (Russian)](../../SETUP.md)

## 运行要求

安装 Python 3.12 和 LM Studio，并下载能够遵循结构化 JSON 指令的文本 instruct/chat 模型。Windows 安装脚本会在本地虚拟环境中安装 pygame 2.6.1。

## Windows 安装步骤

1. 通过 **Code → Download ZIP** 下载仓库，解压到具有写入权限的文件夹。不要直接在 ZIP 内运行。
2. 从 [python.org](https://www.python.org/downloads/) 安装 Python 3.12，确认 Windows 的 `py -3.12` 命令可用。
3. 运行一次 `install.bat`，创建 `.venv` 并安装 Python 依赖。
4. 运行 `run.bat`，在游戏中打开 **LM Studio** 设置，或在世界中按 `F2`。
5. 在 LM Studio 的 **Developer** 页面启动服务器；游戏中填入 `http://localhost:1234/v1`。
6. 刷新模型列表并选择模型，保存设置，创建包含 2–6 个国家的世界；先推进一天确认正常后再开启连续观察。

## 手动运行 / Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

## 模型与外部服务器

兼容服务器应提供 `/models` 和 `/chat/completions`。如果服务器缺少 LM Studio 的原生 API，需要关闭严格隔离与服务器上下文窗口管理。使用远程服务器时，游戏数据可能发送到该服务器。

**本项目不包含模型权重、游戏存档或 API 密钥。公开的 v8.0.0 不能直接从 `models` 文件夹加载模型。如果服务器需要 Bearer 令牌，请在游戏的隐藏 API 密钥字段中输入，切勿公开 `config.json`。上下文长度必须适合实际模型与硬件。**

## 更多帮助

- [LM Studio server documentation](https://lmstudio.ai/docs/developer/core/server)
- [Full game guide (Russian)](../../GAME_GUIDE.md)
- [Troubleshooting (Russian)](../../TROUBLESHOOTING.md)
- [Official license](../../../LICENSE) · [Русский перевод](../../../LICENSE.ru.md)
