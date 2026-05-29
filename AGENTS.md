# AGENTS.md

## Changelog 格式

`CHANGELOG.md` 使用以下結構：

```markdown
## 版本號或 Unreleased

### 新增

### 調整

### 修正

### 破壞性變更
```

規則：

- 每個版本使用 `##` 標題，分類使用 `###` 標題。
- 只列出有內容的分類，不保留空分類。
- 每條項目以 `-` 開頭，一句話描述變更。
- 用一般使用者看得懂的語言撰寫，避免技術術語（如 UIPI、stderr、sink、token）。描述「使用者會感受到什麼」而非「技術上做了什麼」。
- 破壞性變更需說明遷移方式。
- Commit message 使用 conventional commits 格式：`feat:`、`fix:`、`refactor!:`、`docs:`、`chore:`。

## 程式碼風格

- 不使用底線前綴（如 `_start_time`），直接用 `start_time`。

## Git 規則

- 永遠不要自行 commit 或 push，必須等使用者明確指示。
