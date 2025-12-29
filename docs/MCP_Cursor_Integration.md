# Cursor AI에서 MCP 서버 연동하기

> 참고: [Cursor 공식 문서 - MCP](https://docs.cursor.com/ko/context/mcp)

## 목차
- [개요](#개요)
- [사전 준비](#사전-준비)
- [Cursor에서 MCP 설정하기](#cursor에서-mcp-설정하기)
- [LightRAG MCP 서버 연동](#lightrag-mcp-서버-연동)
- [MCP 도구 사용하기](#mcp-도구-사용하기)
- [다양한 MCP 서버 예제](#다양한-mcp-서버-예제)
- [트러블슈팅](#트러블슈팅)

## 개요

### MCP(Model Context Protocol)란?

MCP는 AI 모델이 외부 도구 및 데이터 소스와 상호작용할 수 있도록 지원하는 **개방형 표준 프로토콜**입니다. Cursor AI에서 MCP를 활용하면 다양한 외부 서비스와 통합하여 AI의 기능을 확장할 수 있습니다.

### Cursor AI + MCP의 장점

- 🔌 **외부 도구 통합**: Notion, GitHub, 데이터베이스 등과 연결
- 📊 **실시간 데이터 접근**: API를 통한 최신 정보 조회
- 🤖 **자동화**: 반복 작업을 AI가 자동으로 수행
- 🎯 **컨텍스트 확장**: AI가 필요한 정보를 직접 가져올 수 있음

## 사전 준비

### 1. Node.js 설치 확인

MCP를 사용하려면 Node.js 20 이상이 필요합니다.

```bash
# Node.js 버전 확인
node --version

# npm 버전 확인
npm --version
```

**버전이 낮거나 설치되지 않은 경우:**

- **macOS**: `brew install node`
- **Linux**: `curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs`
- **Windows**: [nodejs.org](https://nodejs.org/)에서 다운로드

### 2. Python 설치 (Python 기반 MCP 서버 사용 시)

```bash
# Python 버전 확인 (3.8 이상 권장)
python --version

# 또는
python3 --version
```

### 3. Cursor 최신 버전 설치

MCP 기능을 사용하려면 Cursor의 최신 버전이 필요합니다.

- [Cursor 다운로드](https://cursor.com/)

## Cursor에서 MCP 설정하기

### 1단계: Cursor 설정 열기

1. Cursor를 실행합니다
2. 상단 메뉴에서 **톱니바퀴 아이콘(⚙️)** 을 클릭
3. 또는 단축키 사용:
   - **macOS**: `Cmd + ,`
   - **Windows/Linux**: `Ctrl + ,`

### 2단계: MCP 설정 페이지로 이동

1. 설정 창에서 **"Features"** 탭 선택
2. **"Tools & Integrations"** 섹션 찾기
3. **"Model Context Protocol (MCP)"** 섹션으로 스크롤

또는 설정 검색창에 `mcp`를 입력하여 바로 이동할 수 있습니다.

### 3단계: MCP 설정 파일 열기

1. **"Edit Configuration"** 또는 **"Add MCP Server"** 버튼 클릭
2. `mcp.json` 파일이 열립니다

**파일 위치:**
- **macOS/Linux**: `~/.cursor/mcp.json`
- **Windows**: `%APPDATA%\Cursor\User\mcp.json`

### 4단계: MCP 서버 설정 추가

`mcp.json` 파일에 MCP 서버 정보를 추가합니다.

#### 기본 구조

```json
{
  "mcpServers": {
    "서버이름": {
      "command": "실행할_명령어",
      "args": ["인자1", "인자2"],
      "env": {
        "환경변수명": "값"
      }
    }
  }
}
```

#### 예제: Node.js 기반 MCP 서버

```json
{
  "mcpServers": {
    "weather": {
      "command": "node",
      "args": ["/absolute/path/to/weather-server/dist/index.js"]
    }
  }
}
```

#### 예제: Python 기반 MCP 서버

```json
{
  "mcpServers": {
    "lightrag": {
      "command": "python",
      "args": ["/absolute/path/to/lightrag/mcp/server.py"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/lightrag"
      }
    }
  }
}
```

#### 예제: npx를 사용한 MCP 서버

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/allowed/directory"]
    }
  }
}
```

### 5단계: 설정 저장 및 Cursor 재시작

1. `mcp.json` 파일 저장 (`Cmd+S` / `Ctrl+S`)
2. Cursor 완전히 종료
3. Cursor 재시작

### 6단계: MCP 서버 상태 확인

1. Cursor 재시작 후 설정으로 돌아가기
2. **MCP 섹션**에서 추가한 서버의 상태 확인
3. 초록색 점 또는 "Connected" 표시가 나타나면 성공!

**상태 표시:**
- 🟢 **녹색**: 정상 연결됨
- 🔴 **빨간색**: 연결 실패
- 🟡 **노란색**: 연결 중

## LightRAG MCP 서버 연동

### LightRAG MCP 서버란?

이 프로젝트에 포함된 MCP 서버로, LightRAG의 RAG 쿼리 기능을 Cursor AI에서 직접 사용할 수 있게 합니다.

### 설정 방법

#### 1단계: LightRAG MCP 서버 설정

```bash
# MCP 서버 디렉토리로 이동
cd /nas/code/sungbeom/oi-LightRAG/mcp

# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# LightRAG 설치 (편집 가능 모드)
pip install -e ..

# MCP 서버 의존성 설치
pip install -r requirements.txt

# 환경 변수 파일 복사 및 설정
cp ../env.example .env
# .env 파일을 편집하여 LLM/Embedding 및 스토리지 설정
```

#### 2단계: `.env` 파일 설정

`/nas/code/sungbeom/oi-LightRAG/mcp/.env` 파일을 편집:

```bash
# LLM 설정
LIGHTRAG_LLM_MODEL=gpt-4
LIGHTRAG_LLM_API_KEY=your_openai_api_key

# Embedding 설정
LIGHTRAG_EMBEDDING_MODEL=text-embedding-3-small
LIGHTRAG_EMBEDDING_API_KEY=your_openai_api_key

# 스토리지 경로
WORKING_DIR=./rag_storage
```

#### 3단계: Cursor에 LightRAG MCP 추가

`~/.cursor/mcp.json` 파일에 다음 설정 추가:

```json
{
  "mcpServers": {
    "lightrag": {
      "command": "/nas/code/sungbeom/oi-LightRAG/mcp/.venv/bin/python",
      "args": ["/nas/code/sungbeom/oi-LightRAG/mcp/server.py"],
      "env": {
        "PYTHONPATH": "/nas/code/sungbeom/oi-LightRAG",
        "LIGHTRAG_ENV_PATH": "/nas/code/sungbeom/oi-LightRAG/mcp/.env"
      }
    }
  }
}
```

**주의사항:**
- 절대 경로 사용 필수
- Python 가상환경의 Python 경로 지정
- `LIGHTRAG_ENV_PATH`로 `.env` 파일 위치 명시

#### 4단계: 테스트

먼저 MCP Inspector로 테스트:

```bash
cd /nas/code/sungbeom/oi-LightRAG/mcp
source .venv/bin/activate
npx @modelcontextprotocol/inspector python server.py
```

정상 작동하면 Cursor를 재시작하고 사용합니다.

### LightRAG MCP 도구 사용

#### 1. `rag_query` 도구

RAG 쿼리를 실행하고 응답과 참조를 반환합니다.

**Cursor Chat에서 사용:**

```
@lightrag What is LightRAG?
```

또는 명시적으로:

```
Use the rag_query tool to search for "What is LightRAG?" with mode "mix"
```

**입력 파라미터:**

```json
{
  "query": "What is LightRAG?",
  "mode": "mix",
  "include_references": true
}
```

**반환 예시:**

```json
{
  "response": "LightRAG is an advanced RAG framework...",
  "references": [
    {"source": "doc1.txt", "content": "..."},
    {"source": "doc2.txt", "content": "..."}
  ]
}
```

#### 2. `rag_query_data` 도구

구조화된 검색 데이터를 반환합니다.

**사용 예:**

```
Use rag_query_data to get entities and relations for "LightRAG architecture"
```

**반환 예시:**

```json
{
  "entities": ["LightRAG", "Graph", "RAG"],
  "relations": [
    {"source": "LightRAG", "target": "Graph", "type": "uses"}
  ],
  "chunks": [...]
}
```

## MCP 도구 사용하기

### Cursor Chat에서 MCP 호출하기

#### 방법 1: @ 멘션 사용

가장 간단한 방법:

```
@서버이름 명령어
```

**예제:**

```
@lightrag LightRAG의 주요 기능은 무엇인가요?

@notion 오늘 할 일 목록을 보여줘

@github 최근 커밋 내역 조회
```

#### 방법 2: 명시적 도구 호출

더 정확한 제어가 필요한 경우:

```
Use the [tool_name] tool from [server_name] to [action]
```

**예제:**

```
Use the rag_query tool from lightrag to search for "graph-based RAG" with mode "hybrid"

Use the create_page tool from notion to create a new page with title "Meeting Notes"
```

#### 방법 3: 자연어로 요청

Cursor AI가 자동으로 적절한 MCP 도구를 선택:

```
LightRAG 문서에서 설치 방법을 찾아줘

내 Notion에서 "프로젝트" 페이지를 찾아서 내용을 요약해줘
```

### MCP 도구 확인하기

Cursor Chat에서 사용 가능한 MCP 도구 목록 확인:

```
@를 입력하면 자동 완성으로 사용 가능한 MCP 서버 목록이 표시됩니다
```

또는:

```
Show me all available MCP tools
```

## 다양한 MCP 서버 예제

### 1. Filesystem 서버 (파일 시스템 접근)

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/path/to/allowed/directory"
      ]
    }
  }
}
```

**사용 예:**

```
@filesystem Read the contents of config.json

@filesystem List all Python files in the src directory
```

### 2. GitHub 서버

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "your_github_token"
      }
    }
  }
}
```

**사용 예:**

```
@github Show me recent issues in the repository

@github Create a new issue with title "Bug: Login fails"
```

### 3. Notion 서버

```json
{
  "mcpServers": {
    "notion": {
      "command": "npx",
      "args": ["-y", "notion-mcp"],
      "env": {
        "NOTION_API_KEY": "your_notion_api_key"
      }
    }
  }
}
```

**사용 예:**

```
@notion Search for pages with "meeting" in the title

@notion Create a new database entry for today's tasks
```

### 4. Brave Search 서버 (웹 검색)

```json
{
  "mcpServers": {
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {
        "BRAVE_API_KEY": "your_brave_api_key"
      }
    }
  }
}
```

**사용 예:**

```
@brave-search Search for "MCP protocol documentation"

@brave-search Find recent news about AI developments
```

### 5. PostgreSQL 서버

```json
{
  "mcpServers": {
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres"],
      "env": {
        "POSTGRES_CONNECTION_STRING": "postgresql://user:pass@localhost:5432/dbname"
      }
    }
  }
}
```

**사용 예:**

```
@postgres Show me all tables in the database

@postgres Query users table for active users
```

### 6. 커스텀 날씨 서버

앞서 작성한 날씨 MCP 서버 사용:

```json
{
  "mcpServers": {
    "weather": {
      "command": "node",
      "args": ["/path/to/weather-server/dist/index.js"]
    }
  }
}
```

**사용 예:**

```
@weather Get current weather for Seoul

@weather What's the temperature in New York?
```

## 복잡한 설정 예제

### 여러 MCP 서버 동시 사용

```json
{
  "mcpServers": {
    "lightrag": {
      "command": "/nas/code/sungbeom/oi-LightRAG/mcp/.venv/bin/python",
      "args": ["/nas/code/sungbeom/oi-LightRAG/mcp/server.py"],
      "env": {
        "PYTHONPATH": "/nas/code/sungbeom/oi-LightRAG",
        "LIGHTRAG_ENV_PATH": "/nas/code/sungbeom/oi-LightRAG/mcp/.env"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/nas/code/sungbeom/oi-LightRAG"
      ]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "ghp_xxxxxxxxxxxxx"
      }
    },
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {
        "BRAVE_API_KEY": "BSA_xxxxxxxxxxxxx"
      }
    }
  }
}
```

### 환경별 설정 분리

개발/프로덕션 환경을 분리할 수 있습니다:

**개발 환경** (`~/.cursor/mcp.dev.json`):

```json
{
  "mcpServers": {
    "lightrag-dev": {
      "command": "python",
      "args": ["/path/to/dev/lightrag/mcp/server.py"],
      "env": {
        "LIGHTRAG_ENV_PATH": "/path/to/dev/.env.dev"
      }
    }
  }
}
```

**프로덕션 환경** (`~/.cursor/mcp.prod.json`):

```json
{
  "mcpServers": {
    "lightrag-prod": {
      "command": "python",
      "args": ["/path/to/prod/lightrag/mcp/server.py"],
      "env": {
        "LIGHTRAG_ENV_PATH": "/path/to/prod/.env.prod"
      }
    }
  }
}
```

## 실전 사용 시나리오

### 시나리오 1: LightRAG 문서 검색하며 코드 작성

```
@lightrag LightRAG에서 그래프 기반 검색을 구현하는 방법은?

# AI가 LightRAG 문서에서 관련 정보를 가져옴

이제 이 정보를 바탕으로 search_graph 함수를 작성해줘
```

### 시나리오 2: GitHub 이슈 생성 자동화

```
@github 최근 커밋에서 TODO 주석을 찾아서 이슈로 만들어줘

@filesystem src/ 디렉토리에서 TODO 주석이 있는 파일들을 찾아줘

# AI가 TODO를 찾고 GitHub 이슈를 자동 생성
```

### 시나리오 3: Notion과 코드 동기화

```
@notion "API 설계" 페이지의 내용을 가져와서

@filesystem docs/api-design.md 파일로 변환해서 저장해줘
```

### 시나리오 4: 웹 검색 + LightRAG

```
@brave-search MCP 프로토콜의 최신 업데이트 검색

# 검색 결과를 LightRAG에 추가
@lightrag Add this information to the knowledge base

# 나중에 다시 조회
@lightrag What are the recent updates to MCP protocol?
```

## 트러블슈팅

### 문제 1: MCP 서버가 연결되지 않음 (빨간색 상태)

**증상:**
- Cursor 설정에서 MCP 서버 상태가 빨간색
- "Connection failed" 메시지

**해결 방법:**

1. **경로 확인**
   ```bash
   # 절대 경로인지 확인
   which python  # Python 경로
   which node    # Node.js 경로
   ```

2. **실행 권한 확인**
   ```bash
   # 실행 파일에 권한 부여
   chmod +x /path/to/server.py
   chmod +x /path/to/dist/index.js
   ```

3. **직접 실행 테스트**
   ```bash
   # MCP 서버를 직접 실행해보기
   python /path/to/server.py
   node /path/to/dist/index.js
   ```

4. **환경 변수 확인**
   ```json
   {
     "mcpServers": {
       "test": {
         "command": "python",
         "args": ["-u", "/path/to/server.py"],
         "env": {
           "PYTHONUNBUFFERED": "1",
           "PYTHONPATH": "/path/to/project"
         }
       }
     }
   }
   ```

### 문제 2: MCP Inspector에서는 작동하지만 Cursor에서 안됨

**증상:**
- `npx @modelcontextprotocol/inspector`로는 정상 작동
- Cursor에서는 도구를 찾을 수 없음

**해결 방법:**

1. **Cursor 로그 확인**
   - **macOS**: `~/Library/Logs/Cursor/`
   - **Linux**: `~/.config/Cursor/logs/`
   - **Windows**: `%APPDATA%\Cursor\logs\`

2. **절대 경로 사용**
   ```json
   {
     "mcpServers": {
       "server": {
         "command": "/usr/local/bin/python",  // which python의 결과
         "args": ["/absolute/path/to/server.py"]
       }
     }
   }
   ```

3. **Cursor 완전히 재시작**
   ```bash
   # macOS/Linux
   killall Cursor
   
   # Windows (관리자 권한 PowerShell)
   Get-Process Cursor | Stop-Process -Force
   ```

### 문제 3: 환경 변수가 로드되지 않음

**증상:**
- API 키 관련 오류
- "환경 변수를 찾을 수 없음" 메시지

**해결 방법:**

1. **mcp.json에서 환경 변수 명시적으로 설정**
   ```json
   {
     "mcpServers": {
       "server": {
         "command": "python",
         "args": ["/path/to/server.py"],
         "env": {
           "API_KEY": "your_api_key_here",
           "ENV_FILE": "/path/to/.env"
         }
       }
     }
   }
   ```

2. **환경 변수 파일 경로 확인**
   ```bash
   # .env 파일이 존재하는지 확인
   ls -la /path/to/.env
   cat /path/to/.env
   ```

3. **절대 경로로 .env 파일 지정**
   ```python
   # server.py에서
   from dotenv import load_dotenv
   import os
   
   env_path = os.getenv('ENV_FILE', '/absolute/path/to/.env')
   load_dotenv(env_path)
   ```

### 문제 4: Python 가상환경 문제

**증상:**
- "ModuleNotFoundError" 오류
- 필요한 패키지를 찾을 수 없음

**해결 방법:**

1. **가상환경의 Python 경로 사용**
   ```json
   {
     "mcpServers": {
       "server": {
         "command": "/path/to/venv/bin/python",  // 가상환경의 Python
         "args": ["/path/to/server.py"]
       }
     }
   }
   ```

2. **PYTHONPATH 설정**
   ```json
   {
     "mcpServers": {
       "server": {
         "command": "/path/to/venv/bin/python",
         "args": ["/path/to/server.py"],
         "env": {
           "PYTHONPATH": "/path/to/project:/path/to/dependencies"
         }
       }
     }
   }
   ```

3. **의존성 재설치**
   ```bash
   cd /path/to/mcp
   source .venv/bin/activate
   pip install --upgrade -r requirements.txt
   ```

### 문제 5: stdio vs SSE 혼동

**증상:**
- "Parse error" 메시지
- 터미널에서 직접 실행 시 JSON 오류

**해결:**

**stdio 모드 (기본):**
- Cursor나 MCP 클라이언트를 통해 실행
- 터미널에서 직접 실행하면 안됨

```bash
# ❌ 직접 실행하면 안됨
python server.py

# ✅ Inspector를 통해 실행
npx @modelcontextprotocol/inspector python server.py
```

**SSE 모드:**
- HTTP 서버로 실행 가능
- 외부에서 접근 가능

```bash
# ✅ SSE 모드로 실행
MCP_TRANSPORT=sse python server.py

# 다른 터미널에서 Inspector 연결
npx @modelcontextprotocol/inspector http://localhost:8000/sse
```

### 문제 6: Windows에서 경로 문제

**증상:**
- Windows에서 백슬래시(`\`) 경로 오류

**해결:**

```json
{
  "mcpServers": {
    "server": {
      "command": "python",
      "args": ["C:\\Users\\Username\\project\\server.py"],  // 이스케이프 또는
      "args": ["C:/Users/Username/project/server.py"]       // 슬래시 사용
    }
  }
}
```

### 문제 7: 여러 MCP 서버 중 하나만 작동

**증상:**
- 일부 MCP 서버는 작동하지만 다른 서버는 안됨

**해결:**

1. **각 서버를 개별적으로 테스트**
   ```bash
   # 서버1 테스트
   npx @modelcontextprotocol/inspector python server1.py
   
   # 서버2 테스트
   npx @modelcontextprotocol/inspector python server2.py
   ```

2. **포트 충돌 확인 (SSE 모드)**
   ```bash
   # 포트 사용 확인
   lsof -i :8000
   netstat -an | grep 8000
   ```

3. **로그를 통해 에러 확인**
   ```json
   {
     "mcpServers": {
       "server": {
         "command": "python",
         "args": ["-u", "server.py"],  // unbuffered output
         "env": {
           "PYTHONUNBUFFERED": "1",
           "LOG_LEVEL": "DEBUG"
         }
       }
     }
   }
   ```

## 디버깅 팁

### 1. 상세 로깅 활성화

MCP 서버에 로깅 추가:

```python
import logging
import sys

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/mcp_server.log'),
        logging.StreamHandler(sys.stderr)
    ]
)

logger = logging.getLogger(__name__)
logger.info("MCP 서버 시작됨")
```

### 2. MCP Inspector 활용

```bash
# 상세 모드로 실행
DEBUG=* npx @modelcontextprotocol/inspector python server.py

# 특정 로그만 표시
DEBUG=mcp:* npx @modelcontextprotocol/inspector python server.py
```

### 3. Cursor 개발자 도구

1. Cursor에서 `Cmd+Option+I` (macOS) 또는 `Ctrl+Shift+I` (Windows/Linux)
2. Console 탭에서 MCP 관련 로그 확인

### 4. 연결 테스트 스크립트

```python
# test_mcp.py
import sys
import json

def test_connection():
    """MCP 서버 연결 테스트"""
    try:
        # 기본 설정 출력
        print(json.dumps({
            "python_version": sys.version,
            "python_path": sys.executable,
            "working_directory": os.getcwd()
        }), file=sys.stderr)
        
        # MCP 서버 시작 로직...
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    test_connection()
```

## 보안 고려사항

### 1. API 키 관리

```json
{
  "mcpServers": {
    "server": {
      "command": "python",
      "args": ["server.py"],
      "env": {
        "API_KEY_FILE": "/secure/path/to/api_keys.json"
      }
    }
  }
}
```

**api_keys.json:**
```json
{
  "openai": "sk-...",
  "github": "ghp_...",
  "notion": "secret_..."
}
```

파일 권한 설정:
```bash
chmod 600 /secure/path/to/api_keys.json
```

### 2. 파일 시스템 접근 제한

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/allowed/directory/only"  // 특정 디렉토리만 접근 허용
      ]
    }
  }
}
```

### 3. 네트워크 접근 제한 (SSE 모드)

```bash
# localhost만 허용
MCP_HOST=127.0.0.1 MCP_PORT=8000 python server.py

# 특정 IP만 허용
# server.py에서 IP 화이트리스트 구현
```

## 성능 최적화

### 1. MCP 서버 캐싱

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def expensive_query(query: str):
    """캐시된 쿼리 결과"""
    return perform_search(query)
```

### 2. 비동기 처리

```python
import asyncio

async def handle_request(request):
    """비동기로 요청 처리"""
    results = await asyncio.gather(
        fetch_data_source1(request),
        fetch_data_source2(request)
    )
    return combine_results(results)
```

### 3. 연결 풀링

```python
# PostgreSQL 예제
from psycopg2.pool import SimpleConnectionPool

pool = SimpleConnectionPool(1, 20, dsn=connection_string)
```

## 참고 자료

### 공식 문서

- **Cursor MCP 문서**: https://docs.cursor.com/ko/context/mcp
- **MCP 스펙**: https://spec.modelcontextprotocol.io/
- **MCP GitHub**: https://github.com/modelcontextprotocol

### MCP 서버 목록

- **Smithery.ai**: https://smithery.ai/
  - 다양한 MCP 서버 목록 및 설정 예제
- **Awesome MCP Servers**: https://github.com/punkpeye/awesome-mcp-servers
  - 커뮤니티 기여 MCP 서버 목록

### 관련 도구

- **MCP Inspector**: `@modelcontextprotocol/inspector`
  - MCP 서버 테스트 및 디버깅
- **MCP Framework**: `mcp-framework`
  - MCP 서버 개발 프레임워크

## 다음 단계

1. **간단한 MCP 서버부터 시작**: Filesystem이나 날씨 같은 간단한 서버로 시작
2. **LightRAG MCP 활용**: 프로젝트의 RAG 기능을 Cursor에서 직접 사용
3. **커스텀 MCP 서버 개발**: 프로젝트에 특화된 도구 개발
4. **여러 MCP 서버 조합**: 복잡한 워크플로우 자동화
5. **팀과 공유**: 유용한 MCP 설정을 팀원들과 공유

---

**문서 버전**: 1.0  
**최종 수정일**: 2025-12-23  
**작성자**: LightRAG 팀

