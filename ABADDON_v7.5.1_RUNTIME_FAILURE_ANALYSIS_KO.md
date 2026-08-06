# ABADDON v7.5.1 Render 장애 분석

## 관찰된 장애

Render 프로세스가 `python 222.py`로 시작한 뒤 `apocalypse_bot.commands.v600_game_center` import 중 종료됐다.

```text
RuntimeError: 게임 기능군 연결 오류:
missing=[], duplicated=['guild_donate', 'guild_upgrade'], unknown=[]
```

## 영향

- Discord Gateway 연결 전 프로세스 종료
- 봇 오프라인
- Render 자동 재시작 반복
- 사용자 데이터 손상 징후는 없음

## 직접 원인

게임센터의 `GAME_SECTIONS`에서 길드 기부와 길드 강화 기능 키가 두 기능군 이상에 연결됐다. 기능 정의 자체나 길드 데이터의 중복이 아니라 **메뉴 연결표의 중복**이다.

## 수정

- 두 키를 `guild/organization`에 각각 한 번만 배치
- 모든 276개 기능의 정의·메뉴 연결을 1:1 검사
- 중복 위치를 기능 키별로 기록하는 진단 추가
- 운영 모드 안전 자동 복구 추가
- 스테이징용 엄격 검사 환경변수 추가
- 배포 ZIP에 Render 진입점 `222.py` 포함

## 재발 방지 검증

1. 정상 메뉴를 격리 import함
2. `guild_donate`를 다른 기능군에 인위적으로 한 번 더 삽입함
3. 운영 모드에서 첫 연결을 보존하고 중복 연결을 자동 제거하는지 확인함
4. 정상 메뉴를 복원함
5. `guild_upgrade` 중복을 인위적으로 삽입함
6. 엄격 모드에서 두 충돌 위치가 포함된 `RuntimeError`가 발생하는지 확인함

두 시나리오 모두 통과했다.

## 남은 실서버 확인

제작 환경에서는 `discord.py==2.7.1` 의존성 설치와 실제 Discord Gateway 로그인을 수행하지 못했다. Render 배포 후 첫 부팅 로그, 봇 온라인 상태와 관리자 점검 명령으로 최종 확인해야 한다.
