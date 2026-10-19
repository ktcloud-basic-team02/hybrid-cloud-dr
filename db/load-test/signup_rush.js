// =====================================================
// 스크립트명: signup_rush.js
// 작성자: 정혜빈
// 작성일: 2026-10-18
// 목적: "회원가입 폭주" 부하 테스트를 k6로 재현
//       (10/16 while+curl 테스트의 다음 단계, 멘토링 피드백 반영)
// 실행 위치: 정혜빈 PC (Windows, Tailscale) → EC2 앱 (100.107.129.104:5002)
// 시나리오: 가상 사용자 50명이 같은 username으로 동시에 회원가입 시도
// 기대 결과: 1건만 성공(HTTP 302 리다이렉트), 49건은 중복 에러(HTTP 200)
// 테스트 아이디 접두어: k6test_ (while+curl의 loadtest_와 구분)
//
// 수정 이력:
//   2026-10-18 정혜빈 - 최초 작성
//   2026-10-18 정혜빈 - 중복 판별 조건 변경 ('이미 존재' 문구 → Sign up 화면 재표시)
//                      ※ 본문에서 [10/18 수정] 표시가 붙은 줄이 바뀐 부분
// =====================================================

import http from 'k6/http';
import { check } from 'k6';
import { Counter } from 'k6/metrics';

const BASE_URL = 'http://100.107.129.104:5002';

// 결과 종류별 카운터
const signupSuccess   = new Counter('signup_success');    // 가입 성공 (302)
const signupDuplicate = new Counter('signup_duplicate');  // 중복 아이디 에러 (200 + "이미 존재")
const signupOther     = new Counter('signup_other');      // 그 외 (서버 오류 등)

export const options = {
  scenarios: {
    signup_rush: {
      executor: 'shared-iterations',
      vus: 50,          // 가상 사용자 50명
      iterations: 50,   // 총 50번 요청
      maxDuration: '30s',
    },
  },
  // 자동 판정 기준: 성공 정확히 1건, 기타 0건
  thresholds: {
    signup_success: ['count==1'],
    signup_other:   ['count==0'],
  },
};

// 테스트 시작 전 1번만 실행: 50명이 같이 쓸 아이디 생성
export function setup() {
  const username = `k6test_${Date.now()}`;
  console.log(`테스트 대상 아이디: ${username}`);
  return { username };
}

// 가상 사용자 각각이 실행하는 부분
export default function (data) {
  const res = http.post(
    `${BASE_URL}/signup`,
    { username: data.username, password: 'testpass123' },
    { redirects: 0 }
  );

  const isSuccess   = res.status === 302;
  // [10/18 수정] 중복 판별 조건 변경
  //   이전: res.status === 200 && String(res.body).includes('이미 존재')
  //   이유: 앱이 중복 가입 시 안내 문구 없이 Sign up 화면만 다시 반환함 (응답 본문 확인)
  const isDuplicate = res.status === 200 && String(res.body).includes('<title>Sign up');

  signupSuccess.add(isSuccess ? 1 : 0);
  signupDuplicate.add(isDuplicate ? 1 : 0);
  signupOther.add(!isSuccess && !isDuplicate ? 1 : 0);

  check(res, {
    '응답이 302(성공) 또는 200(중복)': (r) => r.status === 302 || r.status === 200,
  });
}

// 테스트 끝나고 1번만 실행
export function teardown(data) {
  console.log(`테스트 아이디: ${data.username} → DB에서 1건인지 확인할 것`);
}
