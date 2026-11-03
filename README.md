# goldstack

Claude Code로 프로젝트를 진행하는 개인 운영 kit. 처음에 grill로 깊게 정렬하고, `go` 한 번 뒤에는 구현 완료와 main 병합까지 알아서 진행한다.

- 철학: [pstack](https://github.com/cursor/plugins/tree/main/pstack)의 "if you want to go fast, go deep first", "never block on the human".
- 모델: Claude · codex · gemini를 티켓마다 고르고, 리뷰는 항상 다른 계열이 한다. herdr pane에서 worker를 보이게 돌린다.
- 상태: 레포 안 markdown 파일(`.work/<feature>/spec.md`, `tickets/NN.md`)과 git.

시작 배경과 요구사항은 [docs/ORIGINS.md](docs/ORIGINS.md), 참고한 kit 분석은 [docs/research/](docs/research/)(pstack, mattpocock/skills, 비교표).

## 설치와 사용
```sh
uv tool install --reinstall .   # 고정 복사로 설치. main을 받은 뒤 다시 실행한다
gs check <feature>              # .work/<feature>/의 spec과 티켓 그래프 검사
gs check <feature> --only 03,04 # 일부 티켓만 기준으로 순서·frontier 계산
uv run python -m unittest discover -s tests   # 검증 명령
```
