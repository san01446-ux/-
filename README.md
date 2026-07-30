# 아포칼립스 생존 봇 모듈형 프로젝트 v3.0

## 실행 방법
1. `.env.example`을 복사해 `.env`로 이름을 변경합니다.
2. `.env`에 디스코드 봇 토큰을 입력합니다.
3. 기존 `survival_data.json`이 있으면 `main.py` 옆에 복사합니다.
4. 터미널에서 아래 명령을 실행합니다.

```bash
pip install -r requirements.txt
python main.py
```

## 현재 구조
- `main.py`: 실행 전용
- `apocalypse_bot/core/bot.py`: 기존 전체 기능을 안전하게 보존한 핵심 게임 코드
- `apocalypse_bot/commands/`: 다음 단계에서 직업, 지역, 감염, 스토리 등을 기능별로 분리할 폴더
- `apocalypse_bot/game_data/`: 몬스터, 장비, 지역, 업적 데이터를 분리할 폴더

## 중요한 점
이 버전은 기존 명령어와 저장 데이터를 깨지 않도록 먼저 실행 구조만 분리한 1단계 버전입니다.
다음 업데이트부터 기능 묶음별로 Cog 모듈로 이동할 수 있습니다.
