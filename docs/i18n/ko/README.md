Original Living Planet («Живая планета») was created by TPECKA180; original source: https://github.com/TPECKA180/living-planet.

# 🌍 Living Planet — AI가 운영하는 자율 문명

**로컬 언어 모델. 독립 국가. 실제 결정으로 만들어지는 역사.**

**Languages / Языки:** [English](../en/README.md) · [Русский](../../../README.md) · [Español](../es/README.md) · [简体中文](../zh-CN/README.md) · [Português (Brasil)](../pt-BR/README.md) · [Deutsch](../de/README.md) · [Français](../fr/README.md) · [日本語](../ja/README.md) · [한국어](../ko/README.md) · [Italiano](../it/README.md)

![Living Planet interface](../../assets/interface.png)

Living Planet은 로컬에서 실행되는 언어 모델이 2~6개 국가의 결정을 내리는 대전략 시뮬레이션입니다. 각 국가는 고유한 자원, 영토, 계획, 외교 관계, 기억을 가집니다. 세계를 만들고 국가가 건설하고 협상하며 교역하고 전쟁을 벌인 뒤 그 결과를 감당하는 모습을 관찰할 수 있습니다.

## 시뮬레이션의 작동 방식

Python 게임 엔진은 AI가 출력한 구조화 명령을 영토 소유권, 자원, 기술, 경로, 조약에 비추어 검사합니다. AI가 '공장을 짓겠다'고 말해도 실제 건설 조건과 비용을 충족하지 않으면 공장은 생기지 않습니다.

55종의 행동 · 31종의 자원 · 2개 시대 · 25 + 33개 기술 · 산업 시대 건물 45종 · 현대 군대 유형 8종. 경제는 노동력, 생산망, 에너지, 유지비, 보급, 위기를 다룹니다. 시드로 재현 가능한 지도와 군도 모드가 있습니다.

## 빠른 시작

1. Python 3.12와 LM Studio를 설치합니다. 구조화된 JSON을 출력할 수 있는 instruct/chat 모델을 내려받고 **Developer**에서 서버를 시작합니다.
2. 저장소를 ZIP으로 다운로드한 뒤 쓰기 가능한 폴더에 압축을 풀고 Windows에서 `install.bat`를 실행합니다.
3. `run.bat`를 열고 **LM Studio**(또는 `F2`)에서 `http://localhost:1234/v1`을 입력한 후 모델 목록을 새로고침하고 모델을 선택합니다.
4. 2~6개 국가가 있는 세계를 만들고 하루 진행 또는 관찰 기능을 실행합니다(현재 게임 UI는 러시아어입니다).

```bash
python -m pip install -r requirements.txt
python main.py
```

**배포 파일에는 **언어 모델, 모델 가중치, 저장 데이터, API 키가 포함되지 않습니다**. 공개 버전 v8.0.0에는 호환 모델 서버가 필요하며 `models` 폴더에서 모델을 직접 실행하지 못합니다. 기억과 보상은 피드백으로 쓰이지만 **모델 가중치를 파인튜닝하지는 않습니다**.**

![Archipelago mode](../../assets/archipelago.png)

## 문서 및 라이선스

- [설치 및 첫 실행](SETUP.md)
- [전체 게임 가이드(러시아어)](../../GAME_GUIDE.md)
- [스크린샷 갤러리](../../SCREENSHOTS.md)
- [라이선스: 무료 배포 및 원저작자 표시 의무](../../../LICENSE) · [Русский перевод лицензии](../../../LICENSE.ru.md)
- [GitHub / Source](https://github.com/TPECKA180/living-planet)

전체 게임 가이드와 기술 문서 원본은 현재 러시아어입니다. 이 페이지와 번역된 설치 안내는 입문용 번역이며 **게임 내 UI가 한국어로 번역되었다는 뜻은 아닙니다**.

프로젝트를 재배포하거나 수정할 때 원저작자와 원본 저장소 링크를 반드시 유지해야 합니다.
