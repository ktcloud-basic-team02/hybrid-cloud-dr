// =====================================================
// 스크립트명: overload_signup.js
// 작성자: 정혜빈
// 작성일: 2026-10-23
// 목적: 회원가입 경로(앱 Pod → RDS) 과부하 테스트 — 병목이 앱인지 DB인지 구분
// 실행 위치: EKS 클러스터 안 k6 Pod (beaver 네임스페이스) → http://shop (Service)
// 실행: kubectl run k6-overload -i --rm --restart=Never -n beaver \
//         --image=grafana/k6:0.54.0 -- run - < overload_signup.js
// 시나리오: 서로 다른 아이디로 가입, 동시 사용자 10 → 50 → 100 → 200명 단계적 증가
// 자동 중단: 실패율 5% 초과 / p95 응답 2초 초과 / 가입 성공률 95% 미만
// 테스트 아이디 접두어: k6load_ (정리 시 이 접두어만 삭제)
// 결과(10/24 00:07): 약 35명에서 p95 2.13초로 자동 중단, 에러 0% → 병목은 앱 Pod HPA 확장 대기
// =====================================================
import http from 'k6/http';
import { check, sleep } from 'k6';
import exec from 'k6/execution';

const BASE_URL = 'http://shop';   // 클러스터 안 Service 주소

export const options = {
  stages: [
    { duration: '30s', target: 10 },  { duration: '1m', target: 10 },
    { duration: '30s', target: 50 },  { duration: '1m', target: 50 },
    { duration: '30s', target: 100 }, { duration: '1m', target: 100 },
    { duration: '30s', target: 200 }, { duration: '1m', target: 200 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_failed:   [{ threshold: 'rate<0.05',  abortOnFail: true, delayAbortEval: '10s' }],
    http_req_duration: [{ threshold: 'p(95)<2000', abortOnFail: true, delayAbortEval: '10s' }],
    checks:            [{ threshold: 'rate>0.95',  abortOnFail: true, delayAbortEval: '10s' }],
  },
};

export default function () {
  // 사용자번호_반복번호_시각 → 매 요청마다 다른 아이디
  const username = `k6load_${exec.vu.idInTest}_${exec.vu.iterationInInstance}_${Date.now() % 100000}`;
  const res = http.post(`${BASE_URL}/signup`,
    { username: username, password: 'testpass123' },
    { redirects: 0 });
  check(res, { '가입 성공(302)': (r) => r.status === 302 });
  sleep(1);   // 실제 사용자처럼 1초 쉬고 다음 요청
}
