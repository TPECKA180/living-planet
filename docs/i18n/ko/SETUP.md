Original Living Planet («Живая планета») was created by TPECKA180; original source: https://github.com/TPECKA180/living-planet.

# 설치 및 첫 실행

[번역된 프로젝트 개요](README.md) · [GitHub](https://github.com/TPECKA180/living-planet) · [Original setup guide (Russian)](../../SETUP.md)

## 필요한 환경

Python 3.12와 LM Studio를 설치하고 구조화된 JSON 지시를 따를 수 있는 instruct/chat 텍스트 모델을 내려받습니다. Windows 스크립트는 로컬 가상 환경에 pygame 2.6.1을 설치합니다.

## Windows 설치

1. **Code → Download ZIP**에서 저장소를 내려받아 쓰기 가능한 폴더에 압축을 풉니다. ZIP 내부에서 직접 실행하지 마세요.
2. [python.org](https://www.python.org/downloads/)에서 Python 3.12를 설치하고 `py -3.12`가 실행되는지 확인합니다.
3. `install.bat`를 한 번 실행해 `.venv`를 만들고 종속성을 설치합니다.
4. `run.bat`를 실행하고 게임 내 **LM Studio** 설정을 열거나 월드에서 `F2`를 누릅니다.
5. LM Studio의 **Developer**에서 서버를 시작하고 게임에 `http://localhost:1234/v1`을 입력합니다.
6. 목록을 새로고침하여 모델을 선택하고 설정을 저장합니다. 2~6개 국가의 세계를 만든 뒤 연속 관찰 전에 하루만 실행해 확인합니다.

## 수동 실행 / Linux

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

## 모델 및 외부 서버

호환 서버에는 `/models`와 `/chat/completions`가 필요합니다. LM Studio의 기본 API가 없는 서버에서는 엄격한 격리와 서버 컨텍스트 창 관리를 꺼야 합니다. 원격 서버로 게임 데이터가 전송될 수 있습니다.

**모델 가중치, 저장 파일, API 키는 포함되어 있지 않습니다. 공개 v8.0.0은 `models` 폴더에서 모델을 직접 시작하지 않습니다. Bearer 토큰이 필요한 경우 게임의 숨겨진 API 키 필드를 사용하고 `config.json`을 공개하지 마세요. 컨텍스트 길이는 실제 모델 및 메모리에 맞추세요.**

## 추가 도움말

- [LM Studio server documentation](https://lmstudio.ai/docs/developer/core/server)
- [Full game guide (Russian)](../../GAME_GUIDE.md)
- [Troubleshooting (Russian)](../../TROUBLESHOOTING.md)
- [Official license](../../../LICENSE) · [Русский перевод](../../../LICENSE.ru.md)
