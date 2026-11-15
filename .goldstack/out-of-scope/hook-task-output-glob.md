# hook이 백그라운드 출력 글로브를 막는다

**무엇**: worker가 Claude 백그라운드 작업 출력을 `tasks/*.output` 같은 글로브로 읽는 명령을 hook이 deny한다.

**왜 밖**: 처음 한 번 난 일이다(goldstack-v40 03, 출력 5GB). 차단 hook을 바꾸면 large 티켓에 두 번째 리뷰어가 붙는다. goldstack-v41은 brief 규칙 한 줄로 막는다.

**다시 볼 조건**: brief 규칙을 넣은 뒤에도 worker가 출력 글로브로 자기 출력을 읽어 명령이 죽거나 출력이 불어난 일이 다시 나오면.

결정: goldstack-v41 grill 라운드 1-5 (2026-11-14)
