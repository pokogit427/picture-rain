# Picture Rain

Picture Rain은 커플·친구가 초대 코드로 연결된 상대와 사진을 주고받고, 서로의 사진을 꾸며 결과를 함께 공개하는 서비스입니다.

## G03 완료 상태

D01~D31 로컬 기능 구현을 완료했습니다. 각 단위는 구현·검증·커밋·push로 기록되었고 마지막 기능 구현 커밋은 `e07e36d`입니다. 현재 원격 HEAD에는 이 README와 구현 과정 문서를 담은 문서 커밋도 포함되어 있습니다.

구현 범위:

- 아이디/비밀번호 인증과 30일 HttpOnly 세션
- 복수의 독립적인 1:1 연결과 4자리·5분 초대 코드
- 사진 교환, 캔버스 편집, 초안 저장, 완료 제출
- 양쪽 제출 전 모자이크, 양쪽 제출 후 결과 동시 공개
- 개인 이력 삭제·30일 휴지통 복원·연결 해제 완전 삭제
- 무료 모의 사용량 경계, 기본 꺼짐 모의 광고, 모바일 오류 복구

실결제·실광고·스토어 앱·공개 클라우드 배포는 아직 활성화하지 않았습니다.

## 실행

실제 코드 저장소는 WSL `/home/daks/projects/picture-rain`입니다.

```bash
cd /home/daks/projects/picture-rain
docker compose up -d --build
curl http://localhost:8000/health
```

```bash
cd /home/daks/projects/picture-rain/web
npm run test
npm run build
```

## 문서

- [전체 코드 구현 과정](./CODE_IMPLEMENTATION_PROCESS.md)
- [제품 기준](./PROJECT_BRIEF.md)
- [전체 클라우드 과정](./DEVELOPMENT_PLAN.md)
- [G03 인계 기록](./HANDOFF.md)
- [구현 하네스](./HARNESS.md)
- [커밋 규칙](./COMMIT_CONVENTION.md)

G04 이후 단계는 별도 채팅에서 범위를 정한 뒤 시작합니다.
