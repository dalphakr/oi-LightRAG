# MCP(모델 컨텍스트 프로토콜) 서버 구축 가이드

> 출처: [Apidog - MCP 서버 구축 방법](https://apidog.com/kr/blog/build-an-mcp-server-kr/)

## 목차
- [MCP 개요](#mcp-개요)
- [필수 요구사항](#필수-요구사항)
- [MCP 프레임워크 설치](#mcp-프레임워크-설치)
- [첫 번째 도구 만들기](#첫-번째-도구-만들기)
- [서버 빌드 및 테스트](#서버-빌드-및-테스트)
- [실제 API 연결](#실제-api-연결)
- [참고 자료](#참고-자료)

## MCP 개요

### MCP란?

**모델 컨텍스트 프로토콜(Model Context Protocol, MCP)**은 Anthropic에서 개발한 개방형 표준으로, AI 모델이 외부 데이터 소스와 상호작용하는 방식을 표준화합니다.

### 주요 특징

- **표준화된 프로토콜**: 다양한 AI 플랫폼(Claude Desktop 등)과 쉽게 통합
- **도구 개발 간소화**: 통합 프로세스를 단순화하여 개발에 집중 가능
- **플랫폼 호환성**: 호환성 문제 없이 여러 플랫폼에서 작동

### 사용 사례

- 날씨 데이터 가져오기
- 주식 가격 분석
- 작업 자동화
- 외부 API 통합

## 필수 요구사항

MCP 서버 구축을 시작하기 전에 다음 항목이 필요합니다:

| 항목 | 버전 | 설명 |
|------|------|------|
| **Node.js** | 20 이상 | 서버 런타임 환경 |
| **TypeScript** | 5.0 이상 | 서버 구축 언어 |
| **npm** | 최신 버전 | 패키지 관리자 |
| **MCP Framework** | 최신 버전 | MCP 서버 프레임워크 |

### Node.js 다운로드
- 공식 사이트: https://nodejs.org/

## MCP 프레임워크 설치

### 옵션 1: MCP CLI 사용 (권장)

가장 간단하고 빠른 방법입니다:

```bash
# CLI를 전역적으로 설치
npm install -g mcp-framework

# 새 프로젝트 생성
mcp create my-mcp-server

# 프로젝트 디렉토리로 이동
cd my-mcp-server

# 종속성 설치
npm install
```

#### 생성되는 프로젝트 구조

```
my-mcp-server/
├── src/
│   ├── index.ts          # 서버 진입점
│   └── tools/            # 도구 디렉토리
├── package.json
├── tsconfig.json
└── README.md
```

**특징:**
- 사전 구성된 TypeScript 환경
- 예제 도구 포함
- 내장 오류 처리
- 즉시 사용 가능

### 옵션 2: 수동 설치 (기존 프로젝트용)

기존 프로젝트에 MCP를 추가하는 경우:

```bash
# MCP 프레임워크 설치
npm install mcp-framework
```

#### 기본 서버 생성

`src/index.ts` 파일을 생성하고 다음 코드를 추가:

```typescript
import { MCPServer } from "mcp-framework";

const server = new MCPServer();

server.start().catch((error) => {
  console.error("서버 오류:", error);
  process.exit(1);
});
```

## 첫 번째 도구 만들기

### 날씨 도구 예제

주어진 도시의 날씨 정보를 가져오는 간단한 도구를 만들어봅시다.

#### 1단계: 도구 생성

```bash
# MCP CLI를 사용하여 새 도구 생성
mcp add tool weather
```

이 명령은 `src/tools/WeatherTool.ts` 파일을 자동으로 생성합니다.

#### 2단계: 도구 구현

`src/tools/WeatherTool.ts` 파일을 다음과 같이 작성:

```typescript
import { MCPTool } from "mcp-framework";
import { z } from "zod";

interface WeatherInput {
  city: string;
}

class WeatherTool extends MCPTool<WeatherInput> {
  name = "weather";
  description = "도시의 날씨 정보를 가져오기";

  // Zod를 사용한 스키마 검증
  schema = {
    city: {
      type: z.string(),
      description: "도시 이름 (예: 서울, 부산)",
    },
  };

  async execute({ city }: WeatherInput) {
    // 모의 데이터 반환 (나중에 실제 API로 교체)
    return {
      city,
      temperature: 22,
      condition: "맑음",
      humidity: 45,
    };
  }
}

export default WeatherTool;
```

#### 코드 설명

- **MCPTool 상속**: 모든 MCP 도구는 `MCPTool` 클래스를 상속
- **name**: 도구의 고유 식별자
- **description**: 도구의 기능 설명
- **schema**: Zod를 사용한 입력 검증 스키마
- **execute**: 실제 로직을 구현하는 메서드

## 서버 빌드 및 테스트

### 1단계: 프로젝트 빌드

```bash
npm run build
```

이 명령은 TypeScript 코드를 JavaScript로 컴파일합니다.

### 2단계: MCP Inspector로 테스트

MCP Inspector는 MCP 서버를 테스트하는 공식 도구입니다.

#### 전송 방법 선택

MCP는 두 가지 전송 방법을 지원:

1. **stdio (표준 입출력)**
   - 로컬 프로세스 간 통신
   - Claude Desktop과 같은 데스크톱 앱에 적합

2. **SSE (Server-Sent Events)**
   - HTTP 기반 통신
   - 웹 서비스에 적합

#### stdio로 테스트

```bash
npx @modelcontextprotocol/inspector node dist/index.js
```

#### SSE로 테스트

```bash
# 서버 시작
npm start

# 다른 터미널에서 Inspector 실행
npx @modelcontextprotocol/inspector http://localhost:3000/sse
```

### 3단계: 도구 테스트

Inspector에서:
1. 생성한 도구 선택
2. 입력 파라미터 입력 (예: `"서울"`)
3. 실행 버튼 클릭
4. 결과 확인

## 실제 API 연결

### Open-Meteo API를 사용한 실제 날씨 데이터

모의 데이터 대신 실제 날씨 API를 연결해봅시다.

#### 1단계: axios 설치

```bash
npm install axios
npm install --save-dev @types/axios
```

#### 2단계: 날씨 API 도구 구현

`src/tools/WeatherApiTool.ts`:

```typescript
import { MCPTool } from "mcp-framework";
import { z } from "zod";
import axios from "axios";

interface WeatherInput {
  city: string;
}

class WeatherApiTool extends MCPTool<WeatherInput> {
  name = "weather_api";
  description = "실제 날씨 API를 사용하여 도시의 날씨 정보를 가져오기";

  // API 엔드포인트
  private readonly GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search";
  private readonly WEATHER_URL = "https://api.open-meteo.com/v1/forecast";

  schema = {
    city: {
      type: z.string(),
      description: "도시 이름 (예: 서울, 부산, 제주)",
    },
  };

  async execute({ city }: WeatherInput) {
    try {
      // 1. 도시 이름으로 좌표 검색
      const geoResponse = await axios.get(this.GEOCODING_URL, {
        params: {
          name: city,
          count: 1,
          language: "ko",
          format: "json"
        }
      });

      if (!geoResponse.data.results || geoResponse.data.results.length === 0) {
        throw new Error(`도시를 찾을 수 없습니다: ${city}`);
      }

      const location = geoResponse.data.results[0];
      
      // 2. 좌표를 사용하여 날씨 데이터 가져오기
      const weatherResponse = await axios.get(this.WEATHER_URL, {
        params: {
          latitude: location.latitude,
          longitude: location.longitude,
          current: [
            "temperature_2m",
            "relative_humidity_2m",
            "apparent_temperature",
            "precipitation",
            "weather_code",
            "wind_speed_10m"
          ],
          timezone: "auto"
        }
      });

      const current = weatherResponse.data.current;
      
      // 3. 날씨 코드를 조건으로 변환
      const condition = this.getWeatherCondition(current.weather_code);

      return {
        city: location.name,
        temperature: Math.round(current.temperature_2m),
        condition,
        humidity: Math.round(current.relative_humidity_2m),
        windSpeed: Math.round(current.wind_speed_10m),
        feelsLike: Math.round(current.apparent_temperature),
        precipitation: current.precipitation
      };
    } catch (error: unknown) {
      if (error instanceof Error) {
        throw new Error(`날씨 데이터 가져오기 실패: ${error.message}`);
      }
      throw new Error('날씨 데이터 가져오기 실패: 알 수 없는 오류가 발생했습니다');
    }
  }

  private getWeatherCondition(code: number): string {
    // WMO 날씨 해석 코드
    // 참고: https://open-meteo.com/en/docs
    const conditions: Record<number, string> = {
      0: "맑은 하늘",
      1: "주로 맑음",
      2: "부분적으로 흐림",
      3: "흐림",
      45: "안개",
      48: "서리안개",
      51: "가벼운 이슬비",
      53: "보통 이슬비",
      55: "강한 이슬비",
      61: "약한 비",
      63: "보통 비",
      65: "강한 비",
      71: "약한 눈",
      73: "보통 눈",
      75: "강한 눈",
      77: "눈 알갱이",
      80: "약한 소나기",
      81: "보통 소나기",
      82: "강한 소나기",
      85: "약한 눈소나기",
      86: "강한 눈소나기",
      95: "천둥번개",
      96: "약한 우박을 동반한 천둥번개",
      99: "강한 우박을 동반한 천둥번개"
    };
    
    return conditions[code] || "알 수 없음";
  }
}

export default WeatherApiTool;
```

#### 코드 설명

1. **Geocoding API**: 도시 이름을 위도/경도 좌표로 변환
2. **Weather API**: 좌표를 사용하여 실제 날씨 데이터 가져오기
3. **에러 처리**: try-catch로 API 오류 처리
4. **날씨 코드 변환**: WMO 표준 코드를 한글 설명으로 변환

#### 3단계: 재빌드 및 테스트

```bash
# 프로젝트 재빌드
npm run build

# Inspector로 테스트
npx @modelcontextprotocol/inspector node dist/index.js
```

## Claude Desktop과 통합

### 설정 방법

Claude Desktop에서 MCP 서버를 사용하려면 설정 파일을 수정해야 합니다.

#### macOS/Linux

`~/.config/claude/config.json`:

```json
{
  "mcpServers": {
    "weather": {
      "command": "node",
      "args": ["/absolute/path/to/my-mcp-server/dist/index.js"]
    }
  }
}
```

#### Windows

`%APPDATA%\Claude\config.json`:

```json
{
  "mcpServers": {
    "weather": {
      "command": "node",
      "args": ["C:\\absolute\\path\\to\\my-mcp-server\\dist\\index.js"]
    }
  }
}
```

## 베스트 프랙티스

### 1. 에러 처리

항상 적절한 에러 처리를 구현하세요:

```typescript
async execute(input: InputType) {
  try {
    // 로직 구현
  } catch (error) {
    if (error instanceof Error) {
      throw new Error(`작업 실패: ${error.message}`);
    }
    throw new Error('알 수 없는 오류가 발생했습니다');
  }
}
```

### 2. 입력 검증

Zod를 사용하여 입력을 엄격하게 검증:

```typescript
schema = {
  city: {
    type: z.string().min(1).max(100),
    description: "도시 이름",
  },
  country: {
    type: z.string().length(2).optional(),
    description: "국가 코드 (ISO 3166-1 alpha-2)",
  }
};
```

### 3. 로깅

개발 중 디버깅을 위한 로깅:

```typescript
async execute({ city }: WeatherInput) {
  console.log(`날씨 정보 요청: ${city}`);
  // ... 로직
  console.log(`날씨 정보 반환 완료`);
}
```

### 4. 환경 변수

API 키와 같은 민감한 정보는 환경 변수 사용:

```typescript
private readonly API_KEY = process.env.WEATHER_API_KEY;
```

`.env` 파일:

```
WEATHER_API_KEY=your_api_key_here
```

### 5. 타임아웃 설정

외부 API 호출 시 타임아웃 설정:

```typescript
const response = await axios.get(url, {
  params: {},
  timeout: 5000  // 5초
});
```

## 고급 기능

### 다중 도구 지원

하나의 MCP 서버에서 여러 도구를 제공할 수 있습니다:

```typescript
import { MCPServer } from "mcp-framework";
import WeatherTool from "./tools/WeatherTool";
import StockTool from "./tools/StockTool";
import NewsTools from "./tools/NewsTool";

const server = new MCPServer();

// 여러 도구 등록
server.registerTool(new WeatherTool());
server.registerTool(new StockTool());
server.registerTool(new NewsTool());

server.start();
```

### 리소스 제공

파일이나 데이터베이스 같은 리소스를 제공:

```typescript
import { MCPResource } from "mcp-framework";

class FileResource extends MCPResource {
  name = "files";
  description = "파일 시스템 접근";

  async list() {
    // 파일 목록 반환
  }

  async read(uri: string) {
    // 파일 내용 읽기
  }
}
```

### 프롬프트 템플릿

재사용 가능한 프롬프트 템플릿 제공:

```typescript
import { MCPPrompt } from "mcp-framework";

class WeatherPrompt extends MCPPrompt {
  name = "weather_report";
  description = "날씨 리포트 생성";

  async getPrompt(args: { city: string }) {
    return {
      messages: [
        {
          role: "user",
          content: `${args.city}의 날씨를 분석하고 리포트를 작성해주세요.`
        }
      ]
    };
  }
}
```

## 트러블슈팅

### 일반적인 문제와 해결책

#### 1. 서버가 시작되지 않음

**증상**: `npm start` 실행 시 오류 발생

**해결책**:
```bash
# 종속성 재설치
rm -rf node_modules package-lock.json
npm install

# TypeScript 재컴파일
npm run build
```

#### 2. Inspector에서 도구가 보이지 않음

**증상**: MCP Inspector에서 생성한 도구가 표시되지 않음

**해결책**:
- `src/index.ts`에서 도구가 제대로 등록되었는지 확인
- 빌드 후 `dist/` 폴더에 파일이 생성되었는지 확인
- 서버를 재시작

#### 3. API 호출 실패

**증상**: 외부 API 호출 시 오류 발생

**해결책**:
```typescript
// 더 자세한 에러 로깅
catch (error) {
  if (axios.isAxiosError(error)) {
    console.error('API 오류:', error.response?.data);
    console.error('상태 코드:', error.response?.status);
  }
  throw error;
}
```

#### 4. TypeScript 컴파일 오류

**증상**: `npm run build` 실행 시 타입 오류

**해결책**:
- `@types/*` 패키지 설치 확인
- `tsconfig.json` 설정 확인
- IDE에서 TypeScript 버전 확인

## 참고 자료

### 공식 문서

- **MCP 공식 문서**: https://modelcontextprotocol.io/
- **MCP Framework GitHub**: https://github.com/modelcontextprotocol/mcp-framework
- **MCP 스펙**: https://spec.modelcontextprotocol.io/

### API 참고

- **Open-Meteo API**: https://open-meteo.com/
  - 무료 날씨 API
  - API 키 불필요
  - WMO 표준 날씨 코드 사용

### 개발 도구

- **Apidog**: API 테스트 및 문서화 도구
  - 웹사이트: https://apidog.com/
  - MCP 개발 시 API 테스트에 유용

### 커뮤니티

- **MCP Discord**: 개발자 커뮤니티
- **GitHub Discussions**: 질문 및 토론

## 다음 단계

1. **더 많은 도구 추가**: 주식, 뉴스, 검색 등 다양한 도구 구현
2. **데이터베이스 연동**: PostgreSQL, MongoDB 등과 연결
3. **인증 추가**: API 키 기반 인증 구현
4. **배포**: Docker, Kubernetes로 프로덕션 배포
5. **모니터링**: 로깅 및 메트릭 수집

## 결론

MCP 서버 구축은 AI 워크플로우를 크게 향상시킬 수 있는 강력한 방법입니다. 이 가이드를 따라하면 기본적인 MCP 서버부터 실제 API와 연동된 도구까지 구현할 수 있습니다.

주요 포인트:
- **표준화**: MCP는 AI 통합을 위한 표준 프로토콜 제공
- **간편한 개발**: MCP Framework로 빠르게 시작
- **확장 가능**: 다양한 도구와 리소스 추가 가능
- **실전 적용**: Claude Desktop 등 실제 AI 앱과 통합 가능

---

**문서 버전**: 1.0  
**최종 수정일**: 2025-12-23  
**작성자**: LightRAG 팀

