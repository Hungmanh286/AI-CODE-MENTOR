# Kế hoạch triển khai AG-UI MVP cho Mentor Code (dành cho sub-agent)

> **Người đọc:** orchestrator (phiên Claude chính) và các sub-agent A–F.
> **Nguyên tắc tối thượng:** chính xác và ổn định. Kế hoạch này **không có deadline**. Không được bỏ qua một tiêu chí hay lách một cổng kiểm tra để "xong cho nhanh".
> **Repo:** `/home/hungmanh/Documents/mentor-code-ui`. Nhánh làm việc: `feat/agui-mvp`, tách từ `dev`.

---

## 0. Mục tiêu và phạm vi

**Mục tiêu:** frontend chat được qua giao thức AG-UI (dùng assistant-ui), chạy với một mock agent server bám đúng hợp đồng, và render ổn định các UI do agent sinh ra: quiz, khối UI khai báo, trích dẫn, mindmap, form xác nhận, state của Studio. Phần backend thật được giao dưới dạng một bộ khung tham chiếu Python kèm contract test, để người dùng tự port sang repo backend.

### Definition of Done (bắt buộc đạt đủ)

| # | Tiêu chí | Kiểm bằng |
| --- | --- | --- |
| M1 | Build thành công | `npx vite build` exit 0 |
| M2 | Không thêm lỗi lint nào so với baseline | `npx eslint .` có số problem không vượt `BASELINE.md`, trong khi mọi file mới đều 0 lỗi |
| M3 | Contract test pass toàn bộ kịch bản (kể cả lỗi và resume) | `node scripts/agui-smoke.mjs` exit 0 |
| M4 | Toàn bộ checklist E2E trên trình duyệt đạt | Mục 7.3, có ảnh chụp màn hình |
| M5 | Khi `VITE_USE_AGUI` tắt, luồng chat cũ (WebSocket) không bị hồi quy | Mục 7.3, phần hồi quy |
| M6 | Không thêm lỗi console nào so với baseline | Console trình duyệt trong lúc chạy E2E |
| M7 | Bộ khung backend compile được, README đủ để port | `python3 -m py_compile backend-reference/agent/*.py`, kèm review README |
| M8 | Review độc lập không còn lỗi đã xác nhận nào chưa xử lý | Mục 8 |

### Ngoài phạm vi (để thay đổi nhỏ, dễ review, ít rủi ro)

Tích hợp backend thật (nằm ở repo khác), thread list adapter, JWT, `npx assistant-ui init` (registry TSX cùng Tailwind v4), chuyển sang TypeScript, frontend tool `highlight_source`, A2UI, layout mobile.

### Quyết định đã chốt (kèm lý do)

| Quyết định | Lý do |
| --- | --- |
| Dựng UI bằng **primitives** của `@assistant-ui/react` và style bằng Tailwind v3 sẵn có | Registry `init` sinh ra file TSX và có thể buộc lên Tailwind v4. Như vậy là đụng tới toàn bộ UI cũ. |
| Đăng ký Tool UI bằng **plain toolkit**: `defineToolkit({ tên: { type: "backend", render } })`, mount qua `AuiConfig({ tools: Tools({ toolkit }) })` | Đây là API hiện hành, không deprecated, và **không cần** compiler `"use generative"` (xem `.claude/skills/tools/references/toolkits.md`, mục "Plain toolkits without the compiler"). Không dùng `makeAssistantToolUI` (đã deprecated). |
| Dữ liệu UI đi qua **tool call**, không đi qua `CUSTOM` hay data part | Tool call được lưu cùng lịch sử (`fromAgUiMessages` dựng lại được), còn data part chỉ tồn tại phía client và bị reset sau mỗi run. LangGraph cũng tự phát tool call. |
| Mock server viết bằng **Node thuần** (`node:http`) | Máy chưa có `fastapi`. Mock chỉ phục vụ phát triển frontend; contract test đảm bảo nó bám hợp đồng. |
| Chỉ dùng **npm**, ghim **phiên bản chính xác** (`--save-exact`) | Repo đang theo dõi `package-lock.json`. Ghim chính xác tránh trôi phiên bản giữa các lần cài. |
| Markdown dùng **`react-markdown` sẵn có** (remark-gfm, remark-math, rehype-katex) | Đây là thư viện đang dùng, đã chạy ổn với KaTeX, và không thêm dependency. |
| Mock và contract test do **hai agent khác nhau** viết | Mỗi bên đọc hợp đồng độc lập, nên chỗ nào một bên hiểu sai sẽ lộ ra khi chạy test. |

---

## 1. Luật chung cho mọi agent (bắt buộc)

1. **Không đoán API.** Nguồn sự thật xếp theo thứ tự ưu tiên:
   1. `docs/agui/status/API.md` (do Agent A xác minh ở Đợt 1).
   2. Typings trong `node_modules/@assistant-ui/*/dist/**/*.d.ts` và `node_modules/@ag-ui/client/dist/*.d.ts`.
   3. Skill tham chiếu trong repo, đọc trực tiếp bằng Read:

      | Chủ đề | File |
      | --- | --- |
      | AG-UI runtime | `.claude/skills/setup/references/ag-ui.md` |
      | Tool UI | `.claude/skills/tools/SKILL.md`, `tools/references/toolkits.md`, `tools/references/tool-ui.md` |
      | Primitives | `.claude/skills/primitives/references/{thread,message,composer}.md` |
      | Hook trạng thái | `.claude/skills/runtime/references/state-hooks.md` |

   4. `https://www.assistant-ui.com/llms.txt`.

   Nếu đã tra hết mà vẫn không chắc, ghi `BLOCKED` vào status, kèm những gì đã tra và hai phương án. **Không bịa.**
2. **Chỉ sửa file mình sở hữu** (mục 3.2). Cần đụng file của agent khác thì ghi yêu cầu vào status để orchestrator xử lý.
3. **Code đúng hợp đồng ở mục 4.** Thấy hợp đồng sai hoặc thiếu thì không tự đổi; ghi `CONTRACT_ISSUE` vào status để orchestrator quyết định và cập nhật file này.
4. **Chỉ Agent A được chạy `npm install` / `npm uninstall`** và sửa `package.json`.
5. **Báo cáo trung thực.** Chỉ ghi `DONE` sau khi đã chạy lệnh tự kiểm tra, và phải dán output thật (rút gọn). Việc nào chưa làm hoặc làm không được thì ghi rõ, không che giấu.
6. **Ổn định trước, đẹp sau.** Mọi renderer phải chịu được args rỗng hoặc mới stream một phần mà không crash. Mọi lệnh gọi mạng đều phải xử lý lỗi. Không để `console.log` gỡ lỗi sót lại trong code mới.
7. **Không** commit, push, refactor ngoài phạm vi, hay để process chạy treo (server phải chạy nền kèm `timeout` hoặc kill khi xong).
8. **Status file** `docs/agui/status/<X>.md` chỉ được nối thêm dòng:
   ```
   - STARTED
   - DONE A1 | verify: npm ls ... OK
   - BLOCKED A4: <vấn đề> | đã tra: <file> | phương án: (1)… (2)…
   - CONTRACT_ISSUE: <mô tả>
   - FINAL done=[…] not_done=[… + lý do] files=[…] verify="<lệnh + kết quả>" notes="…"
   ```
9. **Ngôn ngữ:** text hiển thị trên UI viết bằng tiếng Việt, code và identifier viết bằng tiếng Anh. Style theo design token ở mục 4.9.

---

## 2. Các đợt và cổng kiểm tra

Muốn sang đợt sau phải **qua cổng** của đợt trước. Cổng chưa đạt thì orchestrator sửa, hoặc giao lại cho đúng agent, rồi kiểm lại cổng đó.

```
Đợt 0 (orchestrator) ─► Đợt 1: A · C1 · D · E1 · F (song song) ─► CỔNG 1
   ─► Đợt 2: B · C2 · E2 (song song) ─► CỔNG 2 ─► Đợt 3: E2E ─► CỔNG 3
   ─► Đợt 4: review độc lập + sửa ─► chạy lại CỔNG 2–3 ─► Đợt 5: báo cáo
```

| Đợt | Ai | Việc | Cổng ra |
| --- | --- | --- | --- |
| 0 | Orchestrator | Mục 7.1: tạo nhánh, thư mục status, ghi baseline | Đã có `BASELINE.md` |
| 1 | A, C1, D, E1, F | Những phần **không phụ thuộc lẫn nhau**: nền tảng và xác minh API (A), component trình bày thuần (C1), mock (D), contract test (E1), backend tham chiếu (F) | **Cổng 1** (mục 7.2) |
| 2 | B, C2, E2 | Những phần **cần API đã xác minh và mock đang chạy**: Thread (B), đăng ký toolkit (C2), state Studio (E2) | **Cổng 2** (mục 7.2) |
| 3 | Orchestrator | Chạy E2E trên trình duyệt (mục 7.3) | **Cổng 3** |
| 4 | Reviewer độc lập, rồi đến orchestrator | Mục 8 | Không còn lỗi đã xác nhận; Cổng 2–3 vẫn pass |
| 5 | Orchestrator | Báo cáo (mục 7.4) | — |

C2 và E2 là **phần tiếp theo của chính agent C và E**. Orchestrator dùng `SendMessage` gửi tiếp cho agent cũ để giữ nguyên ngữ cảnh, không khởi chạy agent mới.

---

## 3. Vai trò và quyền sở hữu file

### 3.1 Vai trò

| Agent | Đợt | Vai trò |
| --- | --- | --- |
| **A** | 1 | Cài và gỡ dependency, config, gỡ CopilotKit, **xác minh API rồi ghi `API.md`**, runtime provider, history adapter, đổi URL |
| **B** | 2 | Thread (primitives), MarkdownText, chip chọn tool, InterruptPanel, gắn vào SessionPage sau feature flag |
| **C** | 1 → 2 | C1: QuizCard, catalog block, MindmapView, SourceCitation, FollowUps, ToolFallback, ToolErrorBoundary. C2: `toolkit.jsx` |
| **D** | 1 | Mock AG-UI server và các kịch bản |
| **E** | 1 → 2 | E1: contract test `scripts/agui-smoke.mjs`. E2: `useMentorState`, StudioAgentArtifacts, chèn vào StudioDashboard |
| **F** | 1 | Backend tham chiếu Python và README hướng dẫn port |
| **R** | 4 | Reviewer độc lập: agent mới, **không đọc kế hoạch này trước khi review code** |

### 3.2 Quyền sở hữu file (mỗi file chỉ có một chủ)

| Agent | File |
| --- | --- |
| A | `package.json`, `package-lock.json`, `.env.sample`, `src/config.js` (mới), `src/main.jsx`, `src/copilot.config.js` (xóa), `src/agent/MentorRuntimeProvider.jsx` (mới), `src/agent/adapters/historyAdapter.js` (mới), `src/contexts/AuthContext.jsx`, `src/components/Chatbot.jsx`, `src/components/SourcePanel.jsx`, `src/pages/*.jsx` **trừ** `SessionPage.jsx`, `docs/agui/status/API.md` |
| B | `src/agent/thread/{Thread,MarkdownText,ToolChips,Reasoning}.jsx`, `src/agent/tools/InterruptPanel.jsx`, `src/components/AgentChat.jsx`, `src/pages/SessionPage.jsx` |
| C | `src/agent/toolkit.jsx`, `src/agent/tools/{QuizCard,MindmapView,SourceCitation,FollowUps,ToolFallback,ToolErrorBoundary}.jsx`, `src/agent/catalog/*.jsx`, `src/agent/fixtures.js` |
| D | `mock-agent/**` |
| E | `scripts/agui-smoke.mjs`, `src/agent/state/{useMentorState.js,StudioAgentArtifacts.jsx}`, `src/components/StudioDashboard.jsx` (chỉ chèn một khối và đổi URL) |
| F | `backend-reference/**` |

---

## 4. Hợp đồng (mọi agent code theo đúng mục này)

### 4.1 Config: `src/config.js` (A viết)

```js
export const API_URL    = import.meta.env.VITE_API_URL   ?? "http://0.0.0.0:8686";        // REST cũ
export const AGENT_URL  = import.meta.env.VITE_AGENT_URL ?? "http://localhost:8787/agent"; // AG-UI
export const AGENT_BASE = AGENT_URL.replace(/\/agent\/?$/, "");                            // cho /threads/...
export const USE_AGUI   = import.meta.env.VITE_USE_AGUI === "true";
```

### 4.2 Giao diện module giữa các agent

| Export | File (chủ) | Chữ ký / hành vi | Dùng bởi |
| --- | --- | --- | --- |
| `default MentorRuntimeProvider` | `src/agent/MentorRuntimeProvider.jsx` (A) | `({ threadId, getExtraContext, children })`. `getExtraContext?: () => Context[]`. Bên trong tạo `HttpAgent` và `useAgUiRuntime`, rồi render `<AssistantRuntimeProvider runtime config={auiConfig}>`, trong đó `auiConfig` được tạo từ `mentorToolkit` | B |
| `mentorToolkit` | `src/agent/toolkit.jsx` (C) | Export mức module, tham chiếu ổn định: `defineToolkit({...})` gồm 5 tool ở mục 4.5, mỗi `render` đều được bọc trong `ToolErrorBoundary` | A |
| `default ToolFallback` | `src/agent/tools/ToolFallback.jsx` (C) | Nhận `ToolCallMessagePartProps` | B (nhánh `part.toolUI ?? <ToolFallback {...part}/>`) |
| `default ToolErrorBoundary` | `src/agent/tools/ToolErrorBoundary.jsx` (C) | `({ toolName, children })`. Khi lỗi, hiện card "Không hiển thị được nội dung này" kèm tên tool, không làm sập cả thread | C |
| `default InterruptPanel` | `src/agent/tools/InterruptPanel.jsx` (B) | Không có props. Đọc `useAgUiInterrupts()` | B |
| `default MarkdownText` | `src/agent/thread/MarkdownText.jsx` (B) | `({ text })` | B, C (cho các field `*_md`) |
| `useMentorState` | `src/agent/state/useMentorState.js` (E) | `() => ({ artifacts: { quizzes, mindmaps }, jobs })`, luôn có giá trị mặc định | E |
| `default StudioAgentArtifacts` | `src/agent/state/StudioAgentArtifacts.jsx` (E) | Không có props | E |
| `FIXTURES` | `src/agent/fixtures.js` (C) | Args mẫu cho 5 tool, gồm cả bản đầy đủ và bản đang stream dở | C (tự kiểm tra) |

**Ràng buộc runtime:** hook `useAgUi*`, `useAui*`, `AuiIf` và mọi primitive chỉ được dùng **bên trong** `MentorRuntimeProvider`. Khi `USE_AGUI` bật, `SessionPage` (B) bọc **cả layout 3 cột** trong provider. Khi flag tắt, không render bất kỳ thành phần AG-UI nào.

### 4.3 Endpoint của agent (mock bây giờ, backend thật sau này)

- `POST {AGENT_URL}`: body là `RunAgentInput` dạng camelCase (`threadId`, `runId`, `state`, `messages`, `tools`, `context`, `forwardedProps`, `resume?`), response là `text/event-stream`, mỗi dòng `data:` chứa đúng một event JSON, kết thúc bằng `\n\n`.
- `GET {AGENT_BASE}/threads/:threadId/messages` → `{ "messages": AgUiMessage[] }`. Phải gồm cả assistant `toolCalls` (`{id, type:"function", function:{name, arguments}}`, với `arguments` là JSON string) lẫn message `role:"tool"` (`toolCallId`, `content`). Thread chưa có gì thì trả về `{ "messages": [] }`, không trả 404.
- `GET {AGENT_BASE}/health` → `{ "ok": true }`
- CORS: `Access-Control-Allow-Origin: *`, các header `content-type, authorization, accept`, preflight `OPTIONS` trả 204.
- `threadId` = `sessionId` trên URL. Phiên mới thì dùng `crypto.randomUUID()`, tạo một lần mỗi lần mount trang.

### 4.4 Context gửi lên

`getRunContext` trả về `Context[]`, trong đó `value` **luôn là string**.

| `description` | `value` (JSON string) | Nguồn |
| --- | --- | --- |
| `"user"` | `{"user_id":…,"user_name":…}` | A (`useAuth().user`) |
| `"requested_tools"` | `["generate-questions" \| "mindmap", …]` | B (chip ở composer). Chữa lỗi cũ: trước đây tool đã chọn không được gửi lên backend |
| `"active_document_ids"` | `[]` (để phase sau) | B |

### 4.5 Tool do backend thực thi, frontend chỉ render

Trong lúc `status.type === "running"`, `args` có thể **chưa đầy đủ**. Mọi renderer phải dùng `?.`, đặt giá trị mặc định, hiện skeleton, và **không được ném lỗi**.

```ts
show_quiz:         { title: string, questions: Array<{ id: string, question: string, options: string[],
                     answer_index: number, explanation: string, difficulty: "easy"|"medium"|"hard" }> }
show_mindmap:      { title: string, root: Node }   // Node = { id: string, label: string, children?: Node[] }
cite_sources:      { sources: Array<{ file_id: string, file_name: string, page?: number, quote: string }> }
suggest_followups: { questions: string[] }
present_ui:        { title?: string, blocks: Block[] }
```

`Block` là union phân biệt theo field `type`:

```ts
{ type: "callout",          tone: "info"|"tip"|"warning", title: string, body_md: string }
{ type: "steps",            items: Array<{ title: string, body_md: string }> }
{ type: "comparison_table", columns: string[], rows: string[][], highlight_col?: number }
{ type: "code_diff",        language: string, before: string, after: string, explanation_md: string }
{ type: "concept_card",     term: string, definition_md: string, example_code?: string, language?: string }
```

Gặp `type` lạ thì render khung "Không hỗ trợ khối này" và vẫn hiện các block còn lại. Kết quả `TOOL_CALL_RESULT.content` của các tool này là `"ok"`; frontend không phụ thuộc vào giá trị này.

### 4.6 Interrupt `quiz_config` (human-in-the-loop)

Trước interrupt **luôn có một assistant text message**: runtime cần một message đang hoạt động để chuyển nó sang `requires-action`.

```json
{"type":"RUN_FINISHED","threadId":"…","runId":"…","outcome":{"type":"interrupt","interrupts":[{
  "id":"int_…","reason":"input_required","message":"Sinh câu hỏi từ tài liệu đang bật?",
  "metadata":{"kind":"quiz_config","defaults":{"count":10,"difficulty":"medium"},"documents":[]}}]}}
```

Frontend trả lời bằng `useAgUiSubmitInterruptResponses()(entries)`, trong đó `entries` phải **phủ hết** các interrupt đang mở: `{ interruptId, status: "resolved", payload: { count, difficulty } }`, hoặc `status: "cancelled"`. Run tiếp theo mang `resume: [...]` trong body. Nếu người dùng bỏ qua form và gõ câu khác thì dùng `useAgUiSteerAway`.

### 4.7 Shared state (`STATE_SNAPSHOT` / `STATE_DELTA` dạng RFC 6902)

```json
{ "artifacts": { "quizzes": [{ "id": "q1", "title": "…", "count": 5 }], "mindmaps": [{ "id": "m1", "title": "…" }] },
  "jobs": { "job_1": { "kind": "quiz", "label": "Đang sinh câu hỏi", "progress": 40, "status": "running" } } }
```

`status` nhận một trong các giá trị `"running" | "done" | "error"`, `progress` là số nguyên từ 0 đến 100. Không đặt base64 hay dữ liệu lớn vào state. `STATE_SNAPSHOT` luôn chứa đủ hai khóa `artifacts` và `jobs`.

### 4.8 Luật thứ tự event (verifier của `@ag-ui/client` sẽ ném lỗi nếu sai)

1. Event đầu tiên là `RUN_STARTED {threadId, runId}` (đúng giá trị của input). Event cuối là `RUN_FINISHED` hoặc `RUN_ERROR {message, code?}`. Sau event cuối không phát gì thêm.
2. Text: `TEXT_MESSAGE_START {messageId, role:"assistant"}` → `TEXT_MESSAGE_CONTENT {messageId, delta}` (delta **không rỗng**) → `TEXT_MESSAGE_END {messageId}`.
3. Tool: `TOOL_CALL_START {toolCallId, toolCallName, parentMessageId}` → `TOOL_CALL_ARGS {toolCallId, delta}` (ghép các delta phải ra JSON hợp lệ) → `TOOL_CALL_END {toolCallId}` → `TOOL_CALL_RESULT {messageId, toolCallId, content, role:"tool"}`.
4. Mọi message và tool call đều phải đóng trước `RUN_FINISHED`. Riêng `RUN_ERROR` được phát khi đang có message mở (kịch bản lỗi). Mọi id là duy nhất trên toàn server.
5. `STATE_SNAPSHOT {snapshot}` và `STATE_DELTA {delta:[…]}` được phát ở bất kỳ đâu giữa START và event cuối.

### 4.9 Design token (hướng A "Studio tinh gọn", lấy từ `.design/redesign/Main.dc.html`)

| Vai trò | Giá trị | Vai trò | Giá trị |
| --- | --- | --- | --- |
| Chữ chính | `#002B31` (`text-main-text`) | Accent / link | `#2E5A6E`, hover `#1D3E4B` |
| Chữ phụ / label | `#7C9499`, `#8FA3A7` | Đúng / thành công | `#4E8F6E` |
| Viền | `#E3E1DC`, `#E7E5E0` | Lỗi | `text-error-red` |
| Nền bề mặt | `#FFFFFF`, `#F7F6F3`, `#FBFAF8` | Nền hover / chip | `#F4F7F8`, `#F1F5F6`, `#EEF1F2` |

Bo góc card `8px`, tag nhỏ `2px`. Font `font-sans` (Open Sans), tiêu đề dùng `font-urbanist`. Label viết hoa cỡ `10px`, tracking `.14em`, màu `#7C9499`. Dùng Tailwind arbitrary value và **không sửa `tailwind.config.js`**. Ưu tiên tái sử dụng `src/components/ui/*` (`card`, `badge`, `button`, `progress`, `collapsible`, `table`, `skeleton`).

---

## 5. API đã biết (A phải xác minh lại và ghi kết quả vào `API.md`)

Phiên bản cần ghim: `@assistant-ui/react@0.15.36`, `@assistant-ui/react-ag-ui@0.1.10`, `@ag-ui/client@1.0.5`. Peer dependency là React `^18 || ^19`, tương thích với React 18.3 của repo.

| Mảng | API | Nguồn |
| --- | --- | --- |
| Runtime | `useAgUiRuntime({ agent, showThinking?, onError?, onCancel?, adapters?: { history, attachments, … }, getRunContext?: ({ messages, runConfig }) => Context[], resumeTranscript?, autoCancelPendingToolCalls? })` | d.ts, `setup/references/ag-ui.md` |
| Hook AG-UI | `useAgUiState<T>()`, `useAgUiSetState`, `useAgUiInterrupts(): AgUiInterrupt[]`, `useAgUiSubmitInterruptResponses(): (entries) => Promise<void>`, `useAgUiSteerAway()`, `fromAgUiMessages`, `toAgUiMessages` | d.ts |
| Kiểu dữ liệu | `AgUiInterrupt = { id, reason, message?, toolCallId?, responseSchema?, expiresAt?, metadata? }`; `AgUiResumeEntry = { interruptId, status: "resolved" \| "cancelled", payload? }` | d.ts |
| History | `adapters.history = { async load() { return ExportedMessageRepository.fromArray(fromAgUiMessages(messages)); }, async append() {} }` (append để trống vì backend tự lưu) | `ag-ui.md` |
| Tool UI | `defineToolkit` + `{ type: "backend", render }`; `AuiConfig({ tools: Tools({ toolkit }) })` truyền vào prop `config` của `AssistantRuntimeProvider`. Render props: `args` (một phần khi đang stream), `argsText`, `result`, `isError`, `status.type` (`running` \| `complete` \| `incomplete` \| `requires-action`), `toolName`, `toolCallId` | `tools/SKILL.md`, `toolkits.md` |
| Thread | `ThreadPrimitive.Root/Viewport/Messages/ViewportFooter/ScrollToBottom`. `Messages` nhận hàm con `({ message }) => …`. `.Empty` và `.If` **đã deprecated**, dùng `AuiIf condition={(s) => s.thread.isEmpty}` hoặc `s.thread.isRunning` thay thế | `primitives/references/thread.md` |
| Message | `MessagePrimitive.Root`; `MessagePrimitive.Parts` nhận hàm con `({ part }) => …`: `text` → `<MarkdownText text={part.text}/>`, `reasoning` → khối thu gọn, `tool-call` → `part.toolUI ?? <ToolFallback {...part}/>`. Lỗi hiển thị bằng `ErrorPrimitive.Root` + `ErrorPrimitive.Message` | `primitives/references/message.md` |
| Composer | `ComposerPrimitive.Root` (`<form>`), `.Input` (`<textarea>`), `.Send`, `.Cancel` | `primitives/references/composer.md` |
| Gửi message bằng code | `useAui().thread.append({ role: "user", content: [{ type: "text", text }] })` (từ 0.15 scope accessor là property) | `runtime/references/state-hooks.md` |
| Client | `new HttpAgent({ url, headers?, threadId? })` từ `@ag-ui/client` | README AG-UI; field `threadId` cần xác minh trong d.ts |

---

## 6. Nhiệm vụ từng agent

### 6.A Nền tảng, xác minh API, runtime (Đợt 1)

1. Cài và gỡ dependency:
   ```bash
   npm i --save-exact @assistant-ui/react@0.15.36 @assistant-ui/react-ag-ui@0.1.10 @ag-ui/client@1.0.5
   npm uninstall @copilotkit/react-core @copilotkit/react-ui
   ```
   Kiểm bằng `npm ls @assistant-ui/react @assistant-ui/react-ag-ui @ag-ui/client` (không có dòng `invalid` hay `UNMET`). Thêm script vào `package.json`: `"mock:agent": "node mock-agent/server.mjs"`, `"smoke:agui": "node scripts/agui-smoke.mjs"`.
2. **Xác minh API rồi viết `docs/agui/status/API.md`:**
   - Liệt kê export thật bằng lệnh `node --input-type=module -e "import('@assistant-ui/react').then(m=>console.log(Object.keys(m).sort().join('\n')))"`, làm tương tự cho `@assistant-ui/react-ag-ui` và `@ag-ui/client`. Nếu import trong Node lỗi thì chuyển sang đọc d.ts.
   - Với **từng dòng** ở mục 5: ghi ✅ hoặc ❌, kèm đường dẫn d.ts và chữ ký thật.
   - Bổ sung bảng những gì B, C, E cần: tên sub-component của các primitive, kiểu của `part` trong `Parts` (`part.text`, `part.toolUI`), các field của `AgentConfig` trong `HttpAgent`, cách import `AuiIf`, `AuiConfig`, `Tools`.
3. Tạo `src/config.js` đúng như mục 4.1. Thêm `VITE_API_URL`, `VITE_AGENT_URL`, `VITE_USE_AGUI=false` vào `.env.sample`, mỗi biến kèm chú thích.
4. Gỡ CopilotKit: bỏ provider trong `src/main.jsx`, xóa `src/copilot.config.js`, xóa import và khối `useLangGraphInterrupt` trong `Chatbot.jsx` (đây là code chết, vì WS phát `window.CustomEvent` mà CopilotKit không nghe). Mount `<Toaster />` từ `src/components/ui/sonner.jsx` trong `src/main.jsx` (hiện chưa nơi nào mount).
5. `src/agent/MentorRuntimeProvider.jsx`:
   - `agent = useMemo(() => new HttpAgent({ url: AGENT_URL, threadId }), [threadId])`
   - `useAgUiRuntime({ agent, showThinking: true, onError: (e) => toast.error(…tiếng Việt…), adapters: { history }, getRunContext })`
   - `auiConfig` tạo bằng `useMemo` từ `mentorToolkit` (import từ `@/agent/toolkit`)
   - `getRunContext` trả về `[userCtx, ...(getExtraContext?.() ?? [])]`
   - Phải đúng dưới React StrictMode: không phát sinh run trùng, không tạo agent mới ở mỗi lần render.
6. `historyAdapter.js`: `load()` gọi `GET {AGENT_BASE}/threads/{threadId}/messages` qua `AbortController`, timeout 10 giây. Gặp lỗi mạng hoặc status khác 2xx thì ghi `console.warn` và trả về repository rỗng. Không được ném lỗi làm sập trang. `append()` để no-op.
7. Thay `http://0.0.0.0:8686` bằng `` `${API_URL}…` `` trong mọi file mình sở hữu, nhớ đổi chuỗi trong nháy đơn thành template literal.

**Tự kiểm tra:**
- `grep -rn "0.0.0.0:8686" src` chỉ còn khớp ở `src/config.js` và `StudioDashboard.jsx` (phần của E).
- `grep -rn copilotkit src package.json` không còn kết quả nào.
- `npx eslint <các file mình sở hữu>` không có lỗi mới.
- `npx vite build` pass. Toolkit của C có thể chưa tồn tại lúc này: nếu `src/agent/toolkit.jsx` chưa có thì **tạm tạo một stub** `export const mentorToolkit = defineToolkit({})` và báo cho orchestrator. C sẽ ghi đè ở Đợt 2.

### 6.B Thread (Đợt 2: đọc `API.md` trước)

1. `Thread.jsx` dựng từ primitives:
   - `ThreadPrimitive.Root` > `Viewport` (`turnAnchor="bottom"`).
   - Màn hình trống dùng `AuiIf s.thread.isEmpty`, hiện "👋 Chào {user_name}! Hỏi mình bất cứ điều gì về lập trình." cùng 3 gợi ý (bấm vào thì gọi `append`).
   - `Messages` rẽ nhánh theo `message.role`: UserMessage nằm trong bubble `bg-primary-blue/10`; AssistantMessage gồm `Parts` theo đúng mục 5, cộng `ErrorPrimitive`.
   - `ViewportFooter` sticky chứa `InterruptPanel` và composer; có `ScrollToBottom`.
   - Khi `s.thread.isRunning` và message cuối chưa có nội dung, hiện chỉ báo "Đang suy nghĩ…".
2. `MarkdownText.jsx` (`{ text }`): `react-markdown` + `remark-gfm` + `remark-math` + `rehype-katex` (`strict:false, throwOnError:false`), import `katex/dist/katex.min.css`, bọc trong `.markdown-container`. `<pre>` nền `#F7F6F3`, cuộn ngang. Không render HTML thô (không thêm `rehype-raw`).
3. `Reasoning.jsx`: khối thu gọn "Quá trình suy nghĩ", mặc định đóng.
4. Composer: `ComposerPrimitive.Root/Input/Send/Cancel`. Enter để gửi, Shift+Enter để xuống dòng (kiểm hành vi mặc định của `Input` rồi mới tự bắt phím). Khi đang chạy, ẩn nút Gửi và hiện nút Dừng.
5. `ToolChips.jsx`: nút "+" có hai lựa chọn "💡 Sinh câu hỏi" (`generate-questions`) và "🗺️ Mindmap" (`mindmap`). Chip gỡ được. Danh sách đã chọn lưu trong `useRef` ở SessionPage, và `getExtraContext` đọc từ ref đó.
6. `InterruptPanel.jsx`:
   - `metadata.kind === "quiz_config"`: card gồm số câu (5/10/15), độ khó (Dễ/Vừa/Khó), nút "Sinh câu hỏi" và "Hủy".
   - Interrupt loại khác: hiện `message` kèm hai nút Đồng ý / Hủy.
   - Gửi response phủ **hết** các interrupt đang mở. Disable nút trong lúc promise chạy. Nếu promise reject thì hiện lỗi và cho bấm lại.
7. `SessionPage.jsx`:
   - `const [newId] = useState(() => crypto.randomUUID()); const threadId = sessionId ?? newId;` (hook gọi vô điều kiện).
   - Khi `USE_AGUI` bật: bọc **cả layout** trong `<MentorRuntimeProvider threadId getExtraContext>`, cột giữa render `<AgentChat/>`.
   - Khi flag tắt: giữ nguyên `<Chatbot/>` như hiện tại, không đổi gì khác.
8. `AgentChat.jsx` = `<Thread/>` cùng phần layout, cuộn trong cột giữa.

**Tự kiểm tra:** `npx eslint` trên các file mình sở hữu; `npx vite build`; chạy cùng mock qua `VITE_USE_AGUI=true npx vite` để thử nhanh kịch bản mặc định.

### 6.C Generative UI (C1 ở Đợt 1, C2 ở Đợt 2)

**C1: component trình bày thuần.** Chỉ nhận props `{ args, result, status }`, không import gì từ `@assistant-ui/*`.

1. `fixtures.js`: args mẫu cho 5 tool, mỗi tool có hai biến thể `full` và `partial` (thiếu field, mảng dở, object rỗng).
2. `ToolErrorBoundary.jsx`: class component; `componentDidCatch` ghi `console.error` một lần; fallback là card trung tính.
3. `QuizCard.jsx`:
   - Header gồm tiêu đề, số câu và badge độ khó; mỗi lần hiện một câu, có nút Trước / Sau và thanh tiến độ.
   - Chọn đáp án thì khóa câu đó; đáp án đúng viền `#4E8F6E`, đáp án sai viền `error-red`, kèm giải thích render bằng MarkdownText.
   - Kết thúc hiện điểm và nút "Làm lại".
   - Khi đang `running`: skeleton và "Đã nhận N câu…".
   - Hỗ trợ bàn phím (phím số 1–4 để chọn, mũi tên trái/phải để chuyển câu).
4. Thư mục `catalog/`: `CatalogRenderer.jsx` dispatch theo `type`, có fallback cho type lạ. Các block: `Callout.jsx` (3 tone), `ComparisonTable.jsx` (cuộn ngang, tô cột `highlight_col`), `CodeDiff.jsx` (2 cột, xuống 1 cột khi hẹp, có nhãn ngôn ngữ, mỗi cột có nút sao chép), `Steps.jsx` (đánh số), `ConceptCard.jsx`.
5. `MindmapView.jsx`: cây thu gọn được, vẽ bằng CSS thuần (đường nối trái), mặc định mở 2 cấp, có nút "Mở hết / Thu gọn". Giới hạn độ sâu render ở 6 cấp để tránh vòng lặp khi dữ liệu xấu.
6. `SourceCitation.jsx`: chip "tên file · tr.N", hover hoặc focus vào thì hiện quote (dùng `hover-card` hoặc `tooltip` có sẵn).
7. `ToolFallback.jsx`: card thu gọn hiện tên tool, trạng thái và `argsText` trong `<pre>`.
8. `FollowUps.jsx`: danh sách chip. Bấm vào thì gọi prop `onSelect(question)`; prop này được gắn ở bước C2.

**C2: `toolkit.jsx`** (Đợt 2, đọc `API.md`).
- `export const mentorToolkit = defineToolkit({ show_quiz: { type: "backend", render: (p) => <ToolErrorBoundary toolName="show_quiz"><QuizCard {...p}/></ToolErrorBoundary> }, … })` cho đủ 5 tool, đặt ở mức module.
- `suggest_followups` dùng một wrapper gọi `useAui().thread.append(...)` cho `onSelect`.
- Ghi đè stub mà A đã tạo (nếu có).

**Tự kiểm tra:**
- `npx eslint` trên các file mình sở hữu.
- Thêm một bước render thử ngắn trong Node bằng `react-dom/server` `renderToString` với **mọi** biến thể trong `FIXTURES`. Không component nào được ném lỗi. Chạy được bằng `node` cùng loader JSX của esbuild sẵn có (`npx esbuild … --bundle --platform=node`); nếu không dựng nổi bước này thì ghi rõ vào status.
- Sau C2: `npx vite build`.

### 6.D Mock AG-UI server (Đợt 1)

1. `mock-agent/server.mjs`: dùng `node:http`, cổng `process.env.PORT ?? 8787`, CORS theo mục 4.3, các route `POST /agent`, `GET /threads/:id/messages`, `GET /health`. Route khác trả 404 kèm JSON.
   - Phát SSE với header `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `Connection: keep-alive`. Mỗi chunk cách nhau 20–40 ms.
   - Body JSON lỗi thì trả 400 **trước khi** mở stream.
   - Đọc câu cuối của user: `content` có thể là string hoặc mảng part `{type:"text", text}`.
   - Mỗi run: `RUN_STARTED` → `STATE_SNAPSHOT` (state hiện tại của thread, lưu trong bộ nhớ) → kịch bản → event cuối. Tuân thủ **tuyệt đối** mục 4.8.
   - Lưu transcript và state theo `threadId` (user, assistant + `toolCalls`, tool) để phục vụ `/threads/:id/messages`. Khi gặp `resume` thì không thêm lại message trùng.
   - **Client ngắt kết nối** (`req.on("close")`) thì dừng kịch bản, không ghi tiếp, không để lọt exception.
   - Có log ngắn ra stdout cho mỗi run (`threadId`, kịch bản, event cuối).
2. `mock-agent/scenarios.mjs`: chọn kịch bản theo từ khóa (không phân biệt hoa thường, ưu tiên từ trên xuống). Nội dung là kiến thức OOP/Java bằng tiếng Việt:

   | Điều kiện | Kịch bản |
   | --- | --- |
   | body có `resume` | Nếu resolved: job quiz (state delta progress 0 → 40 → 80 → done), sau đó `show_quiz` với `payload.count` câu, rồi thêm vào `/artifacts/quizzes/-`. Nếu cancelled: text "Đã hủy sinh câu hỏi." |
   | `lỗi`, `error` | Mở text, stream vài delta rồi `RUN_ERROR {message:"Mô phỏng lỗi từ agent", code:"MOCK_ERROR"}` |
   | `chậm`, `slow` | Text dài khoảng 15 giây (dùng để thử nút Dừng) |
   | `cấu hình`, `config` | Text ngắn rồi interrupt `quiz_config` (mục 4.6) |
   | `quiz`, `câu hỏi`, `kiểm tra` | Giống nhánh resolved ở trên với count = 5 |
   | `so sánh`, `khác`, `compare` | Text dẫn nhập, sau đó `present_ui` có `comparison_table` (abstract class và interface), `callout` loại tip, `code_diff`, `steps` |
   | `mindmap`, `sơ đồ` | `show_mindmap` (gốc "Lập trình hướng đối tượng", 4 nhánh, mỗi nhánh 2–3 lá), rồi thêm vào `/artifacts/mindmaps/-` |
   | `requested_tools` trong context có giá trị | Đi theo nhánh tương ứng (`generate-questions` → quiz, `mindmap` → mindmap), bất kể từ khóa |
   | (mặc định) | Markdown giải thích đa hình (có `$O(1)$` và một khối code Java), sau đó `cite_sources` (2 nguồn), rồi `suggest_followups` (3 câu) |

   Quiz cần **5 câu có nội dung thật**. Khi `count` lớn hơn 5 thì lặp lại có biến đổi, đánh số khác nhau.
3. `mock-agent/README.md`: cách chạy, bảng kịch bản, ví dụ `curl -N`, giới hạn của mock.

**Tự kiểm tra:** `node --check mock-agent/*.mjs`. Chạy `timeout 20 node mock-agent/server.mjs &`, rồi dùng `curl` chạy **từng** kịch bản, kiểm bằng mắt thứ tự event, và thử preflight `curl -i -X OPTIONS`.

### 6.E Contract test (E1 ở Đợt 1) và state Studio (E2 ở Đợt 2)

**E1: `scripts/agui-smoke.mjs`.** Node thuần, dùng `fetch` có sẵn, không đọc code của mock, chỉ đọc hợp đồng. Cách chạy: `node scripts/agui-smoke.mjs [AGENT_URL]`.

- **Kịch bản:** mặc định, quiz, so sánh, mindmap, lỗi (bắt buộc kết thúc bằng `RUN_ERROR`), cấu hình (bắt buộc có interrupt hợp lệ), resume resolved `{count:3}` (bắt buộc đúng 3 câu), resume cancelled, và context `requested_tools:["mindmap"]` (bắt buộc ra `show_mindmap`).
- **Kiểm protocol:** toàn bộ luật ở mục 4.8; `threadId`/`runId` khớp với input; args của từng tool có đủ field bắt buộc theo mục 4.5 (kiểm kiểu cơ bản); `STATE_DELTA` có `op` thuộc tập RFC 6902 và `path` bắt đầu bằng `/`; snapshot có đủ `artifacts` và `jobs`.
- **Kiểm HTTP:** preflight `OPTIONS` trả 204 kèm đủ header CORS; body lỗi trả 400; `GET /threads/<id>/messages` sau các run có đủ assistant `toolCalls` và message `tool` tương ứng; thread mới trả `{messages:[]}`; hai thread chạy **song song** không lẫn transcript.
- **Kết quả:** in PASS/FAIL cho từng kiểm tra kèm lý do; nếu có kiểm tra FAIL thì `exit 1`. Script phải dùng lại được làm contract test cho backend thật.

**E2: state Studio** (Đợt 2, đọc `API.md`).

1. `useMentorState.js`: bọc `useAgUiState()` và luôn trả về giá trị mặc định theo mục 4.7, kể cả khi state mang shape lạ.
2. `StudioAgentArtifacts.jsx`:
   - Mục "Đang xử lý": các job đang `running`, hiện label cùng `ui/progress`. Job lỗi hiện màu `error-red`.
   - Mục "Từ trợ lý": quiz (có badge số câu) và mindmap.
   - Style theo mục 4.9. Khi rỗng thì không render gì.
3. `StudioDashboard.jsx`: **chỉ** chèn `{USE_AGUI && <StudioAgentArtifacts />}` ngay dưới header, và đổi `http://0.0.0.0:8686` thành `API_URL`. Không refactor gì khác.

**Tự kiểm tra:** `node --check scripts/agui-smoke.mjs`; chạy script với mock khi mock đã có (ở Cổng 1, mọi FAIL đều phải phân loại được là lỗi của mock hay của script). Với E2: `npx eslint` trên file mình sở hữu, chỉ cần không có lỗi mới ở các dòng mình sửa trong StudioDashboard.

### 6.F Backend tham chiếu (Đợt 1)

1. `backend-reference/README.md`: hướng dẫn port từng bước vào backend FastAPI hiện có (cổng 8686).
   - Cài `ag-ui-protocol`, `ag-ui-langgraph`, `langgraph-checkpoint-postgres`.
   - Mount `/agent`, dùng checkpointer Postgres với `thread_id = session_uuid`.
   - Bảng ánh xạ WS cũ sang AG-UI: `start` → `RUN_STARTED`, `stream` → `TEXT_MESSAGE_*`, `suggest` → tool `suggest_followups`, `error` → `RUN_ERROR`, `end` → `RUN_FINISHED`, `interrupt` → `outcome.interrupt` với `emit_interrupt_outcome=True`.
   - Đổi SSE `mindmap_done`/`question_done` sang `STATE_DELTA` trên `artifacts`/`jobs`.
   - Thêm endpoint `/threads/{id}/messages`.
   - Job dài (Kafka/Redis) chạy ngoài run, cập nhật `jobs` trong state; AG-UI không hỗ trợ nối lại stream.
   - Cách chạy `scripts/agui-smoke.mjs` với backend thật.
   - Mục **"Cần xác minh khi port"**: chữ ký `add_langgraph_fastapi_endpoint` (truyền `agent=` hay `graph`); cách frontend tool được đưa vào graph; việc `AIMessage(tool_calls)` mà node tự thêm vào state có được stream thành `TOOL_CALL_*` hay chỉ xuất hiện trong `MESSAGES_SNAPSHOT`; cách `ag-ui-langgraph` ánh xạ state của graph sang `STATE_SNAPSHOT`/`STATE_DELTA`.
2. `agent/ui_catalog.py`: Pydantic v2 khớp **đúng** mục 4.5. `Block` khai báo bằng `Annotated[Union[...], Field(discriminator="type")]`. Thêm hàm `validate_present_ui(payload) -> PresentUI`.
3. `agent/server.py`: `LangGraphAgent(name="mentor", graph=graph, emit_interrupt_outcome=True)` cùng `add_langgraph_fastapi_endpoint(app=app, agent=agent, path="/agent")`, có CORS; route `/threads/{id}/messages` lấy từ `history.py`.
4. Các file còn lại:
   - `agent/state.py`: `MentorState(MessagesState)` theo mục 4.7, thêm `requested_tools`, `active_document_ids`.
   - `agent/tools.py`: các `@tool` cho mục 4.5, `args_schema` lấy từ `ui_catalog`.
   - `agent/graph.py`: router đọc `requested_tools` trước, sau đó mới phân loại intent; các node `qa_rag`, `summarize`, `mindmap`, `quiz` (dùng `interrupt()` cho `quiz_config`, xử lý sentinel `__agui_cancelled__`), `code_mentor`; lời gọi LLM để `# TODO` nhưng phải nêu rõ input/output.
   - `agent/history.py`: chuyển message của checkpointer sang định dạng AG-UI.
   - `requirements.txt`: ghi rõ phiên bản tối thiểu.

**Tự kiểm tra:** `python3 -m py_compile backend-reference/agent/*.py`. Đối chiếu từng field giữa `ui_catalog.py` và mục 4.5, rồi ghi kết quả đối chiếu vào status.

---

## 7. Việc của orchestrator

### 7.1 Đợt 0: chuẩn bị và baseline

```bash
git switch -c feat/agui-mvp
mkdir -p docs/agui/status
{ echo "# Baseline"; echo "## vite build"; npx vite build 2>&1 | tail -5;
  echo "## eslint"; npx eslint . 2>&1 | tail -3; } > docs/agui/status/BASELINE.md
```

Ghi thêm vào `BASELINE.md` các lỗi console sẵn có khi mở `/session` ở chế độ dev, nếu kiểm được.

### 7.2 Các cổng

- **Cổng 1 (sau Đợt 1):**
  - `API.md` có đủ mọi dòng ở mục 5, đều đã được đánh ✅/❌; mục nào ❌ thì orchestrator sửa mục 5 và mục 6 trước khi sang Đợt 2.
  - `npm ls` sạch; `npx vite build` pass.
  - Mock chạy được; `node scripts/agui-smoke.mjs` pass. Mọi FAIL đều đã phân loại được và sửa (lỗi của mock thì giao lại D, lỗi của script thì giao lại E).
  - Lệnh `py_compile` của F pass.
  - Mọi `CONTRACT_ISSUE` đã được quyết và cập nhật vào file này.
- **Cổng 2 (sau Đợt 2):** `npx vite build` pass; eslint không vượt baseline và mọi file mới đều 0 lỗi; smoke pass; bước render thử fixtures của C pass.

### 7.3 Đợt 3: E2E trên trình duyệt (bắt buộc, chụp màn hình từng mục)

Chạy `node mock-agent/server.mjs` nền, kèm `VITE_USE_AGUI=true npx vite --port 3001`, rồi mở `/session` sau khi đăng nhập (hoặc tạm đặt `localStorage.user` nếu backend REST không chạy).

| # | Thao tác | Kỳ vọng |
| --- | --- | --- |
| 1 | Gửi "giải thích đa hình" | Text stream mượt, KaTeX và code block hiện đúng; chip trích dẫn; 3 follow-up, bấm một cái thì gửi được |
| 2 | "tạo quiz" | Skeleton rồi đến QuizCard; chọn đáp án thấy đúng/sai và giải thích; Studio hiện job chạy rồi xong, có quiz mới |
| 3 | "so sánh abstract class và interface" | Hiện đủ 4 block, bảng cuộn ngang được, code diff đọc rõ |
| 4 | "vẽ mindmap" | Cây thu gọn và mở rộng được; Studio có mindmap |
| 5 | "cấu hình quiz" → chọn 10 câu, Khó → Sinh | Form hiện ra, gửi xong ra QuizCard đúng 10 câu; thử thêm nhánh Hủy |
| 6 | "cấu hình quiz" → bỏ qua form, gõ câu khác | Form đóng, câu mới được trả lời (steer away) |
| 7 | "chậm" → bấm Dừng | Stream dừng ngay, có thể gửi tiếp |
| 8 | "lỗi" | Hiện lỗi trong message kèm toast; thread vẫn dùng được |
| 9 | Chọn chip "Mindmap" rồi gửi "abc" | Ra mindmap (context `requested_tools` đã được gửi) |
| 10 | Tải lại trang (F5) | Lịch sử được khôi phục, **kể cả QuizCard và mindmap** |
| 11 | Tắt mock rồi gửi | Báo lỗi thân thiện, không trắng trang; bật lại mock thì gửi được |
| 12 | Hồi quy: tắt `VITE_USE_AGUI` | Trang dùng `<Chatbot/>` cũ; WebSocket vẫn thử kết nối như trước; không có lỗi import |
| 13 | Console trong suốt quá trình | Không có lỗi mới so với baseline; không có cảnh báo React key hay hook |

### 7.4 Đợt 5: báo cáo cho người dùng

Gồm: bảng M1–M8 (PASS/FAIL kèm bằng chứng), ảnh E2E, danh sách file thay đổi, các vấn đề còn mở và lý do, cách chạy thử, việc tiếp theo. **Không commit** khi người dùng chưa yêu cầu.

---

## 8. Đợt 4: review độc lập

1. Khởi chạy **Agent R** (agent mới, `general-purpose`). Chỉ đưa cho R lệnh `git diff dev...HEAD` cùng danh sách file mới, cộng mục 4 (hợp đồng). **Không đưa** kết luận hay báo cáo của các agent khác, để R không bị neo theo.
   - Yêu cầu R tìm lỗi correctness: crash khi args dở, rò subscription hoặc request, StrictMode chạy hai lần, xử lý lỗi mạng, hook gọi có điều kiện, XSS qua markdown, lệch hợp đồng, hồi quy khi flag tắt.
   - Mỗi phát hiện phải kèm kịch bản tái hiện cụ thể.
   - Có thể dùng skill `code-review` ở mức `high` thay cho R.
2. Orchestrator xác minh từng phát hiện, chỉ sửa những lỗi **đã xác nhận**, rồi chạy lại Cổng 2 và các mục E2E bị ảnh hưởng.

---

## 9. Prompt khởi chạy

`subagent_type: general-purpose`. Các agent cùng đợt được khởi chạy trong một message.

```
Bạn là Agent <X> trong kế hoạch docs/agui/PLAN.md
(repo /home/hungmanh/Documents/mentor-code-ui, nhánh feat/agui-mvp).
Đọc mục 0, 1, 4, 5 và mục 6.<X> (nếu đang ở Đợt 2 thì đọc thêm docs/agui/status/API.md), rồi thực hiện.
Ưu tiên chính xác và ổn định; không có giới hạn thời gian. Không đoán API, hãy tra theo luật 1.
Chỉ sửa file thuộc quyền sở hữu của bạn (mục 3.2).
Ghi tiến độ append-only vào docs/agui/status/<X>.md.
Câu trả lời cuối = dòng FINAL kèm danh sách file, các lệnh tự kiểm tra và output thật.
```

Khi giao tiếp phần Đợt 2 cho C và E, dùng `SendMessage` tới agent cũ với nội dung `"Cổng 1 đã qua. Đọc docs/agui/status/API.md và làm phần C2/E2 trong mục 6.<X>."`

---

## 10. Phase tiếp theo (ngoài kế hoạch này)

1. Port `backend-reference/` sang backend thật, trỏ `VITE_AGENT_URL` tới `http://<host>:8686/agent`, rồi chạy `npm run smoke:agui` với backend thật.
2. Cân nhắc chuyển sang TypeScript cùng Tailwind v4 để dùng được registry element của assistant-ui (ToolGroup, Reasoning, code highlighting bằng Shiki).
3. Thread list adapter dùng `/user-sessions`; frontend tool `highlight_source` cho SourcePanel; JWT; A2UI (`ACTIVITY_SNAPSHOT` với `a2ui-surface`) hoặc `@assistant-ui/generative-ui` cho `present_ui`; layout mobile theo `.design/redesign/Mobile.dc.html`.
